"""Guardian contracts, disjoint synthetic evaluation, review workflow and rover lifecycle.

Adaptation fixtures represent operator-reviewed misses as well as false alarms.
Their terrain corridors/seeds are independent of the frozen evaluation set.
"""

import asyncio
from collections import deque
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import sqlite3
import sys
import threading
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as lab
from guardian import GuardianEngine, extract_features, generate_dataset, predict_model
from rover_sim import CAUSES, RoverSimulator, RoverSimManager, TERRAIN_PATH

P = {"Authorization": "Bearer guardian-producer"}
V = {"Authorization": "Bearer guardian-viewer"}


@pytest.fixture
def rig(tmp_path):
    cfg = lab.Settings(producer_token="guardian-producer", viewer_token="guardian-viewer",
                       db=tmp_path / "live.sqlite3", mesh_dir=tmp_path / "meshes",
                       log_dir=tmp_path / "logs", min_history_interval=0)
    now = [1_800_000_000.0]
    application = lab.create_app(cfg, clock=lambda: now[0])
    with TestClient(application) as client:
        yield client, application, cfg, now


def adaptation_incidents():
    """Reviewed windows only; never obtain training examples from holdout."""
    incidents = []
    for trajectory in generate_dataset("adaptation"):
        if trajectory["cause"] != "wheel_slip":
            continue
        for index in range(4, len(trajectory["frames"])):
            incidents.append({"id": len(incidents) + 1,
                              "trueCause": "wheel_slip" if index >= trajectory["onset"] + 6 else "nominal",
                              "window": deepcopy(trajectory["frames"][index - 4:index + 1])})
    return incidents


@pytest.fixture(scope="module")
def trained():
    engine = GuardianEngine()
    result = engine.retrain(adaptation_incidents())
    return engine.dump_state(), result


def seed_review_queue(application, now, incidents=None):
    """Seed operator-reported misses, which automatic alarms cannot discover."""
    incidents = incidents if incidents is not None else adaptation_incidents()
    with application.state.store.connect() as db:
        for incident in incidents:
            prediction = application.state.guardian.predict(incident["window"])
            db.execute("""INSERT INTO incidents(room,carrier_id,carrier_type,created_at,
                predicted_cause,risk_score,window_json) VALUES(?,?,?,?,?,?,?)""",
                ("review", "review-rover", "rover", now + incident["id"] / 100,
                 prediction["predictedCause"], prediction["riskScore"], json.dumps(incident["window"])))
    return incidents


def post_frame(client, **changes):
    return client.post("/api/live/frame", headers=P, json={"points": [[1, 2, 3]], **changes})


def test_baseline_holdout_is_reproducible_and_terrain_disjoint():
    engine = GuardianEngine()
    metrics = engine.evaluate_holdout()
    assert metrics == engine.baseline_metrics == GuardianEngine().evaluate_holdout()
    assert metrics["caughtFailures"] == 26 and metrics["totalFailures"] == 30
    assert metrics["evaluatedWindows"] == 1152 and metrics["holdoutTrajectories"] == 36
    assert metrics["microSlipRecall"] == 0
    assert metrics["meanLeadTimeS"] > 10 and metrics["falseAlarmRate"] < .03
    corridors = {}
    for split in ("train", "adaptation", "holdout"):
        trajectories = generate_dataset(split)
        corridors[split] = {r for t in trajectories for r in range(t["terrainRow"] - 6, t["terrainRow"] + 7)}
    assert not corridors["train"] & corridors["holdout"]
    assert not corridors["train"] & corridors["adaptation"]
    assert not corridors["adaptation"] & corridors["holdout"]
    training = {tuple(extract_features(t["frames"][i-4:i+1]))
                for t in generate_dataset("train") for i in range(4, 36)}
    holdout = {tuple(extract_features(t["frames"][i-4:i+1]))
               for t in generate_dataset("holdout") for i in range(4, 36)}
    assert training.isdisjoint(holdout)


@pytest.mark.parametrize("cause", CAUSES[1:])
def test_fast_loop_warns_before_each_standard_failure(cause):
    engine = GuardianEngine()
    for trajectory in generate_dataset("holdout"):
        if trajectory["cause"] != cause or trajectory["pattern"] != "standard":
            continue
        alarms = []
        for index in range(4, trajectory["failureAt"]):
            result = engine.predict(trajectory["frames"][index-4:index+1])
            if result["predictedCause"] == cause and result["riskLevel"] != "nominal":
                alarms.append((index, result))
        assert alarms and trajectory["failureAt"] - alarms[0][0] >= 10
        assert alarms[0][1]["leadTimeS"] > 0
        assert alarms[0][1]["lowConfidence"] is True and alarms[0][1]["recoveryAction"]


def test_nominal_trajectories_and_exported_fast_loop():
    engine = GuardianEngine()
    model = json.loads(json.dumps(engine.export_model(), allow_nan=False))
    assert model["windowSize"] == 5 and len(model["featureNames"]) == 18
    assert len(model["prototypes"]) <= 8 * len(CAUSES)
    for trajectory in generate_dataset("holdout"):
        if trajectory["cause"] == "nominal":
            for index in range(4, 36):
                window = trajectory["frames"][index-4:index+1]
                prediction = engine.predict(deque(window, maxlen=5))
                assert prediction == predict_model(model, window)
                assert prediction["riskLevel"] == "nominal" and prediction["lowConfidence"] is False
    model["modelVersion"] = "tampered"
    assert engine.model_version == "v1"


def test_retraining_improves_micro_slip_without_holdout_training(trained):
    state, result = trained
    before, after = result["beforeMetrics"], result["candidateMetrics"]
    assert result["ok"] and result["improved"] and result["candidateVersion"] == "v2"
    assert after["caughtFailures"] == 30 > before["caughtFailures"]
    assert after["F1"] > before["F1"] and after["accuracy"] > before["accuracy"]
    assert after["microSlipRecall"] > .95 > before["microSlipRecall"]
    assert after["meanLeadTimeS"] > 10 and after["falseAlarmRate"] < .03
    for cause in CAUSES[1:]:
        assert after["perCauseRecall"][cause] >= before["perCauseRecall"][cause]
    assert state["activeModel"]["modelVersion"] == "v1"
    assert len(state["candidateModel"]["prototypes"]) <= 16 * len(CAUSES)
    assert len(json.dumps(state["candidateModel"])) < 100_000


def test_engine_requires_human_approval_and_validated_improvement(trained):
    engine = GuardianEngine()
    with pytest.raises(ValueError, match="approval"):
        engine.deploy()
    with pytest.raises(ValueError, match="validated"):
        engine.deploy(approved=True)
    state, _ = trained
    engine.restore_state(state)
    with pytest.raises(ValueError, match="approval"):
        engine.deploy(approved=False)
    assert engine.model_version == "v1"
    assert engine.deploy(approved=True, at=123)["deployedAt"] == 123
    assert engine.model_version == "v2" and engine.candidate_model is None
    assert engine.evaluate_holdout() == engine.current_metrics
    assert state["activeModel"]["modelVersion"] == "v1"  # restore is a deep copy


@pytest.mark.parametrize("cause", CAUSES[1:])
def test_rover_manager_fault_modes_use_hirise_and_same_ingest(cause):
    terrain = json.loads(TERRAIN_PATH.read_text(encoding="utf-8"))
    terrain_points = {tuple(p) for p in terrain["points"]}
    received, window, engine = [], deque(maxlen=5), GuardianEngine()

    async def ingest(frame):
        window.append({"telemetry": frame["telemetry"], "receivedAt": len(received)})
        frame["guardian"] = engine.predict(window)
        received.append(frame)
        return frame

    async def scenario():
        manager = RoverSimManager(ingest)
        for _ in range(5):
            await manager.control("step")
        await manager.control("fault", cause)
        for _ in range(24):
            result = await manager.control("step")
        assert result["simState"]["fault"] == cause and result["simState"]["steps"] == 29
        assert result["simState"]["terrainSource"] == "nasa-pds-hirise"
        assert result["latestFrame"]["guardian"]["predictedCause"] == cause
        assert any(f["guardian"]["leadTimeS"] > 0 for f in received[5:])
        for frame in received:
            assert frame["carrierType"] == "rover" and frame["source"] == "simulated-rover"
            assert {tuple(p) for p in frame["points"]} <= terrain_points
            assert tuple(frame["telemetry"]["position"]) in terrain_points
        nominal, faulty = received[4]["telemetry"], received[-1]["telemetry"]
        if cause == "wheel_slip":
            assert faulty["observedSpeedMps"] < nominal["observedSpeedMps"] / 2
        else:
            assert faulty["pointCount"] < nominal["pointCount"] / 2
        if cause == "sensor_drop":
            assert faulty["linkOk"] is False and faulty["fps"] < 2
        await manager.stop()

    asyncio.run(scenario())


def test_manager_start_stop_is_idempotent_and_cleans_up():
    async def scenario():
        arrived = asyncio.Event()
        received = []

        async def ingest(frame):
            received.append(frame)
            if len(received) >= 2:
                arrived.set()
            return frame

        manager = RoverSimManager(ingest, interval=.01)
        await asyncio.gather(manager.control("start"), manager.control("start"))
        task = manager.task
        await asyncio.wait_for(arrived.wait(), timeout=2)
        assert manager.state()["running"]
        await manager.control("stop")
        assert task.done() and not manager.state()["running"]
        count = len(received)
        await manager.control("stop")
        assert manager.task is None and len(received) == count

    asyncio.run(scenario())


def test_manager_records_background_failure():
    async def scenario():
        calls = []

        async def broken(frame):
            calls.append(frame)
            if len(calls) > 1:
                raise OSError("unavailable")
            return frame

        manager = RoverSimManager(broken, interval=.001)
        await manager.control("start")
        await asyncio.wait_for(manager.task, timeout=2)
        assert manager.state()["error"] == "OSError" and not manager.state()["running"]
        await manager.stop()

    asyncio.run(scenario())


def test_frame_schema_history_ws_and_per_carrier_window(rig):
    client, application, cfg, now = rig
    keys = {"room", "carrierId", "carrierType", "telemetry", "guardian", "points", "pointCount",
            "yawDeg", "receivedAt", "source"}
    with client.websocket_connect("/api/live/stream?token=guardian-viewer") as ws:
        assert ws.receive_json()["rooms"] == []
        with patch.object(application.state.guardian, "predict", wraps=application.state.guardian.predict) as predict:
            for index in range(7):
                now[0] += 1
                for carrier in ("rover", "mast"):
                    result = post_frame(client, room="same-room", carrierId=carrier,
                                        carrierType="rover" if carrier == "rover" else "helmet",
                                        telemetry={"fps": 29 + index / 10, "linkOk": True,
                                                   "position": [1, 2, 3]}).json()
                    streamed = ws.receive_json()
                    assert keys <= result.keys() and keys == streamed.keys()
                    assert {key: result[key] for key in keys} == streamed
            for call in predict.call_args_list[-2:]:
                assert len(call.args[0]) == 5
                assert [r["telemetry"]["fps"] for r in call.args[0]] == [29.2, 29.3, 29.4, 29.5, 29.6]
    latest = client.get("/api/live/latest", headers=V).json()["rooms"]
    assert {f["carrierId"] for f in latest} == {"rover", "mast"}
    assert client.get("/api/live/sessions", headers=V).json()["total"] == 2
    for frame in latest:
        row = client.get(f"/api/live/sessions/{1 if frame['carrierId'] == 'rover' else 2}", headers=V).json()["frame"]
        assert row["carrierId"] == frame["carrierId"] and row["guardian"] == frame["guardian"]
        assert row["telemetry"] == frame["telemetry"]
    now[0] += 31
    moved = post_frame(client, carrierId="rover").json()
    assert len(application.state.live.telemetry_windows["rover"]) == 1
    assert len(client.get("/api/live/latest", headers=V).json()["rooms"]) == 1
    assert moved["sessionId"] == 3
    assert client.get("/api/live/sessions/3", headers=V).json()["frame"]["room"] == "default"


@pytest.mark.parametrize("changes", [
    {"carrierId": 1}, {"carrierId": None}, {"carrierId": ""}, {"carrierId": "x" * 65},
    {"carrierType": "astronaut"}, {"carrierType": None}, {"carrierType": []},
    {"telemetry": []}, {"telemetry": None}, {"telemetry": {"fps": True}},
    {"telemetry": {"fps": "30"}}, {"telemetry": {"fps": None}},
    {"telemetry": {"fps": float("nan")}}, {"telemetry": {"poseJumpM": float("inf")}},
    {"telemetry": {"slipRatio": -float("inf")}}, {"telemetry": {"linkOk": 1}},
    {"telemetry": {"linkOk": "true"}}, {"telemetry": {"position": [0, 0]}},
    {"telemetry": {"position": [0, 0, True]}}, {"telemetry": {"position": [0, 0, float("nan")]}},
    {"telemetry": {"position": [0, 0, float("inf")]}}, {"telemetry": {"extra": {"fps": 1}}},
])
def test_invalid_carriers_and_telemetry_are_422(rig, changes):
    client, application, cfg, now = rig
    response = client.post("/api/live/frame", headers=P, content=json.dumps({"points": [], **changes}))
    assert response.status_code == 422
    assert application.state.live.ingest == 0


def test_incident_cooldown_is_per_carrier_cause_and_persistent(rig):
    client, application, cfg, now = rig
    danger = {"pointCount": 0, "fps": 0, "linkOk": False, "poseJumpM": 1}
    for _ in range(8):
        response = post_frame(client, carrierId="faulty", telemetry=danger)
        now[0] += 1
    assert response.json()["guardian"]["riskLevel"] == "critical"
    incidents = client.get("/api/guardian/incidents?limit=30", headers=V).json()["incidents"]
    assert len(incidents) == 1 and incidents[0]["status"] == "pending"
    assert incidents[0]["sessionId"] == response.json()["sessionId"]
    # Another worker/restart must honor the same persisted cooldown.
    other = lab.create_app(cfg, clock=lambda: now[0])
    with TestClient(other) as second:
        post_frame(second, carrierId="faulty", telemetry=danger)
        assert len(second.get("/api/guardian/incidents", headers=V).json()["incidents"]) == 1
    post_frame(client, carrierId="other", telemetry=danger)
    now[0] += lab.INCIDENT_COOLDOWN_SECONDS
    post_frame(client, carrierId="faulty", telemetry=danger)
    rows = client.get("/api/guardian/incidents", headers=V).json()["incidents"]
    assert len(rows) == 3 and [r["id"] for r in rows] == sorted([r["id"] for r in rows], reverse=True)
    assert len(client.get("/api/guardian/incidents?limit=0", headers=V).json()["incidents"]) == 1
    with application.state.store.connect() as db:
        assert len(json.loads(db.execute("SELECT window_json FROM incidents ORDER BY id DESC").fetchone()[0])) <= 5
    # Reviewed training evidence survives ordinary session retention/deletion.
    client.delete(f"/api/live/sessions/{response.json()['sessionId']}", headers=P)
    rows = client.get("/api/guardian/incidents", headers=V).json()["incidents"]
    assert next(r for r in rows if r["id"] == incidents[0]["id"])["sessionId"] is None


def test_slow_loop_sqlite_review_retrain_human_deploy_and_workers(rig):
    client, application, cfg, now = rig
    incidents = seed_review_queue(application, now[0])
    second_app = lab.create_app(cfg, clock=lambda: now[0])
    with TestClient(second_app) as second:
        for incident in incidents:
            labeled = client.post(f"/api/guardian/incidents/{incident['id']}/label", headers=P,
                                  json={"trueCause": incident["trueCause"], "notes": "Operator reviewed"})
            assert labeled.status_code == 200 and labeled.json()["status"] == "labeled"
        assert second.get("/api/guardian/status", headers=V).json()["labeledIncidents"] == len(incidents)
        result = second.post("/api/guardian/retrain", headers=P).json()
        assert result["improved"] and result["candidateMetrics"]["microSlipRecall"] > .95
        assert result["candidateMetrics"]["caughtFailures"] == 30
        status = client.get("/api/guardian/status", headers=V).json()
        assert set(status) == {"modelVersion", "activeModel", "candidateReady", "candidateVersion", "baselineMetrics",
                               "currentMetrics", "candidateMetrics", "pendingIncidents", "labeledIncidents",
                               "deployedAt", "simState"}
        assert status["candidateReady"] and status["modelVersion"] == "v1"
        assert status["candidateVersion"] == "v2"
        assert status["currentMetrics"] == result["beforeMetrics"]
        assert client.get("/api/guardian/model", headers=V).json()["modelVersion"] == "v1"
        # Restart while a candidate is awaiting approval.
        restarted = lab.create_app(cfg, clock=lambda: now[0])
        with TestClient(restarted) as third:
            assert third.get("/api/guardian/status", headers=V).json()["candidateReady"]
            for approval in ({}, {"approved": False}, {"approved": 1}, {"approved": "true"}):
                assert third.post("/api/guardian/deploy", headers=P, json=approval).status_code == 422
            assert third.post("/api/guardian/deploy", headers=P,
                              json={"approved": True, "candidateVersion": "v999"}).status_code == 409
            # A failed commit must leave both the cached and persisted model intact.
            with patch.object(restarted.state.store, "save_guardian", side_effect=sqlite3.OperationalError("full")):
                assert third.post("/api/guardian/deploy", headers=P, json={"approved": True}).status_code == 503
            assert restarted.state.guardian.model_version == "v1"
            assert third.get("/api/guardian/status", headers=V).json()["candidateReady"]
            with third.websocket_connect("/api/live/stream?token=guardian-viewer") as ws:
                ws.receive_json()
                deployed = third.post("/api/guardian/deploy", headers=P,
                                      json={"approved": True, "candidateVersion": "v2"}).json()
                event = ws.receive_json()
                assert event == {"type": "guardian_update", **deployed}
            assert deployed["modelVersion"] == "v2" and deployed["deployedAt"] == now[0]
        assert second.get("/api/guardian/model", headers=V).json()["modelVersion"] == "v2"
        assert post_frame(client).json()["guardian"]["modelVersion"] == "v2"
        assert post_frame(second).json()["guardian"]["modelVersion"] == "v2"
    with application.state.store.connect() as db:
        assert db.execute("SELECT count(*) FROM incidents WHERE status='deployed'").fetchone()[0] == len(incidents)
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    with TestClient(lab.create_app(cfg)) as after_restart:
        status = after_restart.get("/api/guardian/status", headers=V).json()
        assert status["modelVersion"] == "v2" and not status["candidateReady"]
        assert status["currentMetrics"] == result["candidateMetrics"]
        assert status["activeModel"] == after_restart.get("/api/guardian/model", headers=V).json()


def test_no_improvement_is_not_deployable_and_unlabeled_data_is_ignored(rig):
    client, application, cfg, now = rig
    seed_review_queue(application, now[0], adaptation_incidents()[:1])
    result = client.post("/api/guardian/retrain", headers=P).json()
    assert result["ok"] and not result["improved"]
    assert result["candidateMetrics"] == result["beforeMetrics"]
    assert not client.get("/api/guardian/status", headers=V).json()["candidateReady"]
    assert client.post("/api/guardian/deploy", headers=P, json={"approved": True}).status_code == 409


def test_correcting_candidate_label_requires_revalidation(rig, trained):
    client, application, cfg, now = rig
    seed_review_queue(application, now[0], adaptation_incidents()[:1])
    state = deepcopy(trained[0])
    state["candidateIncidentIds"] = [1]
    application.state.guardian.restore_state(state)
    with application.state.store.connect() as db:
        db.execute("UPDATE incidents SET true_cause='wheel_slip',status='validated'")
        application.state.store.save_guardian(db, application.state.guardian)
    labeled = client.post("/api/guardian/incidents/1/label", headers=P,
                          json={"trueCause": "nominal", "notes": "Corrected false alarm"})
    assert labeled.json()["status"] == "labeled" and labeled.json()["trueCause"] == "nominal"
    assert not client.get("/api/guardian/status", headers=V).json()["candidateReady"]
    assert client.post("/api/guardian/deploy", headers=P, json={"approved": True}).status_code == 409


@pytest.mark.parametrize("label", [None, "not-a-cause", 2, [], {}])
def test_invalid_label_and_missing_incident(rig, label):
    client, application, cfg, now = rig
    assert client.post("/api/guardian/incidents/999/label", headers=P,
                       json={"trueCause": label}).status_code == 422
    assert client.post("/api/guardian/incidents/999/label", headers=P,
                       json={"trueCause": "dust"}).status_code == 404


def test_label_storage_failure_rolls_back(rig):
    client, application, cfg, now = rig
    seed_review_queue(application, now[0], adaptation_incidents()[:1])
    with patch.object(application.state.store, "save_guardian", side_effect=OSError("full")):
        result = client.post("/api/guardian/incidents/1/label", headers=P, json={"trueCause": "nominal"})
        assert result.status_code == 503
    row = client.get("/api/guardian/incidents", headers=V).json()["incidents"][0]
    assert row["status"] == "pending" and row["trueCause"] is None


def test_slow_loop_cannot_block_active_prediction_or_websocket(rig):
    client, application, cfg, now = rig
    entered, release = threading.Event(), threading.Event()

    def paused_training(engine, incidents):
        entered.set()
        assert release.wait(timeout=5)
        return {"ok": True}

    with client.websocket_connect("/api/live/stream?token=guardian-viewer") as ws:
        ws.receive_json()
        with ThreadPoolExecutor(max_workers=2) as pool, patch.object(GuardianEngine, "retrain", paused_training):
            training = pool.submit(client.post, "/api/guardian/retrain", headers=P)
            try:
                assert entered.wait(timeout=3)
                ingesting = pool.submit(post_frame, client)
                assert ingesting.result(timeout=2).status_code == 200
                frame = ws.receive_json()
                assert frame["guardian"]["modelVersion"] == "v1"
                assert not training.done()
            finally:
                release.set()
            assert training.result(timeout=5).status_code == 200


@pytest.mark.parametrize("path,method", [
    ("/api/guardian/status", "get"), ("/api/guardian/model", "get"),
    ("/api/guardian/incidents?limit=30", "get"), ("/api/guardian/incidents/1/label", "post"),
    ("/api/guardian/retrain", "post"), ("/api/guardian/deploy", "post"), ("/api/sim/rover", "post"),
])
def test_guardian_producer_viewer_boundaries(rig, path, method):
    client, application, cfg, now = rig
    for headers in ({}, P if method == "get" else V,
                    {"Authorization": "Bearer invalid"}, {"Authorization": "Basic guardian-producer"}):
        response = client.request(method, path, headers=headers)
        assert response.status_code == 401 and response.headers["www-authenticate"] == "Bearer"
    cfg.producer_token = cfg.viewer_token = "same"
    assert client.request(method, path, headers={"Authorization": "Bearer same"}).status_code == 401


@pytest.mark.parametrize("payload", [{}, {"action": "bad"}, {"action": "fault"},
                                     {"action": "fault", "fault": "wind"}, {"action": []},
                                     {"action": "start", "fault": 3}])
def test_invalid_sim_controls(rig, payload):
    client, application, cfg, now = rig
    assert client.post("/api/sim/rover", headers=P, json=payload).status_code == 422
    assert application.state.simulator.sim is None


@pytest.mark.parametrize("path", ["/api/sim/rover", "/api/guardian/deploy", "/api/guardian/incidents/1/label"])
@pytest.mark.parametrize("body", [b"[1]", b"null", b"bad json"])
def test_guardian_json_object_validation(rig, path, body):
    client, application, cfg, now = rig
    assert client.post(path, headers=P, content=body).status_code == 422


def test_sim_api_uses_full_pipeline_and_shutdown_stops_background_task(rig):
    client, application, cfg, now = rig
    with client.websocket_connect("/api/live/stream?token=guardian-viewer") as ws:
        ws.receive_json()
        result = client.post("/api/sim/rover", headers=P, json={"action": "step", "fault": "dust"}).json()
        streamed = ws.receive_json()
        latest = client.get("/api/live/latest", headers=V).json()["rooms"][0]
        assert streamed == latest
        assert all(result["latestFrame"][k] == v for k, v in streamed.items())
        assert result["latestFrame"]["stored"] and result["latestFrame"]["sessionId"] == 1
        assert streamed["source"] == "simulated-rover" and streamed["guardian"]["modelVersion"] == "v1"
    archived = client.get("/api/live/sessions/1", headers=V).json()["frame"]
    assert archived["source"] == "archived-rover" and archived["telemetry"] == latest["telemetry"]
    assert archived["guardian"] == latest["guardian"]
    stopped = client.post("/api/sim/rover", headers=P, json={"action": "stop"}).json()
    assert not stopped["simState"]["running"] and stopped["latestFrame"] is not None
    # A separate app scope explicitly exercises lifespan shutdown.
    other_app = lab.create_app(cfg)
    with TestClient(other_app) as second:
        result = second.post("/api/sim/rover", headers=P, json={"action": "start"}).json()
        assert result["simState"]["running"]
        task = other_app.state.simulator.task
    assert task.done() and other_app.state.simulator.task is None


def test_existing_v1_database_migrates_without_losing_compressed_frames(tmp_path):
    cfg = lab.Settings(producer_token="guardian-producer", viewer_token="guardian-viewer",
                       db=tmp_path / "v1.sqlite3", mesh_dir=tmp_path / "mesh", log_dir=tmp_path / "logs")
    with sqlite3.connect(cfg.db) as db:
        db.execute("""CREATE TABLE sessions(id INTEGER PRIMARY KEY AUTOINCREMENT,room TEXT NOT NULL,
            started_at REAL NOT NULL,ended_at REAL NOT NULL,frame_count INTEGER NOT NULL DEFAULT 0,
            max_points INTEGER NOT NULL DEFAULT 0,has_mesh INTEGER NOT NULL DEFAULT 0,
            mesh_bytes INTEGER NOT NULL DEFAULT 0)""")
        db.execute("""CREATE TABLE frames(id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            received_at REAL NOT NULL,yaw REAL,point_count INTEGER NOT NULL,payload BLOB NOT NULL)""")
        db.execute("INSERT INTO sessions(room,started_at,ended_at,frame_count,max_points) VALUES('v1',1,1,1,1)")
        db.execute("INSERT INTO frames(session_id,received_at,point_count,payload) VALUES(1,1,1,?)",
                   (gzip.compress(b"[[1,2,3]]"),))
    with TestClient(lab.create_app(cfg)) as client:
        frame = client.get("/api/live/sessions/1", headers=V).json()["frame"]
        assert frame["points"] == [[1, 2, 3]] and frame["source"] == "archived-quest"
        assert frame["carrierId"] == "v1" and frame["telemetry"] == {}
        assert client.get("/api/guardian/status", headers=V).json()["modelVersion"] == "v1"
