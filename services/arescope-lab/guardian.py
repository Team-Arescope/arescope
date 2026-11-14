"""Two-loop Guardian: a small supervised prototype classifier, entirely stdlib.

Hold-out trajectories have disjoint terrain rows and seeds. Their labels/failure
times are used ONLY by evaluate_holdout, never by training. All optical/chassis
measurements are synthetic; HiRISE contributes terrain and slope, not fault truth.
The baseline intentionally lacks the emerging soft-sand micro-slip pattern.
"""

from copy import deepcopy
from functools import lru_cache
import json
import random
import threading
import time

from rover_sim import CAUSES, RoverSimulator

DEFAULTS = {"pointCount": 1200, "fps": 30, "poseJumpM": .01, "lumaContrast": .58,
            "slipRatio": .03, "linkOk": True}
SCALES = (1600, 30, .5, 1, 1, 1)
FEATURE_NAMES = tuple(f"{key}.{stat}" for key in DEFAULTS for stat in ("mean", "min", "trend"))
ACTIONS = {
    "nominal": "Продолжать наблюдение / Continue monitoring",
    "dust": "Остановиться, очистить и проверить оптический датчик / Stop; clean/check optical sensor",
    "low_texture": "Остановиться и осмотреть ориентир / Stop and inspect a landmark",
    "glare": "Вернуться к последней надёжной точке, изменить угол камеры / Return to last reliable point; change camera angle",
    "wheel_slip": "Снизить скорость на мягком грунте, остановиться и сменить траекторию / Reduce speed on soft ground; stop and reroute",
    "sensor_drop": "Остановиться и вернуться к последней надёжной точке; проверить датчик / Stop; return to last reliable point; check sensor",
}


def extract_features(window):
    rows = list(window)[-5:]
    rows = [row.get("telemetry", row) for row in rows] or [{}]
    values = []
    for (key, default), scale in zip(DEFAULTS.items(), SCALES):
        series = [max(-2, min(2, float(row.get(key, default)) / scale)) for row in rows]
        values.extend((sum(series) / len(series), min(series),
                       (series[-1] - series[0]) / max(1, len(series) - 1)))
    return values


def _distance(a, b):
    # Trend carries independent evidence of progressive degradation.
    return sum((x - y) ** 2 * (9 if i % 3 == 2 else 1) for i, (x, y) in enumerate(zip(a, b)))


def _train(samples, version):
    """Class-wise deterministic k-means compression of labeled rolling windows."""
    prototypes = []
    for cause in CAUSES:
        vectors = [x for x, label in samples if label == cause]
        if not vectors:
            continue
        centers = [vectors[0][:]]
        for _ in range(min(7, len(vectors) - 1)):
            farthest = max(vectors, key=lambda x: min(_distance(x, c) for c in centers))
            if min(_distance(farthest, c) for c in centers) < 1e-9:
                break
            centers.append(farthest[:])
        for _ in range(5):
            groups = [[] for _ in centers]
            for vector in vectors:
                groups[min(range(len(centers)), key=lambda i: _distance(vector, centers[i]))].append(vector)
            centers = [[sum(v[i] for v in group) / len(group) for i in range(len(FEATURE_NAMES))]
                       if group else old for old, group in zip(centers, groups)]
        prototypes.extend({"cause": cause, "weights": c} for c in centers)
    return {"modelVersion": version, "algorithm": "nearest-prototype-v1", "windowSize": 5,
            "featureNames": list(FEATURE_NAMES), "scales": list(SCALES),
            "defaults": DEFAULTS.copy(), "trendWeight": 9,
            "prototypes": prototypes, "riskThresholds": {"warning": .45, "critical": .78},
            "provenance": "synthetic chassis/optics on disjoint HiRISE terrain trajectories"}


@lru_cache(maxsize=2)
def generate_dataset(split="train"):
    if split not in ("train", "adaptation", "holdout"):
        raise ValueError("Expected train, adaptation or holdout")
    rng = random.Random({"train": 121, "adaptation": 521, "holdout": 921}[split])
    trajectories = []
    for cause in CAUSES:
        for index in range(6):
            # Entire trajectories, including their terrain corridors, belong to one split.
            row = 51 + index * 2 if split == "adaptation" else (12 if split == "train" else 77) + index * 5
            emerging = cause == "wheel_slip" and split != "train" and index >= 2
            sim = RoverSimulator(seed=rng.randrange(1_000_000), row=row, col=15 + index * 3, emerging=emerging)
            frames = []
            onset = 7 + index % 3
            for step in range(36):
                if step == onset:
                    sim.inject_fault(cause)
                frame = sim.step()
                frames.append({"telemetry": frame["telemetry"], "receivedAt": float(step)})
            trajectories.append({"id": f"{split}-{cause}-{index}", "cause": cause,
                                 "pattern": "micro-slip" if emerging else "standard",
                                 "terrainRow": row, "onset": onset,
                                 "failureAt": onset + 21 if cause != "nominal" else None,
                                 "frames": frames})
    return trajectories


@lru_cache(maxsize=1)
def _base_samples():
    samples = []
    for trajectory in generate_dataset("train"):
        for index in range(4, len(trajectory["frames"])):
            # Transition frames before detectable onset remain nominal examples.
            label = trajectory["cause"] if index >= trajectory["onset"] + 6 else "nominal"
            samples.append((extract_features(trajectory["frames"][max(0, index - 4):index + 1]), label))
    return samples


def predict_model(model, window):
    window = list(window)[-5:]
    features = extract_features(window)
    distances = {cause: float("inf") for cause in CAUSES}
    for prototype in model["prototypes"]:
        cause = prototype["cause"]
        distances[cause] = min(distances[cause], _distance(features, prototype["weights"]))
    cause = min(distances, key=distances.get)
    row = list(window)[-1] if window else {}
    telemetry = row.get("telemetry", row)
    severity = max(0, min(1, max(1 - features[0] / .75, 1 - features[3], features[6],
                                  abs(features[9] - .58) / .58, features[12], 1 - features[15])))
    risk = min(.99, .48 + .5 * severity) if cause != "nominal" else min(.4, .05 + .25 * severity)
    level = "critical" if risk >= .78 else "warning" if risk >= .45 else "nominal"
    lead = 0.0
    if cause != "nominal" and len(window) >= 2:
        # Extrapolation to a physical telemetry limit; this is an estimate, not ground truth.
        key, threshold, direction = {"dust": ("lumaContrast", .07, -1),
            "low_texture": ("pointCount", 100, -1), "glare": ("lumaContrast", .97, 1),
            "wheel_slip": ("slipRatio", .85, 1), "sensor_drop": ("fps", 2, -1)}[cause]
        first = window[0].get("telemetry", window[0])
        elapsed = max(.001, window[-1].get("receivedAt", len(window) - 1) - window[0].get("receivedAt", 0))
        slope = (telemetry.get(key, DEFAULTS[key]) - first.get(key, DEFAULTS[key])) / elapsed
        remaining = threshold - telemetry.get(key, DEFAULTS[key])
        if slope * direction > 1e-6 and remaining * direction > 0:
            lead = min(120.0, remaining / slope)
    return {"riskScore": round(risk, 4), "riskLevel": level, "predictedCause": cause,
            "leadTimeS": round(lead, 3), "recoveryAction": ACTIONS[cause],
            "lowConfidence": level != "nominal", "modelVersion": model["modelVersion"]}


def _evaluate(model):
    caught, total, false_alarms, correct, count = 0, 0, 0, 0, 0
    tp = {c: 0 for c in CAUSES}
    actual = {c: 0 for c in CAUSES}
    predicted = {c: 0 for c in CAUSES}
    leads, micro_correct, micro_count = [], 0, 0
    for trajectory in generate_dataset("holdout"):
        first_alarm = None
        for index in range(4, len(trajectory["frames"])):
            truth = trajectory["cause"] if index >= trajectory["onset"] + 6 else "nominal"
            result = predict_model(model, trajectory["frames"][index - 4:index + 1])
            guess = result["predictedCause"]
            actual[truth] += 1
            predicted[guess] += 1
            correct += truth == guess
            count += 1
            tp[truth] += truth == guess
            if trajectory["pattern"] == "micro-slip" and truth == "wheel_slip":
                micro_count += 1
                micro_correct += guess == truth
            false_alarms += truth == "nominal" and result["riskLevel"] != "nominal"
            # A caught failure requires a correctly attributed warning BEFORE failure.
            if truth != "nominal" and guess == truth and result["riskLevel"] != "nominal" and first_alarm is None:
                first_alarm = index
        if trajectory["failureAt"] is not None:
            total += 1
            if first_alarm is not None and first_alarm < trajectory["failureAt"]:
                caught += 1
                leads.append(float(trajectory["failureAt"] - first_alarm))
    recall = {c: tp[c] / actual[c] if actual[c] else 0.0 for c in CAUSES}
    f1 = sum(2 * tp[c] / max(1, actual[c] + predicted[c]) for c in CAUSES) / len(CAUSES)
    return {"caughtFailures": caught, "totalFailures": total, "detectionRate": caught / max(1, total),
            "meanLeadTimeS": sum(leads) / max(1, len(leads)), "falseAlarms": false_alarms,
            "accuracy": correct / max(1, count), "F1": f1, "perCauseRecall": recall,
            "microSlipRecall": micro_correct / max(1, micro_count),
            "falseAlarmRate": false_alarms / max(1, actual["nominal"]),
            "evaluatedWindows": count, "holdoutTrajectories": len(generate_dataset("holdout")),
            "falseAlarmUnit": "nominal windows", "leadTimeBasis": "failure time minus first correct warning"}


@lru_cache(maxsize=1)
def _baseline():
    model = _train(_base_samples(), "v1")
    return model, _evaluate(model)


class GuardianEngine:
    def __init__(self):
        self.active_model, self.baseline_metrics = deepcopy(_baseline())
        self.current_metrics = deepcopy(self.baseline_metrics)
        self.candidate_model, self.candidate_metrics = None, None
        self.candidate_incident_ids = []
        self.deployed_at = None
        self.lock = threading.RLock()

    @property
    def model_version(self):
        return self.active_model["modelVersion"]

    def predict(self, window):
        with self.lock:
            return predict_model(self.active_model, window)

    def export_model(self):
        with self.lock:
            return deepcopy(self.active_model)

    def evaluate_holdout(self, model=None):
        return _evaluate(model or self.active_model)

    def retrain(self, incidents=()):
        with self.lock:
            incidents = list(incidents)
            samples = list(_base_samples())
            ids, reviewed = [], []
            for incident in incidents:
                cause = incident.get("trueCause", incident.get("true_cause"))
                if cause not in CAUSES:
                    raise ValueError("Incident requires a valid trueCause")
                window = incident.get("window", incident.get("window_json", []))
                if isinstance(window, str):
                    window = json.loads(window)
                if not window:
                    continue
                reviewed.append((extract_features(window), cause))
                ids.append(incident.get("id"))
            samples.extend(reviewed)
            version = f"v{int(self.model_version[1:]) + 1}"
            candidate = _train(samples, version)
            # Keep rare reviewed patterns represented without growing the on-board
            # model with the incident archive: at most 16 prototypes per cause.
            if reviewed:
                candidate["prototypes"].extend(_train(reviewed, version)["prototypes"])
            metrics = self.evaluate_holdout(candidate)
            self.candidate_model, self.candidate_metrics = candidate, metrics
            self.candidate_incident_ids = [i for i in ids if i is not None]
            improved = self.candidate_ready
            return {"ok": True, "candidateVersion": version, "beforeMetrics": deepcopy(self.current_metrics),
                    "candidateMetrics": deepcopy(metrics), "improved": improved}

    @property
    def candidate_ready(self):
        metrics, current = self.candidate_metrics, self.current_metrics
        return bool(self.candidate_model and metrics and
                    metrics["F1"] > current["F1"] and
                    metrics["caughtFailures"] >= current["caughtFailures"] and
                    metrics["accuracy"] >= current["accuracy"] and
                    metrics["falseAlarmRate"] <= max(.05, current["falseAlarmRate"]))

    def deploy(self, approved=False, at=None):
        if approved is not True:
            raise ValueError("Explicit human approval is required")
        with self.lock:
            if not self.candidate_ready:
                raise ValueError("No validated candidate is ready")
            self.active_model, self.current_metrics = self.candidate_model, self.candidate_metrics
            self.candidate_model, self.candidate_metrics = None, None
            self.deployed_at = time.time() if at is None else at
            return {"ok": True, "modelVersion": self.model_version, "deployedAt": self.deployed_at}

    def dump_state(self):
        with self.lock:
            return {"activeModel": self.export_model(), "currentMetrics": deepcopy(self.current_metrics),
                    "candidateModel": deepcopy(self.candidate_model), "candidateMetrics": deepcopy(self.candidate_metrics),
                    "candidateIncidentIds": self.candidate_incident_ids[:], "deployedAt": self.deployed_at}

    def restore_state(self, state):
        with self.lock:
            if state:
                state = deepcopy(state)
                self.active_model = state["activeModel"]
                self.current_metrics = state["currentMetrics"]
                self.candidate_model, self.candidate_metrics = state["candidateModel"], state["candidateMetrics"]
                self.candidate_incident_ids, self.deployed_at = state["candidateIncidentIds"], state["deployedAt"]
