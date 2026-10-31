# Final Inji Conformance Harness validation

Observed 2026-10-31T07:50:22.388989+00:00 (UTC); user timezone Asia/Calcutta.

**Overall assessment: partially working.** The local backend stack is deployed,
the metadata fallback is fixed and verified live, and the harness correctly
records failures. **Full OID4VCI/OID4VP conformance has not passed.**

## 1. Requirements and acceptance checklist

| Requirement | Assessment | Evidence |
| --- | --- | --- |
| Python REST plan creation, execution, polling and exports | Implemented; successfully exercised | Fresh plan IDs, per-module logs and plan-export.zip files |
| Certify, Verify, suite, MongoDB, PostgreSQL, gateway | Successfully deployed | Six healthy containers in inji-final-validation |
| Patched metadata through real gateway/security chain | Successfully tested | Both Accept variants return identical 2,037-byte application/json bodies; affected suite module SKIPPED |
| Full Certify issuer conformance | Blocked | 12 interrupted modules; missing authorization_endpoint |
| Verify backend happy presentations | Partially working | Actual SUCCESS results for happy-flow and minimal-cnf-jwk |
| Full Verify conformance | Blocked | 12 failed modules; client_metadata, screenshot review and negative status behavior remain |
| Combined aggregation and build failure | Successfully tested | 26 modules; both component exits 1; combined exit 1 |
| Java TestNG adapter and standalone Extent | Implemented; successfully exercised | Final actual TestNG XML and HTML counts verified |
| Full MOSIP api-testrig reporting bootstrap | Unverified | Standalone listener is not the full MOSIP bootstrap |
| Prior-result status regression comparison | Implemented; exercised | No newly failing modules against already-failing baseline; absolute gate remains 1 |
| Performance/latency benchmark thresholds | Not implemented | Module durations exist; no approved performance thresholds or benchmark dataset |
| Remote CI conformance | Blocked | Latest run failed at suite image pull; no new remote run triggered |
| Genuine demonstration recording | Recorded | Browser viewport capture of real subprocesses and reports; see video verification |
| Product Verify frontend screenshot integration | Not implemented/validated | No fabricated evidence uploaded; actual suite review still required |

## 2. Audit scope and implementation

Inspected README and docs (architecture, API driver, component handoffs, image
versions, TLS scope, live verification, metadata investigation, troubleshooting,
test cases); Python runner, typed renderer, handoffs, archive/diff/merge,
diagnostic/startup helpers and optional MinIO upload; Java adapters, POM, installer
and reporting listener; Compose, gateway configuration, plan variants, CI workflow,
unit tests, saved local artifacts and the latest remote CI run. MinIO was not
configured or exercised. Optional prior TLS/UI enhancement files were inspected
but were not developed or deployed in this validation.

## 3. Actual deployment and Docker health

Docker Engine **27.5.1**, context **desktop-linux**. Original containers were
retained, stopped. A separate **inji-final-validation** project uses the existing
PostgreSQL, MongoDB and Certify-key volumes; no volumes were deleted or reset.
The six validation services are certify, verify, server, httpd, postgres, mongodb.
See `evidence/services-current.txt` and final health evidence.

Certify image: `inji-certify-unsigned-metadata:validation`.
Actual running image ID: `sha256:026781536eb3c280f5bda7fe8fe39ca1ad3619f6558aced9adf1b8a17b2c1051`.
Running jar SHA256: `9e20845163f75393f682eaa6e0b9586faeeee7661c4c952a6478e73519335984` (matches the built jar).
The reviewed exact release is `8fdf71656979a72fa8263766d4dec3cc25127b76`.
The derived jar differs from the inspected pinned base in **one class entry**.
No issuer metadata values or AS endpoint names were fabricated.

All public endpoint probes use `local/tls/ca.crt` with certificate verification.
Suite /plans.html, Certify health, Verify health and discovery returned HTTP 200.
The suite root redirects to /plans.html; the initial probe's exit 1 was due to
its overstrict 200-only check of that legitimate 302 and was corrected by probing
the actual page. The initial response evidence is retained separately.
The existing JDK probe from the actual suite container returned exit 0, including
rejection of wrong hostnames and an untrusted CA. This verifies the TLS topology;
the upstream suite protocol client itself remains permissive internally.

## 4–6. Actual Certify, Verify and combined results

| Execution | Modules | PASSED | FAILED | INTERRUPTED | WARNING | SKIPPED | Exit |
| --- | --- | --- | --- | --- | --- | --- | --- |
| certify | 14 | 0 | 0 | 12 | 1 | 1 | 1 |
| verify | 12 | 0 | 12 | 0 | 0 | 0 | 1 |
| combined | 26 | 0 | 12 | 12 | 1 | 1 | 1 |

Individual plans: Certify `HvUZ5Cjqr18yA`, Verify `OoQNv5SIoiJ1j`.
Combined invocation component plans: Certify `LVPourI4QfvgX`,
Verify `jn4DJgcO4RjC2`.
All were real plans created through the REST driver, not fixture results.
WAITING budgets were deliberately 10 seconds to surface unresolved external
evidence review; the shorter deadline does not make any failing test pass.
Expected-failure lists remained empty. No failure was allowlisted.

The targeted signed-metadata module, plan FC5ZpxaHdMj25/test v3vLO3mgfNNHRFq,
completed **SKIPPED**, exit 0. This fixes the previous empty-body/JWT-decoding
interruption; it does **not** implement signed metadata or establish conformance.

Verify happy-flow, minimal-cnf-jwk, and credential-without-status returned actual backend SUCCESS, while
suite validation still failed and screenshot evidence remained pending.
Invalid signatures and SD hash examples returned backend rejection. Several
invalid nonce/audience/iat cases terminated at suite failure without a saved
backend result. The actual suite description requires acceptance of an otherwise
valid credential without status information; that case is positive and backend
SUCCESS is expected. The revoked-credential example unexpectedly returned
SUCCESS with an empty statusCheck list and is not a validated negative test.
Tagged Verify code permits an empty list in its aggregate success calculation;
why the credential verifier produced no status result remains unresolved.
The final revoked-credential module recorded 309 seconds of duration. The
10-second WAITING budget is not a cap on total module duration; the extra delay
has not been attributed to a confirmed cause. No performance pass is claimed.

## 7. TestNG/Extent, automation and gates

| Adapter | Total | TestNG passed | Failed | Skipped | Actual Extent entries |
| --- | --- | --- | --- | --- | --- |
| certify | 14 | 1 | 12 | 1 | {'fail': 12, 'skip': 1, 'warning': 1} |
| verify | 12 | 0 | 12 | 0 | {'fail': 12} |

The Certify TestNG pass is the suite WARNING, not a conformance PASSED module.
The Extent listener correctly retains that as WARNING. XML totals, normalized
module totals, and HTML per-test status counts were compared in
`evidence/report-verification.json`. Both Maven runs return 1 for real module
failures and retain raw Python runner logs. No new Surefire dumpstream exists in
the final report directories after fixing native inherited stdout.

Python automation: **55 passed, zero failed, zero skipped**, with one cryptography
deprecation warning on retained Python 3.8.10. Includes mocked API regressions,
the real loopback Python/Java CA test, and both compiled Spring MVC controller
regressions. These are harness tests, not passing product conformance.

Status benchmark: current versus previous module statuses produced zero newly
failing modules; the baseline already contained product failures. The independent
runner/combined absolute gates still returned 1. This comparison cannot establish
performance compliance or a clean conformance run. No performance benchmark was
invented. Invalid/missing output and infrastructure failures remain exit 2.

## 8. CI/CD and artifact retention

Latest available remote run: [https://github.com/afraa786/inji-conformance-harness/actions/runs/40281698859](https://github.com/afraa786/inji-conformance-harness/actions/runs/40281698859), commit `13a0a26a8c368205dc77a242c27d4490937eaa44`,
completed with failure. Unit tests/adapter compilation succeeded; all conformance
matrix jobs failed at startup. The downloaded diagnostic reports **manifest
unknown** for pinned suite digest
`sha256:899265eabbe900a3583b2d18cca09e077a147ab1cc74dd5382c664c8a7577373`.
Local execution succeeds using the retained cached image. No replacement image
was selected speculatively, pushed or published. Restoring an approved immutable
suite image in an accessible registry remains necessary for reproducible remote CI.

Workflow review: unit dependency, three real modes, nonzero failure propagation,
always-run diagnostics/report upload and teardown are configured. Existing
artifacts were downloaded and inspected. No new remote CI was triggered, so
these local changes are not remotely validated. Full MOSIP reporting and MinIO
uploads remain unverified. Raw suite exports may contain synthetic private test
material; evidence and source recordings are ignored by Git and not shown in the
video. Existing historical summaries were archived by the wrapper.

## 9. Fixes, attempted work, and outstanding root causes

1. **Fixed live:** tagged JSON-only metadata negotiation rejected JWT Accept,
   the recorded error path returned an empty 200, and the suite attempted to read null as
   a JWT string. The exact reviewed controller now explicitly returns the existing
   JSON metadata. Real request/response evidence and a genuine SKIPPED test prove
   the fallback, rather than a unit-test-only claim.
2. **Fixed test discovery:** retained IDE-managed target output had misplaced
   classes despite Maven incremental metadata. A configurable separate Maven
   build directory permits a fresh compile without cleaning existing output.
   First no-tests-selected attempts are retained as infrastructure failures.
3. **Fixed bridge output transport:** child inheritIO wrote directly into Surefire's
   native control stream. Both adapters now redirect real child output to retained
   runner logs. Final runs still fail on actual product outcomes and generate reports.
4. **Still blocked:** native AS deliberately omits authorization_endpoint and
   implements form-POST IAR at /oauth/iae. The pinned suite requires conventional
   AS metadata before pre-authorized issuance. Tagged credential configuration
   can advertise AS URLs/mappings, but no compatible external-AS/token/issuer
   deployment was established; changing the URL alone would not prove it works.
5. **Still failing:** Verify lacks required client_metadata in the emitted request,
   genuine frontend screenshot/review remains uncompleted, and negative credential
   status enforcement requires further product investigation.
6. **Still blocked in remote CI:** pinned registry manifest unavailable. No successful
   remote deployment or clean CI run was claimed.

Changed existing files: `.gitignore`, `README.md`,
`docs/certify-metadata-investigation.md`, `docs/live-verification.md`,
`docs/test-cases.md`, `docs/troubleshooting.md`, `testrig-bridge/pom.xml`,
`testrig-bridge/certify/OpenIDConformanceTest.java`, and
`testrig-bridge/verify/OpenIDConformanceTest.java`.
Added implementation/test files: `docker-compose.validation.yml`,
`tools/build_certify_metadata.py`, `tools/final_validation_probe.py`,
`tools/record_validation_demo.py`, and `runner/tests/test_validation_probe.py`.
Generated deliverables and ignored local build/evidence files are retained
separately; existing source checkouts and dependency caches were not replaced.

The cached Selenium image separately failed to execute its shell with an I/O error.
It was not repaired or used for product evidence. Recording instead uses already
installed host Edge/Playwright and FFmpeg; no recording dependencies were installed.

## 10. Commands and results

Initial deployment/build commands (repository root):

```powershell
docker --context desktop-linux info --format "{{.ServerVersion}}"
docker --context desktop-linux cp inji-conformance-harness-certify-1:/home/inji/certify-service.jar local/final-validation/original-certify-service.jar
python tools/build_certify_metadata.py --base-jar local/final-validation/original-certify-service.jar --out local/final-validation/certify-build-v2
docker --context desktop-linux build -t inji-certify-unsigned-metadata:validation local/final-validation/certify-build-v2
docker --context desktop-linux compose -p inji-final-validation -f docker-compose.yml -f docker-compose.validation.yml up -d --pull never --wait --wait-timeout 300 postgres mongodb server httpd certify verify
python tools/final_validation_probe.py --out artifacts/demo/evidence/endpoint-probes.json
python runner/conformance_runner.py --component certify --target https://certify.test:8446 --module oid4vci-1_0-issuer-metadata-test-signed --waiting-timeout-seconds 10 --out artifacts/demo/evidence/metadata-targeted/results-certify.json
python -m pytest runner/tests -q -rs --basetemp=local/pytest-final-55 --junitxml=artifacts/demo/evidence/unit-tests-final-55.xml
```

Python commands use retained `.local-deps` via PYTHONPATH. The isolated MVC test
uses `CERTIFY_REGRESSION_M2=C:/Users/Afraa/.m2/repository`. Recorded wrapper/Java
jobs additionally set DOCKER_CONTEXT=desktop-linux, COMPOSE_PROJECT_NAME=
inji-final-validation, COMPOSE_FILE to the two absolute Compose paths (semicolon
separated), COMPOSE_PATH_SEPARATOR=semicolon and WAITING_TIMEOUT_SECONDS=10.

Complete recorded command outcomes (including initial failed reporting attempts):

- `docker compose up -d --no-recreate --pull never --wait --wait-timeout 120` → exit **0** (deployment-health)
- `docker compose ps -a` → exit **0** (docker-services)
- `C:\Users\Afraa\AppData\Local\Programs\Python\Python38\python.exe tools/final_validation_probe.py --out artifacts/demo/evidence/endpoint-probes-recorded.json` → exit **0** (gateway-metadata)
- `"C:/Program Files/Git/bin/bash.exe" run-full-stack-conformance.sh --component certify --no-up` → exit **1** (certify)
- `"C:/Program Files/Git/bin/bash.exe" run-full-stack-conformance.sh --component verify --no-up` → exit **1** (verify)
- `"C:/Program Files/Git/bin/bash.exe" run-full-stack-conformance.sh --combined --no-up` → exit **1** (combined)
- `mvn.cmd -q -o -f testrig-bridge/pom.xml -Dmaven.repo.local=C:\Users\Afraa\Downloads\inji-conformance-harness\local\m2 test -Dtest=io.inji.testrig.apirig.injicertify.testscripts.OpenIDConformanceTest -Dconformance.root=C:\Users\Afraa\Downloads\inji-conformance-harness -Denv.endpoint=https://certify.test:8446 -Dconformance.results=C:\Users\Afraa\Downloads\inji-conformance-harness\artifacts\demo\evidence\certify-testng\results-certify.json -Dconformance.reportsDirectory=C:\Users\Afraa\Downloads\inji-conformance-harness\artifacts\demo\evidence\certify-testng -Dconformance.waitingTimeoutSeconds=10` → exit **1** (certify-testng)
- `mvn.cmd -q -o -f testrig-bridge/pom.xml -Dmaven.repo.local=C:\Users\Afraa\Downloads\inji-conformance-harness\local\m2 test -Dtest=io.inji.testrig.apirig.injiverify.testscripts.OpenIDConformanceTest -Dconformance.root=C:\Users\Afraa\Downloads\inji-conformance-harness -Denv.endpoint=https://verify.test:8447/v1/verify -Dconformance.results=C:\Users\Afraa\Downloads\inji-conformance-harness\artifacts\demo\evidence\verify-testng\results-verify.json -Dconformance.reportsDirectory=C:\Users\Afraa\Downloads\inji-conformance-harness\artifacts\demo\evidence\verify-testng -Dconformance.waitingTimeoutSeconds=10` → exit **1** (verify-testng)
- `mvn.cmd -q -o -f testrig-bridge/pom.xml -Dmaven.repo.local=C:\Users\Afraa\Downloads\inji-conformance-harness\local\m2 test -Dconformance.buildDirectory=C:\Users\Afraa\Downloads\inji-conformance-harness\local\final-validation\bridge-target-v2 -Dtest=io.inji.testrig.apirig.injicertify.testscripts.OpenIDConformanceTest -Dconformance.root=C:\Users\Afraa\Downloads\inji-conformance-harness -Denv.endpoint=https://certify.test:8446 -Dconformance.results=C:\Users\Afraa\Downloads\inji-conformance-harness\artifacts\demo\evidence\certify-testng-recovery\results-certify.json -Dconformance.reportsDirectory=C:\Users\Afraa\Downloads\inji-conformance-harness\artifacts\demo\evidence\certify-testng-recovery -Dconformance.waitingTimeoutSeconds=10` → exit **1** (certify-testng-recovery)
- `mvn.cmd -q -o -f testrig-bridge/pom.xml -Dmaven.repo.local=C:\Users\Afraa\Downloads\inji-conformance-harness\local\m2 test -Dconformance.buildDirectory=C:\Users\Afraa\Downloads\inji-conformance-harness\local\final-validation\bridge-target-v2 -Dtest=io.inji.testrig.apirig.injiverify.testscripts.OpenIDConformanceTest -Dconformance.root=C:\Users\Afraa\Downloads\inji-conformance-harness -Denv.endpoint=https://verify.test:8447/v1/verify -Dconformance.results=C:\Users\Afraa\Downloads\inji-conformance-harness\artifacts\demo\evidence\verify-testng-recovery\results-verify.json -Dconformance.reportsDirectory=C:\Users\Afraa\Downloads\inji-conformance-harness\artifacts\demo\evidence\verify-testng-recovery -Dconformance.waitingTimeoutSeconds=10` → exit **1** (verify-testng-recovery)
- `C:\Users\Afraa\AppData\Local\Programs\Python\Python38\python.exe -c "from pathlib import Path; print('ACTUAL PROJECT FILES'); [print(str(p)) for p in sorted(Path('runner').glob('*.py'))]; print('ACTUAL COMPOSE SERVICE / IMAGE CONFIGURATION'); [print(line) for line in Path('docker-compose.yml').read_text().splitlines() if line.startswith('  ') and (line.strip().endswith(':') and len(line)-len(line.lstrip())==2 or line.strip().startswith('image:'))]; print('Derived Certify override:'); print(Path('docker-compose.validation.yml').read_text()); print('Status comparison is a regression benchmark, not a performance benchmark.')"` → exit **0** (project-inspection-testng-final)
- `mvn.cmd -q -o -f testrig-bridge/pom.xml -Dmaven.repo.local=C:\Users\Afraa\Downloads\inji-conformance-harness\local\m2 test -Dconformance.buildDirectory=C:\Users\Afraa\Downloads\inji-conformance-harness\local\final-validation\bridge-target-final -Dtest=io.inji.testrig.apirig.injicertify.testscripts.OpenIDConformanceTest -Dconformance.root=C:\Users\Afraa\Downloads\inji-conformance-harness -Denv.endpoint=https://certify.test:8446 -Dconformance.results=C:\Users\Afraa\Downloads\inji-conformance-harness\artifacts\demo\evidence\certify-testng-final\results-certify.json -Dconformance.reportsDirectory=C:\Users\Afraa\Downloads\inji-conformance-harness\artifacts\demo\evidence\certify-testng-final -Dconformance.waitingTimeoutSeconds=10` → exit **1** (certify-testng-final)
- `mvn.cmd -q -o -f testrig-bridge/pom.xml -Dmaven.repo.local=C:\Users\Afraa\Downloads\inji-conformance-harness\local\m2 test -Dconformance.buildDirectory=C:\Users\Afraa\Downloads\inji-conformance-harness\local\final-validation\bridge-target-final -Dtest=io.inji.testrig.apirig.injiverify.testscripts.OpenIDConformanceTest -Dconformance.root=C:\Users\Afraa\Downloads\inji-conformance-harness -Denv.endpoint=https://verify.test:8447/v1/verify -Dconformance.results=C:\Users\Afraa\Downloads\inji-conformance-harness\artifacts\demo\evidence\verify-testng-final\results-verify.json -Dconformance.reportsDirectory=C:\Users\Afraa\Downloads\inji-conformance-harness\artifacts\demo\evidence\verify-testng-final -Dconformance.waitingTimeoutSeconds=10` → exit **1** (verify-testng-final)
- `C:\Users\Afraa\AppData\Local\Programs\Python\Python38\python.exe runner/diff_results.py C:\Users\Afraa\Downloads\inji-conformance-harness\results\previous\20261031T072127346345Z-793a7f2c\results-combined.json results/results-combined.json` → exit **0** (benchmark-status-comparison-testng-final)
- `C:\Users\Afraa\AppData\Local\Programs\Python\Python38\python.exe -c "from pathlib import Path; [print(str(p)) for p in Path('artifacts/demo/evidence').glob('*testng*/*') if p.is_file()]"` → exit **0** (evidence-index-testng-final)

All exact arguments/timestamps are also in `evidence/all-command-outcomes.json`.
Derived build v3 added a base-jar refusal check and reproduced the identical
deployed jar SHA256; four targeted probe/builder tests passed before the final
55-test suite. `git diff --check` passed. No commit, push, reset or clean was used.

## 11. Video and evidence locations

- Final MP4: `C:\Users\Afraa\Downloads\inji-conformance-harness\artifacts\demo\inji-conformance-working-demo.mp4`
- This report: `C:\Users\Afraa\Downloads\inji-conformance-harness\artifacts\demo\final-validation-report.md`
- Evidence: `C:\Users\Afraa\Downloads\inji-conformance-harness\artifacts\demo\evidence`
- Video facts: `{"durationSeconds": 478.24, "duration": "07:58.24", "resolution": "1440x900", "fps": 25, "codec": "H.264", "fullDecodePassed": true, "bytes": 14081951, "sha256": "552b57d012622192a2e68dc7bcb7803097d1367ee563259827c353f6550ecac9", "scope": "Genuine browser viewport recording; no desktop/chat capture", "edit": "Waiting time omitted with visible label; original recordings retained", "sampleFrameSeconds": [20, 445, 458, 470], "sampleFramesVisuallyReviewed": true, "review": "Actual Certify and Verify Extent reports and final failing status visible; no chat or private desktop visible"}`

The silent video records real browser viewport rendering of an audit console,
actual subprocess output, and actual generated reports. It does not capture the
desktop, VS Code, chat, private conversations, or prompts. Architecture and status
explanations are onscreen. Original raw WebM recordings and interim MP4 attempts
are retained separately. The final edit joins genuine execution and final reporting
segments; no terminal output or conformance result was synthesized. The source
recording includes the initial reporting failure; the final reporting segment shows
its correction. Early sidebar summaries can reflect retained earlier results until
each fresh invocation finishes; the final combined result and this report are
authoritative for this validation.

## 12–13. Final assessment and next step

The harness implements and exercises real orchestration, evidence retrieval,
consolidation and standalone reporting. The backend services are deployed and
healthy. **The project does not meet full end-to-end conformance acceptance**:
zero conformance modules passed, issuer protocol compatibility remains blocked,
Verify requires protocol/evidence/status work, and remote CI cannot pull the pin.

Next: establish an upstream-supported AS/issuer/suite combination with actual
token/client-authentication and sender-constraint compatibility; separately fix
Verify metadata and investigate its empty credential-status result, then implement
genuine frontend evidence review. Restore an approved pullable suite image for CI.
Keep the current failures visible and rerun the exact plans after each supported fix.
