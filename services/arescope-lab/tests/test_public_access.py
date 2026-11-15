"""Public demo access uses no shared browser credential; private roles still work."""

from dataclasses import replace
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as lab


@pytest.fixture
def public_rig(tmp_path):
    cfg = lab.Settings(public_access=True, producer_token="", viewer_token="",
                       db=tmp_path / "public.sqlite3", mesh_dir=tmp_path / "meshes",
                       log_dir=tmp_path / "logs", min_history_interval=0)
    application = lab.create_app(cfg)
    with TestClient(application) as client:
        yield client, application, cfg


def test_public_mode_requires_explicit_environment_opt_in(monkeypatch):
    monkeypatch.delenv("ARESCOPE_LAB_PUBLIC_ACCESS", raising=False)
    assert lab.Settings().public_access is False
    for value in ("0", "true", "yes", "", " 1"):
        monkeypatch.setenv("ARESCOPE_LAB_PUBLIC_ACCESS", value)
        assert lab.Settings().public_access is False
    monkeypatch.setenv("ARESCOPE_LAB_PUBLIC_ACCESS", "1")
    assert lab.Settings().public_access is True


def test_config_only_discloses_public_capability(public_rig):
    c, _, cfg = public_rig
    cfg.viewer_token, cfg.producer_token = "private-viewer-fixture", "private-producer-fixture"
    response = c.get("/api/config")
    assert response.status_code == 200
    assert response.json() == {"publicAccess": True}
    assert response.headers["cache-control"] == "no-store"
    assert "private-" not in response.text


def test_private_config_and_auth_remain_closed(public_rig):
    _, _, cfg = public_rig
    private = replace(cfg, public_access=False, producer_token="producer-fixture", viewer_token="viewer-fixture")
    with TestClient(lab.create_app(private)) as client:
        assert client.get("/api/config").json() == {"publicAccess": False}
        assert client.get("/api/sim/fleet").status_code == 401
        assert client.post("/api/sim/fleet", json={"action": "stop"}).status_code == 401
    with pytest.raises(ValueError), TestClient(lab.create_app(replace(cfg, public_access=False))):
        pass


@pytest.mark.parametrize("path,method", [
    ("/api/live/latest", "get"), ("/api/live/stats", "get"),
    ("/api/live/sessions", "get"), ("/api/live/sessions/99999", "get"),
    ("/api/live/sessions/99999/export.ply", "get"), ("/api/live/sessions/99999/mesh", "get"),
    ("/api/live/logs", "get"), ("/api/live/logs/missing.log", "get"),
    ("/api/live/frame", "post"), ("/api/live/mesh?session=99999", "post"),
    ("/api/live/log", "post"), ("/api/live/sessions/99999", "delete"),
    ("/api/guardian/status", "get"), ("/api/guardian/model", "get"),
    ("/api/guardian/incidents", "get"), ("/api/guardian/incidents/99999/label", "post"),
    ("/api/guardian/retrain", "post"), ("/api/guardian/deploy", "post"),
    ("/api/sim/rover", "post"), ("/api/sim/fleet", "get"), ("/api/sim/fleet", "post"),
])
def test_public_routes_do_not_request_credentials(public_rig, path, method):
    client, _, _ = public_rig
    response = getattr(client, method)(path)
    assert response.status_code in (200, 404, 409, 422), response.text
    assert "www-authenticate" not in response.headers


def test_public_ws_and_complete_scan_session_without_tokens(public_rig):
    c, application, _ = public_rig
    with c.websocket_connect("/api/live/stream") as ws:
        assert ws.receive_json()["rooms"] == []
        response = c.post("/api/live/frame", json={"room": "public-fixture", "points": [[1, 2, 3]]})
        assert response.status_code == 200
        assert ws.receive_json()["room"] == "public-fixture"
    assert not application.state.live.subscribers
    session_id = response.json()["sessionId"]
    assert c.get("/api/live/latest").json()["rooms"][0]["room"] == "public-fixture"
    assert c.get(f"/api/live/sessions/{session_id}/export.ply").status_code == 200
    assert c.post("/api/live/log", content=b"Public test log\n").status_code == 200
    assert c.delete(f"/api/live/sessions/{session_id}").status_code == 200
    assert c.get(f"/api/live/sessions/{session_id}").status_code == 404


def test_public_fleet_controls_keep_serious_recovery_approval(public_rig):
    c, _, _ = public_rig
    def control(action, **fields):
        response = c.post("/api/sim/fleet", json={"action": action, **fields})
        assert response.status_code == 200, response.text
        return response.json()["fleetState"]
    state = control("reset", count=3, speedMultiplier=120, autoRepair=True)
    rover_id = state["rovers"][0]["carrierId"]
    control("start")
    state = control("fault", roverId=rover_id, fault="sensor_drop")
    rover = state["rovers"][0]
    assert rover["recovery"]["requiresApproval"] is True
    assert rover["recovery"]["approved"] is False
    request_id = rover["recovery"]["requestId"]
    state = control("hold_recovery", roverId=rover_id, requestId=request_id)
    assert state["rovers"][0]["recovery"]["held"] is True
    control("approve_recovery", roverId=rover_id, requestId=request_id)
    assert c.post("/api/sim/fleet", json={"action": "approve_recovery", "roverId": rover_id,
                                           "requestId": request_id - 1}).status_code == 422
    assert control("stop")["running"] is False


def test_public_validation_and_limits_are_still_enforced(public_rig):
    c, _, cfg = public_rig
    assert c.post("/api/live/frame", json={"points": [[1, "invalid", 3]]}).status_code == 422
    cfg.max_log_bytes = 3
    assert c.post("/api/live/log", content=b"too large").status_code == 413
    assert c.post("/api/sim/fleet", json={"action": "not-real"}).status_code == 422
