"""Probe real public endpoints with the retained development CA; save responses."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import requests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    checks = [("suite", "https://localhost:8443/plans.html", "text/html"),
              ("certify-health", "https://localhost:8446/v1/certify/actuator/health", "application/json"),
              ("verify-health", "https://localhost:8447/v1/verify/actuator/health", "application/json"),
              ("issuer-json", "https://localhost:8446/.well-known/openid-credential-issuer", "application/json"),
              ("issuer-jwt-accept", "https://localhost:8446/.well-known/openid-credential-issuer", "application/jwt"),
              ("native-as", "https://localhost:8446/.well-known/oauth-authorization-server", "application/json")]
    records = []
    for name, url, accept in checks:
        response = requests.get(url, headers={"Accept": accept}, verify="local/tls/ca.crt",
                                allow_redirects=False, timeout=30)
        record = dict(name=name, url=url, accept=accept, status=response.status_code,
                      contentType=response.headers.get("Content-Type"), bytes=len(response.content),
                      caVerification=True)
        if "json" in response.headers.get("Content-Type", "").lower():
            record["body"] = response.json()
        records.append(record)
        print("{}: HTTP {} | {} | {} bytes | CA verified".format(
            name, response.status_code, record["contentType"], len(response.content)), flush=True)
    by_name = {record["name"]: record for record in records}
    fallback = (by_name["issuer-json"].get("body") == by_name["issuer-jwt-accept"].get("body")
                and bool(by_name["issuer-json"].get("body"))
                and (by_name["issuer-jwt-accept"]["contentType"] or "").startswith("application/json"))
    healthy = all(by_name[name].get("body", {}).get("status") == "UP"
                  for name in ("certify-health", "verify-health"))
    result = dict(observedAt=datetime.now(timezone.utc).isoformat(), checks=records,
                  unsignedFallbackVerified=fallback, applicationHealthUp=healthy)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("Unsigned fallback through real gateway/security: " + str(fallback))
    metadata = by_name["native-as"].get("body", {})
    print("Native AS authorization_endpoint: " + str(metadata.get("authorization_endpoint", "ABSENT")))
    print("Native AS interactive_authorization_endpoint: " + str(metadata.get("interactive_authorization_endpoint", "ABSENT")))
    return 0 if fallback and healthy and all(record["status"] == 200 for record in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
