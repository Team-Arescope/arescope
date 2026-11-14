"""Deterministic HiRISE terrain replay; chassis/optics are synthetic, not NASA measurements.

CLI: python rover_sim.py --url http://127.0.0.1:18965 --fault dust --steps 40
The producer token is read from ARESCOPE_LIVE_PRODUCER_TOKEN, never printed.
"""

import argparse
import asyncio
import json
import math
import os
from pathlib import Path
from functools import lru_cache
import random
import time
from urllib.request import Request, urlopen

CAUSES = ("nominal", "dust", "low_texture", "glare", "wheel_slip", "sensor_drop")
TERRAIN_PATH = Path(__file__).resolve().parent / "static/data/hirise-gale.json"


@lru_cache(maxsize=2)
def _terrain(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class RoverSimulator:
    def __init__(self, terrain_path=TERRAIN_PATH, seed=41, row=40, col=30, emerging=False):
        data = _terrain(str(terrain_path))
        self.rows, self.cols = data["grid"]["rows"], data["grid"]["cols"]
        self.terrain = data["points"]
        self.spacing = data["metadata"]["effective_spacing_m"]
        self.product_id = data["metadata"]["product_id"]
        if len(self.terrain) != self.rows * self.cols or self.spacing <= 0:
            raise ValueError("Invalid HiRISE grid")
        self.rng = random.Random(seed)
        self.row, self.col = row, float(col)
        self.elapsed, self.steps = 0.0, 0
        self.fault, self.fault_age = "nominal", 0.0
        self.emerging = emerging

    def inject_fault(self, fault):
        if fault not in CAUSES:
            raise ValueError("Unknown rover fault")
        self.fault, self.fault_age = fault, 0.0

    def step(self, dt=1.0):
        if isinstance(dt, bool) or not isinstance(dt, (int, float)) or not math.isfinite(dt) or dt <= 0:
            raise ValueError("dt must be positive and finite")
        self.steps += 1
        self.elapsed += dt
        self.fault_age += dt
        severity = min(1.0, self.fault_age / 22) if self.fault != "nominal" else 0.0
        index = max(1, min(self.cols - 2, round(self.col)))
        row = max(6, min(self.rows - 7, self.row))
        origin = self.terrain[row * self.cols + index]
        neighbor = self.terrain[row * self.cols + index + 1]
        slope = min(1.0, abs(neighbor[1] - origin[1]) / self.spacing)
        noise = lambda scale: self.rng.uniform(-scale, scale)
        commanded = .22
        slip = max(0.0, .035 + slope * .035 + noise(.012))
        count, fps, contrast, jump, link = 1200 + noise(35), 29 + noise(.6), .58 + noise(.015), .012, True
        if self.fault == "dust":
            count *= 1 - .94 * severity
            contrast *= 1 - .94 * severity
            fps *= 1 - .55 * severity
        elif self.fault == "low_texture":
            count *= 1 - .95 * severity
            contrast *= 1 - .36 * severity
            jump += .22 * severity
        elif self.fault == "glare":
            count *= 1 - .8 * severity
            contrast = min(1, contrast + .42 * severity)
            jump += .35 * severity
        elif self.fault == "wheel_slip":
            # New soft-sand pattern: coherent small slips can accumulate immobilisation
            # before the large instantaneous slip seen in the baseline training runs.
            slip = min(.99, slip + (.14 if self.emerging else .94) * severity)
        elif self.fault == "sensor_drop":
            count *= 1 - .99 * severity
            fps *= 1 - .98 * severity
            jump += .9 * severity
            link = severity < .8
        observed = commanded * (1 - slip)
        self.col += observed * dt / self.spacing
        if self.col >= self.cols - 7:
            self.col, self.row = 7.0, 6 + (self.row + 9) % (self.rows - 13)
        center = self.terrain[row * self.cols + max(0, min(self.cols - 1, round(self.col)))]
        # Sparse local terrain patch, preserving the DTM's real 8.09 m sample spacing.
        points = [self.terrain[r * self.cols + c][:]
                  for r in range(row - 6, row + 7)
                  for c in range(max(0, index - 6), min(self.cols, index + 7))]
        keep = max(0, min(len(points), round(len(points) * count / 1200)))
        points = self.rng.sample(points, keep)
        telemetry = {"pointCount": max(0, round(count)), "fps": max(0, fps),
                     "poseJumpM": jump, "lumaContrast": contrast,
                     "commandedSpeedMps": commanded, "observedSpeedMps": observed,
                     "slipRatio": slip, "linkOk": link, "position": center[:]}
        return {"source": "simulated-rover", "room": "gale-rover-sim", "carrierId": "rover-sim-01", "carrierType": "rover",
                "yawDeg": 90.0, "points": points, "telemetry": telemetry}


class RoverSimManager:
    """One event-loop-owned task; manual and background steps use the same ingest callback."""

    def __init__(self, ingest, interval=1.0):
        if isinstance(interval, bool) or not isinstance(interval, (float, int)) or not math.isfinite(interval) or interval <= 0:
            raise ValueError("interval must be positive and finite")
        self.ingest, self.interval = ingest, interval
        self.sim = None  # Load the read-only terrain only when the simulator is requested.
        self.task, self.latest_frame, self.error = None, None, None
        self.lock = asyncio.Lock()
        self.control_lock = asyncio.Lock()

    def state(self):
        return {"running": self.task is not None and not self.task.done(),
                "fault": self.sim.fault if self.sim else "nominal",
                "steps": self.sim.steps if self.sim else 0,
                "elapsedS": self.sim.elapsed if self.sim else 0,
                "source": "simulated-rover", "terrainSource": "nasa-pds-hirise", "error": self.error}

    async def step(self):
        async with self.lock:
            if self.sim is None:
                self.sim = RoverSimulator()
            self.latest_frame = await self.ingest(self.sim.step(self.interval))
            return self.latest_frame

    async def _run(self):
        try:
            while True:
                await asyncio.sleep(self.interval)
                await self.step()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.error = type(exc).__name__

    async def control(self, action, fault=None):
        if fault is not None and fault not in CAUSES:
            raise ValueError("Unknown rover fault")
        if action not in ("start", "stop", "step", "fault") or (action == "fault" and fault is None):
            raise ValueError("Expected start, stop, step, or fault with a valid fault")
        async with self.control_lock:
            async with self.lock:
                if self.sim is None:
                    self.sim = RoverSimulator()
                if fault is not None:
                    self.sim.inject_fault(fault)
            if action == "stop":
                await self.stop()
            elif action == "step":
                await self.step()
            elif action == "start" and not self.state()["running"]:
                self.error = None
                await self.step()
                self.task = asyncio.create_task(self._run())
            return {"ok": True, "simState": self.state(), "latestFrame": self.latest_frame}

    async def stop(self):
        if self.task is not None:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:18965")
    parser.add_argument("--fault", choices=CAUSES, default="nominal")
    parser.add_argument("--steps", type=int, default=40)
    parser.add_argument("--interval", type=float, default=1)
    args = parser.parse_args()
    token = os.environ.get("ARESCOPE_LIVE_PRODUCER_TOKEN", "")
    if not token or args.interval <= 0 or not math.isfinite(args.interval) or args.steps < 1:
        parser.error("Set producer token, positive interval, and steps >= 1")
    sim = RoverSimulator()
    sim.inject_fault(args.fault)
    for _ in range(args.steps):
        payload = json.dumps(sim.step(args.interval), allow_nan=False).encode()
        request = Request(args.url.rstrip("/") + "/api/live/frame", data=payload,
                          headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        with urlopen(request, timeout=10) as response:
            result = json.load(response)
            print(json.dumps({"step": sim.steps, "guardian": result["guardian"]}))
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
