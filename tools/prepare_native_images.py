"""Reproduce the reviewed native fixes without touching existing containers/volumes."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import uuid


def run(*args):
    subprocess.run(list(args), check=True)


def copy_jar(image, container_path, destination, expected):
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        name = "inji-native-build-" + uuid.uuid4().hex[:12]
        run("docker", "create", "--name", name, "--entrypoint", "/bin/true", image)
        try:
            run("docker", "cp", name + ":" + container_path, str(destination))
        finally:
            # Only this newly-created, stopped, volume-free helper is removed.
            run("docker", "rm", name)
    if hashlib.sha256(destination.read_bytes()).hexdigest() != expected:
        raise ValueError("Unexpected immutable image jar; refuse to patch")


def main():
    from build_certify_metadata import BASE, COMMIT, SOURCE_SHA, BASE_JAR_SHA
    root = Path.cwd()
    checkout = root / "local/certify-alpha-metadata-validation"
    if not checkout.exists():
        run("git", "clone", "--depth", "1", "--branch", "v1.0.0-alpha.1",
            "https://github.com/inji/inji-certify.git", str(checkout))
    git = ["git", "-c", "safe.directory=" + checkout.as_posix(), "-C", str(checkout)]
    if subprocess.check_output(git + ["rev-parse", "HEAD"], text=True).strip() != COMMIT:
        raise ValueError("Existing source checkout is not the reviewed release")
    source = checkout / "certify-service/src/main/java/io/mosip/certify/controller/WellKnownController.java"
    digest = hashlib.sha256(source.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    if digest != SOURCE_SHA:
        if digest != "84a2cf4ff2a81e70a5158cc86c69ecee24a33d241e001b0e311e249d5324a0f4":
            raise ValueError("Preserve unreviewed source modifications; refuse to apply patch")
        run(*(git + ["apply", str(root / "patches/certify-alpha-unsigned-metadata.patch")]))
    copy_jar(BASE, "/home/inji/certify-service.jar", root / "local/native-ci/certify-base.jar", BASE_JAR_SHA)
    verify = "injistack/inji-verify-service@sha256:064fcfa12773ec11834d5d769f2b6bb6bcc61cf9ae89ae918f8ae3934419907d"
    copy_jar(verify, "/home/inji/verify-service.jar", root / "local/blocker-resolution/verify-service.jar",
             "b7c43dc937d8731e4f82373bb5da6a941d05658742dba9a8a924c4ab11d52881")
    run(sys.executable, "tools/build_certify_metadata.py", "--base-jar", "local/native-ci/certify-base.jar", "--out", "local/native-ci/certify-build")
    run(sys.executable, "tools/build_verify_fixes.py", "--prepare", "--out", "local/native-ci/verify-build")
    for component, image in [("certify", "inji-certify-unsigned-metadata:validation"), ("verify", "inji-verify-status-metadata:validation-v2")]:
        run("docker", "build", "-t", image, "local/native-ci/" + component + "-build")
    output = Path("results/derived-image-provenance.json")
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps({c: json.loads(Path("local/native-ci", c + "-build/provenance.json").read_text())
                                  for c in ("certify", "verify")}, indent=2) + "\n")


if __name__ == "__main__":
    main()
