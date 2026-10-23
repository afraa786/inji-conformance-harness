{
  "_comment": [
    "Sources: inji/inji-verify tag v1.0.0-alpha.1 VPRequestCreateDto, AuthorizationRequestResponseDto, Constants and VerifiablePresentationRequestServiceImpl.",
    "Alpha accepts DCQL and echoes a non-decentralized_identifier clientId in unsigned authorizationDetails. redirect_uri clientId equals the public v2 direct-post URI with its scheme prefix; response_mode is direct_post.",
    "The suite creates SD-JWT credentials with vct urn:eudi:pid:1. A real result is fetched with status checks enabled; no client_metadata or verification outcome is fabricated."
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
