# Execution-time budgets

`configs/benchmark-thresholds.json` is the versioned policy. Every default limit
is **null** because no deployment SLO or approved numeric budget was supplied.
Null means `NOT_CONFIGURED`, never a performance pass. Set `BENCHMARK_CONFIG` to
another policy path, or supply the workflow-dispatch `benchmark_thresholds_json`
input. Configured limits are finite nonnegative seconds; invalid policies fail
with infrastructure exit 2 before a plan is created.

Per component (`certify`, `verify`):

- `max_run_seconds`: elapsed monotonic time of the Python plan execution,
  including rendering, API/handoff time, polling, and export; excludes stack startup.
- `max_module_seconds`: budget for each actual module's recorded execution time.

Combined `max_run_seconds` compares the sum of both sequential component execution
times. It excludes wrapper startup and inter-command gaps. This is an execution
budget, not a request-latency percentile, throughput test, or concurrent load test.
There is no invented performance baseline or implicit threshold inferred from an
already-failing run. Operators must choose and approve budgets for their environment.

The boundary is inclusive: measured time equal to its limit passes; greater time
fails. Empty/missing/nonfinite configured measurements fail closed. Reports retain
each metric, measured seconds, configured seconds and PASSED/FAILED status.
Conformance module statuses remain unchanged. `conformanceExitCode` records the
protocol outcome; `exitCode` additionally fails on a benchmark breach. Infrastructure
exit 2 takes precedence. Expected-failure lists do not suppress budget failures.

TestNG adds a separate benchmark row only when a budget was evaluated; Extent
receives that actual row. Combined JSON retains both component benchmark results
and its own budget result. A failed component budget or combined budget keeps the
build failing even if every protocol module passes. CI's real-run step has no
continue-on-error and preserves that nonzero exit; diagnostics still upload.

Validation includes below/equal/above boundaries, invalid limits, independent
component budgets, missing measurements, a real runner process gate with protocol
PASSED, and a combined process gate with two PASSED protocol records. Numeric
budgets in these tests are synthetic test inputs, not operational recommendations.

To use an approved policy:

```powershell
$env:BENCHMARK_CONFIG='C:/path/to/approved-benchmark-thresholds.json'
& 'C:/Program Files/Git/bin/bash.exe' run-full-stack-conformance.sh --combined --no-up
```

Without approved limits, the implementation can be validated but performance
acceptance remains unevaluated. Do not label a NOT_CONFIGURED result as passed.
