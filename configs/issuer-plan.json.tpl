{
  "_comment": "TODO(verify): variants are a JSON-encoded object to preserve the existing runner string contract. Confirm SD-JWT, private_key_jwt, DPoP, wallet-initiated authorization-code flow and credential ID against Inji 1.0.x. Supply registered clients/JWKs and trust anchors before running; render ALIAS, CLIENT_ID, CLIENT2_ID and CREDENTIAL_CONFIGURATION_ID manually. Register {{SUITE_URL}}/test/a/{{ALIAS}}/callback as redirect URI. See README for runner API blockers.",
  "planName": "oid4vci-1_0-issuer-test-plan",
  "variant": "{\"authorization_request_type\":\"simple\",\"client_auth_type\":\"private_key_jwt\",\"fapi_request_method\":\"unsigned\",\"sender_constrain\":\"dpop\",\"vci_authorization_code_flow_variant\":\"wallet_initiated\",\"vci_grant_type\":\"authorization_code\",\"fapi_profile\":\"vci\",\"credential_format\":\"sd_jwt_vc\",\"vci_credential_encryption\":\"plain\",\"openid\":\"plain_oauth\",\"fapi_response_mode\":\"plain_response\"}",
  "config": {
    "alias": "{{ALIAS}}",
    "description": "Inji Certify OID4VCI 1.0 issuer conformance",
    "vci": {
      "credential_issuer_url": "{{TARGET}}",
      "credential_configuration_id": "{{CREDENTIAL_CONFIGURATION_ID}}"
    },
    "client": {"client_id": "{{CLIENT_ID}}"},
    "client2": {"client_id": "{{CLIENT2_ID}}"}
  }
}
