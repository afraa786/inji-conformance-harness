#!/usr/bin/env python3
"""Render typed JSON plan templates using environment variables, never shell substitution."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def read_env(path=".env"):
    """Load literal KEY=value inputs without executing .env as code. Shell wins."""
    if not Path(path).is_file():
        return
    for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            raise ValueError("Invalid .env line (expected literal KEY=value)")
        os.environ.setdefault(key, value.strip().strip("\"'"))


def render_plan(component, target, suite_url, env=None):
    env = dict(os.environ if env is None else env)
    env.update(TARGET=target, SUITE_URL=suite_url)
    env.setdefault("ALIAS", "inji-" + component)
    env.setdefault("REDIRECT_URI", suite_url.rstrip("/") + "/test/a/" + env["ALIAS"] + "/callback")
    name = "issuer" if component == "certify" else "verifier"
    template = json.loads((ROOT / "configs" / (name + "-plan.json.tpl")).read_text(encoding="utf-8"))
    template.pop("_comment", None)

    def variable(key):
        value = env.get(key)
        if not value and env.get(key + "_FILE"):
            value = Path(env[key + "_FILE"]).read_text(encoding="utf-8")
        if value is None or not value.strip():
            raise ValueError("Missing plan variable: " + key + " (or " + key + "_FILE)")
        if key.endswith("_JSON"):
            try:
                return json.loads(value)
            except ValueError as error:
                raise ValueError("Invalid JSON variable: " + key) from error
        return value

    def replace(value):
        if isinstance(value, dict):
            return {k: replace(v) for k, v in value.items()}
        if isinstance(value, list):
            return [replace(v) for v in value]
        if not isinstance(value, str):
            return value
        match = TOKEN.fullmatch(value)
        if match:
            return variable(match[1])
        return TOKEN.sub(lambda m: str(variable(m[1])), value)

    plan = replace(template)
    if "{{" in json.dumps(plan) or not isinstance(plan["variant"], dict):
        raise ValueError("Unresolved placeholder or invalid variant object")
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component", choices=("certify", "verify"), required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--suite-url", default="https://localhost:8443")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        read_env()
        plan = render_plan(args.component, args.target, args.suite_url)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError) as error:
        # JSON errors can contain input snippets, so print variable names only.
        print(str(error) if type(error) is ValueError else "Cannot read/write plan inputs", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
