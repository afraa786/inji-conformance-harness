"""Create Verify VP request, deliver its query to suite uriInputRequests, read outcome.

Sources: verify-service/.../VPRequestCreateDto.java, VPRequestResponseDto.java,
VerifiablePresentationRequestServiceImpl.java; suite/static/js/log-detail.js
handleSubmitUri. This is the same HTTP handoff as the UI, without a browser.
"""
import json
import os
from pathlib import Path
from urllib.parse import urlencode, quote
try:
    from .common import RunnerError, HandoffFailure, target_request
except ImportError:
    from common import RunnerError, HandoffFailure, target_request


class VerifyHandoff:
    def __init__(self, target, plan):
        self.target = os.environ.get("VERIFY_API_URL", target).rstrip("/")
        self.plan = plan
        self.deadline = 0

    def drive(self, api, info, context):
        inputs = info.get("browser", {}).get("uriInputRequests", [])
        if not inputs or context.get("submitted"):
            return False
        payload_text = os.environ.get("VERIFY_REQUEST_JSON")
        if not payload_text and os.environ.get("VERIFY_REQUEST_JSON_FILE"):
            payload_text = Path(os.environ["VERIFY_REQUEST_JSON_FILE"]).read_text(encoding="utf-8")
        if not payload_text:
            raise RunnerError("Set VERIFY_REQUEST_JSON or VERIFY_REQUEST_JSON_FILE (VPRequestCreateDto)")
        try:
            payload = json.loads(payload_text)
            if not isinstance(payload, dict) or not (payload.get("presentationDefinition") or payload.get("presentationDefinitionId")):
                raise ValueError()
        except ValueError as error:
            raise RunnerError("VERIFY_REQUEST_JSON requires a presentation definition") from error
        payload.setdefault("clientId", self.plan["config"]["client"]["client_id"])
        created = target_request("POST", self.target + "/vp-request", self.deadline, json=payload)
        if not all(isinstance(created.get(k), str) and created[k] for k in ("requestId", "transactionId")):
            raise RunnerError("Verify did not return requestId/transactionId")
        if created.get("requestUri"):
            params = {"client_id": payload["clientId"], "request_uri": created["requestUri"]}
        else:
            details = created.get("authorizationDetails", {})
            mapping = {"clientId": "client_id", "responseType": "response_type", "responseMode": "response_mode",
                       "responseUri": "response_uri", "nonce": "nonce", "presentationDefinition": "presentation_definition"}
            params = {dst: json.dumps(details[src]) if isinstance(details[src], dict) else details[src]
                      for src, dst in mapping.items() if src in details}
            # Constants.RESPONSE_MODE is direct_post; legacy DTO omits it.
            params.setdefault("response_mode", "direct_post")
            params["state"] = created["requestId"]
            if not all(params.get(k) for k in ("response_uri", "nonce", "presentation_definition")):
                raise RunnerError("Incomplete Verify authorizationDetails")
        submit = inputs[0].get("submitUrl")
        if not isinstance(submit, str):
            raise RunnerError("Suite did not expose uriInputRequests.submitUrl")
        api.request("GET", submit + "?" + urlencode(params), decode=False)
        context.update(submitted=True, requestId=created["requestId"], transactionId=created["transactionId"])
        return True

    def finish(self, context, name):
        if not context.get("submitted"):
            return
        status = target_request("GET", self.target + "/vp-request/" + quote(context["requestId"], safe="") + "/status", self.deadline)
        if status.get("status") != "VP_SUBMITTED":
            raise HandoffFailure("Verify did not confirm VP_SUBMITTED")
        result = target_request("GET", self.target + "/vp-result/" + quote(context["transactionId"], safe=""), self.deadline)
        if result.get("vpResultStatus") not in {"SUCCESS", "FAILED"}:
            raise RunnerError("Verify did not return vpResultStatus")
        context["verifyOutcome"] = result["vpResultStatus"]
        if name.endswith("happy-flow") and result["vpResultStatus"] != "SUCCESS":
            raise HandoffFailure("Verify rejected the happy-flow presentation")
