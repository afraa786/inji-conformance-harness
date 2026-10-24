import json
import os
import subprocess
import sys
from pathlib import Path

from runner.capture_diagnostics import redact
from runner import stack_control
from runner.archive_results import archive


def test_startup_timeout_fails_and_preserves_log(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])
    monkeypatch.setattr(stack_control.subprocess, "run", timeout)
    assert stack_control.main() == 2
    assert (tmp_path / "results/diagnostics/compose-up.txt").exists()


def test_service_logs_redact_secrets(monkeypatch):
    monkeypatch.setenv("OIDC_SUITE_TOKEN", "UNIT_TEST_SECRET")
    value = redact('Bearer UNIT_TEST_SECRET password=DEV_ONLY_CHANGE_ME access_token=abc123')
    assert "UNIT_TEST_SECRET" not in value
    assert "DEV_ONLY_CHANGE_ME" not in value
    assert "abc123" not in value


def test_combined_output_fails_on_actual_failed_or_interrupted_status(tmp_path):
    # This is fabricated unit-test input, not a recorded conformance run.
    root = tmp_path / "results"; root.mkdir()
    for component, status in (("certify", "FAILED"), ("verify", "INTERRUPTED")):
        (root / ("results-" + component + ".json")).write_text(json.dumps({"component": component,
            "modules": [{"name": "test-module", "status": status}]}))
    script = Path(__file__).resolve().parents[1] / "merge_results.py"
    result = subprocess.run([sys.executable, str(script), "1", "1"], cwd=tmp_path, capture_output=True)
    assert result.returncode == 1
    combined = json.loads((root / "results-combined.json").read_text())
    assert combined["summary"]["failed"] == 1 and combined["summary"]["interrupted"] == 1


def test_archive_preserves_previous_results_and_other_component(tmp_path):
    root = tmp_path / "results"
    root.mkdir()
    for component in ("certify", "verify"):
        (root / ("results-" + component + ".json")).write_text(component)
    first = archive("certify", root)
    second = archive("certify", root)
    assert first != second
    assert (first / "results-certify.json").read_text() == "certify"
    assert not (first / "results-verify.json").exists()
    assert (root / "results-verify.json").read_text() == "verify"


def test_merge_rejects_missing_component_and_preserves_infrastructure_exit(tmp_path):
    script = Path(__file__).resolve().parents[1] / "merge_results.py"
    result = subprocess.run([sys.executable, str(script), "0"], cwd=tmp_path, capture_output=True)
    assert result.returncode == 2
    result = subprocess.run([sys.executable, str(script), "2", "0"], cwd=tmp_path, capture_output=True)
    assert result.returncode == 2
    assert json.loads((tmp_path / "results/results-combined.json").read_text())["exitCode"] == 2
