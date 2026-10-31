#!/usr/bin/env python3
"""Merge this invocation's results and produce a compact Markdown report."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from diff_results import load_modules
from benchmarks import load_policy, evaluate, DEFAULT_CONFIG


def main() -> int:
    if len(sys.argv) != 3 or any(code not in {"0", "1", "2"} for code in sys.argv[1:]):
        print("Expected exactly two runner exit codes (0, 1 or 2)", file=sys.stderr)
        return 2
    root = Path("results")
    modules, runs, errors, durations, component_benchmarks = [], {}, [], [], {}
    for component, code in zip(("certify", "verify"), sys.argv[1:]):
        runs[component] = int(code)
        path = root / f"results-{component}.json"
        if not path.is_file():
            errors.append(f"{component}: no results (runner exit {code})")
            continue
        try:
            load_modules(str(path))
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("component") != component or not data["modules"]:
                raise ValueError("wrong component or empty module list")
            if data.get("errors") or data.get("exitCode", int(code)) != int(code):
                errors.append(f"{component}: infrastructure errors or exit/result mismatch")
            modules.extend(dict(m, component=component) for m in data["modules"])
            durations.append(data.get("durationSeconds"))
            component_benchmarks[component] = data.get("benchmark", {"status": "NOT_CONFIGURED", "checks": []})
        except (OSError, ValueError, TypeError) as error:
            errors.append(f"{component}: invalid results ({error})")
    summary = {s.lower(): sum(m["status"] == s for m in modules) for s in
               ("PASSED", "FAILED", "INTERRUPTED", "REVIEW", "SKIPPED", "WARNING", "EXPECTED_FAILURE", "EXPECTED_SKIP")}
    exit_code = (2 if errors or 2 in runs.values() else
                 int(bool(summary["failed"] or summary["interrupted"] or any(runs.values()))))
    output = dict(component="combined", runs=runs, summary=summary, modules=modules, errors=errors, exitCode=exit_code)
    try:
        policy = load_policy(os.environ.get("BENCHMARK_CONFIG", str(DEFAULT_CONFIG)))
        duration = sum(durations) if len(durations) == 2 and all(isinstance(d, (int, float)) and not isinstance(d, bool) for d in durations) else None
        output["durationSeconds"] = duration
        output["benchmark"] = evaluate("combined", duration, modules, policy)
        output["componentBenchmarks"] = component_benchmarks
        if any(b["status"] == "FAILED" for b in component_benchmarks.values()):
            output["benchmark"]["status"] = "FAILED"
        elif output["benchmark"]["status"] == "NOT_CONFIGURED" and any(b["status"] == "PASSED" for b in component_benchmarks.values()):
            output["benchmark"]["status"] = "PASSED"
        if output["benchmark"]["status"] == "FAILED" and exit_code == 0:
            exit_code = 1
    except (OSError, ValueError, TypeError):
        errors.append("Invalid benchmark policy or execution measurements")
        exit_code = 2
    output["exitCode"] = exit_code
    root.mkdir(exist_ok=True)
    (root / "results-combined.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    report = ["# Combined conformance report", "", "| Component | Runner exit |", "| --- | --- |"]
    report += [f"| {c} | {code} |" for c, code in runs.items()]
    report += ["", " | ".join(f"{s}: {n}" for s, n in summary.items()), ""] + errors
    if output.get("benchmark"):
        report += ["", "Benchmark combined: " + output["benchmark"]["status"]]
        for check in output["benchmark"]["checks"]:
            report.append("- {}: {}s <= {}s: {}".format(check["subject"], check["measuredSeconds"], check["limitSeconds"], check["status"]))
        for component, benchmark in component_benchmarks.items():
            report.append("- " + component + " benchmark: " + benchmark["status"])
    (root / "report-combined.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
