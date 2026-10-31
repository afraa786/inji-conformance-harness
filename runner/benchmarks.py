"""Explicit execution-time budgets. Null means not configured, never a pass."""
import json
import math
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "configs/benchmark-thresholds.json"


def load_policy(path):
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(policy, dict) or set(policy) != {"schemaVersion", "components", "combined"} or type(policy["schemaVersion"]) is not int or policy["schemaVersion"] != 1:
        raise ValueError("Invalid benchmark schema")
    components = policy["components"]
    if not isinstance(components, dict) or set(components) != {"certify", "verify"}:
        raise ValueError("Benchmark components must be certify and verify")
    for name, limits in list(components.items()) + [("combined", policy["combined"])]:
        allowed = {"max_run_seconds"} if name == "combined" else {"max_run_seconds", "max_module_seconds"}
        if not isinstance(limits, dict) or set(limits) != allowed:
            raise ValueError("Invalid benchmark limits for " + name)
        for value in limits.values():
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0):
                raise ValueError("Benchmark limits must be null or finite nonnegative seconds")
    return policy


def evaluate(component, duration, modules, policy):
    limits = policy["combined"] if component == "combined" else policy["components"][component]
    checks = []
    for key, limit in limits.items():
        if limit is None:
            continue
        measurements = [(component, duration)] if key == "max_run_seconds" else [
            (module["name"], module.get("duration")) for module in modules]
        if not measurements:
            raise ValueError("Configured module benchmark requires actual module measurements")
        for name, measured in measurements:
            if isinstance(measured, bool) or not isinstance(measured, (float, int)) or not math.isfinite(measured) or measured < 0:
                raise ValueError("Configured benchmark requires finite nonnegative execution measurements")
            checks.append(dict(metric=key, subject=name, measuredSeconds=measured, limitSeconds=limit,
                               status="PASSED" if measured <= limit else "FAILED"))
    return dict(status=("FAILED" if any(c["status"] == "FAILED" for c in checks) else
                        "PASSED" if checks else "NOT_CONFIGURED"), checks=checks,
                measurementScope="plan execution; combined sums sequential component execution; excludes Docker startup")
