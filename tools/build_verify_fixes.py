"""Build the reviewed native Verify fixes against the retained exact release jar.

Prepare the two patched source files from patches/verify-alpha-status-metadata.patch
under local/blocker-resolution/verify-patched-source. Original checkouts are untouched.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import urllib.request
import shutil
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="local/blocker-resolution/verify-build")
    parser.add_argument("--prepare", action="store_true", help="Fetch/hash-check exact release source and apply the reviewed patch to copies")
    args = parser.parse_args()
    root = Path("local/blocker-resolution").resolve()
    original = root / "verify-service.jar"
    expected = "b7c43dc937d8731e4f82373bb5da6a941d05658742dba9a8a924c4ab11d52881"
    if hashlib.sha256(original.read_bytes()).hexdigest() != expected:
        raise ValueError("Unverified Verify base jar")
    source = root / "verify-patched-source"
    if args.prepare:
        source.mkdir(parents=True, exist_ok=True)
        files = {
            "verify-service/src/main/java/io/inji/verify/dto/authorizationrequest/AuthorizationRequestResponseDto.java": "b868f9fd7978e868e531a09465350e7eccd3e71a215f3d03d1bc0fe180982668",
            "verify-service/src/main/java/io/inji/verify/services/impl/VCVerificationServiceImpl.java": "ef788622c20072b8ebd93e4f147cc613c26b3cba6448672a6b77523a85fc6741"}
        with tempfile.TemporaryDirectory(dir=root) as directory:
            tree = Path(directory)
            for name, digest in files.items():
                url = "https://raw.githubusercontent.com/inji/inji-verify/4c4289026968beb535d3dbdd500947152c43f708/" + name
                value = urllib.request.urlopen(url, timeout=30).read().replace(b"\r\n", b"\n")
                if hashlib.sha256(value).hexdigest() != digest:
                    raise ValueError("Pinned release source checksum mismatch")
                path = tree / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(value)
            subprocess.run(["git", "apply", str(Path("patches/verify-alpha-status-metadata.patch").resolve())], cwd=tree, check=True)
            for name in files:
                target_source = source / Path(name).name
                value = (tree / name).read_bytes().replace(b"\r\n", b"\n")
                if target_source.exists() and target_source.read_bytes().replace(b"\r\n", b"\n") != value:
                    raise ValueError("Existing source differs; preserve it and review before rebuilding")
                if not target_source.exists():
                    target_source.write_bytes(value)
    compiled = root / "verify-compiled"
    compiled.mkdir(exist_ok=True)
    runtime = root / "verify-runtime/BOOT-INF"
    if not runtime.is_dir():
        with zipfile.ZipFile(original) as jar:
            for entry in jar.infolist():
                if entry.filename.startswith(("BOOT-INF/classes/", "BOOT-INF/lib/")):
                    jar.extract(entry, root / "verify-runtime")
    classpath = os.pathsep.join([str(runtime / "classes"), str(runtime / "lib/*")])
    subprocess.run(["javac", "--release", "21", "-parameters", "-cp", classpath, "-d", str(compiled),
                    str(source / "AuthorizationRequestResponseDto.java"),
                    str(source / "VCVerificationServiceImpl.java"),
                    "tools/verify-fixes/TokenStatusListChecker.java"], check=True)
    out = Path(args.out).resolve()
    out.mkdir(exist_ok=True)
    target = out / "verify-service.jar"
    if target.exists():
        raise ValueError("Preserve previous build; use a separate workspace for another candidate")
    replacements = {"BOOT-INF/classes/" + p.relative_to(compiled).as_posix(): p.read_bytes()
                    for p in compiled.rglob("*.class")}
    with zipfile.ZipFile(original) as base, zipfile.ZipFile(target, "w") as new:
        for entry in base.infolist():
            new.writestr(entry, replacements.pop(entry.filename, base.read(entry.filename)))
        for name, data in replacements.items():
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            new.writestr(entry, data)
    with zipfile.ZipFile(original) as base, zipfile.ZipFile(target) as new:
        changes = [n for n in new.namelist() if n not in base.namelist() or base.read(n) != new.read(n)]
        if len(changes) != 3 or new.testzip():
            raise ValueError("Unexpected modified archive entries: " + str(changes))
    (out / "Dockerfile").write_text(
        "FROM injistack/inji-verify-service@sha256:064fcfa12773ec11834d5d769f2b6bb6bcc61cf9ae89ae918f8ae3934419907d\n"
        'LABEL io.inji.harness.patch="metadata-and-sd-jwt-status"\n'
        "COPY --chown=1001:1001 verify-service.jar /home/inji/verify-service.jar\n")
    (out / ".dockerignore").write_text("*\n!verify-service.jar\n!Dockerfile\n")
    report = dict(baseJarSha256=expected, derivedJarSha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                  changedEntries=changes, sourceCommit="4c4289026968beb535d3dbdd500947152c43f708",
                  sourceSha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob("*.java")},
                  checkerSha256=hashlib.sha256(Path("tools/verify-fixes/TokenStatusListChecker.java").read_bytes()).hexdigest(),
                  profile="Native metadata; same-issuer-key SD-JWT Token Status List; HTTPS, no cache, fail closed")
    (out / "provenance.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
