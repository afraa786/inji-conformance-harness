#!/usr/bin/env python3
"""Optional MinIO upload. No credentials: no upload; partial config: fail."""
import os
from pathlib import Path
import sys


def main():
    names = ("MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY")
    values = [os.environ.get(n) for n in names]
    if not any(values):
        return 0
    if not all(values):
        print("MinIO configuration incomplete", file=sys.stderr)
        return 2
    try:
        import boto3
        from botocore.config import Config
        client = boto3.client("s3", endpoint_url=values[0], aws_access_key_id=values[1],
                              aws_secret_access_key=values[2], config=Config(s3={"addressing_style": "path"}))
        root = Path("results")
        files = [p for p in root.rglob("*") if p.is_file() and "previous" not in p.parts and "rendered" not in p.parts]
        if not files:
            raise ValueError("No results")
        prefix = os.environ.get("MINIO_RESULTS_PREFIX", "conformance").strip("/")
        for path in files:
            client.upload_file(str(path), "automationtests", prefix + "/" + path.relative_to(root).as_posix())
    except Exception:
        print("MinIO upload failed (check optional dependency, bucket and credentials)", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
