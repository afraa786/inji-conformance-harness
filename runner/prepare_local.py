#!/usr/bin/env python3
"""Prepare isolated alpha-release dev fixtures and a local CA; never touch reference repos.

Fetch only the named release configuration/SQL assets. Existing private .env and
keys are retained. Run from the repository root before Docker Compose.
"""
import base64
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

try:
    from .render_plans import read_env
except ImportError:
    from render_plans import read_env

RELEASE = "v1.0.0-alpha.1"
CERTIFY_ROOT = "docker-compose/docker-compose-injistack/"


def source(repo, path):
    cached = Path("local/release-source") / repo / path
    if not cached.is_file():
        url = f"https://raw.githubusercontent.com/inji/{repo}/{RELEASE}/{path}"
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(urllib.request.urlopen(url, timeout=30).read())
    return cached.read_text(encoding="utf-8")


def text(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(value)


def keytool(*args):
    result = subprocess.run([shutil.which("keytool") or "keytool", *args], capture_output=True, env=os.environ)
    if result.returncode:
        raise RuntimeError("keytool failed; inspect Java installation and local certificate files")


def certificates():
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    import ipaddress
    root = Path("local/tls"); root.mkdir(parents=True, exist_ok=True)
    if not (root / "server.key").exists():
        now = datetime.now(timezone.utc)
        ca_key = ec.generate_private_key(ec.SECP256R1())
        ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Inji Harness Development CA")])
        ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key())
              .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5))
              .not_valid_after(now + timedelta(days=365)).add_extension(x509.BasicConstraints(ca=True, path_length=0), True)
              .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), True)
              .sign(ca_key, hashes.SHA256()))
        leaf_key = ec.generate_private_key(ec.SECP256R1())
        leaf = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
                .issuer_name(ca_name).public_key(leaf_key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=90))
                .add_extension(x509.SubjectAlternativeName([x509.DNSName(n) for n in
                    ("localhost", "suite.test", "certify.test", "verify.test", "httpd")] +
                    [x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), False)
                .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), False)
                .sign(ca_key, hashes.SHA256()))
        for filename, key in (("ca.key", ca_key), ("server.key", leaf_key)):
            (root / filename).write_bytes(key.private_bytes(serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        (root / "ca.crt").write_bytes(ca.public_bytes(serialization.Encoding.PEM))
        (root / "server.crt").write_bytes(leaf.public_bytes(serialization.Encoding.PEM) + ca.public_bytes(serialization.Encoding.PEM))
    os.environ.setdefault("DEV_TRUSTSTORE_PASSWORD", "DEV_ONLY_CHANGE_ME")
    if not (root / "truststore.jks").exists():
        # JVM loads certificate-only JKS without a password (no integrity check).
        # No password is placed in JAVA_TOOL_OPTIONS or application logs.
        keytool("-importcert", "-noprompt", "-alias", "harness-ca", "-file", str(root / "ca.crt"),
                "-keystore", str(root / "truststore.jks"), "-storetype", "JKS", "-storepass:env", "DEV_TRUSTSTORE_PASSWORD")
    os.environ.setdefault("VERIFY_KEYSTORE_PASSWORD", "DEV_ONLY_CHANGE_ME")
    if not (root / "verify-keystore.p12").exists():
        keytool("-genkeypair", "-alias", "verify-ed25519", "-keyalg", "Ed25519", "-dname", "CN=Harness Test Verifier",
                "-validity", "90", "-keystore", str(root / "verify-keystore.p12"), "-storetype", "PKCS12",
                "-storepass:env", "VERIFY_KEYSTORE_PASSWORD")
    # Independent test issuer key for credentials emitted by the real suite wallet.
    if not Path("local/verifier-signing-jwk.json").exists():
        key = ec.generate_private_key(ec.SECP256R1()).private_numbers()
        encode = lambda n: base64.urlsafe_b64encode(n.to_bytes(32, "big")).decode().rstrip("=")
        jwk = dict(kty="EC", crv="P-256", alg="ES256", use="sig", kid="harness-test-issuer",
                   d=encode(key.private_value), x=encode(key.public_numbers.x), y=encode(key.public_numbers.y))
        text("local/verifier-signing-jwk.json", json.dumps(jwk, indent=2) + "\n")
    # The alpha's SD-JWT verifier requires an x5c chain. The suite propagates
    # credential.signing_jwk.x5c into its real signed credentials.
    jwk_path = Path("local/verifier-signing-jwk.json")
    jwk = json.loads(jwk_path.read_text(encoding="utf-8"))
    if not jwk.get("x5c"):
        private_value = int.from_bytes(base64.urlsafe_b64decode(jwk["d"] + "=="), "big")
        signing_key = ec.derive_private_key(private_value, ec.SECP256R1())
        ca = x509.load_pem_x509_certificate((root / "ca.crt").read_bytes())
        ca_key = serialization.load_pem_private_key((root / "ca.key").read_bytes(), password=None)
        now = datetime.now(timezone.utc)
        credential_certificate = (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "suite.test")]))
            .issuer_name(ca.subject).public_key(signing_key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=90))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("suite.test")]), False)
            .add_extension(x509.KeyUsage(True, False, False, False, False, False, False, False, False), True)
            .sign(ca_key, hashes.SHA256()))
        jwk["x5c"] = [base64.b64encode(c.public_bytes(serialization.Encoding.DER)).decode()
                      for c in (credential_certificate, ca)]
        text(jwk_path, json.dumps(jwk, indent=2) + "\n")


def main():
    if not Path(".env").exists():
        shutil.copyfile(".env.example", ".env")
    read_env()
    try:
        certificates()
        init = source("inji-certify", CERTIFY_ROOT + "certify_init.sql")
        # The tagged init is destructive by design. Apply it only on a NEW empty
        # volume via Postgres entrypoint; this script never resets an existing DB.
        init = init.replace("/home/mosip/config/", "/home/inji/config/")
        # Register an actual SD-JWT credential rather than running an SD-JWT plan
        # against the upstream SQL's LDP-only FarmerCredential sample.
        # Fields/template shape: alpha api-test/Sd_Jwt/AddCredentialConfigSd_Jwt.
        template = {"issuer": "${_issuer}", "validFrom": "${validFrom}", "validUntil": "${validUntil}",
                    "credentialSubject": {"id": "${_holderId}", "fullName": "${fullName}"}}
        encoded = base64.b64encode(json.dumps(template).encode()).decode()
        init += """\nINSERT INTO certify.credential_config (
credential_config_key_id, config_id, status, vc_template, sd_jwt_vct,
credential_format, did_url, key_manager_app_id, key_manager_ref_id, signature_algo,
sd_claim, display, display_order, scope, cryptographic_binding_methods_supported,
credential_signing_alg_values_supported, proof_types_supported, sd_jwt_claims,
plugin_configurations, cr_dtimes)
VALUES ('HarnessSdJwtCredential',gen_random_uuid()::text,'active','""" + encoded + """',
'urn:eudi:pid:1','dc+sd-jwt','did:web:certify.test%3A8446:v1:certify',
'CERTIFY_VC_SIGN_EC_R1','EC_SECP256R1_SIGN','ES256','fullName',
'[{"name":"Harness Test Credential","locale":"en","logo":{"uri":"https://certify.test:8446/assets/test.svg","alt_text":"Synthetic test issuer"},"background_color":"#ffffff","text_color":"#000000","background_image":{"uri":"https://certify.test:8446/assets/test.svg"}}]'::jsonb, ARRAY['fullName'],
'harness-test',ARRAY['did:jwk'],ARRAY['ES256'],
'{"jwt":{"proof_signing_alg_values_supported":["ES256"]}}'::jsonb,
'{"fullName":{"display":[{"name":"Test name","locale":"en"}]}}'::jsonb,
'[]'::jsonb,now());\n"""
        text("local/db-init/10-certify.sql", init)
        text("local/db-init/20-verify.sql", "\\connect inji_verify\nCREATE SCHEMA IF NOT EXISTS verify;\n")
        base = source("inji-certify", CERTIFY_ROOT + "config/certify-default.properties")
        # The tagged wildcard allowlist returned an HTTP-200 auth error for health
        # in the real image. Explicit health-only matches below fix that defect.
        overrides = '''
# Harness single-instance development overrides; original property names from the alpha.
mosip.certify.security.ignore-auth-urls=/actuator/health,/v1/certify/actuator/health,**/error,**/swagger-ui/**,**/v3/api-docs/**,**/issuance/**,**/rendering-template/**,**/system-info/**,**/credential-configurations/**,**/.well-known/**,**/ledger-search/**,**/credentials/**,**/oauth/**,**/pre-authorized-data/**,**/credential-offer-data/**,**/nonce
spring.cloud.config.enabled=false
mosip.certify.domain.url=https://certify.test:8446
mosip.certify.identifier=https://certify.test:8446
mosip.certify.database.hostname=postgres
spring.datasource.username=postgres
spring.datasource.password=${POSTGRES_PASSWORD}
spring.cache.type=simple
management.health.redis.enabled=false
management.endpoint.env.show-values=NEVER
management.endpoints.web.exposure.include=health,info
mosip.kernel.keymanager.hsm.config-path=/home/inji/CERTIFY_PKCS12/local.p12
mosip.kernel.keymanager.hsm.keystore-pass=${CERTIFY_KEYSTORE_PASSWORD}
mosip.certify.authorization.url=${mosip.certify.domain.url}
mosip.certify.authn.issuer-uri=${mosip.certify.authorization.url}
mosip.certify.authn.jwk-set-uri=${mosip.certify.authorization.url}${server.servlet.path}/.well-known/jwks.json
mosip.certify.authn.allowed-audiences={ '${mosip.certify.authorization.url}${server.servlet.path}/issuance/credential' }
'''
        # Preserve all alpha nonce/pre-auth cache definitions from the tagged base.
        text("local/certify-config/certify-default.properties", base + overrides)
        plugin = source("inji-certify", CERTIFY_ROOT + "config/certify-csvdp-farmer.properties")
        plugin = plugin.replace("/home/mosip/", "/home/inji/")
        plugin += "\nmosip.certify.data-provider-plugin.did-url=did:web:certify.test%3A8446:v1:certify\n"
        text("local/certify-config/certify-csvdp-farmer.properties", plugin)
        text("local/certify-config/farmer_identity_data.csv", "id,fullName,mobileNumber,dateOfBirth,gender,state,district,villageOrTown,postalCode,landArea,landOwnershipType,primaryCropType,secondaryCropType,face,farmerID\nTEST001,Test Farmer,0000000000,2000-01-01,Other,Test,Test,Test,000000,1,Test,Test,Test,,TEST001\n")
        text("local/verify-config/verify.properties", """# Alpha entities create their schema on a fresh dev database; no stale PEX DDL.
spring.jpa.hibernate.ddl-auto=update
inji.keystore.file.path=file:/tls/verify-keystore.p12
""")
        text("local/public/test.svg", '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="60"><rect width="160" height="60" fill="#fff"/><text x="12" y="38" font-size="24">TEST ISSUER</text></svg>\n')
        text("local/verify-request.json", json.dumps({"responseCodeValidationRequired": False, "dcqlQuery": {
            "credentials": [{"id": "pid", "format": "dc+sd-jwt", "meta": {"vct_values": ["urn:eudi:pid:1"]},
                             "require_cryptographic_holder_binding": True}]}}, indent=2) + "\n")
        text("local/claims.json", json.dumps({"fullName": "Test Farmer"}) + "\n")
        print("Prepared release-matched development SQL/properties, synthetic inputs and local CA under local/.")
        print("Existing .env/keys were retained. No containers or databases were changed.")
        return 0
    except Exception as error:
        print("Local preparation failed: " + type(error).__name__ + "; check dependencies, keytool and release-source access", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
