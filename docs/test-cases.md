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

Product-level runs are separate: use both component modes and combined mode in
the README. Their observed failures are recorded in [live verification](live-verification.md).
Unit fixtures never establish product conformance or certification.

Additional regression cases cover lost POST responses and state-changing GET
callbacks (no duplicate execution), malformed live browser state, unknown module
selection, retained prior reports and combined infrastructure exit code 2.
