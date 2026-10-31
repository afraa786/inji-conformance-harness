# Harness tests

Run from the repository root with dependencies installed and Java 21 available:

```bash
python -m pytest runner/tests -q --basetemp=local/pytest-tmp --junitxml=results/unit-tests.xml
```

| Test group | Purpose |
| --- | --- |
| test_runner | Suite API contract, terminal failures, WAITING deadlines, retries, expected failures, evidence export and origin isolation |
| test_handoff_verify | Alpha v2/DCQL validation, real API shapes using mocked HTTP, API errors, timeouts, expired requests and verification rejection |
| test_render_and_diff | Placeholder failures, rendering, result comparison and merging |
| test_reporting | Startup bounds, redaction and combined failure reporting |
| test_tls | Real loopback HTTPS with generated CA, Python requests and Java HttpClient trust |
| test_certify_metadata_release | Compile the original/patched release controller and exercise Spring MVC negotiation using cached jars |
| test_validation_probe | Public endpoint probe evidence requirements and rejection of an unverified base jar |

Product-level runs are separate: use both component modes and combined mode in
the README. Their observed failures are recorded in [live verification](live-verification.md).
Unit fixtures never establish product conformance or certification.

The 2026-10-31 full local suite completed with 55 passed and no skips. The metadata
MVC test needs cached Spring/Jackson/Servlet jars (`CERTIFY_REGRESSION_M2` may
point to an existing Maven repository); missing jars cause explicit skips rather
than a dependency installation. Actual Java adapter/reporting validation is
recorded separately in the final validation report.

Additional regression cases cover lost POST responses and state-changing GET
callbacks (no duplicate execution), malformed live browser state, unknown module
selection, retained prior reports and combined infrastructure exit code 2.
