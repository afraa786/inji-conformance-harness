"""Contract tests against alpha DTO/controller shapes; all HTTP here is mocked."""
import json
import time
from urllib.parse import parse_qs, urlsplit
import pytest
import requests
import responses

from runner.common import RunnerError, HandoffFailure
from runner.conformance_runner import SuiteAPI
from runner.handoff_verify import VerifyHandoff

PUBLIC = "https://verify.test:8447/v1/verify"
HOST = "https://localhost:8447/v1/verify"
SUITE = "https://localhost:8443"
CLIENT = "redirect_uri:" + PUBLIC + "/v2/vp-submission/direct-post"
QUERY = {"credentials": [{"id": "pid", "format": "dc+sd-jwt", "meta": {"vct_values": ["urn:eudi:pid:1"]},
                           "require_cryptographic_holder_binding": True}]}


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv("VERIFY_API_URL", HOST)
    monkeypatch.setenv("VERIFY_REQUEST_JSON", json.dumps({"dcqlQuery": QUERY}))
    monkeypatch.setenv("OIDC_SUITE_INSECURE", "false")
    plan = {"variant": {"credential_format": "sd_jwt_vc", "client_id_prefix": "redirect_uri",
                        "request_method": "url_query", "response_mode": "direct_post"},
            "config": {"client": {"client_id": CLIENT}}}
    return plan


def created():
    return {"requestId": "req-1", "transactionId": "txn-1", "authorizationDetails": {
        "clientId": CLIENT, "responseType": "vp_token", "responseMode": "direct_post",
        "responseUri": PUBLIC + "/v2/vp-submission/direct-post", "nonce": "verified_server_nonce_123",
        "dcqlQuery": QUERY}}


def instance(plan):
    handoff = VerifyHandoff(PUBLIC, plan)
    handoff.deadline = time.monotonic() + 60
    return handoff


@responses.activate
def test_valid_dcql_handoff_and_real_result_contract(setup):
    responses.add(responses.POST, HOST + "/v2/vp-request", json=created(), status=201)
    responses.add(responses.GET, SUITE + "/authorize", body="captured")
    responses.add(responses.GET, HOST + "/vp-request/req-1/status", json={"status": "VP_SUBMITTED"})
    responses.add(responses.POST, HOST + "/v2/vp-results/txn-1", json={"transactionId": "txn-1", "allChecksSuccessful": True,
        "credentialResults": [{"allChecksSuccessful": True}]})
    handoff = instance(setup)
    api = SuiteAPI(SUITE, handoff.deadline)
    context = {}
    assert handoff.drive(api, {"browser": {"uriInputRequests": [{"submitUrl": SUITE + "/authorize"}]}}, context)
    assert json.loads(responses.calls[0].request.body) == {"dcqlQuery": QUERY, "clientId": CLIENT}
    params = parse_qs(urlsplit(responses.calls[1].request.url).query)
    assert json.loads(params["dcql_query"][0]) == QUERY
    assert "presentation_definition" not in params and "client_metadata" not in params
    assert params["state"] == ["req-1"]
    handoff.finish(context, "oid4vp-1final-verifier-happy-flow")
    assert context["verifyOutcome"] == "SUCCESS"
    assert json.loads(responses.calls[-1].request.body) == {"skipStatusChecks": False, "statusCheckFilters": [], "includeClaims": False}
    api.session.close()


@pytest.mark.parametrize("payload", [[], {}, {"presentationDefinition": {}}, {"dcql_query": QUERY},
    {"dcqlQuery": {"credentials": []}}, {"dcqlQuery": QUERY, "clientId": "wrong-client"},
    {"dcqlQuery": QUERY, "nonce": "short"}, {"dcqlQuery": QUERY, "responseCodeValidationRequired": True}])
def test_invalid_configuration_rejected_before_api(setup, monkeypatch, payload):
    monkeypatch.setenv("VERIFY_REQUEST_JSON", json.dumps(payload))
    with pytest.raises(RunnerError):
        instance(setup)


def test_variant_and_https_mismatch_rejected(setup, monkeypatch):
    setup["variant"]["request_method"] = "request_uri_signed"
    with pytest.raises(RunnerError, match="requires SD-JWT"):
        instance(setup)
    monkeypatch.setenv("VERIFY_API_URL", "http://localhost:8080/v1/verify")
    with pytest.raises(RunnerError, match="trusted HTTPS"):
        instance(setup)


@pytest.mark.parametrize("code", [400, 404, 500])
@responses.activate
def test_api_errors_never_fall_back_to_legacy(setup, code):
    responses.add(responses.POST, HOST + "/v2/vp-request", status=code, json={"error": "not echoed"})
    handoff = instance(setup)
    with pytest.raises(RunnerError, match=f"HTTP {code}"):
        handoff.drive(None, {"browser": {"uriInputRequests": [{"submitUrl": SUITE + "/authorize"}]}}, {})
    assert len(responses.calls) == 1


@responses.activate
def test_timeout_is_infrastructure_failure(setup, monkeypatch):
    from runner import common
    monkeypatch.setattr(common.time, "sleep", lambda _: None)
    responses.add(responses.POST, HOST + "/v2/vp-request", body=requests.Timeout("private request data"))
    with pytest.raises(RunnerError, match="after 3 attempts"):
        instance(setup).drive(None, {"browser": {"uriInputRequests": [{"submitUrl": SUITE + "/authorize"}]}}, {})
    assert len(responses.calls) == 3


@responses.activate
def test_expired_request_and_failed_verification_fail_positive_test(setup):
    handoff = instance(setup)
    context = {"submitted": True, "requestId": "req-1", "transactionId": "txn-1"}
    responses.add(responses.GET, HOST + "/vp-request/req-1/status", json={"status": "EXPIRED"})
    with pytest.raises(HandoffFailure, match="expired"):
        handoff.finish(context, "oid4vp-1final-verifier-happy-flow")
    responses.replace(responses.GET, HOST + "/vp-request/req-1/status", json={"status": "VP_SUBMITTED"})
    responses.add(responses.POST, HOST + "/v2/vp-results/txn-1", json={"transactionId": "txn-1", "allChecksSuccessful": False,
        "credentialResults": [{"allChecksSuccessful": False}]})
    with pytest.raises(HandoffFailure, match="successful verification"):
        handoff.finish(context, "oid4vp-1final-verifier-happy-flow")
