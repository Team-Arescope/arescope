"""Synthetic, accelerated fleet mission on an archived HiRISE terrain grid.

Guardian ML is supplied by the normal ingest callback. Deterministic mission
policies partition survey work, latch safety halts and plan assistance routes.
Minor repairs are timed synthetic procedures; serious recovery requires a
Mission Control decision. There is no LLM motor control or physical repair.
Mission state lives in this process; frames/incidents use ingest's normal store.
"""

import asyncio
from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field
import heapq
import json
import math
import time

from rover_sim import CAUSES, TERRAIN_PATH, grid_geometry

MAX_TRAIL = 128
MAX_EVENTS = 100
MAX_PATH_NODES = 16_384
DRIVE_SPEED_MPS = .8
MAX_HELPER_SLOPE = .65
MINOR_FAULTS = frozenset(("dust", "wheel_slip", "wheel_jam"))
FLEET_CAUSES = (*CAUSES, "wheel_jam", "hq_link_broken")
REPAIR_DURATION_S = 600.0
VALIDATION_STEPS = 3
# Fixed-size display vehicles use a bounded final service approach. This is a
# continuous interpolation of the archived height field, not new terrain detail.
SERVICE_MIN_M = 22.0
SERVICE_DISTANCE_M = 24.0
SERVICE_MAX_M = 26.0
SERVICE_FOOTPRINT_M = 12.0
APPROACH_SAMPLE_M = 4.0


@dataclass
class Recovery:
    phase: str = "none"
    progress: float = 0.0
    helper_id: str | None = None
    requires_approval: bool = False
    approved: bool = False
    held: bool = False
    request_id: int = 0
    elapsed: float = 0.0
    nominal_steps: int = 0

    def state(self):
        return {"phase": self.phase, "progress": self.progress, "helperId": self.helper_id,
                "requiresApproval": self.requires_approval, "approved": self.approved,
                "held": self.held, "requestId": self.request_id}


def distance(a, b):
    return math.hypot(a[0] - b[0], a[2] - b[2])


@dataclass
class FleetRover:
    carrier_id: str
    sector: str
    columns: tuple
    position: list
    survey: list
    cursor: int = 1
    heading: float = 90.0
    status: str = "surveying"
    fault: str = "nominal"
    guardian: dict | None = None
    clearance_requested: bool = False
    target_id: str | None = None
    inspection: deque = field(default_factory=deque)
    approach: deque = field(default_factory=deque)
    trail: deque = field(default_factory=lambda: deque(maxlen=MAX_TRAIL))
    recovery: Recovery = field(default_factory=Recovery)


class FleetSimManager:
    def __init__(self, ingest, interval=1.0, clock=time.time, terrain_path=TERRAIN_PATH, clear_windows=None):
        if (isinstance(interval, bool) or not isinstance(interval, (float, int))
                or not math.isfinite(interval) or interval < 1):
            raise ValueError("Fleet interval must be finite and at least one second")
        data = json.loads(terrain_path.read_text(encoding="utf-8"))
        source_rows, self.source_cols, self.spacing_east, self.spacing_south = grid_geometry(data)
        self.rows, self.cols = source_rows - 1, self.source_cols - 1
        self.points = data["points"]
        self.spacing = data["metadata"]["effective_spacing_m"]
        self.cell_area_m2 = self.spacing_east * self.spacing_south
        # Conservative physical clearance on either axis, expressed in metres.
        self.standoff_min_m = max(2 * max(self.spacing_east, self.spacing_south), SERVICE_DISTANCE_M * 1.5)
        self.standoff_max_m = max(3 * max(self.spacing_east, self.spacing_south), SERVICE_DISTANCE_M * 2)
        self.ingest, self.interval, self.clock = ingest, interval, clock
        self.clear_windows = clear_windows
        self.lock, self.control_lock = asyncio.Lock(), asyncio.Lock()
        self.task = None
        self.count, self.speed_multiplier = min(3, self.cols), 60.0
        self.elapsed = 0.0
        self.covered = set()
        self.events = deque(maxlen=MAX_EVENTS)
        self.event_id = 0
        self.has_frames = False
        self.unavailable = set()
        self.auto_repair = True
        self.recovery_id = 0
        self._reset(self.count)

    def _position(self, row, col):
        return self._surface(row + .5, col + .5)

    def _surface(self, row, col):
        row, col = max(0.0, min(self.rows, row)), max(0.0, min(self.cols, col))
        r, c = min(self.rows - 1, int(row)), min(self.cols - 1, int(col))
        fr, fc = row - r, col - c
        corners = [self.points[r * self.source_cols + c], self.points[r * self.source_cols + c + 1],
                   self.points[(r + 1) * self.source_cols + c], self.points[(r + 1) * self.source_cols + c + 1]]
        weights = [(1 - fr) * (1 - fc), (1 - fr) * fc, fr * (1 - fc), fr * fc]
        return [sum(p[i] * w for p, w in zip(corners, weights)) for i in range(3)]

    def _cell(self, position):
        return (max(0, min(self.rows - 1, int((position[2] - self.points[0][2]) / self.spacing_south))),
                max(0, min(self.cols - 1, int((position[0] - self.points[0][0]) / self.spacing_east))))

    def _reset(self, count):
        if self.clear_windows is not None:
            self.clear_windows([r.carrier_id for r in getattr(self, "rovers", [])])
        self.count, self.elapsed, self.has_frames = count, 0.0, False
        self.covered.clear()
        self.events.clear()
        self.unavailable.clear()
        self.rovers = []
        for index in range(count):
            first, end = index * self.cols // count, (index + 1) * self.cols // count
            survey = [(row, col) for lane, row in enumerate(range(0, self.rows, 3))
                      for col in (range(first, end) if lane % 2 == 0 else range(end - 1, first - 1, -1))]
            rover = FleetRover(f"fleet-rover-{index + 1:02d}", f"sector-{index + 1:02d} (columns {first}..{end - 1})",
                               (first, end), self._position(*survey[0]), survey)
            rover.trail.append(rover.position[:])
            self.rovers.append(rover)
        self._event("reset", None, None,
                    f"Synthetic accelerated survey of the archived {self.rows * self.cols * self.cell_area_m2 / 1e6:.2f} km² HiRISE tile. "
                    "Guardian ML detects risk; explicit mission policies control survey and inspection. "
                    "Minor repairs are simulated; serious recovery requires Mission Control approval. No LLM motor control.")

    def _event(self, kind, rover, target, message):
        self.event_id += 1
        self.events.append({"id": self.event_id, "ts": self.clock(), "type": kind,
                            "roverId": rover, "targetId": target, "message": message})

    def state(self):
        total = self.rows * self.cols
        return {"running": self.task is not None and not self.task.done(), "count": self.count,
                "speedMultiplier": self.speed_multiplier, "elapsedS": self.elapsed, "autoRepair": self.auto_repair,
                "terrainSource": "nasa-pds-hirise", "simulation": True,
                "synthetic": True, "acceleratedTime": True,
                "timeBasis": "elapsedS is simulated seconds; speedMultiplier accelerates mission time",
                "serviceZone": {"minimumM": SERVICE_MIN_M, "distanceM": SERVICE_DISTANCE_M, "maximumM": SERVICE_MAX_M},
                "coverage": {"scannedCells": len(self.covered), "totalCells": total,
                             "percent": 100 * len(self.covered) / total,
                             "areaM2": len(self.covered) * self.cell_area_m2,
                             "totalAreaM2": total * self.cell_area_m2,
                             "cells": [list(cell) for cell in sorted(self.covered)]},
                "rovers": [{"carrierId": r.carrier_id, "position": r.position[:], "headingDeg": r.heading,
                            "status": r.status, "fault": r.fault, "guardian": deepcopy(r.guardian),
                            "targetId": r.target_id, "assignedSector": r.sector, "recovery": r.recovery.state(),
                            "trail": [p[:] for p in r.trail]} for r in self.rovers],
                "events": [e.copy() for e in self.events]}

    def _validate(self, data):
        if not isinstance(data, dict) or set(data) - {"action", "count", "speedMultiplier", "roverId", "fault", "autoRepair", "requestId"}:
            raise ValueError("Unknown fleet command fields")
        action = data.get("action")
        if not isinstance(action, str) or action not in ("start", "stop", "step", "reset", "fault", "configure", "approve_recovery", "hold_recovery"):
            raise ValueError("Unknown fleet action")
        if "autoRepair" in data and (type(data["autoRepair"]) is not bool or action not in ("configure", "start", "reset", "step")):
            raise ValueError("autoRepair must be a boolean on configure, start, reset or step")
        if action == "configure" and set(data) != {"action", "autoRepair"}:
            raise ValueError("configure requires only autoRepair")
        count, speed = data.get("count", self.count), data.get("speedMultiplier", self.speed_multiplier)
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 6:
            raise ValueError("count must be an integer from 1 to 6")
        if count > self.cols:
            raise ValueError("count cannot exceed the number of terrain cell columns")
        if (isinstance(speed, bool) or not isinstance(speed, (int, float))
                or not 1 <= speed <= 120 or not math.isfinite(speed)):
            raise ValueError("speedMultiplier must be finite and between 1 and 120")
        if count != self.count and (action not in ("reset", "start", "step") or (self.has_frames and action != "reset")):
            raise ValueError("Changing count after mission activity requires reset")
        if action == "fault":
            if (not isinstance(data.get("roverId"), str)
                    or data["roverId"] not in {r.carrier_id for r in self.rovers}
                    or not isinstance(data.get("fault"), str) or data["fault"] not in FLEET_CAUSES):
                raise ValueError("fault requires a known roverId and supported fleet fault")
            if "requestId" in data:
                raise ValueError("requestId is only valid for a recovery decision")
        elif action in ("approve_recovery", "hold_recovery"):
            if set(data) != {"action", "roverId", "requestId"}:
                raise ValueError("Recovery decision requires roverId and requestId only")
            rover = next((r for r in self.rovers if r.carrier_id == data.get("roverId")), None)
            request_id = data.get("requestId")
            if (type(request_id) is not int or rover is None or request_id <= 0
                    or rover.recovery.request_id != request_id or rover.status != "halted"
                    or rover.recovery.phase != "awaiting_approval" or not rover.recovery.requires_approval
                    or rover.recovery.approved):
                raise ValueError("No matching pending Mission Control recovery request")
        elif "roverId" in data or "fault" in data:
            raise ValueError("roverId and fault are only valid for the fault action")
        elif "requestId" in data:
            raise ValueError("requestId is only valid for a recovery decision")
        return action, count, float(speed)

    def _telemetry(self, rover):
        row, col = self._cell(rover.position)
        neighbor = self._position(row, min(self.cols - 1, col + 1))
        separation = distance(neighbor, rover.position)
        slip = .035 + .035 * min(1.0, abs(neighbor[1] - rover.position[1]) / separation) if separation else .035
        count, fps, contrast, jump, link = 1200, 29.0, .58, .012, True
        if rover.fault == "dust":
            count, fps, contrast = 72, 13.0, .035
        elif rover.fault == "low_texture":
            count, contrast, jump = 60, .37, .232
        elif rover.fault == "glare":
            count, contrast, jump = 240, 1.0, .362
        elif rover.fault in ("wheel_slip", "wheel_jam"):
            slip = .98
        elif rover.fault == "sensor_drop":
            count, fps, jump, link = 12, .58, .912, False
        elif rover.fault == "hq_link_broken":
            link = False
        commanded = DRIVE_SPEED_MPS if rover.status in ("surveying", "responding", "approaching") else 0.0
        return {"pointCount": count, "fps": fps, "poseJumpM": jump, "lumaContrast": contrast,
                "commandedSpeedMps": commanded, "observedSpeedMps": commanded * (1 - slip),
                "slipRatio": slip, "linkOk": link, "position": rover.position[:],
                "simulation": 1, "elapsedS": self.elapsed, "speedMultiplier": self.speed_multiplier}

    async def _observe(self, rover):
        row, col = self._cell(rover.position)
        telemetry = self._telemetry(rover)
        # Real archived samples, with a synthetic sensor return rate; no invented detail.
        patch = [self.points[r * self.source_cols + c][:]
                 for r in range(max(0, row - 3), min(self.rows + 1, row + 4))
                 for c in range(max(0, col - 3), min(self.source_cols, col + 4))]
        keep = round(len(patch) * telemetry["pointCount"] / 1200)
        frame = await self.ingest({"source": "simulated-rover", "room": "gale-fleet-sim",
                                   "carrierId": rover.carrier_id, "carrierType": "rover",
                                   "yawDeg": rover.heading, "points": patch[:keep], "telemetry": telemetry})
        self.has_frames = True
        rover.guardian = deepcopy(frame["guardian"])
        if rover.clearance_requested:
            rover.recovery.nominal_steps = rover.recovery.nominal_steps + 1 if rover.guardian["riskLevel"] == "nominal" else 0
            if rover.recovery.nominal_steps >= VALIDATION_STEPS:
                rover.clearance_requested = False
                rover.status = "surveying"
                rover.recovery.phase, rover.recovery.progress = "recovered", 1.0
                self._event("guardian_clearance", rover.carrier_id, None,
                            "Three consecutive nominal Guardian observations confirm recovery; survey may resume.")
        if (rover.guardian["riskLevel"] in ("warning", "critical") or rover.fault != "nominal") and rover.status != "halted":
            previous_target = rover.target_id
            self._release_helper(rover)
            rover.status, rover.target_id = "halted", None
            rover.inspection.clear()
            rover.approach.clear()
            if rover.recovery.phase in ("none", "recovered"):
                self._new_recovery(rover)
            detected = rover.guardian["riskLevel"] in ("warning", "critical")
            reason = (f"Guardian {rover.guardian['riskLevel']}: {rover.guardian['predictedCause']} "
                      f"(risk {rover.guardian['riskScore']:.2f}). " if detected else
                      f"Operator-injected synthetic fault {rover.fault}; classifier has not raised an alert yet. ")
            self._event("guardian_halt" if detected else "safety_halt", rover.carrier_id, previous_target,
                        reason + "Policy latched a safety halt; "
                        "minor faults may use simulated helper recovery; serious faults require Mission Control approval.")

    def _new_recovery(self, rover):
        self.recovery_id += 1
        serious = rover.fault not in MINOR_FAULTS
        rover.recovery = Recovery(phase="awaiting_approval" if serious else "waiting_helper",
                                  requires_approval=serious, request_id=self.recovery_id)
        if serious:
            self._event("mission_control_requested", rover.carrier_id, None,
                        f"Mission Control decision required for {rover.fault}; automatic recovery is blocked. "
                        "A nearby rover may inspect, but recovery needs an explicit approval.")

    def _release_helper(self, helper):
        if helper.target_id is None:
            return
        target = next((r for r in self.rovers if r.carrier_id == helper.target_id), None)
        helper.target_id = None
        helper.inspection.clear()
        helper.approach.clear()
        if helper.status in ("responding", "approaching", "assisting", "repairing"):
            helper.status = "surveying" if helper.fault == "nominal" else "halted"
        if target and target.recovery.helper_id == helper.carrier_id:
            target.recovery.helper_id = None
            if target.recovery.phase not in ("recovered", "validating"):
                target.recovery.elapsed, target.recovery.progress = 0.0, 0.0
                target.recovery.phase = ("awaiting_approval" if target.recovery.requires_approval and not target.recovery.approved
                                         else "waiting_helper")

    def _repair_permitted(self, target):
        return target.recovery.approved if target.recovery.requires_approval else self.auto_repair

    def _service_segment(self, a, b, helper, target):
        """Validate the swept final approach against footprint, slopes and rovers."""
        obstacles = [r for r in self.rovers if r is not helper]
        # Apply a physical display-footprint exclusion, rather than the coarse
        # inspection disc, only on this explicitly authorized service approach.
        dx, dz = b[0] - a[0], b[2] - a[2]
        norm = dx * dx + dz * dz
        for other in obstacles:
            obstacle = other.position
            t = max(0.0, min(1.0, ((obstacle[0] - a[0]) * dx + (obstacle[2] - a[2]) * dz) / norm)) if norm else 0.0
            clearance = SERVICE_MIN_M if other is target else 2 * SERVICE_FOOTPRINT_M
            if math.hypot(a[0] + t * dx - obstacle[0], a[2] + t * dz - obstacle[2]) + 1e-7 < clearance:
                return False
        samples = max(1, math.ceil(distance(a, b) / APPROACH_SAMPLE_M))
        previous = a
        first, last = self.points[0], self.points[-1]
        for index in range(1, samples + 1):
            f = index / samples
            x, z = a[0] + dx * f, a[2] + dz * f
            if not (first[0] + SERVICE_FOOTPRINT_M <= x <= last[0] - SERVICE_FOOTPRINT_M
                    and first[2] + SERVICE_FOOTPRINT_M <= z <= last[2] - SERVICE_FOOTPRINT_M):
                return False
            point = self._surface((z - first[2]) / self.spacing_south, (x - first[0]) / self.spacing_east)
            length = distance(previous, point)
            if length and abs(point[1] - previous[1]) / length > MAX_HELPER_SLOPE:
                return False
            previous = point
        return True

    def _service_path(self, helper, target):
        bearing = math.atan2(helper.position[0] - target.position[0], helper.position[2] - target.position[2])
        for offset in (0, .392699, -.392699, .785398, -.785398, 1.178097, -1.178097, 1.570796, -1.570796):
            angle = bearing + offset
            x = target.position[0] + math.sin(angle) * SERVICE_DISTANCE_M
            z = target.position[2] + math.cos(angle) * SERVICE_DISTANCE_M
            goal = self._surface((z - self.points[0][2]) / self.spacing_south,
                                 (x - self.points[0][0]) / self.spacing_east)
            if (not SERVICE_MIN_M <= distance(goal, target.position) <= SERVICE_MAX_M
                    or abs(goal[1] - target.position[1]) > 8 or not self._service_segment(helper.position, goal, helper, target)):
                continue
            count = max(1, math.ceil(distance(helper.position, goal) / APPROACH_SAMPLE_M))
            return [self._surface((helper.position[2] + (goal[2] - helper.position[2]) * i / count - self.points[0][2]) / self.spacing_south,
                                  (helper.position[0] + (goal[0] - helper.position[0]) * i / count - self.points[0][0]) / self.spacing_east)
                    for i in range(1, count + 1)]
        return None

    def _advance_repairs(self, dt):
        by_id = {r.carrier_id: r for r in self.rovers}
        for helper in self.rovers:
            target = by_id.get(helper.target_id)
            if target is None or helper.status not in ("approaching", "assisting", "repairing"):
                continue
            recovery = target.recovery
            healthy = helper.fault == "nominal" and helper.guardian and helper.guardian["riskLevel"] == "nominal"
            near = SERVICE_MIN_M - 1e-7 <= distance(helper.position, target.position) <= SERVICE_MAX_M + 1e-7
            if not healthy or target.status != "halted":
                self._release_helper(helper)
                continue
            if recovery.phase in ("validating", "recovered") or not self._repair_permitted(target):
                if helper.status in ("repairing", "approaching"):
                    helper.status = "assisting"
                    helper.approach.clear()
                    recovery.elapsed, recovery.progress = 0.0, 0.0
                    recovery.phase = "awaiting_approval" if recovery.requires_approval and not recovery.approved else "waiting_helper"
                    self._event("repair_cancelled", helper.carrier_id, target.carrier_id,
                                "Recovery authorization removed; simulated procedure cancelled, fault and safety halt retained.")
                continue
            if helper.status == "approaching":
                continue
            if near and (not self._service_segment(helper.position, helper.position, helper, target)
                         or abs(helper.position[1] - target.position[1]) > 8):
                helper.status, recovery.phase = "assisting", "failed"
                recovery.elapsed, recovery.progress = 0.0, 0.0
                continue
            if not near:
                path = self._service_path(helper, target)
                if path is None:
                    if recovery.phase != "failed":
                        self._event("service_approach_blocked", helper.carrier_id, target.carrier_id,
                                    "No safe close approach: slope, boundary or vehicle clearance blocks service. Target remains halted.")
                    recovery.phase, recovery.progress, recovery.elapsed = "failed", 0.0, 0.0
                    continue
                helper.approach = deque(path)
                helper.status, recovery.phase = "approaching", "approaching"
                self._event("service_approach", helper.carrier_id, target.carrier_id,
                            f"Authorized final approach to {SERVICE_DISTANCE_M:.0f} m centre separation on the interpolated archive surface.")
                continue
            if helper.status != "repairing":
                helper.heading = math.degrees(math.atan2(target.position[0] - helper.position[0],
                                                        target.position[2] - helper.position[2])) % 360
                helper.status = "repairing"
                recovery.phase, recovery.elapsed, recovery.progress = "repairing", 0.0, 0.0
                self._event("repair_started", helper.carrier_id, target.carrier_id,
                            "Starting a timed synthetic service procedure after a checked close approach. "
                            "This is a simulation, not physical contact or a verified hardware repair.")
                continue
            recovery.elapsed = min(REPAIR_DURATION_S, recovery.elapsed + dt)
            recovery.progress = recovery.elapsed / REPAIR_DURATION_S
            if recovery.elapsed >= REPAIR_DURATION_S:
                target.fault, target.clearance_requested = "nominal", True
                recovery.phase, recovery.nominal_steps = "validating", 0
                helper.status = "assisting"
                self._event("repair_completed", helper.carrier_id, target.carrier_id,
                            "Synthetic service finished. Target stays halted until three fresh nominal Guardian observations confirm recovery.")

    def _scan(self, rover):
        row, col = self._cell(rover.position)
        # Synthetic three-cell swath at the source spacing, clipped to the sector.
        self.covered.update((r, c) for r in range(max(0, row - 1), min(self.rows, row + 2))
                            for c in range(max(rover.columns[0], col - 1), min(rover.columns[1], col + 2)))

    def _move(self, rover, dt):
        if rover.status not in ("surveying", "responding", "approaching"):
            return
        surveying = rover.status == "surveying"
        approaching = rover.status == "approaching"
        budget = DRIVE_SPEED_MPS * dt * (1 - self._telemetry(rover)["slipRatio"])
        if surveying:
            self._scan(rover)
        while budget > 1e-8:
            if surveying:
                if rover.cursor >= len(rover.survey):
                    rover.status = "waiting"
                    self._event("sector_complete", rover.carrier_id, None, "Assigned survey sector complete.")
                    break
                destination = self._position(*rover.survey[rover.cursor])
            elif approaching:
                target = next((r for r in self.rovers if r.carrier_id == rover.target_id), None)
                if target is None or target.status != "halted" or not self._repair_permitted(target):
                    rover.status = "assisting"
                    rover.approach.clear()
                    break
                if not rover.approach:
                    rover.status = "assisting"
                    rover.heading = math.degrees(math.atan2(target.position[0] - rover.position[0],
                                                           target.position[2] - rover.position[2])) % 360
                    self._event("service_arrived", rover.carrier_id, rover.target_id,
                                "Close approach complete; both vehicles remain stationary during service.")
                    break
                destination = rover.approach[0]
                if not self._service_segment(rover.position, destination, rover, target):
                    rover.status = "assisting"
                    rover.approach.clear()
                    target.recovery.phase = "failed"
                    self._event("service_approach_blocked", rover.carrier_id, rover.target_id,
                                "A new obstacle blocks the close approach. Stop; service remains incomplete.")
                    break
            else:
                if not rover.inspection:
                    rover.status = "assisting"
                    self._event("inspection_arrived", rover.carrier_id, rover.target_id,
                                "Reached the safe coarse-grid assistance zone. Target remains halted; recovery policy checks authorization.")
                    break
                destination = self._position(*rover.inspection[0])
                obstacles = [r.position for r in self.rovers if r.status == "halted"]
                if not self._safe_segment(rover.position, destination, obstacles):
                    target_id = rover.target_id
                    self._release_helper(rover)
                    rover.status = "waiting"
                    self._event("inspection_route_blocked", rover.carrier_id, target_id,
                                "New safety exclusion blocks inspection route; stop and replan before moving.")
                    break
            length = distance(rover.position, destination)
            if length > 1e-8:
                fraction = min(1.0, budget / length)
                dx, dz = destination[0] - rover.position[0], destination[2] - rover.position[2]
                rover.heading = math.degrees(math.atan2(dx, dz)) % 360
                x, z = rover.position[0] + fraction * dx, rover.position[2] + fraction * dz
                rover.position = self._surface((z - self.points[0][2]) / self.spacing_south,
                                               (x - self.points[0][0]) / self.spacing_east)
                budget -= min(budget, length)
                rover.trail.append(rover.position[:])
                if surveying:
                    self._scan(rover)
                if fraction < 1:
                    break
            if surveying:
                rover.cursor += 1
            elif approaching:
                rover.approach.popleft()
            else:
                rover.inspection.popleft()

    def _safe_segment(self, a, b, obstacles):
        dx, dz = b[0] - a[0], b[2] - a[2]
        norm = dx * dx + dz * dz
        for target in obstacles:
            t = max(0.0, min(1.0, ((target[0] - a[0]) * dx + (target[2] - a[2]) * dz) / norm)) if norm else 0.0
            # Bilinear resampling can shift a grid coordinate by a few ulps.
            if math.hypot(a[0] + t * dx - target[0], a[2] + t * dz - target[2]) + 1e-7 < self.standoff_min_m:
                return False
        return True

    def _inspection_path(self, helper, target):
        """Bounded four-neighbor A*, respecting slopes and a two-cell exclusion disc."""
        obstacles = [r.position for r in self.rovers if r.status == "halted"]
        start = self._cell(helper.position)
        start_position = self._position(*start)
        if not self._safe_segment(helper.position, start_position, obstacles):
            return None
        start_distance = distance(helper.position, start_position)
        if start_distance and abs(helper.position[1] - start_position[1]) / start_distance > MAX_HELPER_SLOPE:
            return None
        heuristic = lambda p: max(0.0, distance(p, target.position) - self.standoff_max_m)
        frontier = [(heuristic(start_position), 0.0, start)]
        costs, parents, closed = {start: 0.0}, {}, set()
        while frontier and len(closed) < MAX_PATH_NODES:
            _, cost, cell = heapq.heappop(frontier)
            if cell in closed:
                continue
            closed.add(cell)
            position = self._position(*cell)
            if self.standoff_min_m <= distance(position, target.position) <= self.standoff_max_m:
                path = [cell]
                while cell in parents:
                    cell = parents[cell]
                    path.append(cell)
                return list(reversed(path))
            row, col = cell
            for neighbor in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
                if not (0 <= neighbor[0] < self.rows and 0 <= neighbor[1] < self.cols) or neighbor in closed:
                    continue
                other = self._position(*neighbor)
                length = distance(position, other)
                slope = abs(other[1] - position[1]) / length
                if slope > MAX_HELPER_SLOPE or not self._safe_segment(position, other, obstacles):
                    continue
                candidate = cost + length * (1 + slope)
                if candidate < costs.get(neighbor, math.inf):
                    costs[neighbor], parents[neighbor] = candidate, cell
                    heapq.heappush(frontier, (candidate + heuristic(other), candidate, neighbor))
        return None

    def _assign_helpers(self):
        by_id = {r.carrier_id: r for r in self.rovers}
        for helper in self.rovers:
            if helper.target_id:
                target = by_id.get(helper.target_id)
                if (target is None or target.status != "halted" or helper.fault != "nominal"
                        or helper.status not in ("responding", "approaching", "assisting", "repairing")
                        or not helper.guardian or helper.guardian["riskLevel"] != "nominal"):
                    self._release_helper(helper)
        assigned = {r.target_id for r in self.rovers if r.target_id}
        for target in self.rovers:
            if target.status != "halted" or target.carrier_id in assigned:
                continue
            if target.recovery.phase == "validating":
                continue
            if target.recovery.phase == "none":
                self._new_recovery(target)
            candidates = sorted((r for r in self.rovers if r.status in ("surveying", "waiting")
                                 and r.fault == "nominal" and r.guardian is not None
                                 and r.guardian["riskLevel"] == "nominal"),
                                key=lambda r: (distance(r.position, target.position), r.carrier_id))
            for helper in candidates:
                path = self._inspection_path(helper, target)
                if path is None:
                    continue
                helper.status, helper.target_id = "responding", target.carrier_id
                helper.inspection = deque(path)
                target.recovery.helper_id = helper.carrier_id
                if target.recovery.phase != "awaiting_approval":
                    target.recovery.phase = "en_route"
                assigned.add(target.carrier_id)
                self.unavailable.discard(target.carrier_id)
                self._event("helper_assigned", helper.carrier_id, target.carrier_id,
                            f"Mission policy selected nearest available healthy rover with a safe bounded A* route "
                            f"({distance(helper.position, target.position):.1f} m away). "
                            f"Assistance zone {self.standoff_min_m:.1f}–{self.standoff_max_m:.1f} m; "
                            "minor simulated recovery follows the mode setting; serious recovery needs Mission Control approval.")
                break
            else:
                if target.carrier_id not in self.unavailable:
                    self.unavailable.add(target.carrier_id)
                    self._event("assistance_unavailable", target.carrier_id, None,
                                "No available healthy rover with a safe inspection route; safety halt remains latched.")

    async def _step(self):
        self.elapsed += self.interval * self.speed_multiplier
        self._assign_helpers()
        self._advance_repairs(self.interval * self.speed_multiplier)
        for rover in self.rovers:
            self._move(rover, self.interval * self.speed_multiplier)
            await self._observe(rover)
        self._assign_helpers()

    async def step(self):
        async with self.lock:
            await self._step()

    async def _run(self):
        try:
            while True:
                await asyncio.sleep(self.interval)
                await self.step()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._event("simulation_error", None, None, f"Fleet loop stopped: {type(exc).__name__}.")

    async def _stop_task(self):
        if self.task is not None:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None

    async def stop(self):
        async with self.control_lock:
            await self._stop_task()

    async def control(self, data):
        async with self.control_lock:
            # Validate everything, including current mission constraints, before mutation.
            action, count, speed = self._validate(data)
            if action in ("stop", "reset"):
                await self._stop_task()
            async with self.lock:
                # The tick may have completed while this command awaited the lock.
                # Recheck request identity before applying an operator decision.
                action, count, speed = self._validate(data)
                self.speed_multiplier = speed
                if "autoRepair" in data:
                    self.auto_repair = data["autoRepair"]
                if action == "reset" or count != self.count:
                    self._reset(count)
                if action == "fault":
                    rover = next(r for r in self.rovers if r.carrier_id == data["roverId"])
                    self._release_helper(rover)
                    for helper in self.rovers:
                        if helper.target_id == rover.carrier_id:
                            self._release_helper(helper)
                    rover.fault = data["fault"]
                    rover.clearance_requested = rover.fault == "nominal"
                    self._event("fault_injected", rover.carrier_id, None,
                                f"Operator set synthetic fault: {rover.fault}. Guardian inference uses normal ingest.")
                    if rover.fault == "nominal":
                        rover.status, rover.target_id = "halted", None
                        rover.inspection.clear()
                        self.unavailable.discard(rover.carrier_id)
                        self.recovery_id += 1
                        rover.recovery = Recovery(phase="validating", progress=1.0, request_id=self.recovery_id)
                        self._event("operator_clearance", rover.carrier_id, None,
                                    "Operator explicitly cleared fault; Guardian must confirm nominal telemetry before resuming.")
                    else:
                        self._new_recovery(rover)
                    await self._observe(rover)
                    self._assign_helpers()
                elif action in ("approve_recovery", "hold_recovery"):
                    rover = next(r for r in self.rovers if r.carrier_id == data["roverId"])
                    approved = action == "approve_recovery"
                    rover.recovery.approved, rover.recovery.held = approved, not approved
                    if approved:
                        rover.recovery.phase = "en_route" if rover.recovery.helper_id else "waiting_helper"
                    self._event("mission_control_approved" if approved else "mission_control_held", rover.carrier_id, None,
                                "Mission Control approved a simulated recovery attempt; halt remains until procedure and validation finish."
                                if approved else "Mission Control keeps the rover halted; no recovery attempt is authorized.")
                    self._assign_helpers()
                    self._advance_repairs(0)
                elif action == "configure":
                    self._event("recovery_mode", None, None,
                                f"Automatic minor-fault recovery {'enabled' if self.auto_repair else 'disabled'}. Serious faults always require approval.")
                    self._advance_repairs(0)
                elif action == "step":
                    await self._step()
                elif action == "start" and (self.task is None or self.task.done()):
                    await self._step()
                    self.task = asyncio.create_task(self._run())
                    self._event("started", None, None, "Fleet started; at most six synthetic frames per one-second mission tick.")
                elif action == "stop":
                    self._event("stopped", None, None, "Fleet paused; coverage, faults and assignments retained.")
                return {"ok": True, "fleetState": self.state()}
