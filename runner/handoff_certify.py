"""Pre-authorized issuance: PreAuthorizedCodeController + suite exposed endpoints.

Sources: inji-certify/docs/Pre-Authorized-Code.md, api-test/.../PreAuthCodeFlow,
suite/vci10issuer/AbstractVCIIssuerTestModule.java. No browser login is needed.
"""
import json
import os
from urllib.parse import parse_qs, urlsplit
try:
    from .common import RunnerError, target_request
except ImportError:
    from common import RunnerError, target_request


class CertifyHandoff:
    def __init__(self, target, plan):
        self.target = os.environ.get("CERTIFY_API_URL", target).rstrip("/")
        self.plan = plan
        self.deadline = 0

    def drive(self, api, info, context):
        exposed = info.get("exposed", {})
        endpoint = exposed.get("credential_offer_endpoint")
        # Each new offer wait gets a fresh single-use code. Do not replay in a poll loop.
        if not endpoint or context.get("offer_sent"):
            return False
        config = self.plan["config"]["vci"]
        claims = os.environ.get("CERTIFY_CLAIMS_JSON")
        if not claims and os.environ.get("CERTIFY_CLAIMS_JSON_FILE"):
            from pathlib import Path
            claims = Path(os.environ["CERTIFY_CLAIMS_JSON_FILE"]).read_text(encoding="utf-8")
        if not claims:
            raise RunnerError("Set CERTIFY_CLAIMS_JSON or CERTIFY_CLAIMS_JSON_FILE for the registered credential")
        try:
            claims = json.loads(claims)
            if not isinstance(claims, dict):
                raise ValueError()
        except ValueError as error:
            raise RunnerError("CERTIFY_CLAIMS_JSON must contain an object") from error
        payload = dict(credential_configuration_id=config["credential_configuration_id"], claims=claims, expires_in=600)
        if config.get("static_tx_code"):
            payload["tx_code"] = config["static_tx_code"]
        offer = target_request("POST", self.target + "/pre-authorized-data", self.deadline, json=payload)
        uri = offer.get("credential_offer_uri")
        if not isinstance(uri, str):
            raise RunnerError("Certify did not return credential_offer_uri")
        params = parse_qs(urlsplit(uri).query)
        offer_uri = params.get("credential_offer_uri", [uri])[0]
        # The suite validates HTTPS and retrieves the offer using its internal DNS.
        if urlsplit(offer_uri).scheme != "https":
            raise RunnerError("Certify credential_offer_uri must advertise HTTPS")
        api.request("GET", endpoint, params={"credential_offer_uri": offer_uri}, decode=False)
        context["offer_sent"] = True
        return True

    def finish(self, context, name):
        return None
