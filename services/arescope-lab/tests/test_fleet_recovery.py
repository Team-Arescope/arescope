"""Bounded synthetic fleet recovery checks; never exercise a server or hardware."""

import asyncio
from collections import defaultdict, deque
from copy import deepcopy
import json
import math
from pathlib import Path
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as lab
import fleet_sim
from fleet_sim import DRIVE_SPEED_MPS, FleetSimManager, distance
from rover_sim import CAUSES


P = {"Authorization": "Bearer recovery-test-producer"}
V = {"Authorization": "Bearer recovery-test-viewer"}
URL = "/api/sim/fleet"
TARGET = "fleet-rover-01"
MINOR = ("dust", "wheel_slip", "wheel_jam")
SERIOUS = ("sensor_drop", "hq_link_broken", "low_texture", "glare")
PHASES = {"none", "waiting_helper", "en_route", "repairing", "validating",
          "awaiting_approval", "recovered", "failed"}
MAX_TICKS = 100  # 3,000 simulated seconds at 30x; no wall-clock waits.


@pytest.fixture
def terrain(tmp_path):
    """A small rectangular lattice with unequal axes and an affine gentle slope."""
    rows, cols, east, south = 21, 29, 2.0, 3.0
    data = {"grid": {"rows": rows, "cols": cols},
            "metadata": {"product_id": "recovery-test-only",
                         "effective_spacing_m": {"east": east, "south": south}},
            "points": [[(c - 14) * east, 100 + c * east * .03 + r * south * .02,
                        (r - 10) * south] for r in range(rows) for c in range(cols)]}
    path = tmp_path / "recovery-synthetic-rectangle.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class ObservationFeed:
    """Classify nominal versus disturbed telemetry without consulting rover internals."""

    def __init__(self):
        self.frames = []
        self.overrides = defaultdict(deque)
        self.block_nominal = set()

    async def __call__(self, frame):
        t, carrier = frame["telemetry"], frame["carrierId"]
        if t["fps"] < 2 or not t["linkOk"]:
            cause = "sensor_drop"
        elif t["slipRatio"] > .85:
            cause = "wheel_slip"
        elif t["lumaContrast"] < .08:
            cause = "dust"
        elif t["lumaContrast"] > .97:
            cause = "glare"
        elif t["pointCount"] < 100:
            cause = "low_texture"
        else:
            cause = "nominal"
        if self.overrides[carrier]:
            cause = self.overrides[carrier].popleft()
        elif carrier in self.block_nominal and cause == "nominal":
            cause = "dust"
        guardian = {"riskLevel": "nominal" if cause == "nominal" else "critical",
                    "riskScore": .02 if cause == "nominal" else .99,
                    "predictedCause": cause}
        result = {**frame, "guardian": guardian}
        self.frames.append(deepcopy(result))
        return result


@pytest.fixture
def feed():
    return ObservationFeed()


def rover(state, carrier=TARGET):
    return next(r for r in state["rovers"] if r["carrierId"] == carrier)


async def command(fleet, action, **kwargs):
    result = await fleet.control({"action": action, **kwargs})
    assert result["ok"] is True
    return result["fleetState"]


async def ready(terrain, feed, count=2, auto=True):
    fleet = FleetSimManager(feed, terrain_path=terrain)
    await command(fleet, "reset", count=count, speedMultiplier=30, autoRepair=auto)
    await command(fleet, "step")
    # Only initial positions are arranged; route choice, arrival and service are real policy.
    cells = ((10, 6), (10, 24), (17, 6), (17, 24))
    for item, (row, col) in zip(fleet.rovers, cells):
        item.position = fleet._position(row, col)
    return fleet


async def until(fleet, predicate, limit=MAX_TICKS):
    state = fleet.state()
    for _ in range(limit):
        if predicate(state):
            return state
        state = await command(fleet, "step")
    assert predicate(state), f"Recovery condition not reached in {limit} ticks: {state['rovers']}"
    return state


def assert_recovery_contract(state):
    assert type(state["autoRepair"]) is bool
    for item in state["rovers"]:
        recovery = item["recovery"]
        assert recovery["phase"] in PHASES
        assert math.isfinite(recovery["progress"]) and 0 <= recovery["progress"] <= 1
        assert recovery["helperId"] is None or isinstance(recovery["helperId"], str)
        assert all(type(recovery[key]) is bool for key in ("requiresApproval", "approved", "held"))
        assert type(recovery["requestId"]) is int
    json.dumps(state, allow_nan=False)


def test_default_recovery_contract_and_extended_fleet_causes(terrain, feed):
    fleet = FleetSimManager(feed, terrain_path=terrain)
    state = fleet.state()
    assert state["autoRepair"] is True
    assert set(fleet_sim.FLEET_CAUSES) == set(CAUSES) | {"wheel_jam", "hq_link_broken"}
    assert_recovery_contract(state)
    assert all(r["recovery"]["phase"] == "none" and r["recovery"]["progress"] == 0
               and r["recovery"]["helperId"] is None and not r["recovery"]["approved"]
               and not r["recovery"]["requiresApproval"] for r in state["rovers"])


@pytest.mark.parametrize("action", ["configure", "start", "reset", "step"])
def test_supported_commands_accept_boolean_auto_repair(terrain, feed, action):
    async def scenario():
        fleet = FleetSimManager(feed, terrain_path=terrain)
        try:
            state = await command(fleet, action, autoRepair=False)
            assert state["autoRepair"] is False
            state = await command(fleet, "configure", autoRepair=True)
            assert state["autoRepair"] is True
            assert_recovery_contract(state)
        finally:
            await fleet.stop()
    asyncio.run(scenario())


@pytest.mark.parametrize("fault", MINOR)
def test_minor_repair_requires_safe_arrival_and_timed_progress_then_validation(terrain, feed, fault):
    async def scenario():
        fleet = await ready(terrain, feed)
        state = await command(fleet, "fault", roverId=TARGET, fault=fault)
        target = rover(state)
        halted = target["position"][:]
        helper_id = target["recovery"]["helperId"]
        assert helper_id and target["status"] == "halted"
        assert target["recovery"]["progress"] == 0
        assert distance(rover(state, helper_id)["position"], halted) > fleet.standoff_max_m
        assert target["fault"] == fault
        previous = rover(state, helper_id)["position"]
        feed.block_nominal.add(TARGET)
        progress = []
        for _ in range(MAX_TICKS):
            state = await command(fleet, "step")
            target, helper = rover(state), rover(state, helper_id)
            assert target["position"] == halted and target["status"] == "halted"
            assert distance(previous, helper["position"]) <= DRIVE_SPEED_MPS * 30 + 1e-6
            # Check actual swept horizontal clearance, including between grid samples.
            a, b = previous, helper["position"]
            dx, dz = b[0] - a[0], b[2] - a[2]
            length2 = dx * dx + dz * dz
            fraction = min(1, max(0, ((halted[0] - a[0]) * dx + (halted[2] - a[2]) * dz) / length2)) if length2 else 0
            nearest = [a[0] + fraction * dx, 0, a[2] + fraction * dz]
            assert distance(nearest, halted) >= fleet.standoff_min_m - 1e-6
            point = helper["position"]
            assert point[1] == pytest.approx(100 + (point[0] + 28) * .03 + (point[2] + 30) * .02)
            previous = helper["position"]
            phase = target["recovery"]["phase"]
            if phase == "repairing":
                assert helper["status"] == "repairing" and target["fault"] == fault
                assert fleet.standoff_min_m <= distance(helper["position"], halted) <= fleet.standoff_max_m
                progress.append(target["recovery"]["progress"])
            elif phase == "validating":
                assert target["fault"] == "nominal"
                break
        else:
            pytest.fail("Synthetic minor repair never reached Guardian validation")
        assert len(progress) >= 2 and any(0 < p < 1 for p in progress)
        assert progress == sorted(progress)
        feed.block_nominal.remove(TARGET)
        for index in range(3):
            state = await command(fleet, "step")
            target = rover(state)
            if index < 2:
                assert target["status"] == "halted" and target["recovery"]["phase"] == "validating"
        assert target["recovery"]["phase"] == "recovered" and target["fault"] == "nominal"
        assert target["status"] in ("surveying", "waiting")
        assert target["recovery"]["progress"] == 1
        assert_recovery_contract(state)
    asyncio.run(scenario())


def test_validation_requires_three_consecutive_nominal_observations(terrain, feed):
    async def scenario():
        fleet = await ready(terrain, feed)
        feed.block_nominal.add(TARGET)
        await command(fleet, "fault", roverId=TARGET, fault="wheel_jam")
        state = await until(fleet, lambda s: rover(s)["recovery"]["phase"] == "validating")
        assert rover(state)["fault"] == "nominal" and rover(state)["status"] == "halted"
        feed.overrides[TARGET].extend(["nominal", "dust", "nominal", "nominal", "nominal"])
        for index in range(5):
            before = sum(f["carrierId"] == TARGET for f in feed.frames)
            state = await command(fleet, "step")
            assert sum(f["carrierId"] == TARGET for f in feed.frames) == before + 1
            target = rover(state)
            if index < 4:
                assert target["status"] == "halted" and target["recovery"]["phase"] != "recovered"
        assert target["recovery"]["phase"] == "recovered"
    asyncio.run(scenario())


def test_disabling_auto_repair_cancels_progress_retains_fault_and_halt(terrain, feed):
    async def scenario():
        fleet = await ready(terrain, feed)
        await command(fleet, "fault", roverId=TARGET, fault="dust")
        state = await until(fleet, lambda s: 0 < rover(s)["recovery"]["progress"] < 1)
        position = rover(state)["position"]
        state = await command(fleet, "configure", autoRepair=False)
        assert state["autoRepair"] is False and rover(state)["recovery"]["progress"] == 0
        for _ in range(30):
            state = await command(fleet, "step")
            target = rover(state)
            assert target["fault"] == "dust" and target["status"] == "halted"
            assert target["position"] == position and target["recovery"]["progress"] == 0
            assert target["recovery"]["phase"] != "repairing"
        await command(fleet, "configure", autoRepair=True)
        state = await until(fleet, lambda s: rover(s)["recovery"]["phase"] == "recovered")
        assert rover(state)["fault"] == "nominal"
    asyncio.run(scenario())


@pytest.mark.parametrize("fault", SERIOUS)
def test_serious_fault_never_auto_clears_without_mission_control(terrain, feed, fault):
    async def scenario():
        fleet = await ready(terrain, feed)
        state = await command(fleet, "fault", roverId=TARGET, fault=fault)
        position = rover(state)["position"]
        for _ in range(35):  # Beyond the 600 simulated second repair duration.
            target = rover(state)
            assert target["status"] == "halted" and target["fault"] == fault
            assert target["position"] == position
            assert target["recovery"]["phase"] == "awaiting_approval"
            assert target["recovery"]["requiresApproval"] is True
            assert target["recovery"]["approved"] is False
            assert target["recovery"]["requestId"] > 0
            assert target["recovery"]["progress"] == 0
            assert not any(r["status"] == "repairing" for r in state["rovers"])
            state = await command(fleet, "step")
    asyncio.run(scenario())


@pytest.mark.parametrize("fault", ["sensor_drop", "hq_link_broken"])
def test_approved_serious_recovery_waits_for_helper_and_validation(terrain, feed, fault):
    async def scenario():
        fleet = await ready(terrain, feed, auto=False)
        state = await command(fleet, "fault", roverId=TARGET, fault=fault)
        request_id = rover(state)["recovery"]["requestId"]
        state = await command(fleet, "approve_recovery", roverId=TARGET, requestId=request_id)
        target = rover(state)
        assert target["recovery"]["approved"] is True
        assert target["fault"] == fault and target["status"] == "halted"
        assert target["recovery"]["progress"] == 0  # Approval cannot teleport the helper.
        feed.block_nominal.add(TARGET)
        state = await until(fleet, lambda s: rover(s)["recovery"]["phase"] == "repairing")
        target = rover(state)
        helper = rover(state, target["recovery"]["helperId"])
        assert helper["status"] == "repairing" and helper["guardian"]["riskLevel"] == "nominal"
        assert fleet.standoff_min_m <= distance(helper["position"], target["position"]) <= fleet.standoff_max_m
        state = await until(fleet, lambda s: rover(s)["recovery"]["phase"] == "validating")
        assert rover(state)["fault"] == "nominal" and rover(state)["status"] == "halted"
        feed.block_nominal.remove(TARGET)
        for _ in range(3):
            state = await command(fleet, "step")
        assert rover(state)["recovery"]["phase"] == "recovered"
    asyncio.run(scenario())


def test_hold_keeps_serious_target_halted_and_can_later_approve(terrain, feed):
    async def scenario():
        fleet = await ready(terrain, feed)
        state = await command(fleet, "fault", roverId=TARGET, fault="sensor_drop")
        request_id = rover(state)["recovery"]["requestId"]
        state = await command(fleet, "hold_recovery", roverId=TARGET, requestId=request_id)
        for _ in range(30):
            target = rover(state)
            assert target["recovery"]["held"] is True and not target["recovery"]["approved"]
            assert target["status"] == "halted" and target["fault"] == "sensor_drop"
            assert target["recovery"]["progress"] == 0
            state = await command(fleet, "step")
        state = await command(fleet, "approve_recovery", roverId=TARGET, requestId=request_id)
        assert rover(state)["recovery"]["approved"] and not rover(state)["recovery"]["held"]
        state = await until(fleet, lambda s: rover(s)["recovery"]["phase"] == "recovered")
        assert rover(state)["fault"] == "nominal"
    asyncio.run(scenario())


@pytest.mark.parametrize("problem", ["alone", "cliff"])
def test_no_helper_or_no_safe_route_cannot_fabricate_recovery(terrain, feed, problem):
    if problem == "cliff":
        data = json.loads(terrain.read_text(encoding="utf-8"))
        for index, point in enumerate(data["points"]):
            if index % data["grid"]["cols"] >= 15:
                point[1] += 10_000  # Full-depth impassable cliff, not a mocked planner result.
        terrain.write_text(json.dumps(data), encoding="utf-8")

    async def scenario():
        fleet = await ready(terrain, feed, count=1 if problem == "alone" else 2)
        state = await command(fleet, "fault", roverId=TARGET, fault="wheel_jam")
        position = rover(state)["position"]
        for _ in range(30):
            target = rover(state)
            assert target["fault"] == "wheel_jam" and target["status"] == "halted"
            assert target["position"] == position
            assert target["recovery"]["helperId"] is None and target["recovery"]["progress"] == 0
            assert target["recovery"]["phase"] not in ("repairing", "validating", "recovered")
            state = await command(fleet, "step")
    asyncio.run(scenario())


def test_faulty_helper_cannot_finish_interrupted_repair(terrain, feed):
    async def scenario():
        fleet = await ready(terrain, feed)
        await command(fleet, "fault", roverId=TARGET, fault="wheel_slip")
        state = await until(fleet, lambda s: 0 < rover(s)["recovery"]["progress"] < 1)
        helper_id = rover(state)["recovery"]["helperId"]
        state = await command(fleet, "fault", roverId=helper_id, fault="sensor_drop")
        for _ in range(35):
            target, helper = rover(state), rover(state, helper_id)
            assert target["status"] == "halted" and target["fault"] == "wheel_slip"
            assert target["recovery"]["phase"] not in ("validating", "recovered")
            assert target["recovery"]["progress"] < 1
            assert helper["status"] == "halted" and helper["targetId"] is None
            state = await command(fleet, "step")
    asyncio.run(scenario())


def test_helpers_are_nominal_and_uniquely_assigned_per_target(terrain, feed):
    async def scenario():
        fleet = await ready(terrain, feed, count=4)
        await command(fleet, "fault", roverId=TARGET, fault="dust")
        state = await command(fleet, "fault", roverId="fleet-rover-02", fault="wheel_jam")
        seen = set()
        for _ in range(40):
            assignments = [r for r in state["rovers"] if r["targetId"]]
            targets = [r["targetId"] for r in assignments]
            assert len(targets) == len(set(targets))
            for helper in assignments:
                assert helper["fault"] == "nominal" and helper["guardian"]["riskLevel"] == "nominal"
                assert helper["carrierId"] != helper["targetId"]
                target = rover(state, helper["targetId"])
                assert target["recovery"]["helperId"] == helper["carrierId"]
                seen.add(helper["targetId"])
            state = await command(fleet, "step")
        assert seen == {TARGET, "fleet-rover-02"}
    asyncio.run(scenario())


def test_pause_freezes_repair_and_resume_preserves_progress(terrain, feed):
    async def scenario():
        now = [1_800_000_000.0]
        fleet = await ready(terrain, feed)
        fleet.clock = lambda: now[0]
        await command(fleet, "fault", roverId=TARGET, fault="dust")
        await until(fleet, lambda s: 0 < rover(s)["recovery"]["progress"] < 1)
        state = await command(fleet, "start")
        assert state["running"]
        paused = await command(fleet, "stop")
        before = deepcopy(paused)
        now[0] += 86_400
        for _ in range(5):
            await asyncio.sleep(0)  # Drain ready tasks without introducing timed sleeps.
        assert fleet.state() == before and not paused["running"]
        try:
            resumed = await command(fleet, "start")
            assert rover(resumed)["recovery"]["progress"] > rover(paused)["recovery"]["progress"]
        finally:
            await fleet.stop()
    asyncio.run(scenario())


def test_explicit_operator_clearance_still_waits_for_nominal_guardian(terrain, feed):
    async def scenario():
        fleet = await ready(terrain, feed, count=1)
        await command(fleet, "fault", roverId=TARGET, fault="sensor_drop")
        feed.block_nominal.add(TARGET)
        state = await command(fleet, "fault", roverId=TARGET, fault="nominal")
        assert rover(state)["fault"] == "nominal" and rover(state)["status"] == "halted"
        for _ in range(4):
            state = await command(fleet, "step")
            assert rover(state)["status"] == "halted"
        feed.block_nominal.remove(TARGET)
        state = await until(fleet, lambda s: rover(s)["status"] in ("surveying", "waiting"), limit=5)
        assert rover(state)["guardian"]["riskLevel"] == "nominal"
    asyncio.run(scenario())


@pytest.fixture
def api(terrain, tmp_path):
    cfg = lab.Settings(producer_token="recovery-test-producer", viewer_token="recovery-test-viewer",
                       db=tmp_path / "recovery.sqlite3", mesh_dir=tmp_path / "meshes",
                       log_dir=tmp_path / "logs", min_history_interval=0)
    now = [1_800_000_000.0]
    factory = lambda *a, **kw: FleetSimManager(*a, **kw, terrain_path=terrain)
    with patch.object(lab, "FleetSimManager", side_effect=factory):
        application = lab.create_app(cfg, clock=lambda: now[0])
    with TestClient(application) as client:
        yield client, application, now


def api_command(api, action, **kwargs):
    client, application, now = api
    now[0] += 1
    response = client.post(URL, headers=P, json={"action": action, **kwargs})
    assert response.status_code == 200, response.text
    return response.json()["fleetState"]


def pending(api):
    api_command(api, "reset", count=2, speedMultiplier=30)
    for _ in range(5):
        api_command(api, "step")
    state = api_command(api, "fault", roverId=TARGET, fault="sensor_drop")
    for _ in range(6):
        if rover(state)["recovery"]["phase"] == "awaiting_approval":
            return state
        state = api_command(api, "step")
    pytest.fail("Actual Guardian did not raise a serious recovery request")


def assert_api_rejected_without_mutation(api, payload, status=422, headers=P):
    client, application, now = api
    before = client.get(URL, headers=V).json()
    history = application.state.store.stats()["frameCount"]
    ingested = application.state.live.ingest
    response = client.post(URL, headers=headers, json=payload)
    assert response.status_code == status, response.text
    assert client.get(URL, headers=V).json() == before
    assert application.state.store.stats()["frameCount"] == history
    assert application.state.live.ingest == ingested


@pytest.mark.parametrize("bad", [None, 0, 1, "false", [], {}])
def test_api_auto_repair_requires_actual_boolean_without_mutation(api, bad):
    assert_api_rejected_without_mutation(api, {"action": "configure", "autoRepair": bad})


@pytest.mark.parametrize("action", ["configure", "approve_recovery", "hold_recovery"])
def test_new_mutations_require_producer_role(api, action):
    state = pending(api)
    payload = ({"action": action, "autoRepair": False} if action == "configure" else
               {"action": action, "roverId": TARGET, "requestId": rover(state)["recovery"]["requestId"]})
    for headers in ({}, V, {"Authorization": "Bearer incorrect-test-token"}):
        assert_api_rejected_without_mutation(api, payload, status=401, headers=headers)


@pytest.mark.parametrize("action", ["approve_recovery", "hold_recovery"])
@pytest.mark.parametrize("defect", ["missing", "wrong", "boolean", "string", "unknown_rover", "no_pending", "extra"])
def test_api_invalid_recovery_request_is_atomic(api, action, defect):
    state = pending(api)
    payload = {"action": action, "roverId": TARGET, "requestId": rover(state)["recovery"]["requestId"]}
    if defect == "missing":
        del payload["requestId"]
    elif defect == "wrong":
        payload["requestId"] += 100
    elif defect == "boolean":
        payload["requestId"] = True
    elif defect == "string":
        payload["requestId"] = str(payload["requestId"])
    elif defect == "unknown_rover":
        payload["roverId"] = "not-a-fleet-rover"
    elif defect == "no_pending":
        payload["roverId"] = "fleet-rover-02"
    else:
        payload["speedMultiplier"] = 120
    assert_api_rejected_without_mutation(api, payload)


@pytest.mark.parametrize("action", ["approve_recovery", "hold_recovery"])
@pytest.mark.parametrize("replacement", ["reset", "new_fault", "cleared", "already_approved"])
def test_api_stale_recovery_requests_never_authorize_other_work(api, action, replacement):
    state = pending(api)
    old = rover(state)["recovery"]["requestId"]
    if replacement == "reset":
        api_command(api, "reset")
        state = api_command(api, "fault", roverId=TARGET, fault="sensor_drop")
        assert rover(state)["recovery"]["requestId"] != old
    elif replacement == "new_fault":
        state = api_command(api, "fault", roverId=TARGET, fault="hq_link_broken")
        assert rover(state)["recovery"]["requestId"] != old
    elif replacement == "cleared":
        api_command(api, "fault", roverId=TARGET, fault="nominal")
    else:
        api_command(api, "approve_recovery", roverId=TARGET, requestId=old)
    assert_api_rejected_without_mutation(api, {"action": action, "roverId": TARGET, "requestId": old})


@pytest.mark.parametrize("fault,approval", [("wheel_jam", False), ("sensor_drop", True),
                                            ("hq_link_broken", True)])
def test_new_faults_recover_through_real_guardian_ingest_and_api(api, fault, approval):
    api_command(api, "reset", count=2, speedMultiplier=30)
    for _ in range(5):
        api_command(api, "step")
    state = api_command(api, "fault", roverId=TARGET, fault=fault)
    for _ in range(6):
        # Policy halts immediately. The existing classifier has no isolated HQ-loss
        # class; do not invent an ML warning for a policy-detected link failure.
        if (rover(state)["status"] == "halted"
                and (fault == "hq_link_broken"
                     or rover(state)["guardian"]["riskLevel"] in ("warning", "critical"))):
            break
        state = api_command(api, "step")
    target = rover(state)
    assert target["status"] == "halted" and target["fault"] == fault
    if fault != "hq_link_broken":
        assert target["guardian"]["riskLevel"] in ("warning", "critical")
    else:
        assert api[1].state.live.frames[TARGET]["telemetry"]["linkOk"] is False
    assert target["recovery"]["requiresApproval"] is approval
    if approval:
        state = api_command(api, "approve_recovery", roverId=TARGET,
                            requestId=target["recovery"]["requestId"])
        assert rover(state)["fault"] == fault
    phases = set()
    for _ in range(MAX_TICKS):
        phases.add(rover(state)["recovery"]["phase"])
        if rover(state)["recovery"]["phase"] == "recovered":
            break
        state = api_command(api, "step")
    target = rover(state)
    assert {"repairing", "validating", "recovered"} <= phases
    assert target["fault"] == "nominal" and target["guardian"]["riskLevel"] == "nominal"
    assert target["status"] in ("surveying", "waiting")
    client, application, now = api
    assert application.state.live.ingest > 5
    assert application.state.store.stats()["frameCount"] > 5
    assert client.get(URL, headers=V).json() == state
    assert_recovery_contract(state)
