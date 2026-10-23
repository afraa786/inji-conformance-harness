# Inji conformance harness

Python remains the REST driver, built against the OpenID suite's
`scripts/conformance.py` and `scripts/run-test-plan.py` contracts. The Java 21
TestNG bridge invokes it as a subprocess and reports each module separately.
No Python file has been removed and no Java REST port is present.

The defaults now use verified **1.0.0-alpha.1** Certify and Verify backend images.
See [image evidence](docs/image-versions.md). These are alpha releases; a local
end-to-end pass has not been observed. Deployment fixtures, TLS and the Verify
v2 handoff remain incomplete.

## First checks

Prerequisites: Docker Compose v2 for your later live run, Python 3.10+, Git Bash
on Windows or bash on Linux, and Java 21/Maven for the bridge. Both reference
`api-test/pom.xml` files set compiler source/target to **21**, overriding the older
Java 11 requirement in the problem statement.

```bash
docker compose config --quiet
cp .env.example .env
python -m pip install -r requirements.txt
python -m pytest runner/tests -q
bash -n run-full-stack-conformance.sh
python -m py_compile runner/*.py
mvn -q -o -f testrig-bridge/pom.xml validate
```

The unit tests use mocked HTTP, not a running suite or Inji services. Offline
Maven validation checks the project model; it does not compile or run Java tests.

## Prepare the live stack

1. Prepare `local/db-init` with reviewed alpha-version schemas for
   `inji_certify`/`certify` and `inji_verify`/`verify`. Initialization runs only
   on a fresh database volume. Reference SQL lives under each repository's
   `db_scripts/`; do not modify those reference folders.
2. Prepare `local/certify-config` with release-matched `certify-default.properties`,
   `certify-csvdp-farmer.properties`, CSV test identity data, issuer/keystore setup,
   and registered credential configurations. Compose mounts it at `/home/inji/config`.
   The alpha's nonce handling needs Redis configuration; old simple-cache fixtures
   are insufficient. Supply the development database password through `.env`.
3. Configure trusted HTTPS Inji hostnames reachable by the suite. Current internal
   HTTP addresses are bootstrap defaults and cannot satisfy protocol HTTPS checks.
   The suite frontend is service `httpd` (the upstream nginx image), advertising
   `https://httpd:8443`; the host driver accesses `https://localhost:8443`.
   Inji trust stores must trust the suite certificate; Inji HTTPS calls from Python
   use normal certificate validation. Configure `REQUESTS_CA_BUNDLE` if needed.
4. Set plan inputs in `.env` or exported variables. `render_plans.py` resolves
   all placeholders, preserves JSON objects and rejects missing inputs. It never
   executes `.env` as shell code. Shell environment values take precedence.
5. Adapt the remaining Verify alpha v2/DCQL handoff before expecting unattended
   success. The local reference's legacy `/vp-request` flow is not the alpha API.
   See [image evidence](docs/image-versions.md) and [API automation](docs/api-automation.md).

After preparation, run:

```bash
bash run-full-stack-conformance.sh --component certify --down
bash run-full-stack-conformance.sh --component verify --down
bash run-full-stack-conformance.sh --combined --down
```

`--no-up` reuses healthy services. `--down` tears down project containers/network
after preflight, including failures; it retains volumes. `--expected-failures-dir`
selects a directory with `expected-failures-certify.json` and
`expected-failures-verify.json`. The whole-stack health timeout defaults to 600s
(`HEALTH_TIMEOUT_SECONDS` overrides it).

Each runner writes `results/results-<component>.json` and component evidence.
Combined mode attempts both runs, writes `results/results-combined.json` and
`results/report-combined.md`, and fails on either runner error or unexpected
FAILED/INTERRUPTED results. Startup failures exit before combined reporting.
Missing results and empty plans fail. REVIEW/SKIPPED are reported as such; they
do not mean that a certification test passed.

## Test data and script interfaces

Private input files stay under ignored `local/`. Required inputs depend on the
component:

| Input | Purpose |
| --- | --- |
| `CREDENTIAL_CONFIGURATION_ID` | Registered Certify metadata ID |
| `CERTIFY_CLAIMS_JSON` or `_FILE` | Claims accepted by that credential configuration |
| `CLIENT_ID`, `CLIENT2_ID`, `CERTIFY_TX_CODE` | Suite client IDs and pre-authorization test code |
| `VERIFIER_CLIENT_ID` | Verifier registration matching the selected suite variant |
| `VERIFIER_SIGNING_JWK_JSON` or `_FILE` | Private test credential signing JWK |
| `VERIFY_REQUEST_JSON` or `_FILE` | Current legacy handoff's presentation request body |
| `ALIAS`, `REDIRECT_URI` | Optional overrides; renderer derives defaults |

`CERTIFY_TARGET`/`VERIFY_TARGET` are suite-reachable service URLs.
`CERTIFY_API_URL`/`VERIFY_API_URL` are host-Python-reachable handoff URLs.
`SUITE_URL` is host-visible; `SUITE_PUBLIC_URL` is its advertised Docker origin.
`OIDC_SUITE_INSECURE=true` permits the development self-signed certificate only
for the suite session; set false for trusted TLS. `OIDC_SUITE_TOKEN` is optional
and never forwarded to Inji or redirect destinations.

```bash
python runner/render_plans.py --component certify --target https://issuer.example/v1/certify --out results/rendered/certify-plan.json
python runner/conformance_runner.py --component certify --target https://issuer.example/v1/certify --plan results/rendered/certify-plan.json --out results/results-certify.json --expected-failures runner/expected-failures-certify.json
python runner/diff_results.py previous-results.json results/results-certify.json
```

Runner options include `--suite-url`, `--timeout-minutes` (60),
`--module-timeout-seconds` (600), `--waiting-timeout-seconds` (120), and
`--poll-interval` (3). Exit codes are 0 expected outcomes, 1 unexpected test
failure, and 2 configuration/infrastructure failure. [REST sequence and schema](docs/api-automation.md).

Expected-failure lists start empty. Format:

```json
[{"module": "exact-suite-module-name", "reason": "Tracked issue explaining the exception"}]
```

Listed failures/interruption become EXPECTED_FAILURE; listed skips become
EXPECTED_SKIP. A newly passing entry remains PASSED and asks for removal in its
detail. Infrastructure errors cannot be allowlisted. The diff tool reports newly
failing/passing, changed statuses and removals; a missing baseline means no prior
modules. Variant values distinguish multiple instances of the same module.

`upload_results.py` optionally uploads to MinIO's `automationtests` bucket when
all three `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY` and `MINIO_SECRET_KEY` are set;
install `requirements-upload.txt` first. Partial configuration or upload failure
returns 2. With no MinIO configuration it returns 0 without uploading.

## Java bridge

`testrig-bridge/pom.xml` compiles both existing adapters using Java 21, TestNG
and the same OpenJSON parser as Certify's testrig. The adapters use
`env.endpoint`, the real api-testrig `ConfigManager.getproperty("env.endpoint")`
when available, then `ENV_ENDPOINT`. They propagate runner exit failures and
reject stale, empty or invalid results. TestNG `Reporter.log` feeds installed
report listeners; no independent Extent API is assumed.

After configuring a live stack, run the standalone bridge yourself:

```bash
mvn -f testrig-bridge/pom.xml test -Dconformance.root="$(pwd)" -Denv.endpoint=https://issuer.example/v1/certify -Dtest=io.inji.testrig.apirig.injicertify.testscripts.OpenIDConformanceTest
```

Use the equivalent `injiverify` class and Verify endpoint for Verify. Configuration
properties: `conformance.python`, `conformance.runner`, `conformance.root`,
`conformance.target`, `conformance.results`, `conformance.suiteUrl`,
`conformance.plan`, `conformance.expectedFailures`. Environment equivalents are
`PYTHON`, `CONFORMANCE_RUNNER`, `CONFORMANCE_ROOT`, `CONFORMANCE_TARGET`,
`CONFORMANCE_RESULTS`, `SUITE_URL`, `CONFORMANCE_PLAN`, `CONFORMANCE_EXPECTED_FAILURES`.

To install into a real api-testrig, copy the Java class into its matching
`src/main/java/io/inji/testrig/apirig/inji<component>/testscripts` package and
include the supplied component XML in its TestNG suite. Preserve the existing
`EmailableReport` listener. Add OpenJSON 1.0.11 if that checkout lacks it.
The standalone POM intentionally uses no unavailable testrig listener.

## CI and current limitations

The workflow retains Java 21 and Python setup and invokes the Python wrapper as
a component matrix. It uploads available results and tears down after failures.
Private deployment/key fixtures still need provisioning; it does not fabricate
passing results. No commits, pushes or deployments are performed by this work.

Inline verification comments identify remaining deployment requirements beside
their configuration: TLS, schemas, Certify fixture setup, health-command availability,
suite version pinning, and Verify alpha v2/evidence handling. A test run is still
required before calling this an operational full-stack deployment.

`.local-deps/` is ignored for new files. Some dependency files are already tracked
in the current Git history; adding an ignore rule does not untrack them. They were
left intact. To remove only those index entries yourself while retaining the
installed files, run `git rm -r --cached .local-deps` before your next commit.
