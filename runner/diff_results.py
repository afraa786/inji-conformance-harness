#!/usr/bin/env python3
"""Compare normalized harness outputs; regression exit=1, invalid input exit=2."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

STATUSES = {"PASSED", "FAILED", "WARNING", "SKIPPED", "INTERRUPTED", "REVIEW", "EXPECTED_FAILURE", "EXPECTED_SKIP"}
FAILURES = {"FAILED", "INTERRUPTED"}


def load_modules(path: str) -> dict[str, str]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("modules"), list):
        raise ValueError("results must contain a modules list")
    result = {}
    for module in data["modules"]:
        if not isinstance(module, dict):
            raise ValueError("module must be an object")
        name, status = module.get("name"), module.get("status")
        component = module.get("component", data.get("component", ""))
        if not isinstance(name, str) or not name or status not in STATUSES:
            raise ValueError("module requires a name and recognized status")
        key = f"{component}/{name}" if component else name
        if module.get("variant"):
            key += json.dumps(module["variant"], sort_keys=True, separators=(",", ":"))
        if key in result:
            raise ValueError(f"duplicate module: {key}")
        result[key] = status
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("previous")
    parser.add_argument("current")
    args = parser.parse_args()
    try:
        previous = load_modules(args.previous) if Path(args.previous).is_file() else {}
        current = load_modules(args.current)
    except (OSError, ValueError, TypeError) as error:
        print(f"Invalid results: {error}", file=sys.stderr)
        return 2
    failing = [n for n, s in current.items() if s in FAILURES and previous.get(n) not in FAILURES]
    passing = [n for n, s in current.items() if s == "PASSED" and previous.get(n) != s]
    changed = [n for n in current.keys() & previous.keys() if current[n] != previous[n]]
    for label, names in (("Newly failing", failing), ("Newly passing", passing), ("Changed status", changed)):
        print(f"{label}: {len(names)}")
        for name in sorted(names):
            print(f"  {name}: {previous.get(name, 'ABSENT')} -> {current[name]}")
    for name in sorted(previous.keys() - current.keys()):
        print(f"Removed module: {name} (previously {previous[name]})")
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
