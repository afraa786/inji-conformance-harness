"""Mocked suite API contract tests. No Docker, browser, or external services."""
import io
import json
import time
import zipfile
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
import responses

from runner import conformance_runner as runner

BASE = "https://suite.example"
MODULE = "oid4vci-1_0-issuer-happy-flow"


@pytest.fixture
def clock(monkeypatch):
    state = [100.0]
    monkeypatch.setattr(runner.time, "monotonic", lambda: state[0])
    monkeypatch.setattr(runner.time, "sleep", lambda seconds: state.__setitem__(0, state[0] + seconds))
    return state


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # Do not load a developer's real .env.
    monkeypatch.delenv("OIDC_SUITE_TOKEN", raising=False)
    monkeypatch.setenv("OIDC_SUITE_INSECURE", "true")
    plan = {"planName": "oid4vci-1_0-issuer-test-plan", "variant": {"fapi_profile": "vci"}, "config": {"alias": "unit-test"}}
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
    return ["--component", "certify", "--target", "https://certify.example/v1/certify",
            "--suite-url", BASE, "--plan", str(path), "--out", str(tmp_path / "results.json"),
            "--poll-interval", "1", "--waiting-timeout-seconds", "3"]


def api_setup(states):
    responses.add(responses.POST, BASE + "/api/plan", json={"id": "plan-1"}, status=201)
    modules = [{"testModule": MODULE, "variant": {"credential_format": "sd_jwt_vc"}}]
    responses.add(responses.GET, BASE + "/api/plan/plan-1", json={"modules": modules})
    responses.add(responses.POST, BASE + "/api/runner", json={"id": "run-1"}, status=201)
    for state in states:
        responses.add(responses.GET, BASE + "/api/info/run-1", json=state)
    responses.add(responses.GET, BASE + "/api/log/run-1", json={"entries": []})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("results.json", "{}")
    responses.add(responses.GET, BASE + "/api/plan/export/plan-1", body=buffer.getvalue(), content_type="application/zip")


@responses.activate
def test_happy_path_exact_api_contract(inputs, tmp_path, clock):
    api_setup([{"status": "CREATED"}, {"status": "CONFIGURED"}, {"status": "FINISHED", "result": "PASSED"}])
    responses.add(responses.POST, BASE + "/api/runner/run-1", json={})
    assert runner.main(inputs) == 0
    calls = list(responses.calls)
    create = calls[0].request
    assert parse_qs(urlsplit(create.url).query) == {"planName": ["oid4vci-1_0-issuer-test-plan"], "variant": ['{"fapi_profile": "vci"}']}
    assert json.loads(create.body) == {"alias": "unit-test"}
    module = next(c.request for c in calls if c.request.method == "POST" and urlsplit(c.request.url).path == "/api/runner")
    assert module.body is None
    assert module.headers["Content-Type"] == "application/json"
    assert parse_qs(urlsplit(module.url).query) == {"test": [MODULE], "plan": ["plan-1"], "variant": ['{"credential_format": "sd_jwt_vc"}']}
    assert any(c.request.method == "POST" and c.request.url == BASE + "/api/runner/run-1" for c in calls)
    result = json.loads((tmp_path / "results.json").read_text())
    record = result["modules"][0]
    assert record["status"] == "PASSED"
    assert record["logUrl"].endswith("log=run-1")
    assert record["duration"] == 2
    assert (tmp_path / "certify-evidence/plan-export.zip").is_file()


@pytest.mark.parametrize("status,code", [("FAILED", 1), ("WARNING", 0), ("SKIPPED", 0), ("REVIEW", 0), ("UNKNOWN", 1)])
@responses.activate
def test_terminal_outcomes(inputs, tmp_path, clock, status, code):
    api_setup([{"status": "FINISHED", "result": status}])
    assert runner.main(inputs) == code


@responses.activate
def test_interrupted_cannot_pass(inputs, clock):
    api_setup([{"status": "INTERRUPTED", "result": "PASSED"}])
    assert runner.main(inputs) == 1


@responses.activate
def test_waiting_reads_live_state_then_times_out_and_cancels(inputs, tmp_path, clock):
    api_setup([{"status": "WAITING"}])
    responses.add(responses.GET, BASE + "/api/runner/run-1", json={"exposed": {}, "browser": {}})
    responses.add(responses.DELETE, BASE + "/api/runner/run-1", json={})
    assert runner.main(inputs) == 1
    result = json.loads((tmp_path / "results.json").read_text())
    assert result["modules"][0]["status"] == "FAILED"
    assert "WAITING timeout" in result["modules"][0]["detail"]
    assert any(c.request.method == "DELETE" for c in responses.calls)


@responses.activate
def test_connection_failure_is_infrastructure_not_expected(inputs, tmp_path, clock):
    api_setup([])
    responses.add(responses.GET, BASE + "/api/info/run-1", body=requests.ConnectionError("PRIVATE_TOKEN_MUST_NOT_LEAK"))
    assert runner.main(inputs) == 2
    result = (tmp_path / "results.json").read_text()
    assert "PRIVATE_TOKEN" not in result
    assert json.loads(result)["errors"]
    assert len([c for c in responses.calls if c.request.url.endswith("/api/info/run-1")]) == 3


@responses.activate
def test_expected_failure_and_unexpected_pass(inputs, tmp_path, clock):
    path = tmp_path / "expected.json"
    path.write_text(json.dumps([{"module": MODULE, "reason": "Tracked test issue"}]))
    inputs += ["--expected-failures", str(path)]
    api_setup([{"status": "FINISHED", "result": "FAILED"}])
    assert runner.main(inputs) == 0
    assert json.loads((tmp_path / "results.json").read_text())["modules"][0]["status"] == "EXPECTED_FAILURE"
    status, detail = runner.apply_expected_outcome(MODULE, "PASSED", "Passed", {MODULE: "issue"})
    assert status == "PASSED" and "unexpectedly passing" in detail


@responses.activate
def test_empty_plan_fails(inputs, clock):
    responses.add(responses.POST, BASE + "/api/plan", json={"id": "p"}, status=201)
    responses.add(responses.GET, BASE + "/api/plan/p", json={"modules": []})
    assert runner.main(inputs) == 2


@responses.activate
def test_invalid_export_fails(inputs, clock):
    api_setup([{"status": "FINISHED", "result": "PASSED"}])
    responses.replace(responses.GET, BASE + "/api/plan/export/plan-1", body="not a zip")
    assert runner.main(inputs) == 2


def test_tls_and_token_scoped_to_suite(monkeypatch):
    monkeypatch.setenv("OIDC_SUITE_TOKEN", "UNIT_TEST_TOKEN")
    monkeypatch.setenv("OIDC_SUITE_INSECURE", "false")
    api = runner.SuiteAPI(BASE, time.monotonic() + 60)
    assert api.session.verify is True
    assert api.session.headers["Authorization"] == "Bearer UNIT_TEST_TOKEN"
    with pytest.raises(runner.RunnerError, match="another origin"):
        api.request("GET", "https://other.example/api/info/test")
    api.session.close()


@responses.activate
def test_redirect_is_not_followed(monkeypatch):
    monkeypatch.setenv("OIDC_SUITE_TOKEN", "UNIT_TEST_TOKEN")
    responses.add(responses.GET, BASE + "/api/info/test", status=302, headers={"Location": "https://other.example/"})
    api = runner.SuiteAPI(BASE, time.monotonic() + 60)
    with pytest.raises(runner.RunnerError, match="HTTP 302"):
        api.request("GET", "/api/info/test")
    assert len(responses.calls) == 1
    api.session.close()
