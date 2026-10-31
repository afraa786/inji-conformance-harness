"""Native checker + real HTTPS/signed tokens. Does not claim full VP conformance."""
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import threading
import time
import zlib

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils
from runner.prepare_local import certificates

ROOT = Path(__file__).resolve().parents[2]


def b64(data):
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def jwt(key, payload, typ, embed=False):
    header = {"alg": "ES256", "typ": typ}
    if embed:
        numbers = key.public_key().public_numbers()
        header["jwk"] = dict(kty="EC", crv="P-256", x=b64(numbers.x.to_bytes(32, "big")), y=b64(numbers.y.to_bytes(32, "big")))
    signing = (b64(json.dumps(header).encode()) + "." + b64(json.dumps(payload).encode())).encode()
    r, s = utils.decode_dss_signature(key.sign(signing, ec.ECDSA(hashes.SHA256())))
    return signing.decode() + "." + b64(r.to_bytes(32, "big") + s.to_bytes(32, "big"))


@pytest.fixture(scope="module")
def native_checker(tmp_path_factory):
    runtime = ROOT / "local/blocker-resolution/verify-runtime/BOOT-INF"
    if not runtime.is_dir() or not shutil.which("javac"):
        pytest.skip("Requires extracted pinned Verify runtime and Java 21; no dependencies are installed")
    work = tmp_path_factory.mktemp("native-status-check")
    previous = Path.cwd()
    try:
        os.chdir(work)
        certificates()
    finally:
        os.chdir(previous)
    driver = work / "StatusProbe.java"
    driver.write_text('''
import io.inji.verify.services.impl.TokenStatusListChecker;
public class StatusProbe {
 public static void main(String[] args) throws Exception {
  if (args[0].equals("--metadata")) {
   var mapper=new com.fasterxml.jackson.databind.ObjectMapper().findAndRegisterModules();
   var dto=new io.inji.verify.dto.authorizationrequest.AuthorizationRequestResponseDto("redirect_uri:https://verify.example/response",null,null,"nonce-value","https://verify.example/response",false,false);
   String json=mapper.writeValueAsString(dto);
   var restored=mapper.readValue(json,io.inji.verify.dto.authorizationrequest.AuthorizationRequestResponseDto.class);
   if (!restored.getNonce().equals("nonce-value") || !json.contains("clientMetadata")) throw new AssertionError("Metadata roundtrip failed");
   System.out.println(json); return;
  }
  var result=TokenStatusListChecker.check(java.nio.file.Files.readString(java.nio.file.Path.of(args[0])));
  System.out.println(new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(result));
 }
}''')
    cp = os.pathsep.join([str(runtime / "classes"), str(runtime / "lib/*")])
    dto_source = ROOT / "local/blocker-resolution/verify-patched-source/AuthorizationRequestResponseDto.java"
    subprocess.run(["javac", "--release", "21", "-parameters", "-cp", cp, "-d", str(work), str(dto_source)], check=True, capture_output=True)
    cp = str(work) + os.pathsep + cp
    subprocess.run(["javac", "--release", "21", "-proc:none", "-cp", cp, "-d", str(work),
                    str(ROOT / "tools/verify-fixes/TokenStatusListChecker.java"), str(driver)], check=True, capture_output=True)
    state = dict(token="", status=200, requests=0)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            state["requests"] += 1
            self.send_response(state["status"])
            self.send_header("Content-Type", "application/statuslist+jwt")
            self.end_headers()
            self.wfile.write(state["token"].encode())

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(work / "local/tls/server.crt"), str(work / "local/tls/server.key"))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    uri = "https://localhost:" + str(server.server_port) + "/status-list"
    key = ec.generate_private_key(ec.SECP256R1())
    metadata = subprocess.run(["java", "-cp", cp, "StatusProbe", "--metadata"], capture_output=True, text=True)
    assert metadata.returncode == 0, metadata.stderr
    assert json.loads(metadata.stdout)["clientMetadata"]["vp_formats_supported"]["dc+sd-jwt"]["sd-jwt_alg_values"] == ["ES256"]

    def check(value=0, **options):
        now = int(time.time())
        claims = dict(sub=options.get("sub", uri), iat=now - 2, exp=now + 60, ttl=60,
                      status_list=dict(bits=options.get("bits", 1), lst=b64(zlib.compress(bytes([value])))))
        claims.update(options.get("claims", {}))
        state["status"] = options.get("http", 200)
        state["token"] = jwt(options.get("key", key), claims, options.get("typ", "statuslist+jwt"))
        credential = dict(iss="https://issuer.example", iat=now, exp=now + 120)
        if not options.get("no_status"):
            credential["status"] = dict(status_list=dict(uri=uri, idx=options.get("index", 0)))
        path = work / "credential.jwt"
        path.write_text(jwt(key, credential, "dc+sd-jwt", True))
        result = subprocess.run(["java", "-Djavax.net.ssl.trustStore=" + str(work / "local/tls/truststore.jks"),
            "-Djavax.net.ssl.trustStoreType=JKS", "-cp", str(work) + os.pathsep + cp, "StatusProbe", str(path)],
            capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    yield check, state
    server.shutdown()
    server.server_close()


def test_valid_revoked_and_no_stale_cache(native_checker):
    check, state = native_checker
    before = state["requests"]
    assert check()[0]["valid"] is True
    result = check(1)[0]
    assert result["valid"] is False and result["error"]["errorCode"] == "CREDENTIAL_REVOKED"
    assert state["requests"] == before + 2


@pytest.mark.parametrize("options,code", [
    ({"http": 503}, "STATUS_UNAVAILABLE"),
    ({"claims": {"exp": 1}}, "STATUS_EXPIRED"),
    ({"claims": {"iat": 1, "ttl": 1}}, "STATUS_STALE"),
    ({"sub": "https://other.example/status"}, "STATUS_SUBJECT_INVALID"),
    ({"index": 99}, "STATUS_INDEX_INVALID"),
    ({"typ": "JWT"}, "STATUS_TOKEN_TYPE_INVALID")])
def test_fail_closed_for_unavailable_and_invalid_status(native_checker, options, code):
    result = native_checker[0](**options)[0]
    assert not result["valid"] and result["error"]["errorCode"] == code


def test_status_signature_cannot_supply_its_own_trust_key(native_checker):
    result = native_checker[0](key=ec.generate_private_key(ec.SECP256R1()))[0]
    assert not result["valid"] and result["error"]["errorCode"] == "STATUS_SIGNATURE_INVALID"


def test_lsb_multibit_and_optional_absence(native_checker):
    check, state = native_checker
    assert check(4, bits=2, index=0)[0]["valid"]
    assert check(4, bits=2, index=1)[0]["error"]["errorCode"] == "CREDENTIAL_REVOKED"
    before = state["requests"]
    assert check(no_status=True) == []
    assert state["requests"] == before
