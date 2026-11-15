"""Synthetic, accelerated fleet mission on the archived ~1 km² HiRISE tile.

Guardian ML is supplied by the normal ingest callback. Deterministic mission
policies partition survey work, latch safety halts and plan inspection routes;
there is no LLM motor control and inspection never repairs another rover.
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

from rover_sim import CAUSES, TERRAIN_PATH

MAX_TRAIL = 128
MAX_EVENTS = 100
MAX_PATH_NODES = 16_384
DRIVE_SPEED_MPS = .8
MAX_HELPER_SLOPE = .65


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
    trail: deque = field(default_factory=lambda: deque(maxlen=MAX_TRAIL))


class FleetSimManager:
    def __init__(self, ingest, interval=1.0, clock=time.time, terrain_path=TERRAIN_PATH, clear_windows=None):
        if (isinstance(interval, bool) or not isinstance(interval, (float, int))
                or not math.isfinite(interval) or interval < 1):
            raise ValueError("Fleet interval must be finite and at least one second")
        data = json.loads(terrain_path.read_text(encoding="utf-8"))
        self.rows, self.cols = data["grid"]["rows"] - 1, data["grid"]["cols"] - 1
        self.points = data["points"]
        self.spacing = data["metadata"]["effective_spacing_m"]
        if (self.rows != 128 or self.cols != 128 or len(self.points) != 129 * 129
                or not math.isfinite(self.spacing) or self.spacing <= 0
                or any(len(p) != 3 or any(not math.isfinite(v) for v in p) for p in self.points)):
            raise ValueError("Expected the existing finite 129 by 129 HiRISE grid")
        self.ingest, self.interval, self.clock = ingest, interval, clock
        self.clear_windows = clear_windows
        self.lock, self.control_lock = asyncio.Lock(), asyncio.Lock()
        self.task = None
        self.count, self.speed_multiplier = 3, 60.0
        self.elapsed = 0.0
        self.covered = set()
        self.events = deque(maxlen=MAX_EVENTS)
        self.event_id = 0
        self.has_frames = False
        self.unavailable = set()
        self._reset(self.count)

    def _position(self, row, col):
        return self._surface(row + .5, col + .5)

    def _surface(self, row, col):
        row, col = max(0.0, min(self.rows, row)), max(0.0, min(self.cols, col))
        r, c = min(self.rows - 1, int(row)), min(self.cols - 1, int(col))
        fr, fc = row - r, col - c
        corners = [self.points[r * 129 + c], self.points[r * 129 + c + 1],
                   self.points[(r + 1) * 129 + c], self.points[(r + 1) * 129 + c + 1]]
        weights = [(1 - fr) * (1 - fc), (1 - fr) * fc, fr * (1 - fc), fr * fc]
        return [sum(p[i] * w for p, w in zip(corners, weights)) for i in range(3)]

    def _cell(self, position):
        return (max(0, min(self.rows - 1, int((position[2] - self.points[0][2]) / self.spacing))),
                max(0, min(self.cols - 1, int((position[0] - self.points[0][0]) / self.spacing))))

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
                    "Synthetic accelerated survey of the archived ~1.07 km² HiRISE tile. "
                    "Guardian ML detects risk; explicit mission policies control survey and inspection. "
                    "No LLM motor control; assistance does not repair faults.")

    def _event(self, kind, rover, target, message):
        self.event_id += 1
        self.events.append({"id": self.event_id, "ts": self.clock(), "type": kind,
                            "roverId": rover, "targetId": target, "message": message})

    def state(self):
        total = self.rows * self.cols
        return {"running": self.task is not None and not self.task.done(), "count": self.count,
                "speedMultiplier": self.speed_multiplier, "elapsedS": self.elapsed,
                "terrainSource": "nasa-pds-hirise", "simulation": True,
                "synthetic": True, "acceleratedTime": True,
                "timeBasis": "elapsedS is simulated seconds; speedMultiplier accelerates mission time",
                "coverage": {"scannedCells": len(self.covered), "totalCells": total,
                             "percent": 100 * len(self.covered) / total,
                             "areaM2": len(self.covered) * self.spacing ** 2,
                             "totalAreaM2": total * self.spacing ** 2,
                             "cells": [list(cell) for cell in sorted(self.covered)]},
                "rovers": [{"carrierId": r.carrier_id, "position": r.position[:], "headingDeg": r.heading,
                            "status": r.status, "fault": r.fault, "guardian": deepcopy(r.guardian),
                            "targetId": r.target_id, "assignedSector": r.sector,
                            "trail": [p[:] for p in r.trail]} for r in self.rovers],
                "events": [e.copy() for e in self.events]}

    def _validate(self, data):
        if not isinstance(data, dict) or set(data) - {"action", "count", "speedMultiplier", "roverId", "fault"}:
            raise ValueError("Expected fleet action and optional count, speedMultiplier, roverId, fault")
        action = data.get("action")
        if not isinstance(action, str) or action not in ("start", "stop", "step", "reset", "fault"):
            raise ValueError("Expected start, stop, step, reset or fault")
        count, speed = data.get("count", self.count), data.get("speedMultiplier", self.speed_multiplier)
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 6:
            raise ValueError("count must be an integer from 1 to 6")
        if (isinstance(speed, bool) or not isinstance(speed, (int, float))
                or not 1 <= speed <= 120 or not math.isfinite(speed)):
            raise ValueError("speedMultiplier must be finite and between 1 and 120")
        if count != self.count and (action not in ("reset", "start", "step") or (self.has_frames and action != "reset")):
            raise ValueError("Changing count after mission activity requires reset")
        if action == "fault":
            if (not isinstance(data.get("roverId"), str)
                    or data["roverId"] not in {r.carrier_id for r in self.rovers}
                    or not isinstance(data.get("fault"), str) or data["fault"] not in CAUSES):
                raise ValueError("fault requires a known roverId and fault in CAUSES")
        elif "roverId" in data or "fault" in data:
            raise ValueError("roverId and fault are only valid for the fault action")
        return action, count, float(speed)

    def _telemetry(self, rover):
        row, col = self._cell(rover.position)
        neighbor = self._position(row, min(self.cols - 1, col + 1))
        slip = .035 + .035 * min(1.0, abs(neighbor[1] - rover.position[1]) / self.spacing)
        count, fps, contrast, jump, link = 1200, 29.0, .58, .012, True
        if rover.fault == "dust":
            count, fps, contrast = 72, 13.0, .035
        elif rover.fault == "low_texture":
            count, contrast, jump = 60, .37, .232
        elif rover.fault == "glare":
            count, contrast, jump = 240, 1.0, .362
        elif rover.fault == "wheel_slip":
            slip = .98
        elif rover.fault == "sensor_drop":
            count, fps, jump, link = 12, .58, .912, False
        commanded = DRIVE_SPEED_MPS if rover.status in ("surveying", "responding") else 0.0
        return {"pointCount": count, "fps": fps, "poseJumpM": jump, "lumaContrast": contrast,
                "commandedSpeedMps": commanded, "observedSpeedMps": commanded * (1 - slip),
                "slipRatio": slip, "linkOk": link, "position": rover.position[:],
                "simulation": 1, "elapsedS": self.elapsed, "speedMultiplier": self.speed_multiplier}

    async def _observe(self, rover):
        row, col = self._cell(rover.position)
        telemetry = self._telemetry(rover)
        # Real archived samples, with a synthetic sensor return rate; no invented detail.
        patch = [self.points[r * 129 + c][:]
                 for r in range(max(0, row - 3), min(129, row + 4))
                 for c in range(max(0, col - 3), min(129, col + 4))]
        keep = round(len(patch) * telemetry["pointCount"] / 1200)
        frame = await self.ingest({"source": "simulated-rover", "room": "gale-fleet-sim",
                                   "carrierId": rover.carrier_id, "carrierType": "rover",
                                   "yawDeg": rover.heading, "points": patch[:keep], "telemetry": telemetry})
        self.has_frames = True
        rover.guardian = deepcopy(frame["guardian"])
        if rover.clearance_requested and rover.guardian["riskLevel"] == "nominal":
            rover.clearance_requested = False
            rover.status = "surveying"
            self._event("guardian_clearance", rover.carrier_id, None,
                        "Guardian confirms nominal observations after explicit operator clearance; survey may resume.")
        if rover.guardian["riskLevel"] in ("warning", "critical") and rover.status != "halted":
            previous_target = rover.target_id
            rover.status, rover.target_id = "halted", None
            rover.inspection.clear()
            self._event("guardian_halt", rover.carrier_id, previous_target,
                        f"Guardian {rover.guardian['riskLevel']}: {rover.guardian['predictedCause']} "
                        f"(risk {rover.guardian['riskScore']:.2f}). Policy latched a safety halt; "
                        "operator clearance is required. Other healthy rovers continue surveying.")

    def _scan(self, rover):
        row, col = self._cell(rover.position)
        # Synthetic ~24 m swath; only traversed cells and their immediate neighbors.
        self.covered.update((r, c) for r in range(max(0, row - 1), min(self.rows, row + 2))
                            for c in range(max(rover.columns[0], col - 1), min(rover.columns[1], col + 2)))

    def _move(self, rover, dt):
        if rover.status not in ("surveying", "responding"):
            return
        surveying = rover.status == "surveying"
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
            else:
                if not rover.inspection:
                    rover.status = "assisting"
                    self._event("inspection_arrived", rover.carrier_id, rover.target_id,
                                "Reached safe standoff for scouting/inspection only; target remains halted and faulty.")
                    break
                destination = self._position(*rover.inspection[0])
                obstacles = [r.position for r in self.rovers if r.status == "halted"]
                if not self._safe_segment(rover.position, destination, obstacles):
                    target_id = rover.target_id
                    rover.status, rover.target_id = "waiting", None
                    rover.inspection.clear()
                    self._event("inspection_route_blocked", rover.carrier_id, target_id,
                                "New safety exclusion blocks inspection route; stop and replan before moving.")
                    break
            length = distance(rover.position, destination)
            if length > 1e-8:
                fraction = min(1.0, budget / length)
                dx, dz = destination[0] - rover.position[0], destination[2] - rover.position[2]
                rover.heading = math.degrees(math.atan2(dx, dz)) % 360
                x, z = rover.position[0] + fraction * dx, rover.position[2] + fraction * dz
                rover.position = self._surface((z - self.points[0][2]) / self.spacing,
                                               (x - self.points[0][0]) / self.spacing)
                budget -= min(budget, length)
                rover.trail.append(rover.position[:])
                if surveying:
                    self._scan(rover)
                if fraction < 1:
                    break
            if surveying:
                rover.cursor += 1
            else:
                rover.inspection.popleft()

    def _safe_segment(self, a, b, obstacles):
        dx, dz = b[0] - a[0], b[2] - a[2]
        norm = dx * dx + dz * dz
        for target in obstacles:
            t = max(0.0, min(1.0, ((target[0] - a[0]) * dx + (target[2] - a[2]) * dz) / norm)) if norm else 0.0
            # Bilinear resampling can shift a grid coordinate by a few ulps.
            if math.hypot(a[0] + t * dx - target[0], a[2] + t * dz - target[2]) + 1e-7 < 2 * self.spacing:
                return False
        return True

    def _inspection_path(self, helper, target):
        """Bounded four-neighbor A*, respecting slopes and a two-cell exclusion disc."""
        obstacles = [r.position for r in self.rovers if r.status == "halted"]
        start = self._cell(helper.position)
        start_position = self._position(*start)
        if not self._safe_segment(helper.position, start_position, obstacles):
            return None
        heuristic = lambda p: max(0.0, distance(p, target.position) - 3 * self.spacing)
        frontier = [(heuristic(start_position), 0.0, start)]
        costs, parents, closed = {start: 0.0}, {}, set()
        while frontier and len(closed) < MAX_PATH_NODES:
            _, cost, cell = heapq.heappop(frontier)
            if cell in closed:
                continue
            closed.add(cell)
            position = self._position(*cell)
            if 2 * self.spacing <= distance(position, target.position) <= 3 * self.spacing:
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
                slope = abs(other[1] - position[1]) / self.spacing
                if slope > MAX_HELPER_SLOPE or not self._safe_segment(position, other, obstacles):
                    continue
                candidate = cost + self.spacing * (1 + slope)
                if candidate < costs.get(neighbor, math.inf):
                    costs[neighbor], parents[neighbor] = candidate, cell
                    heapq.heappush(frontier, (candidate + heuristic(other), candidate, neighbor))
        return None

    def _assign_helpers(self):
        by_id = {r.carrier_id: r for r in self.rovers}
        for helper in self.rovers:
            if helper.target_id and by_id[helper.target_id].status != "halted":
                helper.target_id = None
                helper.inspection.clear()
                helper.status = "surveying"
        assigned = {r.target_id for r in self.rovers if r.target_id}
        for target in self.rovers:
            if target.status != "halted" or target.carrier_id in assigned:
                continue
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
                assigned.add(target.carrier_id)
                self.unavailable.discard(target.carrier_id)
                self._event("helper_assigned", helper.carrier_id, target.carrier_id,
                            f"Mission policy selected nearest available healthy rover with a safe bounded A* route "
                            f"({distance(helper.position, target.position):.1f} m away). "
                            f"Scout/inspect at {2 * self.spacing:.1f}–{3 * self.spacing:.1f} m standoff; no automatic repair.")
                break
            else:
                if target.carrier_id not in self.unavailable:
                    self.unavailable.add(target.carrier_id)
                    self._event("assistance_unavailable", target.carrier_id, None,
                                "No available healthy rover with a safe inspection route; safety halt remains latched.")

    async def _step(self):
        self.elapsed += self.interval * self.speed_multiplier
        self._assign_helpers()
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
                self.speed_multiplier = speed
                if action == "reset" or count != self.count:
                    self._reset(count)
                if action == "fault":
                    rover = next(r for r in self.rovers if r.carrier_id == data["roverId"])
                    rover.fault = data["fault"]
                    rover.clearance_requested = rover.fault == "nominal"
                    self._event("fault_injected", rover.carrier_id, None,
                                f"Operator set synthetic fault: {rover.fault}. Guardian inference uses normal ingest.")
                    if rover.fault == "nominal":
                        # Clearing is an explicit operator action, never a helper effect.
                        rover.status, rover.target_id = "halted", None
                        rover.inspection.clear()
                        self.unavailable.discard(rover.carrier_id)
                        self._event("operator_clearance", rover.carrier_id, None,
                                    "Operator explicitly cleared fault; Guardian must confirm nominal telemetry before resuming.")
                    await self._observe(rover)
                    self._assign_helpers()
                elif action == "step":
                    await self._step()
                elif action == "start" and (self.task is None or self.task.done()):
                    await self._step()
                    self.task = asyncio.create_task(self._run())
                    self._event("started", None, None, "Fleet started; at most six synthetic frames per one-second mission tick.")
                elif action == "stop":
                    self._event("stopped", None, None, "Fleet paused; coverage, faults and assignments retained.")
                return {"ok": True, "fleetState": self.state()}
