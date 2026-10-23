# Inji conformance harness

This repository contains orchestration and result tooling for a local OpenID
conformance suite. **It is not yet an unattended, working 1.0.x deployment.**
The checked-in runner and TestNG bridges are preserved as requested. The stack
and CI deliberately fail until the deployment fixtures and plan inputs exist.

The read-only reference sources establish:

- `inji-certify/docker-compose/docker-compose-injistack/docker-compose.yaml`
  and `helm/inji-certify/values.yaml`: `injistack/inji-certify-with-plugins:0.14.0`,
  Postgres 15, CSV data-provider configuration, and `/home/mosip/config`.
- `inji-verify/docker-compose/docker-compose.yml` and `docker-compose-ci.yaml`:
  `injistack/inji-verify-service:0.18.2`, database variables, schemas, and health path.
- `conformance-suite/docker-compose-prebuilt.yml`, `Dockerfile`, and
  `nginx/Dockerfile`: suite server, Mongo 6.0.13 and nginx TLS frontend. The
  Compose service named `httpd` uses this verified nginx image.
- `scripts/run-test-plan.py`, `scripts/conformance.py`, `.gitlab-ci/run-tests.sh`,
  `scripts/test-configs-rp-against-op/`, `VCIIssuerTestPlan.java`, and
  `VP1FinalVerifierTestPlan.java`: real plan names, variant values and config fields.

No reference files or sample private keys were copied into this repository.

## Deployment preparation

1. Install Docker Compose v2, Git Bash (Windows) or bash (Linux), and Python 3.10+.
   Copy `.env.example` to `.env` and install `requirements.txt`.
2. Replace the reference image tags with verified released 1.0.x tags. The
   references do not identify any, so the defaults retain their documented tags.
   Pin a suite release compatible with the inspected source instead of `latest`.
3. Prepare `local/db-init` with reviewed, release-matched initialization for
   `inji_certify`/`certify` and `inji_verify`/`verify`. Initialization runs only on
   a fresh Postgres volume. This harness never deletes volumes automatically.
4. Prepare `local/certify-config/certify-default.properties` and
   `certify-csvdp-farmer.properties`, local CSV fixture data, keystore settings,
   issuer credentials and registered clients. Use Postgres hostname `postgres`
   and the `.env` development password. Configure the CSV data provider to avoid
   a separate mock identity service. Configure a local authorization server;
   the reference's remote eSignet mock is not a self-contained dependency.
5. Replace non-URL variables in plan templates with your registrations. Add
   client signing JWKs, credential trust anchors and verifier signing credentials
   from private local inputs. Do not commit keys. Variants are JSON-encoded
   strings because the existing runner requires a string; decode them into an
   object when adapting the runner to the real API.

`{{TARGET}}` and `{{SUITE_URL}}` are the only variables the existing runner renders.
Alias, client IDs and credential configuration ID remain explicit inputs;
the shell script rejects unresolved inputs before starting containers.
The issuer callback is `https://httpd:8443/test/a/<alias>/callback`.
The verifier target is an application to drive, not a suite config field.

All containers share one Compose network and resolve `certify`, `verify`,
`postgres`, `mongodb`, `server` and `httpd`. The host Python runner calls
`https://localhost:8443`; the suite advertises `https://httpd:8443` for callbacks.
Host-based interactive browsers need a matching `httpd` hosts entry pointing to
127.0.0.1, or a different shared hostname with equivalent container DNS aliases.
The upstream frontend generates a self-signed certificate (CN localhost).
The existing runner disables certificate verification. Inji's trust stores and
hostname validation still need proper development certificates. HTTP service
URLs in Compose are bootstrap defaults and cannot establish protocol conformance.

## Runner blockers

TODO(verify): adapt the existing runner to the inspected suite API before live
use. `scripts/conformance.py` creates plans with `planName` and JSON `variant`
as query parameters and **config alone** as the body. The current runner posts
an envelope instead. Plan modules use `testModule` and per-module variants;
the runner does not recognize that name or preserve those variants. Creation
uses query parameters `test`, `plan`, and `variant`, followed by a separate
`POST /api/runner/<id>` to start. The current runner omits that start step.
Its result handling also needs to accept string results from `/api/info/<id>`
(rather than treating them as an unrecognized result). Production API tokens
would need explicit support; this stack uses the upstream dev profile.

TODO(verify): implement issuer browser authorization and verifier authorization
request submission, result/evidence interactions and waiting-state handling
against the chosen Inji release. The upstream verifier test explicitly waits
for these interactions; polling alone cannot complete it.

TODO(verify): connect the preserved TestNG bridges to each module's api-testrig
and propagate suite URL/expected-failures settings. They currently spawn the
runner themselves and do not consume precomputed full-stack results. The new
workflow gates on the Python result exit code; it does not run TestNG or Maven.

## Commands

Start with this read-only validation (do not publish its expanded config, which
can contain secrets):

```bash
docker compose config --quiet
cp .env.example .env
python -m pip install -r requirements.txt
bash -n run-full-stack-conformance.sh
python -m py_compile runner/*.py
```

After addressing the deployment and runner blockers above:

```bash
bash run-full-stack-conformance.sh --component certify --down
bash run-full-stack-conformance.sh --component verify --down
bash run-full-stack-conformance.sh --combined --down
python runner/diff_results.py previous-results.json results/results-combined.json
```

`--no-up` checks and reuses the required healthy services. `--down` removes this
Compose project's containers/network on exit after preflight, including failure,
and retains volumes. Use `bash script` in Git Bash if checkout lacks execute bits.
Each run removes only its own old component output before launching Python.
Combined mode attempts both runners even when the first fails, writes
`results/results-combined.json` and `results/report-combined.md`, and fails if
either runner failed, a result is missing/invalid, or a module unexpectedly failed.
Startup failures exit before combined reporting. Health timeout defaults to 600s
for the whole stack; set `HEALTH_TIMEOUT_SECONDS` to override it.

Export shell variables `PYTHON`, `SUITE_URL`, `CERTIFY_TARGET`, `VERIFY_TARGET`,
`DB_INIT_DIR` and `CERTIFY_CONFIG_DIR` for overrides. If changing directories in
`.env`, also export those directory overrides for shell preflight. Avoid sourcing
`.env` as shell code. Targets passed to the suite must use container-reachable
hostnames, not localhost. CI uses the same script and always uploads available
results and tears down; its fixture-provisioning TODO must be completed first.

Expected outcomes default to empty lists in `runner/expected-failures-*.json`.
Use `--expected-failures-dir <dir>` for private overrides containing files with
the same names. Entries have the format:

```json
[{"module": "exact-suite-module-name", "reason": "Tracked issue explaining the exception"}]
```

Only FAILED/SKIPPED outcomes on listed modules become EXPECTED_FAILURE/EXPECTED_SKIP;
an unexpected pass remains PASSED. The diff tool compares component/module pairs,
prints new failures, new passes, changed statuses and removals, and exits 1 on
new FAILED outcomes (2 on invalid input). Expected failures do not count as new
failures. Compare combined output to previous combined output to retain component
identity.
