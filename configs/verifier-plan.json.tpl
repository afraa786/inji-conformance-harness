{
  "_comment": [
    "Sources: inji-verify/docs/OpenID4VPCrossDeviceFlow.md (Draft 23, Presentation Exchange), docs/SD-JWT-Support.md; verify-service Constants.RESPONSE_MODE=direct_post; suite VP1FinalVerifierTestPlan.java.",
    "TODO(verify): final suite only supports redirect_uri/x509_san_dns/x509_hash client prefixes; Inji reference signs with a DID key and uses Presentation Exchange. No supported final-1.0 combination is evidenced. redirect_uri/url_query are suite-valid diagnostic defaults, not compatibility claims. Final DCQL and evidence upload require release-specific support."
  ],
  "planName": "oid4vp-1final-verifier-test-plan",
  "variant": {
    "vp_profile": "plain_vp",
    "credential_format": "sd_jwt_vc",
    "client_id_prefix": "redirect_uri",
    "request_method": "url_query",
    "response_mode": "direct_post"
  },
  "config": {
    "alias": "{{ALIAS}}",
    "description": "Inji Verify OID4VP 1.0 verifier conformance",
    "client": {
      "client_id": "{{VERIFIER_CLIENT_ID}}"
    },
    "credential": {
      "signing_jwk": "{{VERIFIER_SIGNING_JWK_JSON}}"
    }
  }
}
