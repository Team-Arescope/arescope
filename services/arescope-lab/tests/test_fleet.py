"""Fleet policy, terrain movement and the real authenticated Guardian ingest path."""

import asyncio
from copy import deepcopy
import json
from pathlib import Path
import sys
from unittest.mock import patch

import anyio
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocket

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as lab
from fleet_sim import DRIVE_SPEED_MPS, MAX_EVENTS, MAX_TRAIL, FleetSimManager, distance
from rover_sim import CAUSES

P = {"Authorization": "Bearer fleet-producer"}
V = {"Authorization": "Bearer fleet-viewer"}
URL = "/api/sim/fleet"


@pytest.fixture
def rig(tmp_path):
    cfg = lab.Settings(producer_token="fleet-producer", viewer_token="fleet-viewer",
                       db=tmp_path / "fleet.sqlite3", mesh_dir=tmp_path / "meshes",
                       log_dir=tmp_path / "logs", min_history_interval=0)
    now = [1_800_000_000.0]
    application = lab.create_app(cfg, clock=lambda: now[0])
    with TestClient(application) as client:
        yield client, application, cfg, now


def control(client, action, **kwargs):
    response = client.post(URL, headers=P, json={"action": action, **kwargs})
    assert response.status_code == 200, response.text
    result = response.json()
    assert set(result) == {"ok", "fleetState"} and result["ok"] is True
    return result["fleetState"]


@pytest.mark.parametrize("method", ["get", "post"])
def test_role_authentication_and_no_unauthorized_mutation(rig, method):
    client, application, cfg, now = rig
    before = client.get(URL, headers=V).json()
    for headers in ({}, P if method == "get" else V,
                    {"Authorization": "Bearer wrong"}, {"Authorization": "Basic fleet-producer"}):
        result = client.request(method, URL, headers=headers, json={"action": "step"})
        assert result.status_code == 401 and result.headers["www-authenticate"] == "Bearer"
    assert client.get(URL, headers=V).json() == before
    assert application.state.live.ingest == 0
    cfg.producer_token = cfg.viewer_token = "same"
    assert client.request(method, URL, headers={"Authorization": "Bearer same"}).status_code == 401


@pytest.mark.parametrize("payload", [
    {}, {"action": "move"}, {"action": []}, {"action": True},
    {"action": "step", "count": 0}, {"action": "step", "count": 7},
    {"action": "step", "count": True}, {"action": "step", "count": 2.5},
    {"action": "step", "count": "3"}, {"action": "step", "count": None},
    {"action": "step", "speedMultiplier": 0}, {"action": "step", "speedMultiplier": 121},
    {"action": "step", "speedMultiplier": True}, {"action": "step", "speedMultiplier": None},
    {"action": "step", "speedMultiplier": "30"},
    {"action": "fault"}, {"action": "fault", "roverId": "fleet-rover-01"},
    {"action": "fault", "roverId": "missing", "fault": "dust"},
    {"action": "fault", "roverId": [], "fault": "dust"},
    {"action": "fault", "roverId": "fleet-rover-01", "fault": []},
    {"action": "fault", "roverId": "fleet-rover-01", "fault": "wind"},
    {"action": "step", "fault": "dust"}, {"action": "step", "roverId": "fleet-rover-01"},
    {"action": "reset", "extra": 1},
])
def test_invalid_input_never_mutates_state_or_history(rig, payload):
    client, application, cfg, now = rig
    before = client.get(URL, headers=V).json()
    assert client.post(URL, headers=P, json=payload).status_code == 422
    assert client.get(URL, headers=V).json() == before
    assert application.state.live.ingest == 0
    assert application.state.store.stats()["frameCount"] == 0


@pytest.mark.parametrize("body", [b"[1]", b"null", b"not json",
                                     b'{"action":"step","speedMultiplier":NaN}',
                                     b'{"action":"step","speedMultiplier":Infinity}',
                                     b'{"action":"step","speedMultiplier":1e1000}'])
def test_invalid_json_or_nonfinite_config(rig, body):
    client, application, cfg, now = rig
    before = client.get(URL, headers=V).json()
    assert client.post(URL, headers=P, content=body).status_code == 422
    assert client.get(URL, headers=V).json() == before


def test_enormous_integer_speed_is_rejected_without_mutation(rig):
    client, application, cfg, now = rig
    before = client.get(URL, headers=V).json()
    assert client.post(URL, headers=P, json={"action": "step", "speedMultiplier": 10 ** 500}).status_code == 422
    assert client.get(URL, headers=V).json() == before


@pytest.mark.parametrize("count,speed", [(1, 1), (6, 120)])
def test_contract_bounds_and_distinct_carriers(rig, count, speed):
    client, application, cfg, now = rig
    initial = control(client, "reset", count=count, speedMultiplier=speed)
    assert initial["coverage"]["scannedCells"] == 0
    state = control(client, "step")
    assert state["count"] == len(state["rovers"]) == count
    assert state["elapsedS"] == speed and state["speedMultiplier"] == speed
    assert state["terrainSource"] == "nasa-pds-hirise" and state["simulation"] is True
    assert state["synthetic"] is True and state["acceleratedTime"] is True
    assert state["coverage"]["totalCells"] == 128 ** 2
    assert 1_000_000 < state["coverage"]["totalAreaM2"] < 1_100_000
    assert len({r["carrierId"] for r in state["rovers"]}) == count
    assert len({r["assignedSector"] for r in state["rovers"]}) == count
    assert all(r["guardian"]["riskLevel"] == "nominal" for r in state["rovers"])
    assert application.state.live.ingest == count
    assert state == client.get(URL, headers=V).json()
    assert application.state.simulator.sim is None
    json.dumps(state, allow_nan=False)


def test_one_vs_three_coverage_grows_without_overlap_and_reset_is_explicit(rig):
    client, application, cfg, now = rig
    coverage = {}
    for count in (1, 3):
        control(client, "reset", count=count, speedMultiplier=60)
        previous = set()
        for _ in range(8):
            state = control(client, "step")
            cells = {tuple(cell) for cell in state["coverage"]["cells"]}
            assert cells > previous
            assert all(0 <= r < 128 and 0 <= c < 128 for r, c in cells)
            assert len(cells) == state["coverage"]["scannedCells"]
            previous = cells
        coverage[count] = len(previous)
        assert state["coverage"]["percent"] == pytest.approx(100 * len(previous) / 128 ** 2)
        assert state["coverage"]["areaM2"] == pytest.approx(len(previous) * application.state.fleet.spacing ** 2)
        before = client.get(URL, headers=V).json()
        result = client.post(URL, headers=P, json={"action": "start", "count": 2})
        assert result.status_code == 422 and "reset" in result.json()["detail"]
        assert client.get(URL, headers=V).json() == before
    assert coverage[3] > 2 * coverage[1]
    reset = control(client, "reset", count=2)
    assert not reset["running"] and reset["elapsedS"] == 0 and reset["coverage"]["cells"] == []


def test_full_ingest_websocket_incident_and_persisted_per_carrier_history(rig):
    client, application, cfg, now = rig
    with client.websocket_connect("/api/live/stream?token=fleet-viewer") as ws:
        ws.receive_json()
        state = control(client, "step", count=3)
        frames = [ws.receive_json() for _ in range(3)]
        latest = client.get("/api/live/latest", headers=V).json()["rooms"]
        assert frames == latest
        for rover, frame in zip(state["rovers"], frames):
            assert frame["carrierId"] == rover["carrierId"]
            assert frame["source"] == "simulated-rover" and frame["carrierType"] == "rover"
            assert frame["guardian"] == rover["guardian"]
            assert frame["telemetry"]["position"] == rover["position"]
            assert len(application.state.live.telemetry_windows[rover["carrierId"]]) == 1
        state = control(client, "fault", roverId="fleet-rover-02", fault="wheel_slip")
        assert ws.receive_json()["guardian"]["riskLevel"] in ("warning", "critical")
    assert client.get("/api/guardian/incidents", headers=V).json()["incidents"][0]["carrierId"] == "fleet-rover-02"
    sessions = client.get("/api/live/sessions", headers=V).json()["sessions"]
    assert len(sessions) == 3
    archived = [client.get(f"/api/live/sessions/{s['id']}", headers=V).json()["frame"] for s in sessions]
    assert {f["carrierId"] for f in archived} == {r["carrierId"] for r in state["rovers"]}
    assert all(f["source"] == "archived-rover" and f["guardian"] is not None for f in archived)
    with TestClient(lab.create_app(cfg)) as restarted:
        for session, frame in zip(sessions, archived):
            assert restarted.get(f"/api/live/sessions/{session['id']}", headers=V).json()["frame"] == frame


@pytest.mark.parametrize("fault", CAUSES[1:])
def test_each_explicit_fault_is_inferred_and_latches_halt(rig, fault):
    client, application, cfg, now = rig
    control(client, "step", count=1, speedMultiplier=120)
    state = control(client, "fault", roverId="fleet-rover-01", fault=fault)
    for _ in range(6):
        if state["rovers"][0]["status"] == "halted":
            break
        state = control(client, "step")
    rover = state["rovers"][0]
    assert rover["fault"] == fault and rover["status"] == "halted"
    assert rover["guardian"]["riskLevel"] in ("warning", "critical")
    assert rover["guardian"]["predictedCause"] == fault
    position, scanned = rover["position"], state["coverage"]["scannedCells"]
    for _ in range(6):
        state = control(client, "step")
    assert state["rovers"][0]["position"] == position
    assert state["rovers"][0]["fault"] == fault and state["rovers"][0]["status"] == "halted"
    assert state["coverage"]["scannedCells"] == scanned
    assert any(e["type"] == "assistance_unavailable" for e in state["events"])


def test_nearest_healthy_helper_moves_on_terrain_to_standoff_without_healing(rig):
    client, application, cfg, now = rig
    initial = control(client, "step", count=3, speedMultiplier=120)
    target_id = initial["rovers"][0]["carrierId"]
    target_position = initial["rovers"][0]["position"]
    expected_helper = min(initial["rovers"][1:], key=lambda r: distance(r["position"], target_position))["carrierId"]
    state = control(client, "fault", roverId=target_id, fault="wheel_slip")
    helper = next(r for r in state["rovers"] if r["targetId"] == target_id)
    assert helper["carrierId"] == expected_helper and helper["status"] == "responding"
    assert helper["position"] == next(r for r in initial["rovers"] if r["carrierId"] == expected_helper)["position"]
    previous = helper["position"]
    initial_coverage = state["coverage"]["scannedCells"]
    for _ in range(30):
        state = control(client, "step")
        helper = next(r for r in state["rovers"] if r["carrierId"] == expected_helper)
        assert distance(previous, helper["position"]) <= DRIVE_SPEED_MPS * 120 + 1e-6
        assert distance(helper["position"], target_position) >= 2 * application.state.fleet.spacing - 1e-6
        point = helper["position"]
        fleet = application.state.fleet
        on_surface = fleet._surface((point[2] - fleet.points[0][2]) / fleet.spacing,
                                    (point[0] - fleet.points[0][0]) / fleet.spacing)
        assert point == pytest.approx(on_surface)
        previous = point
        if helper["status"] == "assisting":
            break
    assert helper["status"] == "assisting"
    assert 2 * fleet.spacing <= distance(helper["position"], target_position) <= 3 * fleet.spacing
    arrived = deepcopy(helper["position"])
    for _ in range(5):
        state = control(client, "step")
    target = next(r for r in state["rovers"] if r["carrierId"] == target_id)
    helper = next(r for r in state["rovers"] if r["carrierId"] == expected_helper)
    assert helper["position"] == arrived and helper["status"] == "assisting"
    assert target["position"] == target_position and target["status"] == "halted" and target["fault"] == "wheel_slip"
    assert any(r["status"] == "surveying" for r in state["rovers"])
    assert state["coverage"]["scannedCells"] > initial_coverage
    explanation = " ".join(e["message"] for e in state["events"])
    assert "Guardian" in explanation and "nearest" in explanation and "A*" in explanation and "no automatic repair" in explanation


def test_faulted_helper_is_not_reused_and_no_duplicate_assignments(rig):
    client, application, cfg, now = rig
    control(client, "step", count=3, speedMultiplier=120)
    state = control(client, "fault", roverId="fleet-rover-01", fault="wheel_slip")
    helper_id = next(r["carrierId"] for r in state["rovers"] if r["targetId"] == "fleet-rover-01")
    state = control(client, "fault", roverId=helper_id, fault="sensor_drop")
    by_id = {r["carrierId"]: r for r in state["rovers"]}
    assert by_id[helper_id]["status"] == "halted" and by_id[helper_id]["targetId"] is None
    assignments = [r["targetId"] for r in state["rovers"] if r["targetId"]]
    assert len(assignments) == len(set(assignments)) == 1
    assert all(r["fault"] == "nominal" for r in state["rovers"] if r["targetId"])


def test_reset_discards_only_fleet_observation_windows_and_operator_can_clear(rig):
    client, application, cfg, now = rig
    control(client, "step", count=3)
    client.post("/api/live/frame", headers=P, json={"carrierId": "device-outside-fleet", "points": []})
    other_window = application.state.live.telemetry_windows["device-outside-fleet"]
    control(client, "fault", roverId="fleet-rover-01", fault="dust")
    for _ in range(5):
        control(client, "step")
    cleared = control(client, "fault", roverId="fleet-rover-01", fault="nominal")
    assert cleared["rovers"][0]["fault"] == "nominal"
    if cleared["rovers"][0]["guardian"]["riskLevel"] != "nominal":
        assert cleared["rovers"][0]["status"] == "halted"
    for _ in range(6):
        cleared = control(client, "step")
    assert cleared["rovers"][0]["guardian"]["riskLevel"] == "nominal"
    assert cleared["rovers"][0]["status"] == "surveying"
    assert any(e["type"] == "operator_clearance" for e in cleared["events"])
    assert any(e["type"] == "guardian_clearance" for e in cleared["events"])
    control(client, "fault", roverId="fleet-rover-01", fault="sensor_drop")
    with client.websocket_connect("/api/live/stream?token=fleet-viewer") as ws:
        assert len(ws.receive_json()["rooms"]) == 4
        reset = control(client, "reset", count=1)
        snapshot = ws.receive_json()
        assert len(reset["rovers"]) == 1
        assert [frame["carrierId"] for frame in snapshot["rooms"]] == ["device-outside-fleet"]
    assert application.state.live.telemetry_windows["device-outside-fleet"] is other_window
    assert not any(key.startswith("fleet-rover-") for key in application.state.live.telemetry_windows)
    assert not any(key.startswith("fleet-rover-") for key in application.state.live.frames)
    assert "device-outside-fleet" in application.state.live.frames
    state = control(client, "step")
    assert state["rovers"][0]["status"] == "surveying" and state["rovers"][0]["fault"] == "nominal"
    assert len(application.state.live.telemetry_windows["fleet-rover-01"]) == 1


@pytest.mark.parametrize("fault", ["dust", "wheel_slip"])
def test_real_guardian_after_five_nominal_frames_arrives_within_twenty_ticks_at_default_speed(rig, fault):
    client, application, cfg, now = rig
    for _ in range(5):
        state = control(client, "step")
        now[0] += 1
        assert state["speedMultiplier"] == 60
        assert all(r["status"] == "surveying" and r["guardian"]["riskLevel"] == "nominal" for r in state["rovers"])
    assert all(len(w) == 5 for w in application.state.live.telemetry_windows.values())
    assert all(f["telemetry"]["commandedSpeedMps"] == .8 for f in application.state.live.frames.values())
    state = control(client, "fault", roverId="fleet-rover-01", fault=fault)
    previous = {r["carrierId"]: r["position"] for r in state["rovers"]}
    for _ in range(20):
        state = control(client, "step")
        now[0] += 1
        target = state["rovers"][0]
        for helper in state["rovers"][1:]:
            if helper["targetId"] == target["carrierId"]:
                a, b = previous[helper["carrierId"]], helper["position"]
                assert distance(a, b) <= DRIVE_SPEED_MPS * 60 + 1e-6
                assert application.state.fleet._safe_segment(a, b, [target["position"]])
        previous = {r["carrierId"]: r["position"] for r in state["rovers"]}
        if any(r["status"] == "assisting" for r in state["rovers"]):
            break
    assert target["status"] == "halted" and target["fault"] == fault
    assert target["guardian"]["predictedCause"] == fault
    helper = next(r for r in state["rovers"] if r["status"] == "assisting")
    assert helper["targetId"] == target["carrierId"]
    assert 2 * application.state.fleet.spacing <= distance(helper["position"], target["position"]) <= 3 * application.state.fleet.spacing
    assert any(r["status"] == "surveying" for r in state["rovers"])


def test_real_astar_respects_new_exclusions_and_completely_blocked_route():
    async def run():
        async def ingest(frame):
            return {**frame, "guardian": {"riskLevel": "nominal", "predictedCause": "nominal", "riskScore": .05}}
        fleet = FleetSimManager(ingest)
        await fleet.control({"action": "step", "count": 3})
        target, helper, blocker = fleet.rovers
        target.status, target.fault = "halted", "dust"
        fleet._assign_helpers()
        assert helper.status == "responding"
        blocker.position = fleet._position(*list(helper.inspection)[4])
        blocker.status, blocker.fault = "halted", "sensor_drop"
        before = helper.position[:]
        fleet._move(helper, 120)
        assert helper.status == "waiting" and helper.target_id is None
        assert fleet._safe_segment(before, helper.position, [target.position, blocker.position])
        assert any(e["type"] == "inspection_route_blocked" for e in fleet.events)
        fleet._assign_helpers()
        # A viable detour must avoid the newly halted rover along every segment.
        a = helper.position
        for cell in helper.inspection:
            b = fleet._position(*cell)
            assert fleet._safe_segment(a, b, [target.position, blocker.position])
            a = b
        fleet = FleetSimManager(ingest)
        await fleet.control({"action": "step", "count": 6})
        target, helper, *blockers = fleet.rovers
        target.position, helper.position = fleet._position(60, 60), fleet._position(60, 75)
        target.status = "halted"
        for blocker, cell in zip(blockers, [(60, 72), (60, 78), (57, 75), (63, 75)]):
            blocker.position, blocker.status = fleet._position(*cell), "halted"
        # Real A* exhausts a small enclosed region; it cannot teleport through it.
        assert fleet._inspection_path(helper, target) is None
        fleet._assign_helpers()
        assert helper.target_id != target.carrier_id and helper.position == fleet._position(60, 75)
        assert any(e["type"] == "assistance_unavailable" and e["roverId"] == target.carrier_id for e in fleet.events)
    asyncio.run(run())


def test_stop_start_resume_and_shutdown_stops_both_simulators(rig):
    client, application, cfg, now = rig
    control(client, "step", count=3)
    faulted = control(client, "fault", roverId="fleet-rover-01", fault="dust")
    started = control(client, "start")
    task = application.state.fleet.task
    assert started["running"]
    assert control(client, "start")["elapsedS"] == started["elapsedS"]
    assert application.state.fleet.task is task
    stopped = control(client, "stop")
    assert not stopped["running"] and task.done() and application.state.fleet.task is None
    assert stopped["coverage"] == started["coverage"]
    assert stopped["rovers"][0]["fault"] == faulted["rovers"][0]["fault"]
    assert stopped["elapsedS"] == started["elapsedS"]
    other = lab.create_app(cfg)
    with TestClient(other) as second:
        assert control(second, "start", count=1)["running"]
        assert second.post("/api/sim/rover", headers=P, json={"action": "start"}).status_code == 200
        fleet_task, rover_task = other.state.fleet.task, other.state.simulator.task
    assert fleet_task.done() and rover_task.done()
    assert other.state.fleet.task is None and other.state.simulator.task is None


def test_async_concurrent_start_stop_bounded_rate_and_error_shutdown():
    async def run():
        calls = []
        async def ingest(frame):
            calls.append(frame)
            return {**frame, "guardian": {"riskLevel": "nominal", "predictedCause": "nominal", "riskScore": .05}}
        fleet = FleetSimManager(ingest)
        await asyncio.gather(*(fleet.control({"action": "start", "count": 6}) for _ in range(5)))
        assert fleet.state()["running"] and len(calls) == 6
        await asyncio.sleep(1.1)
        assert len(calls) == 12
        await asyncio.gather(*(fleet.control({"action": "stop"}) for _ in range(5)))
        assert not fleet.state()["running"]
        await asyncio.sleep(.05)
        assert len(calls) == 12
        assert len({f["carrierId"] for f in calls[:6]}) == 6
    asyncio.run(run())


@pytest.mark.parametrize("interval", [0, -.1, .5, True, float("nan"), float("inf"), "1"])
def test_bad_manager_interval(interval):
    with pytest.raises(ValueError):
        FleetSimManager(None, interval=interval)


def test_bounded_trails_events_coverage_and_no_route_fallback():
    async def run():
        async def ingest(frame):
            return {**frame, "guardian": {"riskLevel": "nominal", "predictedCause": "nominal", "riskScore": .05}}
        fleet = FleetSimManager(ingest)
        await fleet.control({"action": "step", "count": 3, "speedMultiplier": 120})
        target = fleet.rovers[0]
        target.status, target.fault = "halted", "dust"
        with patch.object(fleet, "_inspection_path", return_value=None):
            fleet._assign_helpers()
            assert not any(r.target_id for r in fleet.rovers)
            assert fleet.events[-1]["type"] == "assistance_unavailable"
        for _ in range(180):
            await fleet.step()
            fleet._event("test", None, None, "bounded event")
        state = fleet.state()
        assert len(state["events"]) == MAX_EVENTS
        assert all(len(r["trail"]) <= MAX_TRAIL for r in state["rovers"])
        assert any(len(r["trail"]) == MAX_TRAIL for r in state["rovers"])
        assert len(state["coverage"]["cells"]) <= 128 ** 2
        assert len({e["id"] for e in state["events"]}) == MAX_EVENTS
        assert target.status == "halted" and target.fault == "dust"
        assert all(len(r.inspection) <= 128 ** 2 for r in fleet.rovers)
    asyncio.run(run())


def test_websocket_disconnect_during_request_cancellation_drains_tasks(rig):
    client, application, cfg, now = rig
    endpoint = next(route.endpoint for route in application.routes if route.path == "/api/live/stream")

    async def run():
        for delay in (1, 2, 3):
            connected = False
            sent = []
            before = asyncio.all_tasks()

            def cancel_after_turns(turns):
                if turns:
                    asyncio.get_running_loop().call_soon(cancel_after_turns, turns - 1)
                else:
                    request_scope.cancel()

            async def receive():
                nonlocal connected
                if not connected:
                    connected = True
                    return {"type": "websocket.connect"}
                await asyncio.sleep(0)
                # Cancel while the handler is draining its disconnected children,
                # matching TestClient's disconnect followed by CancelScope.cancel.
                asyncio.get_running_loop().call_soon(cancel_after_turns, delay)
                return {"type": "websocket.disconnect", "code": 1000}

            async def send(message):
                sent.append(message)

            scope = {"type": "websocket", "path": "/api/live/stream",
                     "query_string": b"token=fleet-viewer", "headers": []}
            with anyio.CancelScope() as request_scope:
                await endpoint(WebSocket(scope, receive, send))
                await anyio.sleep_forever()
            assert request_scope.cancelled_caught
            assert [message["type"] for message in sent] == ["websocket.accept", "websocket.send"]
            assert not application.state.live.subscribers
            assert asyncio.all_tasks() == before

    asyncio.run(run())


@pytest.mark.parametrize("failure_in", ["send", "receive"])
def test_websocket_worker_failure_is_propagated_after_cleanup(rig, failure_in):
    client, application, cfg, now = rig
    endpoint = next(route.endpoint for route in application.routes if route.path == "/api/live/stream")

    async def run():
        connected = False
        before = asyncio.all_tasks()

        async def receive():
            nonlocal connected
            if not connected:
                connected = True
                return {"type": "websocket.connect"}
            if failure_in == "receive":
                raise RuntimeError("injected stream worker failure")
            await anyio.sleep_forever()

        async def send(message):
            if failure_in == "send" and message["type"] == "websocket.send":
                raise RuntimeError("injected stream worker failure")

        scope = {"type": "websocket", "path": "/api/live/stream",
                 "query_string": b"token=fleet-viewer", "headers": []}
        with pytest.raises(RuntimeError, match="injected stream worker failure"):
            await endpoint(WebSocket(scope, receive, send))
        assert not application.state.live.subscribers
        assert asyncio.all_tasks() == before

    asyncio.run(run())
