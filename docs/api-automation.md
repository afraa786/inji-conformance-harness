# Python REST driver

`runner/conformance_runner.py` follows the API contract in the read-only suite's
`scripts/conformance.py` and the orchestration in `scripts/run-test-plan.py`.
The Java bridge invokes this driver as a subprocess. There is no Java REST port.

1. Render config using `runner/render_plans.py` (or pass `--plan rendered.json`).
2. `POST /api/plan?planName=...&variant=<JSON object>` with config alone as JSON body.
3. `GET /api/plan/{id}`; reject an empty module list.
4. `POST /api/runner?test=...&plan=...&variant=<module variant>` with no body and
   JSON Content-Type. Each module is identified by `testModule`.
5. Poll persisted `GET /api/info/{id}`. On CONFIGURED, call `POST /api/runner/{id}`
   once. The inspected server prevents double-starting auto-started modules.
6. On WAITING, read `GET /api/runner/{id}` for live `browser` and `exposed` values;
   persisted info does not contain the live handoff state. Drive the component
   handoff. Unhandled interactions fail at the WAITING timeout.
7. Read string `result` at FINISHED; INTERRUPTED always remains an interruption.
   Timeout triggers `DELETE /api/runner/{id}` to stop the abandoned module.
8. `GET /api/log/{id}` saves evidence. `GET /api/plan/export/{planId}` saves a
   validated, nonempty ZIP. An evidence/API error is infrastructure failure.

Read connection errors and request timeouts retry three times with exponential
backoff. Writes are never retried after a lost response: their outcome is
unknown and a retry could create duplicate plans or runs. Inspect the suite for
orphaned plans after an outage. HTTP status/body errors are not
retried or echoed. Requests have a 30s cap within module/global budgets.

The suite's offer/authorization GET callbacks change state despite their HTTP
method; those calls also disable retries after a lost response.

`OIDC_SUITE_TOKEN` adds an optional bearer header; the dev-profile suite does not
require one. `OIDC_SUITE_INSECURE=false` is the default; generated CA trust is
provided through `REQUESTS_CA_BUNDLE`. Only an explicit true relaxes the isolated
suite session. The suite session never follows redirects and rejects
other origins. `SUITE_PUBLIC_URL` translates Docker-advertised callback addresses
to the host-accessible suite URL. Inji uses separate TLS-verifying requests.

The output contains `component`, `planId`, `modules`, `summary`, `errors`, and
`exitCode`, plus unique `runId`, UTC `startedAt` and `finishedAt`. Module records
contain `name`, original `testId`, `variant`, `status`, `detail`, `logUrl`,
and `duration` in seconds. Infrastructure failures preserve partial records.
Statuses are PASSED, FAILED, WARNING, SKIPPED, INTERRUPTED, REVIEW,
EXPECTED_FAILURE and EXPECTED_SKIP. Missing/unknown results fail.

Exit 0 means no unexpected test failures; 1 means FAILED/INTERRUPTED remains;
2 means invalid/missing configuration, unavailable services or evidence failure.
REVIEW/SKIPPED do not establish a passing certification result. Expected-failure
entries match the base module name; a newly passing entry stays PASSED and its
detail asks for removal from the list. Infrastructure errors cannot be allowlisted.

Raw suite logs, exports and rendered plans may contain sensitive test material.
They stay under ignored `results/`; do not publish them without review.

Evidence is isolated under `results/<component>-evidence/<planId>/`; its path is
reported as `evidenceDirectory`. Export requests explicitly accept application/zip.
Verify records include the actual backend `verifyOutcome` and pending evidence
when available. A screenshot-required WAITING state fails on timeout, even if
backend credential verification succeeded. See [handoff](component-handoff.md).

Repeatable `--module exact-name` selects a diagnostic subset of a fresh plan.
`planModuleCount` and `selectedModules` distinguish it from a complete plan run;
a nonexistent module fails before creating a module run. Subsets cannot establish
whole-plan conformance.
