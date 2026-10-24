# Inji image verification

Verified on 2026-10-23 using read-only local Git inspection and official upstream
release/tagged Helm and Docker Hub metadata. The actual images were subsequently pulled and started locally; see docs/live-verification.md.

| Component | Compose default | Evidence |
| --- | --- | --- |
| Certify | `injistack/inji-certify-with-plugins:1.0.0-alpha.1` | [Tagged Helm values](https://github.com/inji/inji-certify/blob/v1.0.0-alpha.1/helm/inji-certify/values.yaml), [registry metadata](https://hub.docker.com/v2/repositories/injistack/inji-certify-with-plugins/tags/1.0.0-alpha.1) |
| Verify backend | `injistack/inji-verify-service:1.0.0-alpha.1` | [Tagged Helm values](https://github.com/inji/inji-verify/blob/v1.0.0-alpha.1/helm/inji-verify-service/values.yaml), [registry metadata](https://hub.docker.com/v2/repositories/injistack/inji-verify-service/tags/1.0.0-alpha.1) |

Observed registry index digests:

```text
Certify sha256:1579b2449f1a7213fe25de1f6a1509b5636f1fedf0d7f5c4cfd07b9f0fc5b346
Verify  sha256:064fcfa12773ec11834d5d769f2b6bb6bcc61cf9ae89ae918f8ae3934419907d
```

These are **alpha releases**, not evidence of a stable GA 1.0.0 release or of a
passing conformance run. Tag presence and deployment configuration were checked;
Runtime health and trusted HTTPS were subsequently tested. The conformance plans still report failures; see the live verification record.

The local Certify checkout has only tag `v0.14.0`. Verify has no local tags.
Both list only `upstream/master` (plus its HEAD alias). Their local Helm files
still specify 0.14.0 and 0.18.2, respectively. No reference folder was updated.

The official [Certify alpha release notes](https://docs.inji.io/inji-certify/releases/version-1.0.0-alpha.1)
describe final OID4VCI support, the `dc+sd-jwt` format and Redis-backed nonce
handling. The tagged VCICacheService also explicitly supports simple caching for a single pod; the generated local configuration retains its nonce/pre-auth cache names. The production Redis guidance does not require adding Redis to this single-instance development stack.

The official [Verify alpha release notes](https://docs.inji.io/inji-verify/releases/version-1.0.0-alpha.1)
describe DCQL and v2 API migration. The handoff now follows the tagged v2 request/result DTOs and the unversioned status route. Real positive backend verification has been observed; the suite still requires screenshot review. See docs/component-handoff.md for exact endpoints and evidence handling.

The same Verify release's tagged UI Helm values specify
`injistack/inji-verify-ui:1.0.0-alpha.1`. This harness drives the backend directly
and does not currently start a frontend container.
