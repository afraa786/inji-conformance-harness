# Certify alpha metadata failure and targeted source fix

Investigated 2026-10-24. No image was rebuilt or service restarted. The Docker
`desktop-linux` engine pipe is absent; a fresh issuer HTTP probe and E2E retest
could not be executed. The actual response below is saved wire evidence, not a
new request. Existing reference repositories and release caches were not changed.

## Observed request and causal chain

Evidence: `results/extent-certify/certify-evidence/wWOkznE8o4TU9/rDdfJXYAWcRN4x4-log.json`.
At 08:49:42 UTC the suite received HTTP 200, `content-length: 0`, no Content-Type,
and an empty body for `GET /.well-known/openid-credential-issuer` with
`Accept: application/jwt`. This was not a JSON document containing a null value.

1. Python creates and polls the signed-metadata module. The suite, not Python,
   fetches issuer metadata. Python's JSON Content-Type belongs to suite API calls;
   it cannot supply the issuer response's missing Content-Type.
2. The tagged `WellKnownController` maps the issuer endpoint with
   `produces = "application/json"`. Spring rejects JWT-only Accept before calling
   the metadata service. The unmodified controller's 406 is reproduced by the
   standalone Spring MVC regression.
3. The tagged exception advice routes `HttpMediaTypeNotAcceptableException` to
   `handleInternalControllerException`, which selects HTTP 200 with a JSON error
   wrapper. That wrapper is also unacceptable to a JWT-only client. Retained
   service logs contain `Failure in @ExceptionHandler` and
   `HttpMediaTypeNotAcceptableException: No acceptable representation`. Security's
   `LocalAuthenticationEntryPoint` delegates to that resolver without setting an
   error status itself. These paths explain the misleading empty 200, but the
   exact security/error-dispatch sequence of the 08:49:42 request is not captured
   in the available service logs. It remains to be verified live; the isolated
   MVC test does not load the product advice or security chain.
4. The pinned suite's `AbstractCondition.convertResponseForEnvironment` stores
   `response.getBody()` using Gson `addProperty`. Spring's absent String body
   becomes JSON null in `credential_issuer_metadata_endpoint_response.body`.
5. `VCIIssuerMetadataSignedTest` skips only a response whose MIME type is JSON.
   Missing Content-Type therefore fails `EnsureContentTypeApplicationJwt`; the
   suite then calls `VCIDecodeSignedCredentialIssuerMetadata`. Its `env.getString`
   throws on JsonNull before `SignedJWT.parse` is reached. This is not a bad JWT
   signature, Python JSON-decoding failure, or an issuance-handoff failure.
6. The module terminates before WAITING. `CertifyHandoff.drive` never creates an
   offer; `finish` is a no-op. The driver correctly preserves INTERRUPTED and exit
   1. A regression verifies that discovery interruptions cannot become SKIPPED
   or trigger pre-authorized issuance.

The gateway only rewrites the root well-known path to the Spring servlet path;
it neither sets Accept nor synthesizes the response. The corresponding unsigned
metadata module obtains real JSON, so this is representation negotiation rather
than a generally missing discovery route.

## Minimal source patch (not deployed)

`patches/certify-alpha-unsigned-metadata.patch` targets **only** the controller
from Certify `v1.0.0-alpha.1`, commit
`8fdf71656979a72fa8263766d4dec3cc25127b76`. It removes the JSON-only mapping
constraint on this endpoint and returns the same service DTO in a
`ResponseEntity` with explicit `application/json`. Other endpoints are unchanged.
It implements unsigned fallback, not signed metadata. No JWT, metadata field,
endpoint, or proxy response is fabricated.

[OID4VCI 1.0 section 12.2.2](https://openid.net/specs/openid-4-verifiable-credential-issuance-1_0.html#section-12.2.2)
requires unsigned JSON support, makes signed JWT support optional, and requires
the returned Content-Type. Matching Accept is recommended when that format is
supported. The pinned suite explicitly handles this fallback by skipping the
signed-only test. A SKIPPED result would not establish signed-metadata support.

The release controller fixture was fetched from the official pinned GitHub
contents API. Its LF-normalized SHA256 is
`84a2cf4ff2a81e70a5158cc86c69ecee24a33d241e001b0e311e249d5324a0f4`.
The regression checks that hash, applies the actual patch to a temporary copy,
compiles both versions with Java 21 and cached Spring 6.1.4/Jackson 2.15.4, then
executes MockMvc requests. SPI and DTO test doubles isolate the controller from
the database, signing, and security stack. Tests compare the serialized response
with the service fixture for JWT, JSON, mixed, wildcard, and absent Accept;
the release JWT request must fail before service invocation, and unrelated DID
negotiation must remain unchanged. This verifies controller behavior, not a
rebuilt Certify image or its complete security/error-handling behavior.

## Separate authorization-server incompatibility

The saved happy-flow log `74HbO4iYPUsBZiS-log.json` contains native AS metadata
with `interactive_authorization_endpoint` and
`require_interactive_authorization_request: true`, but no `authorization_endpoint`.
The tagged `OAuthAuthorizationServerMetadataDTO` explicitly documents that
omission; `OAuthAuthorizationServerMetadataService` has no conventional
authorization-endpoint property/setter. The pinned suite's
`CheckServerConfiguration` requires `authorization_endpoint`, `token_endpoint`,
and `issuer`. It fails before an offer is requested, even with the pre-authorized
variant. Renaming the IAR endpoint would assert different protocol semantics.
No supported property-only fix or compatible external AS deployment was
established. This patch intentionally does not attempt to solve that mismatch.

Sources verified read-only:

- [Release controller](https://github.com/inji/inji-certify/blob/8fdf71656979a72fa8263766d4dec3cc25127b76/certify-service/src/main/java/io/mosip/certify/controller/WellKnownController.java)
- [Release exception advice](https://github.com/inji/inji-certify/blob/8fdf71656979a72fa8263766d4dec3cc25127b76/certify-service/src/main/java/io/mosip/certify/advice/ExceptionHandlerAdvice.java)
- [Release AS DTO](https://github.com/inji/inji-certify/blob/8fdf71656979a72fa8263766d4dec3cc25127b76/certify-core/src/main/java/io/mosip/certify/core/dto/OAuthAuthorizationServerMetadataDTO.java)
- Suite source inspected with `git show f23736032b52739e5262c91263ee102a7bc6ce1a:<path>`
  in the read-only reference repository. Its current HEAD is different; working
  tree source alone was not treated as evidence for the deployed suite.

## Reproduction and remaining work

PowerShell, using retained dependencies and an existing Maven cache:

```powershell
$env:PYTHONPATH=(Join-Path (Get-Location) '.local-deps')
$env:CERTIFY_REGRESSION_M2='C:/Users/Afraa/.m2/repository'
python -m pytest runner/tests/test_certify_metadata_release.py runner/tests/test_runner.py -q -rs
```

Missing cached Java dependencies cause an explicit skip; no dependency installer
is invoked. CI's Python suite therefore does not guarantee the Java regression
ran unless a suitable cache is provided and the result contains no skips.

Executed locally using the retained Python dependencies and existing user Maven
cache:

```powershell
python -m pytest runner/tests/test_certify_metadata_release.py -q -rs --basetemp=local/pytest-certify-metadata-v2 --junitxml=results/certify-metadata-regression-v2.xml
python -m pytest runner/tests --ignore=runner/tests/test_tls.py -q -rs --basetemp=local/pytest-certify-targeted-final --junitxml=results/certify-targeted-final.xml
git diff --check
```

Results: **2 passed** for the isolated MVC regression; **50 passed, no skips**
for the suite excluding the TLS test; diff whitespace check passed. The first
MVC attempt failed because the test classpath omitted cached Spring AOP; adding
that jar fixed the test setup without installing or changing dependencies. Its
failed XML remains in `results/certify-metadata-regression.xml`. Existing result
summaries and evidence were not replaced. TLS/browser enhancements were not run.

Next, apply the patch to an **isolated checkout of the exact release**, build a
derived Certify image, and test JSON/JWT Accept responses through the real gateway
and security chain. Do not apply it blindly to the newer `local/testrigs` source:
that controller already has a different versioned method signature. After Docker
is restored, repeat only `oid4vci-1_0-issuer-metadata-test-signed` against that image
and confirm unsigned JSON plus an actual suite SKIPPED outcome. Full issuance
remains blocked by the separate AS/suite incompatibility. No E2E pass is claimed.
