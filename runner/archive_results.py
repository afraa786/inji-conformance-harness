"""Preserve previous root outputs before a fresh wrapper invocation."""
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys
import uuid


def archive(mode, root=Path("results")):
    if mode not in {"certify", "verify", "combined"}:
        raise ValueError("Invalid archive mode")
    components = ("certify", "verify", "combined") if mode == "combined" else (mode,)
    files = [root / (prefix + component + suffix) for component in components
             for prefix, suffix in (("results-", ".json"), ("report-", ".md"), ("badge-", ".svg"))]
    files = [path for path in files if path.is_file()]
    if not files:
        return None
    destination = root / "previous" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8])
    destination.mkdir(parents=True)
    for path in files:
        shutil.copy2(path, destination / path.name)
    return destination


if __name__ == "__main__":
    saved = archive(sys.argv[1])
    if saved:
        print(saved.as_posix())
