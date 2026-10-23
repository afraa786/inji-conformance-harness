#!/usr/bin/env python3
"""Bound Compose startup including image pulls. No deletion/reset of volumes."""
import os
from pathlib import Path
import subprocess
import sys
try:
    from .render_plans import read_env
except ImportError:
    from render_plans import read_env


def main():
    root = Path("results/diagnostics"); root.mkdir(parents=True, exist_ok=True)
    try:
        read_env()
        timeout = int(os.environ.get("STACK_START_TIMEOUT_SECONDS", "1200"))
        if timeout <= 0:
            raise ValueError()
        with (root / "compose-up.txt").open("w", encoding="utf-8") as log:
            result = subprocess.run(["docker", "compose", "--progress", "plain", "up", "-d", *sys.argv[1:]],
                                    stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
        if result.returncode:
            print("Compose startup failed; see results/diagnostics/compose-up.txt", file=sys.stderr)
            return 2
        return 0
    except subprocess.TimeoutExpired:
        print("Compose startup/image-pull timeout; see results/diagnostics/compose-up.txt", file=sys.stderr)
        return 2
    except (ValueError, OSError):
        print("Cannot start Compose; check Docker and STACK_START_TIMEOUT_SECONDS", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
