# Final submission readiness — Inji Conformance Harness

Assessment: **2026-11-02**. **Not acceptance-ready for full protocol conformance.** A demonstrable orchestration prototype and traceable reports exist. Docker-dependent workflows could not be rerun in this assessment.

## A. Project status

Implemented: Python REST suite orchestration; real Certify/Verify backend handoffs; individual and combined run modes; Java 21 TestNG bridge; Extent listener; JSON/Markdown/exported evidence; pinned suite defaults; native metadata/status-list fixes for the tested profile; configurable component/module/combined execution-time gates.

Incomplete: external-AS provisioning and client onboarding, compatible authorization/grant coordination, Certify resource-side DPoP validation, genuine Verify UI transaction evidence and required review, and actual all-workflow acceptance. Operational budgets remain null until approved limits are supplied. Unit tests are not protocol conformance passes.

## B. Files changed for submission preparation

| Path | Change |
| --- | --- |
| `tools/create_submission_video.py` | Safe audit and actual browser recording, installed offline narration, current/retained labels, H.264/AAC export and decode checks; refuses existing video replacement. Corrected Docker availability checks and Windows PowerShell array handling during preparation. |
| `README.md` | Submission entry points and Windows commands using retained dependencies. |
| `docs/submission-pitch.md` | Honest presentation content; explicitly not a rendered PPTX/PDF. |
| `artifacts/demo/final-submission-readiness.md` | This current readiness report and deliverable checklist. |
| `artifacts/demo/Final Submission Video.mp4` | Requested narrated final video, preserving earlier videos. |

Existing external-AS assessment and prior blocker documentation were preserved. No runner, native service patch, TestNG result expectation or benchmark threshold was changed to obtain a pass. Isolated audit logs, narration assets and raw recordings are under ignored `artifacts/demo/evidence/final-submission-20261102/`. Local scratch scripts and isolated Maven/pytest outputs remain under ignored `local/`.

## C. Current validation results

**Fresh regression:** 90 passed, 0 failures, 0 errors, 0 skipped; 48.03 seconds. One Python 3.8/cryptography deprecation warning. Retained dependencies were used; nothing was installed. Native signed status tests ran locally rather than being skipped.

| Current check | Exit | Evidence |
| --- | ---: | --- |
| git-branch | 0 | `evidence/final-submission-20261102/git-branch.log` |
| git-status-before | 0 | `evidence/final-submission-20261102/git-status-before.log` |
| docker-current | 0 | `evidence/final-submission-20261102/docker-current.log` |
| docker-services-current | 1 | `evidence/final-submission-20261102/docker-services-current.log` |
| compose-base | 0 | `evidence/final-submission-20261102/compose-base.log` |
| compose-native | 0 | `evidence/final-submission-20261102/compose-native.log` |
| bash-syntax | 0 | `evidence/final-submission-20261102/bash-syntax.log` |
| config-validation | 0 | `evidence/final-submission-20261102/config-validation.log` |
| regression-current | 0 | `evidence/final-submission-20261102/regression-current.log` |
| java-compile-current | 0 | `evidence/final-submission-20261102/java-compile-current.log` |
| git-diff-check | 0 | `evidence/final-submission-20261102/git-diff-check.log` |

The Docker formatted info command returned **exit 0 with no server version and a pipe error**. The service query returned exit 1. The recorder correctly requires an actual version string; exit 0 alone is not evidence of a healthy daemon. Compose `config --quiet` is a static check that succeeds without the daemon and does not prove deployment.

Java `test-compile` passed offline in a separate build directory. **No fresh live TestNG conformance execution** was possible. The recording opens the genuine retained Extent reports and labels their date. Fresh full Certify/Verify/combined workflows were not attempted against unavailable services; their absence is not represented by fabricated pass counts.

Current policy/renderer checks, CI input-script checks, threshold boundaries and exit propagation are covered by the fresh 90-test run. Remote GitHub Actions was not triggered or newly validated. The retained remote CI failure remains historical evidence.

### Retained conformance execution — 2026-10-31

| Workflow | Passed | Failed | Interrupted | Warning | Skipped | Exit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| certify | 0 | 0 | 12 | 1 | 1 | 1 |
| verify | 5 | 7 | 0 | 0 | 0 | 1 |
| combined | 5 | 7 | 12 | 1 | 1 | 1 |

Retained TestNG: Certify 14 tests, 1 adapter pass, 12 failures, 1 skip; Verify 12 tests, 5 passes, 7 failures. Retained Extent: Certify 12 fail/1 warning/1 skip; Verify 5 pass/7 fail. The warning handled by Java is not a Certify protocol pass.

Retained synthetic budget proof: one actual Verify protocol module PASSED (conformanceExitCode 0); 11.079 seconds exceeded the synthetic 0-second budget, benchmark FAILED, runner exit 1. Maven/TestNG recorded 2 tests, 1 pass and 1 benchmark failure, exit 1. This is gate fault injection, not an operational SLO.

Evidence: `evidence/blocker-resolution/demo/`, `benchmark-live-proof/` and `benchmark-java-proof/` under `artifacts/demo/evidence/blocker-resolution/`. See the original [full validation report](final-validation-report.md).

## D. Infrastructure

Current Docker Linux engine is unreachable: `dockerDesktopLinuxEngine` pipe absent. Service status is **unknown**, not healthy or assumed stopped. No service was started, restarted, stopped or pulled. Prior six-healthy-service evidence is historical. Existing volumes, images, private `.env`, keys and local dependencies were preserved.

Installed Edge/Playwright, Windows SAPI voice and FFmpeg were used. No recording dependency was installed. The capture includes only a dedicated browser viewport; the Codex panel is absent from the video. VS Code window/panel state was not changed.

Tracked-path review found no tracked `.env`, `local/` or `.local-deps/` files and no missing required source/template paths. A tracked-file scan under 2 MB found no literal private-key PEM, long private-JWK `d` values or encoded JWT candidates. This bounded pattern review is **not** an exhaustive secret audit. Captured output is redacted and user-specific filesystem prefixes are removed.

## E. Authorization server

No external AS or registered clients are provisioned. Keycloak 26.8.1 is an assessed candidate; eSignet 1.6.1 is a tagged alternative. Neither was deployed or tested live. See [the exact assessment](../../docs/external-as-assessment.md) for discovery routes, source/image pins, clients, exact intended suite callback, issuer/audience/client/scope alignment, subject-to-record mapping and separate protected storage. Native Certify was not reused as an assumed external AS.

## F. Known blockers

**Critical:** actual external-AS/grant integration and DPoP resource validation; genuine Verify UI-owned transaction screenshots associated with suite results; complete protocol acceptance. Docker unavailability currently prevents live reruns.

**Non-critical limitations:** Python 3.8 deprecation; operational performance limits not configured; native status checking supports the documented same-issuer-key JWT-status-list profile rather than every status scheme; clean remote CI not demonstrated.

**Future scope:** broader status profiles and delegated signers, complete browser evidence automation, deployment hardening and concurrent/load performance assessment. None is claimed as an implemented acceptance feature.

## G. Submission checklist

| Deliverable | Location | Actual status |
| --- | --- | --- |
| Complete source | Repository root, `runner/`, `testrig-bridge/`, `configs/`, `tools/`, Compose/CI | Local source present; no commit/push performed. Confirm required final revision is hosted before submission. |
| Prototype/demo | Existing implementation, retained reports and recordings | Demonstrable harness prototype; complete end-to-end conformance remains failing/incomplete. |
| Pitch presentation | `docs/submission-pitch.md` | Source content prepared; no rendered PPTX/PDF found in the repository. Existing external deck was not searched for or changed. Render/provide the final deck manually. |
| Final video | `artifacts/demo/Final Submission Video.mp4` | Created and full decode verified; see section H. |

## H. Final demonstration guide

The narrated video shows: introduction; source-derived architecture; actual runner and Java source walkthrough; current Docker error; retained execution commands and outputs; actual retained Certify and Verify Extent reports; fresh regression output; retained benchmark-breach proof; challenges and next milestones. The viewer was recorded interactively in Edge; it is not a slideshow assembled from still images. Narration uses the installed Microsoft Zira voice, not a claimed human recording.

**Current recorded checks:** regression/configuration/Bash/Java compile outputs and Docker availability. Checks were executed immediately before capture, then their unaltered, redacted outputs were opened in the recording. **Retained evidence:** 2026-10-31 conformance execution, TestNG/Extent reports and synthetic live/Maven benchmark breach; labelled in the screen and narration. **Architecture:** a source-derived visualization of `docs/architecture.md`, not a runtime-health claim.

Video duration: **284.64 seconds (4.74 minutes)**. File size: **15,365,001 bytes**. H.264 video, AAC narration. Full audio/video decode exit 0 with no errors. SHA-256: `76dd2b1164bf11c921e000768db8ab69c99a348ff19e912ac32eab6384350614`. Representative frames and metadata: `evidence/final-submission-20261102/video-verification.json`. Browser playback and visual frame review are recorded separately.

Earlier `inji-conformance-working-demo.mp4`, raw recordings and all previous evidence were preserved. No prior video was overwritten. The final filename was created only if absent. The recording tool retained initial failed narration/setup attempts; those attempts are not successful validation results.

For a judge-facing walkthrough:

1. Play the final video and explain its current-versus-retained labels.
2. Open `docs/architecture.md`, `runner/conformance_runner.py` and `testrig-bridge/verify/OpenIDConformanceTest.java`.
3. Open `artifacts/demo/evidence/blocker-resolution/demo/verify-testng/conformance-extent.html` and the corresponding Certify report.
4. Show the fresh JUnit XML and retained budget gate evidence; keep unit and protocol counts separate.

Safe Windows PowerShell commands with existing dependencies:

```powershell
$env:PYTHONPATH = Join-Path $PWD '.local-deps'
python -m pytest runner/tests -q
docker --context desktop-linux info --format '{{.ServerVersion}}'
```

Require a nonempty server version and successful service query before live execution. The previously exercised Git Bash commands are:

```bash
bash run-full-stack-conformance.sh --component certify --no-up
bash run-full-stack-conformance.sh --component verify --no-up
bash run-full-stack-conformance.sh --combined --no-up
```

Those workflow commands require the correctly configured running stack and are **not new validation results**. The retained patched deployment used the `inji-blocker-resolution` project with `docker-compose.yml`, `docker-compose.validation.yml` and `docker-compose.blocker-resolution.yml`; do not assume a default private `.env` recreates that deployment.

**Manual submission steps:** supply a rendered pitch deck, confirm hosted source revision with the user before any commit/push, and decide whether the competition accepts a prototype with openly documented blockers. Restore Docker and complete the real integrations before claiming end-to-end acceptance. No manual recording or editing is required once the video verification below is complete.

The exact executed commands, times and exits are retained in `evidence/final-submission-20261102/commands.json`. Git checks and safe static validation do not replace protocol testing.

Final playback confirmation: the MP4 was opened and played in installed Edge;
audio/video decoded, playback advanced, and seeking near the end succeeded.
H.264 and AAC streams and non-silent narration were confirmed. Intro, actual
Extent-report and final frames were visually reviewed. See
`evidence/final-submission-20261102/browser-playback-verification.json`,
`audio-verification.log` and `visual-review.json`. No manual recording/editing
steps remain. The prior demo's SHA-256 is unchanged.
