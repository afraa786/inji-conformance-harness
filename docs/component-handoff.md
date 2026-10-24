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

The exact alpha `certify-core/.../dto/OAuthAuthorizationServerMetadataDTO.java`
explicitly documents that authorization_endpoint is excluded for its browserless
IAR flow. `certify-service/.../services/OAuthAuthorizationServerMetadataService.java`
has a property for interactive-authorization-endpoint, not authorization_endpoint.
`OAuthController.processTokenRequest` dispatches pre-authorized grants without
private_key_jwt validation. Changing the metadata URL cannot supply that capability.

Authoritative tagged sources: [metadata DTO](https://github.com/inji/inji-certify/blob/v1.0.0-alpha.1/certify-core/src/main/java/io/mosip/certify/core/dto/OAuthAuthorizationServerMetadataDTO.java),
[metadata service](https://github.com/inji/inji-certify/blob/v1.0.0-alpha.1/certify-service/src/main/java/io/mosip/certify/services/OAuthAuthorizationServerMetadataService.java),
and [OAuth controller](https://github.com/inji/inji-certify/blob/v1.0.0-alpha.1/certify-service/src/main/java/io/mosip/certify/controller/OAuthController.java).
No supported native-AS variant was found in this suite's final issuer plan;
older draft plans do not establish final-version compatibility. This is not
fixed by substituting an invented endpoint or changing the diagnostic variant.

Targeted real rerun: plan `ygScrpZCgnBKj`, test `oE9sI3QaBhjlW28`, condition
CheckServerConfiguration, required field authorization_endpoint. Verify targeted
plan `bmimyUrL5IhZR`, test `FcOJuOzh90j7NuA`, backend SUCCESS followed by explicit
screenshot timeout. Evidence is retained under `results/targeted/`.

The inspected suite contains an optional automated evidence-page stand-in showing
only direct-post acceptance. It does not display Verify's actual deferred result
and is not used by this harness. No real Verify frontend/browser session currently
exists in this backend-only stack; adding a screenshot of a fabricated page would
not satisfy the verifier-result evidence requirement. A real UI/session and suite
review remain external work; no browser automation pass is claimed.

The exact alpha UI `verify-ui/src/components/Home/VerificationSection/VpVerification.tsx`
renders VpSubmissionResult from SDK onVPProcessed state. The tagged SDK's
`OpenID4VPVerification.tsx` owns creation, polling and result retrieval for that
browser session. Its properties accept transactionId but do not expose a way to
attach this running REST handoff's existing requestId. Capturing that real UI
requires a UI-owned flow and trusted browser/network configuration, rather than
rendering this driver's backend JSON as a purported verifier screenshot. That
integration has not been implemented or validated here.
