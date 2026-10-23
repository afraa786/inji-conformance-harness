"""Real loopback TLS interoperability test; this is not an Inji/suite E2E test."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import ssl
import subprocess
import threading
import time

import pytest
import requests

from runner.common import RunnerError, target_request
from runner.conformance_runner import SuiteAPI
from runner.prepare_local import certificates


def test_generated_ca_trusted_by_python_and_java(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    certificates()
    root = tmp_path / "local/tls"
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(root / "ca.crt"))
    monkeypatch.setenv("OIDC_SUITE_INSECURE", "false")
    monkeypatch.delenv("OIDC_SUITE_TOKEN", raising=False)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"verified":true}')

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(root / "server.crt"), str(root / "server.key"))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = "https://127.0.0.1:" + str(server.server_port)
    try:
        assert target_request("GET", base + "/health", time.monotonic() + 10) == {"verified": True}
        api = SuiteAPI(base, time.monotonic() + 10)
        assert api.session.verify is True
        assert api.request("GET", "/health") == {"verified": True}
        api.session.close()
        source = tmp_path / "CheckTls.java"
        source.write_text('''import java.net.URI;
import java.net.http.*;
class CheckTls {
  public static void main(String[] args) throws Exception {
    var response = HttpClient.newHttpClient().send(
        HttpRequest.newBuilder(URI.create(args[0])).GET().build(), HttpResponse.BodyHandlers.ofString());
    if (response.statusCode() != 200 || !response.body().equals("{\\\"verified\\\":true}"))
      throw new IllegalStateException("TLS test failed");
  }
}
''', encoding="utf-8")
        result = subprocess.run(["java", "-Djavax.net.ssl.trustStore=" + str(root / "truststore.jks"),
            "-Djavax.net.ssl.trustStoreType=JKS", str(source), base + "/health"], capture_output=True, timeout=30)
        assert result.returncode == 0, "Java did not trust the generated development CA"
        monkeypatch.setenv("REQUESTS_CA_BUNDLE", requests.certs.where())
        # Public trust roots do not contain this development CA.
        with pytest.raises(RunnerError, match="TLS validation failed"):
            target_request("GET", base + "/health", time.monotonic() + 10)
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
