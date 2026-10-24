"""Build an explicitly derived suite image; leave reference repos untouched."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request

BASE = 'registry.gitlab.com/openid/conformance-suite@sha256:899265eabbe900a3583b2d18cca09e077a147ab1cc74dd5382c664c8a7577373'
SOURCE_COMMIT = 'f23736032b52739e5262c91263ee102a7bc6ce1a'
SOURCE_SHA256 = '1272a3f059ef5bb9cd92b7868738b9593d9ed0194888c3662d4c8253fb1face2'


def patch_source(value):
    start = value.find('\t\tTrustManager[] trustAllCerts = {')
    end = value.find('\n\t\tSSLContext sc =', start)
    if start < 0 or end < start or value.count('sc.init(km, trustAllCerts, new java.security.SecureRandom());') != 1:
        raise ValueError('Suite source differs: refuse an unverified TLS patch')
    value = value[:start] + value[end:]
    value = value.replace('sc.init(km, trustAllCerts, new java.security.SecureRandom());',
                          'sc.init(km, null, new java.security.SecureRandom());')
    old = '.setHostnameVerifier(NoopHostnameVerifier.INSTANCE)'
    if value.count(old) != 1:
        raise ValueError('Suite hostname policy differs: inspect source before patching')
    value = value.replace(old, '.setHostnameVerifier(new org.apache.hc.client5.http.ssl.DefaultHostnameVerifier())')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    path = Path('local/release-source/conformance-suite') / SOURCE_COMMIT / 'AbstractCondition.java'
    if not path.is_file():
        url = ('https://gitlab.com/openid/conformance-suite/-/raw/' + SOURCE_COMMIT +
               '/src/main/java/net/openid/conformance/condition/AbstractCondition.java')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(urllib.request.urlopen(url, timeout=30).read())
    original = path.read_text(encoding='utf-8')
    if hashlib.sha256(original.encode()).hexdigest() != SOURCE_SHA256:
        raise ValueError('Pinned suite source checksum differs; refuse to build')
    patched = patch_source(original)
    root = Path('local/strict-suite-tls'); root.mkdir(parents=True, exist_ok=True)
    (root / 'AbstractCondition.java').write_text(patched, encoding='utf-8')
    for name in ('Dockerfile', 'ConditionTlsProbe.java'):
        shutil.copy2(Path('tools/strict-suite-tls') / name, root / name)
    (root / 'provenance.json').write_text(json.dumps({'baseImage': BASE, 'sourceCommit': SOURCE_COMMIT,
        'sourceSha256': hashlib.sha256(original.encode()).hexdigest(),
        'patchedSha256': hashlib.sha256(patched.encode()).hexdigest(),
        'policy': 'Default JVM trust managers and Apache default hostname verifier; mTLS key managers retained'}, indent=2)+'\n')
    if args.prepare_only:
        return 0
    return subprocess.run(['docker', 'build', '--build-arg', 'SUITE_BASE='+BASE,
                           '-t', 'inji-conformance-suite-strict-tls:local', str(root)]).returncode


if __name__ == '__main__':
    raise SystemExit(main())
