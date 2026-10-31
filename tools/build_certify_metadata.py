"""Build the reviewed metadata controller against the exact shipped release jar.

No upstream checkout, dependency cache, or source jar is modified. The Docker
build context contains a derived jar with exactly one class replaced.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile

BASE = "injistack/inji-certify-with-plugins@sha256:1579b2449f1a7213fe25de1f6a1509b5636f1fedf0d7f5c4cfd07b9f0fc5b346"
COMMIT = "8fdf71656979a72fa8263766d4dec3cc25127b76"
SOURCE_SHA = "1d1fbfbd10ff36e96a0a8736b80e8e5bd8234c22837cd831026d83e21b667b31"
BASE_JAR_SHA = "5452ad28d944c3caa2d68e0010dd5767cb6b217d5c814c792666f7b1c7f0f586"
CLASS = "BOOT-INF/classes/io/mosip/certify/controller/WellKnownController.class"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-jar", required=True)
    parser.add_argument("--checkout", default="local/certify-alpha-metadata-validation")
    parser.add_argument("--out", default="local/final-validation/certify-build")
    args = parser.parse_args()
    base_jar_sha = hashlib.sha256(Path(args.base_jar).read_bytes()).hexdigest()
    if base_jar_sha != BASE_JAR_SHA:
        raise ValueError("Refuse jar not matching the inspected pinned release image")
    checkout = Path(args.checkout).resolve()
    commit = subprocess.check_output(["git", "-c", "safe.directory=" + checkout.as_posix(),
                                      "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    source = checkout / "certify-service/src/main/java/io/mosip/certify/controller/WellKnownController.java"
    source_bytes = source.read_bytes().replace(b"\r\n", b"\n")
    if commit != COMMIT or hashlib.sha256(source_bytes).hexdigest() != SOURCE_SHA:
        raise ValueError("Refuse unreviewed release/source; validate the patch first")
    output = Path(args.out).resolve()
    output.mkdir(parents=True, exist_ok=True)
    target = output / "certify-service.jar"
    if target.exists():
        raise ValueError("Output already exists; choose a fresh build context")
    extracted = output / "shipped"
    with zipfile.ZipFile(args.base_jar) as jar:
        for entry in jar.infolist():
            if entry.filename.startswith(("BOOT-INF/classes/", "BOOT-INF/lib/")):
                jar.extract(entry, extracted)
    compiled = output / "compiled"
    compiled.mkdir()
    classpath = str(extracted / "BOOT-INF/classes") + os.pathsep + str(extracted / "BOOT-INF/lib/*")
    subprocess.run(["javac", "--release", "21", "-proc:none", "-cp", classpath,
                    "-d", str(compiled), str(source)], check=True)
    replacement = (compiled / CLASS[len("BOOT-INF/classes/"):]).read_bytes()
    changed = []
    with zipfile.ZipFile(args.base_jar) as original, zipfile.ZipFile(target, "w") as derived:
        if CLASS not in original.namelist():
            raise ValueError("Release jar lacks expected controller")
        for entry in original.infolist():
            data = original.read(entry.filename)
            if entry.filename == CLASS:
                data = replacement
                changed.append(entry.filename)
            derived.writestr(entry, data)
    with zipfile.ZipFile(args.base_jar) as original, zipfile.ZipFile(target) as derived:
        assert original.namelist() == derived.namelist()
        differences = [name for name in original.namelist() if original.read(name) != derived.read(name)]
        if differences != [CLASS] or derived.testzip():
            raise ValueError("Derived archive changed unexpected entries")
    provenance = dict(baseImage=BASE, releaseCommit=COMMIT, sourceSha256=SOURCE_SHA,
                      baseJarSha256=base_jar_sha,
                      derivedJarSha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                      changedEntries=changed, policy="Unsigned JSON fallback; no metadata values changed")
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    (output / "Dockerfile").write_text(
        "FROM " + BASE + "\n"
        'LABEL io.inji.harness.patch="unsigned-metadata"\n'
        "COPY --chown=1001:1001 certify-service.jar /home/inji/certify-service.jar\n")
    (output / ".dockerignore").write_text("*\n!certify-service.jar\n!Dockerfile\n")
    print(json.dumps(provenance, indent=2))


if __name__ == "__main__":
    main()
