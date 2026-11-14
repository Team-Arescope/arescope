"""UT-04/05 and IT-01..06 against isolated SQLite/files and controlled time."""

import asyncio
from dataclasses import replace
import gzip
import hashlib
import json
import logging
from pathlib import Path
import re
import sqlite3
import struct
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as lab
from arsm import InvalidMesh, MAX_PNG_BYTES, parse_arsm

# Deliberately non-secret fixtures; no deployment credentials are used by tests.
P = {"Authorization": "Bearer test-producer"}
V = {"Authorization": "Bearer test-viewer"}


@pytest.fixture
def rig(tmp_path):
    cfg = lab.Settings(producer_token="test-producer", viewer_token="test-viewer",
        db=tmp_path / "live.sqlite3", mesh_dir=tmp_path / "meshes", log_dir=tmp_path / "logs",
        min_history_interval=0)
    now = [1_800_000_000.0]
    app = lab.create_app(cfg, clock=lambda: now[0])
    with TestClient(app) as client:
        yield client, app, cfg, now


def ingest(client, points=None, room="default", **kwargs):
    return client.post("/api/live/frame", headers=P,
        json={"room": room, "yawDeg": 12.5, "points": points if points is not None else [[1, 2, 3]]}, **kwargs)


def arsm(version=1, indices=(0, 1, 2), png=b"\x89PNG\r\n\x1a\n", vertices=3):
    body = struct.pack("<4sIII", b"ARSM", version, vertices, len(indices))
    body += struct.pack("<" + "f" * vertices * 3, *([0.0] * vertices * 3)) + b"\xff" * vertices * 4
    body += struct.pack("<" + "I" * len(indices), *indices)
    if version == 2:
        body += b"\0" * vertices * 8 + struct.pack("<III", 1, 1, len(png)) + png
    return body


@pytest.mark.parametrize("version", [1, 2])
def test_ut04_valid_arsm(version):
    info = parse_arsm(arsm(version))
    assert (info.version, info.vertex_count, info.index_count) == (version, 3, 3)
    assert info.png_bytes == (8 if version == 2 else 0)


@pytest.mark.parametrize("body", [b"", b"ARSM", b"WRNG" + arsm()[4:],
    struct.pack("<4sIII", b"ARSM", 3, 3, 3),
    struct.pack("<4sIII", b"ARSM", 1, 0, 0),
    struct.pack("<4sIII", b"ARSM", 1, 2_000_001, 0),
    struct.pack("<4sIII", b"ARSM", 1, 3, 1),
    arsm()[:-1], arsm() + b"x", arsm(2)[:-1], arsm(2) + b"x",
    arsm(indices=(0, 1, 3)), arsm(indices=(0, 1, 0xffffffff)),
    arsm(indices=(0, 1, 2) * 100 + (0, 1, 3))])
def test_ut04_malformed_arsm(body):
    with pytest.raises(InvalidMesh):
        parse_arsm(body)


def test_ut04_png_limit():
    body = arsm(2, png=b"")
    with pytest.raises(InvalidMesh, match="24 MiB"):
        parse_arsm(body[:-4] + struct.pack("<I", MAX_PNG_BYTES + 1))
    assert parse_arsm(arsm(vertices=1, indices=())).vertex_count == 1


def test_it01_ingest_and_compact_gzip_schema(rig):
    c, a, cfg, now = rig
    points = [[i / 10, i % 3, -i / 5] for i in range(384)]
    result = ingest(c, points, "q" * 100).json()
    assert result == {"ok": True, "room": "q" * 64, "pointCount": 384, "viewers": 0,
                      "sessionId": 1, "stored": True, "throttled": False}
    latest = c.get("/api/live/latest", headers=V).json()
    assert latest["source"] == "live-quest" and latest["rooms"][0]["points"] == points
    listing = c.get("/api/live/sessions", headers=V).json()
    assert listing["total"] == 1 and listing["sessions"][0]["maxPoints"] == 384
    assert c.get("/api/live/sessions/1", headers=V).json()["frame"]["source"] == "archived-quest"
    with a.state.store.connect() as db:
        assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        raw = db.execute("SELECT payload FROM frames").fetchone()[0]
        assert gzip.decompress(raw) == json.dumps(points, separators=(",", ":")).encode()
        assert len(list(db.execute("PRAGMA index_list(frames)"))) >= 1
        assert len(list(db.execute("PRAGMA index_list(sessions)"))) >= 1


def test_it02_throttle_preserves_live_and_ws(rig):
    c, a, cfg, now = rig
    cfg.min_history_interval = 10
    with c.websocket_connect("/api/live/stream?token=test-viewer") as ws:
        assert ws.receive_json()["rooms"] == []
        assert ingest(c).json()["stored"]
        ws.receive_json()
        now[0] += .1
        result = ingest(c, [[4, 5, 6]]).json()
        assert not result["stored"] and result["throttled"] and result["viewers"] == 1
        assert ws.receive_json()["points"] == [[4, 5, 6]]
    assert c.get("/api/live/latest", headers=V).json()["rooms"][0]["points"] == [[4, 5, 6]]
    assert c.get("/api/live/stats", headers=V).json()["frameCount"] == 1


def test_it03_continuity_split_cap_and_deleted_row(rig):
    c, a, cfg, now = rig
    cfg.max_frames_per_session = 2
    sid = ingest(c).json()["sessionId"]
    for _ in range(6):
        now[0] += 45
        result = ingest(c).json()
        assert result["sessionId"] == sid
    assert c.get(f"/api/live/sessions/{sid}", headers=V).json()["session"]["frameCount"] == 2
    now[0] += 60.001
    second = ingest(c).json()["sessionId"]
    assert second != sid
    # Delete directly to leave a deliberately dangling in-memory pointer.
    with a.state.store.connect() as db:
        db.execute("DELETE FROM sessions WHERE id=?", (second,))
    assert ingest(c).json()["sessionId"] not in (sid, second)


def test_ut05_retention_age_payload_and_cascade(rig):
    c, a, cfg, now = rig
    sid = ingest(c).json()["sessionId"]
    now[0] += 8 * 86400
    fresh = ingest(c).json()["sessionId"]
    assert c.get(f"/api/live/sessions/{sid}", headers=V).status_code == 404
    with a.state.store.connect() as db:
        assert not db.execute("SELECT id FROM frames WHERE session_id=?", (sid,)).fetchall()
    now[0] += 61
    newest = ingest(c, [[9, 8, 7]]).json()["sessionId"]
    with a.state.store.connect() as db:
        cfg.max_db_bytes = db.execute("SELECT length(payload) FROM frames WHERE session_id=?", (newest,)).fetchone()[0]
        a.state.store.prune(db, now[0], force=True)
    assert c.get(f"/api/live/sessions/{fresh}", headers=V).status_code == 404
    assert c.get(f"/api/live/sessions/{newest}", headers=V).status_code == 200
    with a.state.store.connect() as db:
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_ut05_prune_at_most_hourly(rig):
    c, a, cfg, now = rig
    ingest(c)
    cfg.max_db_bytes = 1
    now[0] += 10
    ingest(c)
    assert c.get("/api/live/sessions", headers=V).json()["total"] == 1
    now[0] += 3600
    ingest(c)
    assert c.get("/api/live/sessions", headers=V).json()["total"] == 0


def test_ut05_actual_2000_frame_cap(rig):
    c, a, cfg, now = rig
    frame = {"room": "cap", "receivedAt": now[0], "yawDeg": None, "points": [], "pointCount": 0}
    for i in range(2002):
        frame["receivedAt"] += 1
        sid, stored, throttled = a.state.store.append(frame)
        assert sid == 1 and stored == (i < 2000) and not throttled
    assert a.state.store.session(1)["session"]["frameCount"] == 2000


def test_it04_ply_dedup_last_enum_and_cap(rig):
    c, a, cfg, now = rig
    ingest(c, [[1, 2, 3], [1.001, 2, 3], [4, 5, 6]])
    ingest(c, [[1, 2, 3], [7, 8, 9]])
    def ply(mode):
        r = c.get(f"/api/live/sessions/1/export.ply?frame={mode}", headers=V)
        assert r.status_code == 200 and r.headers["content-type"] == "application/octet-stream"
        assert 'attachment;' in r.headers["content-disposition"]
        assert r.text.startswith("ply\nformat ascii 1.0\n")
        count = int(re.search(r"element vertex (\d+)", r.text)[1])
        lines = r.text.split("end_header\n")[1].splitlines()
        assert count == len(lines)
        return lines
    assert len(ply("merged")) == 3
    assert ply("last") == ["1 2 3", "7 8 9"]
    cfg.max_export_points = 2
    assert len(ply("merged")) == 2
    assert c.get("/api/live/sessions/1/export.ply?frame=other", headers=V).status_code == 422


@pytest.mark.parametrize("version", [1, 2])
def test_it05_mesh_roundtrip_and_errors(rig, version):
    c, a, cfg, now = rig
    ingest(c)
    body = arsm(version)
    r = c.post("/api/live/mesh?session=1", headers=P, content=body)
    assert r.status_code == 200 and r.json()["bytes"] == len(body)
    r = c.get("/api/live/sessions/1/mesh", headers=V)
    assert r.headers["content-type"] == "application/octet-stream"
    assert hashlib.sha256(r.content).digest() == hashlib.sha256(body).digest()
    s = c.get("/api/live/sessions/1", headers=V).json()["session"]
    assert s["hasMesh"] and s["meshBytes"] == len(body)
    assert c.post("/api/live/mesh?session=999", headers=P, content=body).status_code == 404
    assert c.post("/api/live/mesh?session=1", headers=P, content=body + b"x").status_code == 422
    assert c.post("/api/live/mesh?session=1", headers=P, content=arsm(indices=(0, 1, 4))).status_code == 422
    cfg.max_mesh_bytes = len(body) - 1
    assert c.post("/api/live/mesh?session=1", headers=P, content=body).status_code == 413
    assert c.get("/api/live/sessions/1/mesh", headers=V).content == body


def test_it06_logs_utf8_collision_traversal_and_limits(rig):
    c, a, cfg, now = rig
    body = "[ARS] scan | points=384\nПривет\n".encode()
    names = []
    for _ in range(2):
        r = c.post("/api/live/log", params={"source": "../../crash-recovery"}, headers=P, content=body)
        assert r.status_code == 200
        result = r.json(); names.append(result["file"])
        assert result["ok"] and result["bytes"] == len(body)
        assert re.fullmatch(r"\d{8}-\d{6}-crash-recovery\.log", result["file"])
    assert names[0] != names[1]
    listed = c.get("/api/live/logs?limit=0", headers=V).json()["logs"]
    assert len(listed) == 1 and listed[0]["at"].endswith("+00:00")
    r = c.get("/api/live/logs/" + names[0], headers=V)
    assert r.content == body and r.headers["cache-control"] == "no-store"
    assert r.headers["content-type"].startswith("text/plain")
    for invalid in [b"", b"   ", b"\xff"]:
        assert c.post("/api/live/log", headers=P, content=invalid).status_code == 422
    cfg.max_log_bytes = 10
    assert c.post("/api/live/log", headers=P, content=body).status_code == 413
    for name in ["..%5Coutside.log", "%2e%2e%2foutside.log", "other.log"]:
        assert c.get("/api/live/logs/" + name, headers=V).status_code == 404


@pytest.mark.parametrize("path,method", [("/api/live/latest", "get"), ("/api/live/stats", "get"),
    ("/api/live/sessions", "get"), ("/api/live/sessions/1", "get"),
    ("/api/live/sessions/1/export.ply", "get"), ("/api/live/sessions/1/mesh", "get"),
    ("/api/live/logs", "get"), ("/api/live/logs/file.log", "get"),
    ("/api/live/frame", "post"), ("/api/live/mesh?session=1", "post"),
    ("/api/live/log", "post"), ("/api/live/sessions/1", "delete")])
def test_auth_roles_all_routes(rig, path, method):
    c, a, cfg, now = rig
    wrong = P if method == "get" else V
    for headers in [{}, wrong, {"Authorization": "Bearer wrong"}, {"Authorization": "Basic test-viewer"}]:
        r = getattr(c, method)(path, headers=headers)
        assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"
    cfg.producer_token = cfg.viewer_token = ""
    assert getattr(c, method)(path, headers=V).status_code == 401


def test_config_fail_closed_and_compare_digest(rig):
    c, a, cfg, now = rig
    for p, v in [("", "viewer"), ("producer", ""), ("same", "same"), (" ", "viewer")]:
        invalid = replace(cfg, producer_token=p, viewer_token=v)
        with pytest.raises(ValueError), TestClient(lab.create_app(invalid)):
            pass
    with patch.object(lab.hmac, "compare_digest", wraps=lab.hmac.compare_digest) as compare:
        assert c.get("/api/live/latest", headers=V).status_code == 200
        assert compare.call_count >= 1


@pytest.mark.parametrize("token", ["", "test-producer", "bad"])
def test_websocket_unauthorized(rig, token):
    c, a, cfg, now = rig
    with pytest.raises(WebSocketDisconnect) as caught:
        with c.websocket_connect("/api/live/stream?token=" + token) as ws:
            ws.receive_json()
    assert caught.value.code == 4401
    cfg.viewer_token = ""
    with pytest.raises(WebSocketDisconnect) as caught:
        with c.websocket_connect("/api/live/stream?token=test-viewer") as ws:
            ws.receive_json()
    assert caught.value.code == 4401


def test_websocket_snapshot_ping_disconnect_and_bounded_queue(rig, monkeypatch):
    c, a, cfg, now = rig
    ingest(c)
    monkeypatch.setattr(lab, "WS_IDLE_SECONDS", .02)
    with c.websocket_connect("/api/live/stream?token=test-viewer") as ws:
        assert len(ws.receive_json()["rooms"]) == 1
        assert ws.receive_json()["type"] == "ping"
    # Closing a socket wakes the receive task immediately; it needn't wait 20 seconds.
    c.get("/api/live/latest", headers=V)
    assert not a.state.live.subscribers
    queue = asyncio.Queue(maxsize=32)
    a.state.live.subscribers.add(queue)
    for i in range(40):
        a.state.live.broadcast({"index": i})
    assert queue.qsize() == 32 and queue.get_nowait() == {"index": 8}
    a.state.live.subscribers.clear()


@pytest.mark.parametrize("failure", [sqlite3.OperationalError("locked"), OSError("full disk")])
def test_db_failure_still_publishes_and_recovers(rig, failure):
    c, a, cfg, now = rig
    with c.websocket_connect("/api/live/stream?token=test-viewer") as ws:
        ws.receive_json()
        with patch.object(a.state.store, "append", side_effect=failure):
            r = ingest(c)
            assert r.status_code == 200
            assert r.json()["sessionId"] is None and not r.json()["stored"]
            assert ws.receive_json()["pointCount"] == 1
        assert c.get("/api/live/latest", headers=V).json()["rooms"]
        stats = c.get("/api/live/stats", headers=V).json()
        assert stats["ingest"] == 1 and stats["storage_errors"] == 1
        assert ingest(c).json()["stored"]


def test_real_sqlite_lock_cannot_block_broadcast(rig):
    from concurrent.futures import ThreadPoolExecutor
    c, a, cfg, now = rig
    ingest(c)
    locked = sqlite3.connect(cfg.db)
    locked.execute("BEGIN EXCLUSIVE")
    try:
        with c.websocket_connect("/api/live/stream?token=test-viewer") as ws, ThreadPoolExecutor() as pool:
            ws.receive_json()
            pending = pool.submit(ingest, c, [[8, 9, 10]])
            assert ws.receive_json()["points"] == [[8, 9, 10]]
            result = pending.result(timeout=5)
            assert result.status_code == 200 and not result.json()["stored"]
    finally:
        locked.rollback()
        locked.close()
    assert c.get("/api/live/stats", headers=V).json()["storage_errors"] == 1
    assert ingest(c).json()["stored"]


def test_websocket_query_is_redacted_in_uvicorn_logs():
    record = logging.LogRecord("uvicorn.error", logging.INFO, "", 0,
        '%s - "WebSocket %s" [accepted]', ("127.0.0.1", "/api/live/stream?token=test-viewer&other=value"), None)
    assert lab.StreamQueryFilter().filter(record)
    assert "test-viewer" not in record.getMessage() and "[redacted]" in record.getMessage()


def test_unavailable_database_at_startup_still_allows_live(tmp_path):
    cfg = lab.Settings(producer_token="test-producer", viewer_token="test-viewer", db=tmp_path,
        mesh_dir=tmp_path / "meshes", log_dir=tmp_path / "logs")
    with TestClient(lab.create_app(cfg)) as c:
        assert ingest(c).status_code == 200
        assert c.get("/api/live/latest", headers=V).json()["rooms"]
        assert c.get("/api/live/sessions", headers=V).status_code == 503


@pytest.mark.parametrize("payload", [b"not json", b"{", b"[]", b"null", b'{}',
    b'{"points": [[0,NaN,0]]}', b'{"points": [[0,Infinity,0]]}',
    b'{"points": [[true,0,0]]}', b'{"points": [[0,0]]}', b'{"points": [["x",0,0]]}',
    b'{"points":[], "yawDeg":"bad"}', b'{"points":[], "room":123}'])
def test_invalid_frames(rig, payload):
    c, a, cfg, now = rig
    assert c.post("/api/live/frame", headers=P, content=payload).status_code == 422
    assert a.state.live.ingest == 0


def test_point_limit_ttl_default_room_and_delete(rig):
    c, a, cfg, now = rig
    assert ingest(c, [[0, 0, 0]] * 4097).status_code == 422
    assert ingest(c, [[0, 0, 0]] * 4096).status_code == 200
    r = c.post("/api/live/frame", headers=P, json={"points": []}).json()
    assert r["room"] == "default"
    now[0] += 30
    assert len(c.get("/api/live/latest", headers=V).json()["rooms"]) == 1
    now[0] += .01
    assert not c.get("/api/live/latest", headers=V).json()["rooms"]
    assert c.delete("/api/live/sessions/1", headers=P).json() == {"ok": True, "deleted": 1}
    assert ingest(c).json()["sessionId"] != 1
    for path, method in [("/api/live/sessions/999", "get"), ("/api/live/sessions/999", "delete"),
        ("/api/live/sessions/999/export.ply", "get"), ("/api/live/sessions/999/mesh", "get")]:
        assert getattr(c, method)(path, headers=P if method == "delete" else V).status_code == 404


def test_clamped_session_list_and_stats(rig):
    c, a, cfg, now = rig
    for i in range(105):
        ingest(c, room=f"room-{i}")
    assert len(c.get("/api/live/sessions?limit=0", headers=V).json()["sessions"]) == 1
    assert len(c.get("/api/live/sessions?limit=999", headers=V).json()["sessions"]) == 100
    s = c.get("/api/live/stats", headers=V).json()
    assert s["sessionCount"] == 105 and s["frameCount"] == 105 and s["ingest"] == 105
    assert s["dbBytes"] > s["payloadBytes"] > 0 and len(s["activeRooms"]) == 105


def test_streamed_limits_without_content_length(rig):
    c, a, cfg, now = rig
    cfg.max_log_bytes = cfg.max_mesh_bytes = 10
    def chunks():
        yield b"a" * 8
        yield b"b" * 8
    assert c.post("/api/live/log", headers=P, content=chunks()).status_code == 413
    assert c.post("/api/live/mesh?session=1", headers=P, content=chunks()).status_code == 413


def test_public_static_references_and_security_headers(rig):
    c, a, cfg, now = rig
    assert c.get("/healthz").json()["ok"]
    assert c.get("/openapi.json").status_code == 404
    r = c.get("/")
    assert r.status_code == 200 and r.headers["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    refs = set(re.findall(r'(?:src|href)="(/static/[^"?]+)', r.text))
    for path in refs:
        assert c.get(path).status_code == 200, path
    assert c.get("/static/../.env").status_code == 404
