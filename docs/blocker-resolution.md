# Critical blocker investigation and scoped fixes

This project is not acceptance-ready. See the latest `artifacts/demo/final-validation-report.md`
for exact full-plan counts. Passing harness tests and backend rejection are distinct
from passing the suite's protocol and evidence requirements.

## Native Certify AS: still incompatible

Exact release: `8fdf71656979a72fa8263766d4dec3cc25127b76`.
`OAuthController` exposes form-POST `/oauth/iae`, returning IAR JSON, and
`/oauth/token`. Its metadata DTO deliberately excludes `authorization_endpoint`.
The native pre-authorized flow was exercised: create pre-authorized data, retrieve
the actual offer, exchange the single-use code and transaction code, receive an
access token. The returned token type is **Bearer**. Tokens were not printed.
Evidence: `artifacts/demo/evidence/blocker-resolution/native-preauth-flow.json`.

The old pinned suite and official replacement release-v5.3.4 require
authorization_endpoint/token_endpoint/issuer in CheckServerConfiguration before
the issuer handoff. The replacement's actual jar has no class referencing
interactive_authorization_endpoint; its source revision is
`23353b36957d6466010de767c812d2c91ed37638`. Native pre-authorization does not
establish conventional browser authorization, private_key_jwt client support or
DPoP sender-constrained tokens. A renamed discovery property cannot supply those.

Tagged CredentialConfigurationServiceImpl supports advertised AS URLs through
`mosip.certify.authorization.url` and `mosip.certify.credential-config.as-mapping`.
This permits a real external-AS integration, not a synthetic metadata URL. No
compatible external-AS/client/token/issuer deployment has been established here.
The supported paths require actual integration or upstream suite support for IAR;
no complete conventional authorization-flow fix is claimed or test bypass added.

## Verify metadata: native output fixed; UI evidence still blocked

Exact service release: `4c4289026968beb535d3dbdd500947152c43f708`.
The original AuthorizationRequestResponseDto has no clientMetadata property.
The harness previously forwarded the actual fields correctly; missing client
metadata was a native implementation omission, not a URL substitution problem.

| Actual field | Suite parameter / requirement | Finding |
| --- | --- | --- |
| clientId | client_id with redirect_uri prefix | Correct; equals the public response URI |
| responseType | response_type=vp_token | Correct |
| responseMode | response_mode=direct_post | Correct |
| responseUri | response_uri, HTTPS and exact client binding | Correct |
| nonce | Nonempty verifier-generated nonce | Correct; negative nonce checks now pass |
| dcqlQuery | dcql_query with SD-JWT format, vct and holder binding | Correct |
| requestId | state for native direct-post correlation | Forwarded as actual native request ID |
| clientMetadata | client_metadata | Missing originally; added in the native DTO |
| vp_formats_supported.dc+sd-jwt | Required selected-format capability | Published by the native service |
| sd-jwt_alg_values / kb-jwt_alg_values | Optional algorithm restrictions | Conservatively advertise ES256, actually verified for issuer and holder proofs |

The harness only forwards the native clientMetadata object; it does not inject
capabilities. The patch preserves DTO persistence with read-only JSON metadata
and release-compatible constructor parameter names. A first candidate's HTTP 500
was diagnosed as DTO conversion failure and corrected; failed candidate evidence
is retained. The corrected native create endpoint returns 201 with metadata.
Three affected runs against the original pinned suite have **no protocol-condition
FAILURE records** after this fix. Their final failure is evidence timeout.

The selected redirect_uri/url_query/direct_post profile does not require an
invented request_uri, signed request object, verifier JWKS or browser authorization
endpoint. Those belong to other profiles and were not fabricated.

Actual endpoints were probed through the CA-verified gateway; request creation,
suite plan APIs, health and status/result verification are reachable. Signed
status URIs are fetched by the native checker inside the deployment network.

Required evidence is a screenshot of the **actual verifier frontend result for
the same browser-owned transaction**, showing success for positive presentations
or rejection for negative presentations when direct-post returns 2xx. Uploading
that evidence can lead to REVIEW; it does not authorize automated certification
approval. Negative cases rejected by the native direct-post endpoint with 4xx
can finish PASSED without screenshot review. The test without optional credential
status is positive, not negative.

The REST handoff currently creates backend-owned requests. The tagged real UI SDK
owns its own create/poll/result session and cannot simply attach this request ID
through its documented properties. Genuine UI-owned flow integration, capture,
upload and manual review remain unimplemented/unverified. No audit-console image,
backend JSON screenshot or fabricated frontend result was uploaded as evidence.
This remaining failure originates in missing harness/UI evidence integration,
not in the now-correct backend verification outcomes.

## Revoked SD-JWT: native checking implemented and exercised

The actual deployed jar includes **vcverifier-jar-1.9.0**. Its SD-JWT type inherits
the default checkStatus implementation, which throws UnsupportedOperationException.
CredentialsVerifier catches it and returns an empty map. Verify's aggregate
success calculation accepts an empty status result. That path never fetched the
Token Status List, so stale-cache configuration was not its cause.

The explicitly derived native image adds TokenStatusListChecker after the
existing signature/schema validation. It handles the SD-JWT status.status_list
reference, fetches application/statuslist+jwt over ordinary CA/hostname-verified
HTTPS, authenticates its signature against the already-verified credential issuer
key, binds sub to the reference URI, validates timestamps/expiry/TTL, decompresses
bounded zlib data and reads LSB-first packed status values. Valid=0; nonzero fails.
Unavailable, malformed, expired, stale or wrongly signed lists fail closed with
separate error codes. Status absence remains valid because the claim is optional.

This is a deliberately scoped **same-issuer-key JWT status-list profile**. Delegated
status signers, redirects, HTTP providers, CWT status lists, and tokens with neither
expiry nor TTL are rejected/unsupported; no universal format support is claimed.
The explicit size limits and 10-second network timeouts are defensive resource
bounds, not invented performance benchmarks. The normal JVM truststore is retained.

No status cache is used; each evaluation fetches again with caching disabled.
Real signed-token HTTPS tests cover valid → revoked at the same URI, unavailable
provider, expired/TTL-stale lists, signature tampering, subject/index/type errors,
multi-bit ordering and optional absence. The native DTO persistence roundtrip is
also exercised in this fixture. These focused tests are not product conformance.

Actual suite presentations establish:

- Valid credential: native status valid and allChecksSuccessful=true.
- Revoked credential: native allChecksSuccessful=false, **CREDENTIAL_REVOKED**.
- Optional status absent: native accepted, as the actual suite requires.
- After suite status-provider cleanup, the same signed credential through the
  real native VC API has signature valid but status **STATUS_UNAVAILABLE**, and is
  rejected. It is not merely rejected because the credential signature is wrong.

Evidence is under `artifacts/demo/evidence/blocker-resolution/targeted-pinned/`,
including `unavailable-status-native-result.json`. Security/backend behavior is
fixed for this profile; the revoked suite module can still fail on required UI
evidence, which is a separate acceptance condition.

Protocol references:
[Token Status List draft-21](https://datatracker.ietf.org/doc/draft-ietf-oauth-status-list/21/),
[OID4VP 1.0 SD-JWT metadata](https://openid.net/specs/openid-4-verifiable-presentations-1_0.html).

## CI image pin: official immutable replacement

The old suite digest 899265e… returns manifest unknown from the public registry,
not an authentication or architecture error. The old local cache was retained.
Official **release-v5.3.4** is anonymously pullable for linux/amd64 and linux/arm64:

- Suite: `sha256:dcc4bd1fb7e9c00f048a67373fe2bec5ecf9feb45a6b5d55e237e5c30e5312c6`
- Matching frontend: `sha256:9a7850826fcc8690cd43373528f50e9551ba33bf8e4a40b67b13267b0aca3675`
- Actual suite jar revision: `23353b36957d6466010de767c812d2c91ed37638`.

Both manifests were inspected, pulled and deployed. The plan REST API and selected
modules were exercised without modifying suite tests. Compose defaults and
.env.example use the replacement pins; the private .env was preserved. The
blocker-resolution override selects the same exact images locally. Provenance is
in `suite-release-provenance.json`. Restoring pullability does not claim a clean
CI conformance run: the issuer and UI-evidence blockers still fail the workflows.

CI now builds the explicit native fixes with `tools/prepare_native_images.py`,
checks original jar/source hashes, applies the reviewed patches to isolated
copies, uses deterministic added ZIP-entry timestamps, runs native status/DTO
tests, and retains build provenance. This same build path was executed locally.
No new remote workflow was triggered for uncommitted changes; remote validation
is still unverified. No image was pushed or upstream registry modified.

## Performance budgets

See [execution-time budget configuration](benchmark-thresholds.md). Configurable
component, module and combined thresholds are implemented, measured, reported and
enforced through runner/combined/TestNG/CI exits. Defaults are null/NOT_CONFIGURED,
because no approved numeric SLO was supplied. Numeric production limits are not
invented from a failing historical run. Operational performance acceptance remains
unevaluated until an approved policy is provided.

A real conformance module PASSED while a deliberately synthetic zero-second budget
FAILED and the process returned 1. Its protocol result remained PASSED. This is
fault-injection proof of the gate, not a recommended operational limit. See
`benchmark-live-proof/` and `fault-injection-zero-budget.json`.
