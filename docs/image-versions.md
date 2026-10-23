# Inji image verification

Verified on 2026-10-23 using read-only local Git inspection and official upstream
release/tagged Helm and Docker Hub metadata. No image was pulled or started.

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
runtime health, credentials, and protocol compatibility have not been tested.

The local Certify checkout has only tag `v0.14.0`. Verify has no local tags.
Both list only `upstream/master` (plus its HEAD alias). Their local Helm files
still specify 0.14.0 and 0.18.2, respectively. No reference folder was updated.

The official [Certify alpha release notes](https://docs.inji.io/inji-certify/releases/version-1.0.0-alpha.1)
describe final OID4VCI support, the `dc+sd-jwt` format and Redis-backed nonce
handling. They require release-matched properties and credential configurations;
the old CSV/simple-cache configuration cannot simply be relabeled as 1.0.

The official [Verify alpha release notes](https://docs.inji.io/inji-verify/releases/version-1.0.0-alpha.1)
describe DCQL and v2 API migration. The current handoff was derived from the older
local checkout and still uses legacy presentation requests. It must be adapted
before an unattended alpha Verify run can succeed. Failures are reported, never
silently replaced with fabricated passing results.

The same Verify release's tagged UI Helm values specify
`injistack/inji-verify-ui:1.0.0-alpha.1`. This harness drives the backend directly
and does not currently start a frontend container.
