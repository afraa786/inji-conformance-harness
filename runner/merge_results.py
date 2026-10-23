#!/usr/bin/env python3
"""Merge this invocation's results and produce a compact Markdown report."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from diff_results import load_modules


def main() -> int:
    root = Path("results")
    modules, runs, errors = [], {}, []
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
            modules.extend(dict(m, component=component) for m in data["modules"])
        except (OSError, ValueError, TypeError) as error:
            errors.append(f"{component}: invalid results ({error})")
    summary = {s.lower(): sum(m["status"] == s for m in modules) for s in
               ("PASSED", "FAILED", "INTERRUPTED", "REVIEW", "SKIPPED", "WARNING", "EXPECTED_FAILURE", "EXPECTED_SKIP")}
    output = dict(component="combined", runs=runs, summary=summary, modules=modules, errors=errors)
    root.mkdir(exist_ok=True)
    (root / "results-combined.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    report = ["# Combined conformance report", "", "| Component | Runner exit |", "| --- | --- |"]
    report += [f"| {c} | {code} |" for c, code in runs.items()]
    report += ["", " | ".join(f"{s}: {n}" for s, n in summary.items()), ""] + errors
    (root / "report-combined.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    return int(bool(errors or summary["failed"] or summary["interrupted"] or any(runs.values())))


if __name__ == "__main__":
    sys.exit(main())
