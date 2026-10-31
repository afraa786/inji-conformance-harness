# Critical-blocker final validation

Recorded at 2026-10-31T08:55:25.715000+00:00

**NOT ACCEPTANCE-READY. No end-to-end conformance pass occurred.**

This report supersedes the earlier zero-pass report, retained at `evidence/blocker-resolution/prior-final-validation-report.md`. Passing native checks and unit tests are distinct from suite conformance.

| Blocker | Resolution and evidence | Remaining work |
| --- | --- | --- |
| Native Certify AS | BLOCKED. Tagged native `/oauth/iae` is form POST/IAR; it is not a browser authorization endpoint. Actual pre-authorized offer/token exchange returned HTTP 200 and Bearer token. Both inspected suite versions require conventional authorization metadata before handoff. `native-preauth-flow.json`, `suite-iar-scan.json`. | Integrate a real supported external AS/client/token/issuer flow, or obtain upstream IAR suite support. No endpoint rename or fabricated metadata was made. Complete authorization and issuance remain unverified. |
| Verify metadata/evidence | PARTIAL. Native DTO now publishes conservative ES256 SD-JWT/KB-JWT capabilities; REST driver forwards them. Real gateway request creation returns 201. `native-request-v2.json`, `targeted-pinned/`. | Seven modules require a genuine frontend result screenshot for their own UI transaction and potentially manual REVIEW. REST-owned requests are not attached to the tagged UI SDK. No fabricated screenshots were uploaded. |
| Revoked credentials | FIXED FOR THE TESTED SAME-ISSUER-KEY JWT STATUS-LIST PROFILE. Native library default status method was unsupported and swallowed into empty results. Added authenticated HTTPS status fetch, signed/freshness-checked list decoding, no cache, fail-closed handling. Live revoked result is CREDENTIAL_REVOKED; unavailable status is STATUS_UNAVAILABLE with signature still valid. | Delegated status signers, CWT lists and redirects are unsupported/rejected. Full frontend evidence and broader profile coverage remain open; backend rejection is not a suite pass. |
| CI image | LOCAL PULL/DEPLOYMENT FIXED. Official release-v5.3.4 and matching frontend are pinned by immutable multi-architecture index digests. Exact jar revision and hashes retained in suite-release-provenance.json. Same native build path as CI executed locally. | No new remote CI run was triggered for uncommitted changes. Latest remote run 40281698859 remains failed on the old pin. Clean remote CI is unverified. |
| Performance gates | IMPLEMENTED. Component/module/combined execution budgets, inclusive boundaries, explicit pass/fail and failing process/TestNG/CI exits. Real module PASSED with synthetic zero budget FAILED, exit 1. | Defaults null/NOT_CONFIGURED: no approved operational thresholds supplied. No performance acceptance claim; these are execution-time budgets, not throughput/percentile load tests. |

## Exact full-plan counts

| Run | Total | PASSED | FAILED | INTERRUPTED | WARNING | SKIPPED | REVIEW | Exit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| certify | 14 | 0 | 0 | 12 | 1 | 1 | 0 | 1 |
| verify | 12 | 5 | 7 | 0 | 0 | 0 | 0 | 1 |
| combined | 26 | 5 | 7 | 12 | 1 | 1 | 0 | 1 |

Source: `artifacts/demo/evidence/blocker-resolution/demo`; summaries are not inferred from unit tests.

Five passing Verify modules are invalid KB nonce, invalid KB audience, KB iat in the past, KB iat in the future, and wrong vct. Seven remaining failures time out waiting for frontend evidence. Certify metadata is WARNING, signed metadata is SKIPPED, and twelve issuance modules INTERRUPTED. WARNING, SKIPPED and Java adapter success for a warning are not conformance PASSED.

## Regression, native and reporting verification

| Check | Exact result |
| --- | --- |
| Final regression | 90 tests, 0 failures, 0 errors, 0 skipped |
| Native status subset (included above) | 9 passed: valid/revoked/refetch, unavailable, expired/stale, wrong signature, subject/index/type, multibit and optional absence; actual Java checker and HTTPS fixtures |
| certify TestNG | 14 total, 1 passed, 12 failed, 0 errors, 1 skipped |
| certify Extent | {'warning': 1, 'skip': 1, 'fail': 12} |
| verify TestNG | 12 total, 5 passed, 7 failed, 0 errors, 0 skipped |
| verify Extent | {'fail': 7, 'pass': 5} |
| Synthetic budget live gate | 1 protocol PASSED, conformanceExitCode 0; 11.079 seconds > synthetic 0-second budget, benchmark FAILED, process exit 1 |
| Synthetic budget TestNG gate | 2 tests: 1 protocol passed, 1 benchmark failed, 0 errors/skips; Maven exit 1 |
| Workflow input script | 3 passed (included in 90): defaults, supplied policy, rejected invalid input; actual workflow Python block executed locally |

The corrected DTO roundtrip is covered with the native runtime libraries. An initial derived candidate returned HTTP 500 due to DTO persistence conversion; it was corrected with read-only metadata and constructor parameter preservation. Both failed and corrected evidence are retained.

## Evidence and reproducibility

All paths below are relative to `artifacts/demo/evidence/blocker-resolution/` unless stated otherwise.

- `validation-commands.json`: exact commands, exit codes, UTC times for targeted/full/combined/Java runs.
- `demo/demo-commands.json`: exact commands and exits captured in the new video.
- `unit-tests-final.xml`: final 90-test regression JUnit results.
- `targeted-pinned/`: valid, revoked, optional-no-status and unavailable status native responses against the original suite.
- `targeted-release/`: affected modules against release-v5.3.4.
- `native-request.json`, `verify-deployment-log.txt`: retained failed candidate; `native-request-v2.json`: corrected response.
- `endpoint-probes.json`, `demo/endpoint-probes-recorded.json`: actual trusted HTTPS gateway responses.
- `suite-release-provenance.json`: immutable image pins, public pull/platforms, actual jar source revision.
- `native-image-build.log`; repository `results/derived-image-provenance.json`: source/base/output hashes.
- `benchmark-live-proof/`, `benchmark-java-proof/`, `fault-injection-zero-budget.json`: actual gate-failure proof; zero is a synthetic test limit only.
- Per-component `*-testng/conformance-extent.html`, `TEST-*.xml`, runner results and raw plan exports.

Suite release-v5.3.4 source revision: `23353b36957d6466010de767c812d2c91ed37638`. Suite image: `sha256:dcc4bd1fb7e9c00f048a67373fe2bec5ecf9feb45a6b5d55e237e5c30e5312c6`; frontend: `sha256:9a7850826fcc8690cd43373528f50e9551ba33bf8e4a40b67b13267b0aca3675`. Both linux/amd64 and linux/arm64 manifests were verified.

Native exact source: Certify `8fdf71656979a72fa8263766d4dec3cc25127b76`; Verify `4c4289026968beb535d3dbdd500947152c43f708`. Original checkouts and private `.env` retained. Patch preparation/build uses isolated copies and verifies original hashes.

## Files involved

- Native fixes: `patches/verify-alpha-status-metadata.patch`, `tools/verify-fixes/TokenStatusListChecker.java`, `tools/build_verify_fixes.py`, `tools/prepare_native_images.py`; prior Certify patch retained.
- Driver and budgets: `runner/handoff_verify.py`, `runner/conformance_runner.py`, `runner/benchmarks.py`, `runner/merge_results.py`, `configs/benchmark-thresholds.json`.
- Regression: `runner/tests/test_handoff_verify.py`, `test_runner.py`, `test_benchmarks.py`, `test_token_status_list.py`, `test_ci_benchmark_input.py` in the same directory.
- Deployment/CI: `docker-compose.yml`, `docker-compose.blocker-resolution.yml`, `docker-compose.native-fixes.yml`, `.env.example`, `.github/workflows/full-stack-conformance.yml`.
- Java: both `testrig-bridge/{certify,verify}/OpenIDConformanceTest.java` adapters; original bridge/listener retained.
- Documentation/recording: `docs/blocker-resolution.md`, `docs/benchmark-thresholds.md`, `docs/live-verification.md`, `docs/image-versions.md`, `README.md`, `tools/record_validation_demo.py`, this report.

Some task files were committed externally during the session (current Git history records these); this agent issued no commit/push/reset/clean command. Final working-tree snapshot is retained separately.

## Commands and next steps

Focused/full regressions: `python -m pytest runner/tests -q --basetemp=local/pytest-critical-final --junitxml=artifacts/demo/evidence/blocker-resolution/unit-tests-final.xml` with `PYTHONPATH=.local-deps`.

Live environment uses DOCKER_CONTEXT=desktop-linux, COMPOSE_PROJECT_NAME=inji-blocker-resolution, and compose files docker-compose.yml, docker-compose.validation.yml, docker-compose.blocker-resolution.yml. WAITING_TIMEOUT_SECONDS=10 exposes missing evidence; timeout is not converted to pass.

`bash run-full-stack-conformance.sh --component certify --no-up`, corresponding `--component verify`, and `--combined --no-up` all returned 1. Java commands and isolated build/report directories are in the ledgers.

Next concrete inspection: the tagged `CredentialConfigurationServiceImpl` and `OAuthController` for a supported real external-AS integration, plus the tagged Verify UI SDK request/session lifecycle before adding UI-owned transaction capture. See `docs/blocker-resolution.md` for exact protocol findings. Do not rename IAR metadata. Operational benchmark limits require an approved policy before acceptance.

Six `inji-blocker-resolution` services were healthy at last inspection. Prior projects/volumes retained. No remote CI run was triggered; latest inspected remote run remains failed. No dependencies installed or existing work discarded. Browser-only capture excludes VS Code/Codex; the VS Code panel itself was not manipulated or independently verified hidden.

## Demonstration

The requested MP4 records actual subprocesses and actual generated Extent reports, including nonzero exits and remaining blockers. It is an honest failing-validation demonstration, not a working end-to-end acceptance claim. Previous recording retained in `artifacts/demo/recording/pre-critical-blocker-validation.mp4`.

Video SHA-256: `40ffe975d2250efe09a91ffe31c7d2b90b5f9976ff565aaa9e6982f53f15b28f`. Playback/decode evidence: `evidence/blocker-resolution/video-validation.json`.
