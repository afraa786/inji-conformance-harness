# Inji conformance harness

Python is the REST driver; Java 21 TestNG adapters invoke it as a subprocess.
The implementation follows the OpenID suite's `scripts/conformance.py` and
`scripts/run-test-plan.py` contracts. No product endpoint or verification result
is mocked by the live harness.

The actual alpha images have been started and tested. Trusted HTTPS, real DCQL
handoff and positive Verify backend verification work. **The full conformance
plans do not pass.** Certify's native AS/IAR contract and the suite's screenshot
review requirement remain blockers. See [actual verification](docs/live-verification.md),
[handoff evidence](docs/component-handoff.md), and [image evidence](docs/image-versions.md).

## Setup

Use Python 3.10+ (CI uses 3.12), Java 21, Maven, Docker Compose v2, and bash/Git
Bash. Both local Inji api-test POMs require Java 21. Local execution used Java
21.0.5, Maven 3.9.9, Docker Engine 27.5.1 and Compose 2.32.4. The available local
Python was 3.8.10; tests ran, but cryptography warns that its support is deprecated.

From the repository root:

```bash
docker compose config --quiet
# Copy only when .env does not already exist; retain your private settings.
cp .env.example .env
python -m pip install -r requirements.txt
python runner/prepare_local.py
python -m pytest runner/tests -q --basetemp=local/pytest-tmp --junitxml=results/unit-tests.xml
```

Preparation fetches only named files from upstream tag `v1.0.0-alpha.1`, generates
private development keys, a local CA/SAN certificate, Java truststore, synthetic
identity data and alpha-matched properties/SQL under ignored `local/`. Existing
keys and `.env` are retained; generated config/SQL files are refreshed. It never
modifies reference repositories or resets an existing database.

Postgres entrypoint initialization runs **only on an empty volume**. Changes to
generated SQL do not migrate an existing database automatically. Do not delete
existing data to apply a fixture update; use a reviewed targeted migration.

## Start and execute

```bash
docker compose up -d --wait --wait-timeout 180 postgres mongodb server httpd certify verify
WAITING_TIMEOUT_SECONDS=15 bash run-full-stack-conformance.sh --component certify --no-up
WAITING_TIMEOUT_SECONDS=15 bash run-full-stack-conformance.sh --component verify --no-up
WAITING_TIMEOUT_SECONDS=10 bash run-full-stack-conformance.sh --combined --no-up
```

These are the diagnostic run modes exercised locally. The short WAITING budgets
surface unresolved screenshot interactions promptly; they do not establish a
certification pass. Without an override, WAITING timeout is 120s, per-module
timeout 600s and global timeout 60 minutes.

The wrapper normally starts the required services itself. `--no-up` reuses healthy
services; `--down` tears down project containers/network on exit, retaining
volumes. `--expected-failures-dir DIR` chooses files named
`expected-failures-certify.json` and `expected-failures-verify.json`.
`STACK_START_TIMEOUT_SECONDS` defaults to 1200, including image pulls;
`HEALTH_TIMEOUT_SECONDS` defaults to 600. Slow first image pulls can take much
longer than cached startup. Resume interrupted pulls with `docker compose pull`.

Exit 0 means no unexpected module failures; 1 means FAILED/INTERRUPTED remains;
2 means invalid configuration, missing services/results or infrastructure errors.
Empty results fail. REVIEW/SKIPPED never mean a test passed. No observed failure
has been automatically added to an expected-failure list.

## URLs, trust and release configuration

| Variable | Default / purpose |
| --- | --- |
| `CERTIFY_TAG`, `VERIFY_TAG` | `1.0.0-alpha.1`, alpha releases rather than GA |
| `SUITE_IMAGE`, `SUITE_FRONTEND_IMAGE` | Pinned to the exact downloaded server/frontend digests tested locally |
| `SUITE_URL` | `https://localhost:8443`, host Python entry point |
| `SUITE_PUBLIC_URL` | `https://suite.test:8443`, advertised Docker origin |
| `CERTIFY_TARGET` | `https://certify.test:8446`, matching actual `credential_issuer` |
| `CERTIFY_API_URL` | `https://localhost:8446/v1/certify`, host handoff API |
| `VERIFY_TARGET` | `https://verify.test:8447/v1/verify`, suite-reachable verifier |
| `VERIFY_API_URL` | `https://localhost:8447/v1/verify`, host handoff API |
| `REQUESTS_CA_BUNDLE` | `./local/tls/ca.crt`; Python verifies HTTPS |
| `OIDC_SUITE_INSECURE` | `false`; only an explicit true relaxes the isolated suite session |
| `OIDC_SUITE_TOKEN` | Optional bearer token; absent for the dev-profile suite |
| `POSTGRES_PASSWORD`, `CERTIFY_KEYSTORE_PASSWORD`, `VERIFY_KEYSTORE_PASSWORD` | Obvious development defaults supplied through `.env` |
| `DB_INIT_DIR`, `CERTIFY_CONFIG_DIR` | Generated `local/db-init` and `local/certify-config` |

The gateway terminates TLS with a certificate covering localhost and Docker DNS
aliases. Java services trust the generated CA via a certificate-only JKS. The CA
private key is not mounted into containers. The harness configures no global hostname/TLS bypass.
Internal upstream hops use HTTP only on the private Docker network. Host ports
bind to 127.0.0.1. The 8444 listener does not currently exercise mTLS.

The upstream suite's own protocol HTTP client bypasses certificate/hostname
validation internally; our truststore does not change that code. Separate normal
JDK HTTPS checks from the suite container verify this deployment's CA, expiry and
hostnames. This distinction also applies to CI; see [TLS evidence](docs/tls-validation.md).

For manual browser review, trust the development CA and add
`127.0.0.1 suite.test certify.test verify.test` to your hosts file yourself.
Automated host Python uses localhost URLs and needs no hosts-file change.
See [architecture](docs/architecture.md) and [troubleshooting](docs/troubleshooting.md).

Certify uses the alpha source's single-pod simple-cache implementation with its
nonce/pre-auth caches. This is not a multi-pod production configuration. Verify
uses its alpha JPA entities to build the development schema, avoiding stale PEX
DDL. Health checks require JSON `status=UP`, not just HTTP 200.

## Test data and renderer

Generated inputs are synthetic: `HarnessSdJwtCredential`, `Test Farmer`, a
DCQL query for `urn:eudi:pid:1`, and fresh signing keys. They exercise the actual
services. `VERIFIER_SIGNING_JWK_JSON_FILE` includes a real CA-signed `x5c` chain.
Private files stay under `local/` and are never committed by the harness.

The renderer loads literal `.env` values without executing shell code; exported
environment values win. It resolves placeholders recursively and preserves JSON
objects. Missing inputs fail before startup. Inputs include:

- `CREDENTIAL_CONFIGURATION_ID`, `CERTIFY_CLAIMS_JSON` or `_FILE`, `CERTIFY_TX_CODE`.
- `CLIENT_ID`, `CLIENT2_ID`; the suite generates missing client proof keys.
- `VERIFIER_CLIENT_ID`, `VERIFY_REQUEST_JSON` or `_FILE`, and
  `VERIFIER_SIGNING_JWK_JSON` or `_FILE`.
- Optional `ALIAS` and `REDIRECT_URI` overrides.

```bash
python runner/render_plans.py --component verify --target https://verify.test:8447/v1/verify --out results/rendered/verify-plan.json
python runner/conformance_runner.py --component verify --target https://verify.test:8447/v1/verify --plan results/rendered/verify-plan.json --expected-failures runner/expected-failures-verify.json --out results/results-verify.json
python runner/diff_results.py previous-results.json results/results-verify.json
```

The direct runner also accepts `--suite-url`, `--timeout-minutes`,
`--module-timeout-seconds`, `--waiting-timeout-seconds` and `--poll-interval`.
[Exact API sequence and schema](docs/api-automation.md).

To reproduce only the earliest blockers, using fresh diagnostic plans:

```bash
python runner/conformance_runner.py --component certify --target https://certify.test:8446 --module oid4vci-1_0-issuer-happy-flow --waiting-timeout-seconds 5 --out results/diagnostic/results-certify.json
python runner/conformance_runner.py --component verify --target https://verify.test:8447/v1/verify --module oid4vp-1final-verifier-happy-flow --waiting-timeout-seconds 5 --out results/diagnostic/results-verify.json
```

These subsets are labelled explicitly and are not complete-plan results. The
selected plain final verifier plan is itself alpha/non-certifiable in the suite;
a passing diagnostic run would not establish an OpenID certification award.

Expected-failure format is
`[{"module":"exact-suite-module-name","reason":"Tracked issue"}]`. Listed
failures become EXPECTED_FAILURE; a listed module that passes remains PASSED and
asks for removal in its detail. Infrastructure errors cannot be allowlisted.
The diff reports new failures/passes/status changes; absent baseline means no prior
modules. Variants distinguish repeated module names.

The wrapper archives prior summaries under unique `results/previous/` directories
before a fresh run and writes `results/diff-<component>.txt` when a baseline exists.
Read failures retry with backoff; ambiguous writes fail without retrying, preventing
duplicate sessions after a lost response. Results carry unique run IDs, UTC
timestamps and original suite test IDs. Use repeatable `--module exact-name` only
for diagnostic subsets; selected modules and the full plan size are recorded.

## Outputs and CI

- `results/results-certify.json`, `results/results-verify.json`: actual normalized results.
- `results/report-certify.md`, `results/report-verify.md`: component summaries.
- `results/results-combined.json`, `results/report-combined.md`: consolidated gate.
- `results/<component>-evidence/<planId>/`: suite logs, validated ZIP export and
  actual `*-verify-result.json` responses. Per-plan directories avoid mixing runs.
- `results/diagnostics/`: bounded redacted Compose logs/status, plus startup log.
- `results/unit-tests.xml`: tests of the harness, **not** product conformance proof.

Raw suite exports/logs can contain private test credentials. Review before sharing.
The CI workflow runs unit tests plus real certify, verify and combined jobs,
generates ephemeral development fixtures, retains nonzero exits, uploads reports
and diagnostics even after failure, and posts Markdown to the job summary.
CI has not been executed remotely in this session; its failure path was exercised
locally. Current real conformance failures mean those jobs should be red.

Optional MinIO upload uses `runner/upload_results.py` and
`requirements-upload.txt`, bucket `automationtests`, with all three
`MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`. No settings means no
upload; incomplete configuration/upload failure returns 2.

## Java 21 subprocess bridge

Both adapters were compiled and run with the real Python driver. TestNG reports
preserve each module result and fail the build appropriately. Examples, run from
the harness root:

```bash
mvn -f testrig-bridge/pom.xml test -Dtest=io.inji.testrig.apirig.injicertify.testscripts.OpenIDConformanceTest -Dconformance.root="$PWD" -Denv.endpoint=https://certify.test:8446 -Dconformance.results=results/bridge/results-certify.json -Dconformance.waitingTimeoutSeconds=5
mvn -f testrig-bridge/pom.xml test -Dtest=io.inji.testrig.apirig.injiverify.testscripts.OpenIDConformanceTest -Dconformance.root="$PWD" -Denv.endpoint=https://verify.test:8447/v1/verify -Dconformance.results=results/bridge/results-verify.json -Dconformance.waitingTimeoutSeconds=5
```

Properties include `conformance.python`, `conformance.runner`, `conformance.root`,
`conformance.target`, `conformance.results`, `conformance.suiteUrl`,
`conformance.plan`, `conformance.expectedFailures`, `conformance.waitingTimeoutSeconds`,
and `conformance.reportsDirectory`. The target resolver uses `env.endpoint`, the
real ConfigManager when available, then `ENV_ENDPOINT`. The bridge rejects stale,
empty or infrastructure-error results.

Standalone Maven uses TestNG's reports, not MOSIP Extent. To install into a
**writable** real api-testrig checkout:

```bash
bash testrig-bridge/install-into-testrig.sh /path/to/writable/inji-certify certify
bash testrig-bridge/install-into-testrig.sh /path/to/writable/inji-verify verify
```

Include the installed XML in the real master suite and use its existing bootstrap
and `EmailableReport` listener. Add OpenJSON 1.0.11 if absent. `Reporter.log` is
preserved for those hooks. Extent integration has not been observed here because
the standalone POM does not provide that framework runtime. Reference folders
remain read-only; the installer refuses them.

`.local-deps/` remains ignored and `git ls-files .local-deps` returned no files.
No dependencies were deleted. No commit or push is performed by these tools.
