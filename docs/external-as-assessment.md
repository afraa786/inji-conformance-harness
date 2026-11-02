# Local external authorization-server assessment

Assessment date: **2026-11-02**. No external AS is provisioned. No client is
registered. Native Certify is not an external AS. This assessment does not change
the previous conformance results or establish Milestone 1 acceptance.

Docker CLI is present, but the current `desktop-linux` engine check fails because
`//./pipe/dockerDesktopLinuxEngine` is absent. No service was started, restarted or
reconfigured. Discovery, login, tokens and issuance have **not** been tested live.
Public registry manifest inspection works independently of the Docker daemon.

## Decision

**Use Keycloak as the first isolated conventional-OIDC qualification candidate.**
Its ordinary AS role supplies real browser authorization, signed JWT client
authentication and DPoP capabilities. Keep Certify as the credential issuer; do
not enable Keycloak's credential issuer as a substitute for testing Certify.
This is a candidate integration, not a proven Certify-supported end-to-end recipe.

eSignet is the alternative with the clearest tagged Certify integration guidance
and an official local identity-backed demo stack. The inspected eSignet release
returns Bearer tokens and configures authorization-code grants, so it does not
solve the current pre-authorized-code/DPoP suite profile. Neither candidate is a
configuration-only solution to that profile. Do not silently change the existing
diagnostic plan to make it pass.

| Item | eSignet candidate | Keycloak candidate |
| --- | --- | --- |
| Exact source | `mosip/esignet` v1.6.1, commit `7157efb43fd5983b5a3b41d9d0eacb420f264a09` | `keycloak/keycloak` 26.8.1, commit `24ed1dadf3f246a555adb6d3d4a99e9b3003fb3b` |
| Release selection | Historical tagged Java stack assessed against Certify's Java-era integration; no claim it is the latest or currently maintained eSignet line | Latest non-prerelease reported by the official release API during this assessment; published 2026-10-13 |
| Main image manifest | `mosipid/esignet-with-plugins@sha256:5f50a5a7cdf6219187be295bebff4c867a84d579e6b777f519c9b5efce084afc` | `quay.io/keycloak/keycloak@sha256:3f3c5f8e03c614774b4bd9173b88391fefa4153bfc010d8012d59ad825377332` |
| Platforms observed | linux/amd64, linux/arm64 | linux/amd64, linux/arm64, linux/ppc64le; index also contains non-runtime descriptors |
| Deployment footprint | eSignet, matching login UI, Postgres, Redis, mock identity system | Keycloak with its built-in login UI and a dedicated Postgres database |
| Client authentication | Tagged default `private_key_jwt`, RS256 | Signed client JWT with registered public key/JWKS; configure explicitly |
| Current profile gap | Tagged token response is Bearer; authorization-code token DTO requires `code` | AS DPoP support does not add DPoP validation to Certify; Certify's pre-authorized codes are not Keycloak codes |

The matching eSignet UI manifest is
`mosipid/oidc-ui@sha256:d10b0d3bdf4eed07d912a64fa69035f7583f66a4cb5b7dc3577434c177aa72cc`.
The tagged compose references `mosipid/mock-identity-system:0.11.1`; its registry
request timed out, so its availability/digest remain **unverified**, not missing.
The tagged upstream compose also has floating database/cache tags and public demo
credentials. It must not be run unchanged as a reproducible harness deployment.
Pin all dependencies and generate private local credentials before deployment.

## Discovery and routing contract

The following are **source-derived route templates**, not observed responses or
invented metadata. `AS_ORIGIN` denotes a future canonical HTTPS origin that must
be selected, bound and reachable before use.

| Property | eSignet v1.6.1 routes/configuration | Keycloak realm `inji-conformance` routes |
| --- | --- | --- |
| OIDC discovery | `AS_ORIGIN/.well-known/openid-configuration`, routed by the tagged UI nginx to `/v1/esignet/oidc/.well-known/openid-configuration` | `AS_ORIGIN/realms/inji-conformance/.well-known/openid-configuration` |
| OAuth metadata | Tagged nginx exposes `/.well-known/oauth-authorization-server`; validate the suite's exact discovery request | Validate RFC 8414 discovery for the realm's path-based issuer, as well as OIDC discovery |
| Issuer | Tagged discovery map uses `mosip.esignet.domain.url`; token generation uses `mosip.esignet.discovery.issuer-id` | `AS_ORIGIN/realms/inji-conformance` |
| Authorization | `/authorize`, served by the actual eSignet login UI | `/realms/inji-conformance/protocol/openid-connect/auth` |
| Token | `/v1/esignet/oauth/v2/token` | `/realms/inji-conformance/protocol/openid-connect/token` |
| Public keys | `/.well-known/jwks.json`, routed to `/v1/esignet/oauth/.well-known/jwks.json` | `/realms/inji-conformance/protocol/openid-connect/certs` |

**eSignet issuer inconsistency:** tagged defaults set
`mosip.esignet.discovery.issuer-id=${mosip.esignet.domain.url}${server.servlet.path}`,
but the metadata maps use the domain alone. `TokenServiceImpl` signs `iss` using
the former. A local configuration must deliberately align metadata issuer and
signed token issuer using the supported properties, then prove equality on actual
responses. Do not copy the differing defaults into Certify and assume discovery
is valid. VC scopes also need `mosip.esignet.credential.scope-resource-mapping`
to give access tokens Certify's resource audience.

Use one stable browser/host/container-reachable issuer. Do not replace its host
with `localhost` inside containers or publish internal HTTP URLs in metadata.
The existing leaf certificate covers localhost, suite.test, certify.test,
verify.test and httpd; it does **not** cover a new AS hostname. Issue a separate
leaf for a new hostname, preserving existing CA/keys. Configure gateway forwarding,
AS public hostname, DNS and CA trust consistently. Do not use insecure TLS bypasses.

## Registered clients and callback URLs

The current rendered harness inputs are **configuration intent, not registration**:

| Setting | Current value / required action |
| --- | --- |
| Primary client ID | `DEV_ONLY_SUITE_CLIENT` — create an actual AS client with this ID or update harness inputs to the returned registered ID |
| Secondary client ID | `DEV_ONLY_SUITE_CLIENT_2` — separate actual client and public key for multiple-client tests |
| Exact current callback | `https://suite.test:8443/test/a/inji-certify/callback` from `render_plan` with alias `inji-certify`; confirm against the actual created suite runner before registration |
| Credential configuration | `HarnessSdJwtCredential` |
| Existing credential scope | `harness-test`, from generated credential configuration SQL; verify against the running issuer metadata after deployment |
| Existing profile | private_key_jwt, DPoP, pre_authorization_code, issuer_initiated, SD-JWT VC |

Register exact callbacks for each real client and invocation alias; do not use
wildcards or register Certify's credential endpoint as a login callback. The
callback belongs to the suite/wallet acting as client. The AS authorization URL
is not the callback. A host-only `localhost` callback is not interchangeable with
suite.test. Require state correlation and PKCE S256 for an authorization-code
qualification flow. Browser and suite must resolve the same callback host.

For **Keycloak**, create a dedicated realm and confidential OIDC clients with
standard flow enabled, signed-JWT client authentication and the appropriate
registered public JWK/JWKS. Keep password grant and service-account grants off
unless separately required; they do not prove user authorization. Configure
`harness-test` client scope and a resource audience matching Certify. Ensure an
access-token `client_id` claim matches the actual registered client: Certify
requires this claim and must not rely on `azp` being an alias. The inspected
Keycloak source sets issued-for and provides native claim/audience mappers; a
per-client mapper may publish that client's real identifier. Verify the signed
result, do not edit tokens or spoof user claims in the harness. Require DPoP for
the DPoP qualification client only when the resource server validates it too.

For **eSignet**, follow the tagged local README onboarding: obtain CSRF token,
create the OIDC client, register its public key, relying-party ID, allowed user
claims, ACRs, redirect URIs, grant types and client-auth methods, then use the
returned client ID. Register a genuine synthetic identity in the mock identity
system. Tagged DTOs expose these fields; registration is not a fabricated
discovery document. Keep the current pre-authorized plan blocked until an actual
compatible grant is implemented; adding a grant string to metadata is insufficient.

The suite currently generates client JWKs when absent. A provisioner must register
the exact public keys for each run, or securely supply matching pre-registered
client keys through an explicit plan mechanism. Existing renderer/template support
does not establish that onboarding. Never register an unrelated example key and
claim private_key_jwt is integrated. Never upload a private JWK to the AS.

## Certify contract and credential storage

The exact Certify source under `local/certify-alpha-metadata-validation` is commit
`8fdf71656979a72fa8263766d4dec3cc25127b76`. Its non-local
`AccessTokenValidationFilter` verifies JWT signature, time, issuer, audience,
`sub` and `client_id`, and only processes `Authorization: Bearer ...`.
`CertifyIssuanceServiceImpl` additionally maps the authorized scope to a credential
configuration, validates holder proof, and passes token claims to the data provider.

External-AS integration must set the actual `mosip.certify.authorization.url`,
optional `mosip.certify.credential-config.as-mapping`, exact
`mosip.certify.authn.issuer-uri`, actual `mosip.certify.authn.jwk-set-uri`, and
resource-specific `mosip.certify.authn.allowed-audiences`. Merely changing
`authorization_servers` only changes discovery; it does not configure token trust
or implement a grant. Preserve the real non-local validation path.

| Stored material | Owner and isolation requirements |
| --- | --- |
| User login credentials | Keycloak's dedicated database, or the eSignet authenticator/mock identity system; test identities only, with native password handling; no passwords in reports or realm-export fixtures |
| AS clients, public keys, realm settings | AS database; persist with a dedicated named volume and separate database role |
| AS signing private keys / eSignet key material | Native AS key management plus protected persistent storage; do not reuse Certify's VC signing keys |
| Client signing private keys, bootstrap admin and DB secrets | Ignored private `local/external-as/` files or secret references, protected host ACLs, least-privilege mounts; load without echoing; no tracked environment values or secret-bearing command arguments |
| Credential source records and issued-credential ledger | Existing Certify plugin/database, separate from the AS's authentication database |
| Tokens, authorization codes, browser cookies | Short-lived runtime state; omit from reports and screenshots; retain only sanitized outcomes |

eSignet's access-token `sub` is partner-specific; Keycloak's subject also must be
mapped to the intended test identity. Do not assume either is a UIN/CSV row ID.
The plugin receives token claims; qualify its exact subject-to-record mapping
using two distinct test users. Do not map all users to a single credential record.
Keep all existing databases/volumes; provision a separate AS database rather than
repurposing Certify's database. No credential or secret files were created here.

## Acceptance gates and next executable check

1. Restore the Linux engine, then run in Windows CMD:
   `docker --context desktop-linux info --format "{{.ServerVersion}}"`.
2. Prepare an isolated pinned Keycloak/Postgres deployment, protected bootstrap
   material, real public hostname/certificate and client registration. Validate
   compose without printing expanded secrets. Do not overwrite the existing stack.
3. Retrieve real OIDC and OAuth discovery over normal trusted TLS from host,
   browser and suite network; check issuer equality, actual reachable endpoints,
   JWKS, grants, signing/client-auth algorithms and S256/DPoP capabilities.
4. Execute user login, callback/state/PKCE validation and one-use code redemption
   with the registered private_key_jwt client; test wrong callback, replay and
   wrong client/key. Record only statuses and sanitized verified claims.
5. Prove issuer resource trust, real subject/record mapping and complete issuance.
   For the current DPoP profile, first implement supported resource-side proof
   validation (`htm`, `htu`, `ath`, `cnf.jkt`, signature, time and replay handling).
   Accepting a DPoP-bound token as an unchecked Bearer token is not a fix.
6. Establish AS-owned issuer offer/grant coordination. Native Certify's
   pre-authorized codes live in its own store; pointing token requests at a new
   AS does not transfer those codes. A separate authorization-code qualification
   plan may demonstrate supported behavior, but cannot be called a pass of the
   existing pre-authorized-code plan.
7. Only then rerun affected issuer modules, full Certify, Verify and combined
   workflows. Report every FAILED/INTERRUPTED/REVIEW result. OIDC login success
   alone does not establish OID4VCI conformance.

This turn performed source/registry/configuration assessment only. No live test,
deployment, client onboarding, database change or conformance rerun was performed.
No commits/pushes/resets/cleans were issued. Prior private configuration and local
dependencies were preserved.

## Evidence and primary sources

Ignored isolated evidence: `local/external-as-assessment/source-provenance.json`,
`keycloak-source-provenance.json`, `keycloak-release.json`,
`registry-assessment.json` and the exact fetched public source files. These record
content hashes; they contain no newly generated credentials. Registry evidence is
manifest availability, not an image pull or execution.

- [Certify exact tagged local-development guidance](https://github.com/inji/inji-certify/blob/8fdf71656979a72fa8263766d4dec3cc25127b76/docs/Local-Development.md)
- [eSignet exact local setup](https://github.com/mosip/esignet/blob/7157efb43fd5983b5a3b41d9d0eacb420f264a09/docker-compose/README.md)
- [eSignet exact deployment](https://github.com/mosip/esignet/blob/7157efb43fd5983b5a3b41d9d0eacb420f264a09/docker-compose/docker-compose.yml)
- [eSignet exact token generation](https://github.com/mosip/esignet/blob/7157efb43fd5983b5a3b41d9d0eacb420f264a09/oidc-service-impl/src/main/java/io/mosip/esignet/services/TokenServiceImpl.java)
- [Keycloak 26.8.1 release](https://github.com/keycloak/keycloak/releases/tag/26.8.1)
- [Keycloak exact discovery provider](https://github.com/keycloak/keycloak/blob/24ed1dadf3f246a555adb6d3d4a99e9b3003fb3b/services/src/main/java/org/keycloak/protocol/oidc/OIDCWellKnownProvider.java)
- [Keycloak OIDC endpoints](https://www.keycloak.org/securing-apps/oidc-layers)
- [Keycloak container deployment](https://www.keycloak.org/server/containers)
- [Keycloak database configuration](https://www.keycloak.org/server/db)
- [Keycloak signed-JWT clients and DPoP documentation (26.4.7 baseline)](https://www.keycloak.org/docs/26.4.7/server_admin/index.html)

The 26.4.7 guide is explanatory background, not a recommendation to deploy that
older version; actual qualification must use the selected exact version.
