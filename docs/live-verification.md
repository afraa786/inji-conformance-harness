# Observed live verification

These are actual local executions against the alpha images, not unit fixtures.
The latest consolidated artifacts are in ignored `results/`; rerunning replaces
the root summaries while evidence is separated by plan ID.

| Check | Observed result |
| --- | --- |
| Compose services | Postgres, MongoDB, suite server, TLS gateway, Certify and Verify healthy |
| TLS | CA-verified Python calls and Java truststore; no global verification bypass |
| Individual wrapper modes | Certify exit 1; Verify exit 1 |
| Latest combined wrapper | Both runner exits 1; 26 modules: 1 WARNING, 12 FAILED, 13 INTERRUPTED, zero PASSED |
| Real Certify Java subprocess adapter | TestNG: 14 tests, 1 passed, 13 failed |
| Real Verify Java subprocess adapter | TestNG: 12 tests, 0 passed, 12 failed |
| Verify backend | Actual happy-flow and minimal-cnf-jwk presentations returned allChecksSuccessful=true |
| Extent | Not verified: standalone bridge lacks the MOSIP reporting runtime |
| Harness tests (2026-10-24) | 47 passed; one cryptography deprecation warning on Python 3.8.10 |

The harness tests include mocked HTTP contract/error/timeout cases and a real
loopback Python/Java CA-trust interoperability test. They are not an Inji E2E run.

On 2026-10-24 the targeted happy flows, both individual wrapper modes, combined
mode and both updated Java adapters were rerun against the still-running images.
They retained the same failure counts and nonzero exits. TestNG XML now includes
the original suite test IDs, details and log links. Prior summaries were archived;
component diffs reported zero newly failing or changed-status modules.

Additional evidence: `results/audit/runtime.json` records actual image IDs,
health, selected non-secret environment settings and public metadata;
`results/audit/failure-matrix.md` maps each module to its log and observed condition.
`results/tls-container-probe.txt` records normal JDK trust/hostname checks from
the suite container. The upstream suite's own HTTP client is permissive internally;
see [TLS scope](tls-validation.md). Do not equate its requests with CA validation.

TestNG treats WARNING as a pass with a log note; this explains the one Certify
TestNG pass versus the combined JSON's WARNING. Neither result establishes
OpenID certification. Negative Verify presentations also exercised real rejection.

The suite requires screenshot evidence/review after Verify's direct-post flow.
The runner preserves actual backend responses and fails the WAITING deadline;
it does not fabricate screenshots. Certify native AS metadata advertises IAR but
does not expose the authorization_endpoint required by the inspected suite.
The suite also excludes anonymous client authentication from this issuer plan;
private_key_jwt/DPoP is diagnostic configuration, not a claim that the native AS
supports it. Signed issuer metadata is also unavailable.

Commands executed included `docker compose config --quiet`, real `docker compose
up -d` / health checks, preparation, both `--component ... --no-up` modes and
`--combined --no-up`, pytest, bash syntax checks, Maven test compilation and both
real bridge `mvn ... test` commands documented in the README. Maven returned
failure for genuine conformance failures; suite exports and TestNG reports were
retrieved. Local unit tests use mocked HTTP and cannot prove product conformance.

Review `results/report-combined.md`, per-plan suite ZIP/logs and backend result
JSON, plus `results/bridge/{certify,verify}-testng/`. The CI definition preserves
nonzero runner exits and always uploads diagnostics/reports. Remote GitHub CI
was not executed in this session.

Next: resolve the native-AS/suite protocol incompatibility with a supported
authorization-server configuration, and provide actual suite evidence review.
For Extent, install adapters into a writable full api-testrig checkout and run
its existing reporting bootstrap/listener. References remain read-only.

Reproduction commands for the 2026-10-24 checks (Git Bash form; the local session
used retained `.local-deps` via PYTHONPATH and `local/m2` as Maven's repository):

```bash
docker compose config --quiet
docker compose ps
python -m pytest runner/tests -q --basetemp=local/pytest-tmp --junitxml=results/unit-tests.xml
WAITING_TIMEOUT_SECONDS=5 bash run-full-stack-conformance.sh --component certify --no-up
WAITING_TIMEOUT_SECONDS=5 bash run-full-stack-conformance.sh --component verify --no-up
WAITING_TIMEOUT_SECONDS=10 bash run-full-stack-conformance.sh --combined --no-up
docker compose exec -T server jshell --execution local - < tools/probe-container-tls.jsh
mvn -q -o -f testrig-bridge/pom.xml -Dmaven.repo.local="$PWD/local/m2" test-compile
```

Both real `mvn test` adapter commands from the README were also executed offline
with that repository, a five-second WAITING budget and separate report directories
`results/bridge/certify-testng` and `results/bridge/verify-testng`. Both returned 1.
Those failures are product/suite outcomes, not Maven compilation failures. The
latest targeted diagnostic outputs additionally live under `results/targeted-current/`.
