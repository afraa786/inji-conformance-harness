"""Offline contract tests for the evidence probe; these are not live results."""
import json
import sys

import pytest

from tools import final_validation_probe as probe
from tools import build_certify_metadata as builder


def test_image_builder_rejects_unverified_base_jar_before_building(tmp_path, monkeypatch):
    base = tmp_path / "wrong.jar"
    base.write_bytes(b"unverified artifact")
    output = tmp_path / "build"
    monkeypatch.setattr(sys, "argv", ["builder", "--base-jar", str(base), "--out", str(output)])
    with pytest.raises(ValueError, match="pinned release image"):
        builder.main()
    assert not output.exists()


@pytest.mark.parametrize("jwt_content_type,changed,expected", [
    ("application/json", False, 0), (None, False, 1), ("application/json", True, 1)])
def test_probe_requires_matching_real_json_and_verified_requests(
        tmp_path, monkeypatch, jwt_content_type, changed, expected):
    output = tmp_path / "probe.json"
    monkeypatch.setattr(sys, "argv", ["probe", "--out", str(output)])
    calls = []

    class Response:
        status_code = 200

        def __init__(self, content_type, body):
            self.headers = {} if content_type is None else {"Content-Type": content_type}
            self.content = json.dumps(body).encode()
            self.body = body

        def json(self):
            return self.body

    def get(url, **kwargs):
        calls.append(kwargs)
        if "actuator/health" in url:
            return Response("application/json", {"status": "UP"})
        if "openid-credential-issuer" in url:
            jwt = kwargs["headers"]["Accept"] == "application/jwt"
            return Response(jwt_content_type if jwt else "application/json",
                            {"credential_issuer": "https://other.example" if jwt and changed else "https://issuer.example"})
        return Response("application/json", {"issuer": "https://issuer.example"})

    monkeypatch.setattr(probe.requests, "get", get)
    assert probe.main() == expected
    evidence = json.loads(output.read_text())
    assert evidence["unsignedFallbackVerified"] is (expected == 0)
    assert len(calls) == 6
    assert all(call["verify"] == "local/tls/ca.crt" and call["allow_redirects"] is False for call in calls)
