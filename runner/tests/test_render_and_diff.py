import json
import sys
import pytest
from runner import diff_results
from runner.render_plans import render_plan


def test_typed_render_and_no_unresolved_inputs():
    plan = render_plan("verify", "https://verify.example", "https://suite.example", {
        "VERIFIER_CLIENT_ID": 'client"quoted', "VERIFIER_SIGNING_JWK_JSON": '{"kty":"EC","kid":"unit-test"}'})
    assert plan["config"]["credential"]["signing_jwk"]["kty"] == "EC"
    assert plan["config"]["client"]["client_id"] == 'client"quoted'
    assert "{{" not in json.dumps(plan)


def test_missing_render_input_fails():
    with pytest.raises(ValueError, match="Missing plan variable"):
        render_plan("certify", "https://issuer.example", "https://suite.example", {})


def test_result_diff_missing_baseline_and_new_failure(tmp_path, monkeypatch, capsys):
    current = tmp_path / "current.json"
    current.write_text(json.dumps({"component": "certify", "modules": [{"name": "module", "status": "INTERRUPTED"}]}))
    monkeypatch.setattr(sys, "argv", ["diff", str(tmp_path / "absent.json"), str(current)])
    assert diff_results.main() == 1
    assert "Newly failing: 1" in capsys.readouterr().out


def test_diff_expected_failure_is_not_regression(tmp_path, monkeypatch, capsys):
    previous, current = tmp_path / "previous.json", tmp_path / "current.json"
    previous.write_text(json.dumps({"modules": [{"name": "m", "status": "EXPECTED_FAILURE"}]}))
    current.write_text(json.dumps({"modules": [{"name": "m", "status": "PASSED"}]}))
    monkeypatch.setattr(sys, "argv", ["diff", str(previous), str(current)])
    assert diff_results.main() == 0
    out = capsys.readouterr().out
    assert "Newly passing: 1" in out and "Changed status: 1" in out
