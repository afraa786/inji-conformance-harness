# Release-matched component handoff

Sources are pinned to **v1.0.0-alpha.1**. Inspection copies under ignored
`local/release-source/` are not modifications to the read-only reference repos.

## Verify

The actual [VPRequestController](https://github.com/inji/inji-verify/blob/v1.0.0-alpha.1/verify-service/src/main/java/io/inji/verify/controller/VPRequestController.java)
and [request DTO](https://github.com/inji/inji-verify/blob/v1.0.0-alpha.1/verify-service/src/main/java/io/inji/verify/dto/authorizationrequest/VPRequestCreateDto.java)
define `POST /v1/verify/v2/vp-request`, JSON `clientId`, optional `nonce` and
`transactionId`, `dcqlQuery`, and `responseCodeValidationRequired`. Old
`presentationDefinition` fields are rejected; there is no legacy fallback.

The selected suite variants are `sd_jwt_vc`, `redirect_uri`, `url_query`,
`direct_post`. The tagged service echoes a non-DID client ID as unsigned
`authorizationDetails`. For this flow, the client ID must be exactly
`redirect_uri:https://verify.test:8447/v1/verify/v2/vp-submission/direct-post`.
No signed request URI, DID or x509 client-ID support is claimed for this run.

The runner reads the suite's live `uriInputRequests.submitUrl` and delivers the
actual Verify response as `client_id`, `nonce`, `response_type`, `response_mode`,
`response_uri`, `dcql_query`, and `state=requestId`. It does **not** add missing
client metadata or rewrite fields to satisfy a test. The suite creates and signs
the credential and submits the VP to the real Verify endpoint.

The initial query requests `dc+sd-jwt` with `vct_values=["urn:eudi:pid:1"]`,
matching `CreateSdJwtKbCredential` in the inspected suite. Holder binding stays
enabled. Generated test keys include a real CA-signed `x5c` chain: an observed
alpha signature verifier error required this input; no signature validation is
disabled. A positive backend verification was subsequently observed.

The tagged status route remains `GET /vp-request/{requestId}/status` (without
`v2`). On `VP_SUBMITTED`, the handoff calls
`POST /v2/vp-results/{transactionId}` with `skipStatusChecks=false`, no status
filters, and no claims disclosure. It validates the transaction ID, nonempty
credential results, and boolean `allChecksSuccessful`. The actual JSON response
is saved beside the suite log; a positive module rejected by Verify fails.
Negative modules may legitimately reject direct-post without storing a VP.

The suite requires screenshot review when the verifier defers verification after
accepting direct-post. The backend result does not remove that suite requirement.
No screenshot or passing result is synthesized. Pending review therefore reaches
the configured WAITING timeout, is cancelled and reported FAILED. This is a
remaining obstacle to a completely unattended passing plan, even when backend
verification succeeded.

## Certify

`POST /v1/certify/pre-authorized-data` uses the tagged request's
`credential_configuration_id`, claims, expiry and 4–8 character alphanumeric
transaction code. A returned `credential_offer_uri` must advertise HTTPS; the
runner delivers it to the suite's exposed credential-offer endpoint. The intended
next step is native Certify token exchange and issuance; the observed suite run
is interrupted before that step by the metadata incompatibility below.

The generated SD-JWT credential configuration is separate from the upstream SQL's
LDP-only sample. Its fields/template follow the tagged
`api-test/.../Sd_Jwt/AddCredentialConfigSd_Jwt` data. Dummy identity data is clearly
synthetic; issuance is routed to the actual service, never to a stub. Successful
credential issuance has not been observed in these conformance runs.

Certify advertises an origin-only `credential_issuer`; its upstream nginx maps
root well-known URLs into `/v1/certify/.well-known/`. The local gateway now does
the same rather than changing returned metadata.

Two real compatibility limits remain. The inspected suite excludes anonymous
`client_auth_type=none`; its accepted diagnostic `private_key_jwt`/DPoP variants
are not evidence of Certify support. Also, the native AS advertises
`interactive_authorization_endpoint` (IAR), while this suite's
`CheckServerConfiguration` demands `authorization_endpoint`, even for this
pre-authorized run. The runner reports the resulting interruptions. It does not
invent an authorization endpoint or allowlist those failures.
