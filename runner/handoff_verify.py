"""Real Inji Verify v1.0.0-alpha.1 DCQL handoff.

Contract: tagged VPRequestController, VPResultController, VPRequestCreateDto,
AuthorizationRequestResponseDto and Constants; see docs/component-handoff.md.
No legacy fallback, JWT rewriting, fabricated results or relaxed Inji TLS.
"""
import json
import os
import re
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit

try:
    from .common import RunnerError, HandoffFailure, target_request
except ImportError:
    from common import RunnerError, HandoffFailure, target_request


POSITIVE_MODULES = {
    "oid4vp-1final-verifier-happy-flow", "oid4vp-1final-verifier-minimal-cnf-jwk",
    "oid4vp-1final-verifier-request-uri-method-post", "oid4vp-1final-verifier-request-uri-fetched-twice",
}


def validate_request(payload, client_id):
    if not isinstance(payload, dict):
        raise RunnerError("VERIFY_REQUEST_JSON must contain an object")
    allowed = {"clientId", "transactionId", "nonce", "dcqlQuery", "responseCodeValidationRequired"}
    if set(payload) - allowed:
        raise RunnerError("Verify alpha request contains unsupported/legacy fields")
    payload = dict(payload)
    payload.setdefault("clientId", client_id)
    if payload["clientId"] != client_id:
        raise RunnerError("Verify clientId does not match the rendered plan")
    if payload.get("responseCodeValidationRequired", False) is not False:
        raise RunnerError("This cross-device handoff requires responseCodeValidationRequired=false")
    if "nonce" in payload and (not isinstance(payload["nonce"], str) or not re.fullmatch(r"[A-Za-z0-9._~-]{16,}", payload["nonce"])):
        raise RunnerError("Verify nonce must be at least 16 URL-safe ASCII characters")
    query = payload.get("dcqlQuery")
    if not isinstance(query, dict) or not isinstance(query.get("credentials"), list) or not query["credentials"]:
        raise RunnerError("Verify alpha requires nonempty dcqlQuery.credentials")
    identifiers = set()
    for credential in query["credentials"]:
        if not isinstance(credential, dict):
            raise RunnerError("Invalid DCQL credential query")
        identifier = credential.get("id")
        if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", identifier) or identifier in identifiers:
            raise RunnerError("DCQL credential IDs must be unique nonempty identifiers")
        identifiers.add(identifier)
        if credential.get("format") not in {"dc+sd-jwt", "vc+sd-jwt"}:
            raise RunnerError("The SD-JWT suite variant requires a supported SD-JWT DCQL format")
        meta = credential.get("meta")
        values = meta.get("vct_values") if isinstance(meta, dict) else None
        if not isinstance(values, list) or not values or not all(isinstance(v, str) and v for v in values):
            raise RunnerError("SD-JWT DCQL query requires nonempty meta.vct_values")
        if credential.get("require_cryptographic_holder_binding", True) is not True:
            raise RunnerError("Conformance handoff must require cryptographic holder binding")
    # Defer full DCQL claim-set validation to the actual release validator.
    return payload


class VerifyHandoff:
    def __init__(self, target, plan):
        self.target = os.environ.get("VERIFY_API_URL", target).rstrip("/")
        self.public = target.rstrip("/")
        if any(urlsplit(url).scheme != "https" for url in (self.target, self.public)):
            raise RunnerError("Verify public and host API URLs must use trusted HTTPS")
        self.deadline = 0
        variant = plan["variant"]
        required = {"credential_format": "sd_jwt_vc", "client_id_prefix": "redirect_uri",
                    "request_method": "url_query", "response_mode": "direct_post"}
        if any(variant.get(key) != value for key, value in required.items()):
            raise RunnerError("Verify handoff requires SD-JWT, redirect_uri, url_query and direct_post variants")
        self.client_id = plan["config"]["client"]["client_id"]
        self.response_uri = self.public + "/v2/vp-submission/direct-post"
        # The tagged service echoes non-DID clientId in unsigned authorizationDetails.
        # The suite requires the redirect_uri prefix to identify the exact response_uri.
        if self.client_id != "redirect_uri:" + self.response_uri:
            raise RunnerError("Verifier client ID must be redirect_uri:<public v2 direct-post URL>")
        text = os.environ.get("VERIFY_REQUEST_JSON")
        try:
            if not text and os.environ.get("VERIFY_REQUEST_JSON_FILE"):
                text = Path(os.environ["VERIFY_REQUEST_JSON_FILE"]).read_text(encoding="utf-8")
            if not text:
                raise RunnerError("Set VERIFY_REQUEST_JSON or VERIFY_REQUEST_JSON_FILE for alpha DCQL")
            self.payload = validate_request(json.loads(text), self.client_id)
        except (OSError, ValueError) as error:
            raise RunnerError("Cannot read a valid Verify alpha DCQL request") from error

    def _result(self, context):
        if "verification" in context:
            return True
        status = target_request("GET", self.target + "/vp-request/" + quote(context["requestId"], safe="") + "/status", self.deadline)
        if not isinstance(status, dict) or status.get("status") not in {"ACTIVE", "EXPIRED", "VP_SUBMITTED"}:
            raise RunnerError("Verify returned an invalid request status")
        context["requestStatus"] = status["status"]
        if status["status"] == "EXPIRED":
            raise HandoffFailure("Verify request expired before presentation submission")
        if status["status"] != "VP_SUBMITTED":
            return False
        result = target_request("POST", self.target + "/v2/vp-results/" + quote(context["transactionId"], safe=""), self.deadline,
                                json={"skipStatusChecks": False, "statusCheckFilters": [], "includeClaims": False})
        if (not isinstance(result, dict) or type(result.get("allChecksSuccessful")) is not bool
                or result.get("transactionId") != context["transactionId"]
                or not isinstance(result.get("credentialResults"), list) or not result["credentialResults"]):
            raise RunnerError("Verify returned an invalid/empty v2 verification result")
        context["verification"] = result
        context["verifyOutcome"] = "SUCCESS" if result["allChecksSuccessful"] else "FAILED"
        return True

    def drive(self, api, info, context):
        if context.get("submitted"):
            self._result(context)
            if context.get("moduleName") in POSITIVE_MODULES and context.get("verifyOutcome") == "FAILED":
                raise HandoffFailure("Verify rejected the positive-module presentation")
            return False
        inputs = info.get("browser", {}).get("uriInputRequests", [])
        if not inputs:
            return False
        created = target_request("POST", self.target + "/v2/vp-request", self.deadline, json=self.payload, expected=201)
        if not isinstance(created, dict) or not all(isinstance(created.get(k), str) and created[k] for k in ("requestId", "transactionId")):
            raise RunnerError("Verify did not return requestId/transactionId")
        if created.get("requestUri"):
            raise RunnerError("Verify unexpectedly returned a signed requestUri for url_query variant")
        details = created.get("authorizationDetails")
        if not isinstance(details, dict):
            raise RunnerError("Verify did not return authorizationDetails")
        expected = {"clientId": self.client_id, "responseUri": self.response_uri, "responseType": "vp_token", "responseMode": "direct_post"}
        if any(details.get(key) != value for key, value in expected.items()) or details.get("dcqlQuery") != self.payload["dcqlQuery"]:
            raise RunnerError("Verify authorizationDetails do not match the configured request")
        if not isinstance(details.get("nonce"), str) or not details["nonce"]:
            raise RunnerError("Verify authorizationDetails are missing nonce")
        mapping = {"clientId": "client_id", "responseType": "response_type", "responseMode": "response_mode",
                   "responseUri": "response_uri", "nonce": "nonce", "dcqlQuery": "dcql_query"}
        params = {dst: json.dumps(details[src]) if isinstance(details[src], dict) else details[src]
                  for src, dst in mapping.items()}
        params["state"] = created["requestId"]
        submit = inputs[0].get("submitUrl")
        if not isinstance(submit, str):
            raise RunnerError("Suite did not expose uriInputRequests.submitUrl")
        # Preserve the actual verifier output. In particular, do not inject client_metadata
        # or change a protocol field to make a conformance condition pass.
        context.update(submitted=True, requestId=created["requestId"], transactionId=created["transactionId"])
        api.request("GET", submit, params=params, decode=False, retry_safe=False)
        return True

    def finish(self, context, name):
        if not context.get("submitted"):
            return
        submitted = self._result(context)
        # Negative modules can legitimately reject direct-post before storing a VP.
        if name in POSITIVE_MODULES and (not submitted or context.get("verifyOutcome") != "SUCCESS"):
            raise HandoffFailure("Verify did not confirm successful verification for a positive module")
