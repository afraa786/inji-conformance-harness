{
  "_comment": [
    "Sources: inji-certify/docs/Pre-Authorized-Code.md and docs/SD-JWT-Support.md; suite VCIIssuerTestPlan.java and variant enums.",
    "Pre-authorized flow avoids browser login; client_auth_type=none follows anonymous pre-authorized access.",
    "TODO(verify): suite sender_constrain has only mtls/dpop; Certify documents Bearer. dpop is a suite-valid diagnostic choice, not a claim of Inji DPoP support. Confirm against a verified 1.0.x release."
  ],
  "planName": "oid4vci-1_0-issuer-test-plan",
  "variant": {
    "authorization_request_type": "simple",
    "client_auth_type": "none",
    "fapi_request_method": "unsigned",
    "sender_constrain": "dpop",
    "vci_authorization_code_flow_variant": "issuer_initiated",
    "vci_grant_type": "pre_authorization_code",
    "fapi_profile": "vci",
    "credential_format": "sd_jwt_vc",
    "vci_credential_encryption": "plain",
    "openid": "plain_oauth",
    "fapi_response_mode": "plain_response"
  },
  "config": {
    "alias": "{{ALIAS}}",
    "description": "Inji Certify OID4VCI 1.0 issuer conformance",
    "vci": {
      "credential_issuer_url": "{{TARGET}}",
      "credential_configuration_id": "{{CREDENTIAL_CONFIGURATION_ID}}",
      "static_tx_code": "{{CERTIFY_TX_CODE}}"
    },
    "client": {
      "client_id": "{{CLIENT_ID}}",
      "redirect_uri": "{{REDIRECT_URI}}"
    },
    "client2": {
      "client_id": "{{CLIENT2_ID}}"
    }
  }
}
