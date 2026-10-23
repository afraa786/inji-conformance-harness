{
  "_comment": "TODO(verify): confirm SD-JWT VC, x509_san_dns client_id_prefix, signed request_uri and direct_post against Inji 1.0.x. Render ALIAS and VERIFIER_CLIENT_ID manually and add credential.signing_jwk (private JWK matching trusted issuer). The verifier plan receives an authorization request through the suite UI/API; TARGET alone cannot initiate Inji. Automate request creation, wallet submission and evidence upload before unattended CI. Suite base: {{SUITE_URL}}; Inji target: {{TARGET}}.",
  "planName": "oid4vp-1final-verifier-test-plan",
  "variant": "{\"vp_profile\":\"plain_vp\",\"credential_format\":\"sd_jwt_vc\",\"client_id_prefix\":\"x509_san_dns\",\"request_method\":\"request_uri_signed\",\"response_mode\":\"direct_post\"}",
  "config": {
    "alias": "{{ALIAS}}",
    "description": "Inji Verify OID4VP 1.0 verifier conformance",
    "client": {"client_id": "{{VERIFIER_CLIENT_ID}}"}
  }
}
