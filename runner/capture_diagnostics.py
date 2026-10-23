#!/usr/bin/env python3
"""Save bounded, redacted Compose diagnostics; never print raw service logs."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
try:
    from .render_plans import read_env
except ImportError:
    from render_plans import read_env


def redact(value):
    for key, secret in os.environ.items():
        if re.search(r"TOKEN|PASSWORD|SECRET|ACCESS_KEY", key) and len(secret) >= 4:
            value = value.replace(secret, "[REDACTED]")
    value = re.sub(r"(?i)(bearer\s+)[A-Za-z0-9._~+/-]+=*", r"\1[REDACTED]", value)
    value = re.sub(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[REDACTED_JWT]", value)
    value = re.sub(r'(?i)((?:password|secret|access_token|pre-authorized_code|private_key)\s*[=:]\s*)[^,;\s]+', r'\1[REDACTED]', value)
    return value


def main():
    try:
        read_env()
    except (OSError, ValueError):
        pass
    root = Path("results/diagnostics"); root.mkdir(parents=True, exist_ok=True)
    code = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    diagnostics = {}
    for name, args in (("services", ["ps", "-a", "--format", "json"]),
                       ("logs", ["logs", "--no-color", "--tail", "150"])):
        try:
            process = subprocess.run(["docker", "compose", *args], capture_output=True, text=True,
                                     encoding="utf-8", errors="replace", timeout=20)
            output = redact(process.stdout + process.stderr)
            diagnostics[name] = {"exitCode": process.returncode}
            (root / (name + ".txt")).write_text(output, encoding="utf-8")
        except (OSError, subprocess.TimeoutExpired):
            diagnostics[name] = {"error": "Docker unavailable or diagnostic command timed out"}
    (root / "status.json").write_text(json.dumps(dict(wrapperExit=code, diagnostics=diagnostics), indent=2) + "\n", encoding="utf-8")
    Path("results/report-orchestration.md").write_text(
        "# Harness execution\n\nWrapper exit: " + code +
        "\n\nSee diagnostics/status.json and redacted service logs. An infrastructure failure is not a conformance pass.\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
