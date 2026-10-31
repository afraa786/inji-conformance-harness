"""Threshold tests use explicit synthetic budgets, never production defaults."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from runner.benchmarks import load_policy, evaluate, DEFAULT_CONFIG


@pytest.mark.parametrize("measured,status", [(9.999, "PASSED"), (10, "PASSED"), (10.001, "FAILED")])
@pytest.mark.parametrize("component", ["certify", "verify", "combined"])
def test_run_threshold_boundary(component, measured, status):
    policy = load_policy(DEFAULT_CONFIG)
    scope = policy["combined"] if component == "combined" else policy["components"][component]
    scope["max_run_seconds"] = 10
    assert evaluate(component, measured, [], policy)["status"] == status


def test_no_numeric_defaults_or_false_pass():
    policy = load_policy(DEFAULT_CONFIG)
    assert evaluate("certify", 999999, [], policy)["status"] == "NOT_CONFIGURED"


def test_module_budget_is_component_specific():
    policy = load_policy(DEFAULT_CONFIG)
    policy["components"]["verify"]["max_module_seconds"] = 2
    modules = [{"name": "module", "duration": 2.001}]
    assert evaluate("verify", 3, modules, policy)["status"] == "FAILED"
    assert evaluate("certify", 3, modules, policy)["status"] == "NOT_CONFIGURED"
    modules[0]["duration"] = 2
    assert evaluate("verify", 3, modules, policy)["status"] == "PASSED"


@pytest.mark.parametrize("limit", [-1, True, "10", float("inf"), float("nan")])
def test_invalid_limits_fail(tmp_path, limit):
    policy = load_policy(DEFAULT_CONFIG)
    policy["combined"]["max_run_seconds"] = limit
    p = tmp_path / "policy.json"
    p.write_text(json.dumps(policy))
    with pytest.raises(ValueError):
        load_policy(p)


def test_configured_missing_measurement_fails_closed():
    policy = load_policy(DEFAULT_CONFIG)
    policy["combined"]["max_run_seconds"] = 10
    with pytest.raises(ValueError):
        evaluate("combined", None, [], policy)


def test_combined_budget_fails_process_without_altering_conformance(tmp_path):
    root = tmp_path / "results"
    root.mkdir()
    for component in ("certify", "verify"):
        (root / ("results-" + component + ".json")).write_text(json.dumps(dict(
            component=component, exitCode=0, errors=[], durationSeconds=6,
            modules=[dict(name="protocol", status="PASSED", duration=6)])))
    policy = load_policy(DEFAULT_CONFIG)
    policy["combined"]["max_run_seconds"] = 10
    config = tmp_path / "policy.json"
    config.write_text(json.dumps(policy))
    import os
    env = dict(os.environ, BENCHMARK_CONFIG=str(config))
    script = Path(__file__).resolve().parents[1] / "merge_results.py"
    result = subprocess.run([sys.executable, str(script), "0", "0"], cwd=tmp_path, env=env, capture_output=True)
    assert result.returncode == 1
    merged = json.loads((root / "results-combined.json").read_text())
    assert merged["summary"]["passed"] == 2 and merged["summary"]["failed"] == 0
    assert merged["benchmark"]["status"] == "FAILED"
