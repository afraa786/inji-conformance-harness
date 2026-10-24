# TLS validation and scope

Python requests to the suite and Inji APIs validate the generated development CA
and hostname. Inji JVMs and the suite JVM load the certificate-only JKS. TLS
terminates at the gateway; internal upstream HTTP is confined to the Docker network.
The test credential signing JWK/x5c and Verify PKCS12 are application keys, not
TLS server keys. Their successful use does not prove TLS validation.

Important qualification: the inspected suite's `condition/AbstractCondition.java`
builds a permissive X509TrustManager and NoopHostnameVerifier. The actual running
JAR's AbstractCondition bytecode also contains the latter. That upstream protocol
client bypass is not an env flag in this harness and is not corrected by mounting
our JKS. Do not claim suite protocol success proves CA/hostname verification.
The harness has not added any insecure flag or modified upstream protocol code.

The normal JDK client probe checks the network from the same suite container:

```bash
docker compose exec -T server jshell --execution local - < tools/probe-container-tls.jsh
```

Observed: HTTP 200 from suite, issuer discovery and Verify health; certificate
expiry 2027-01-21 14:18:37 UTC; wrong IP hostname and untrusted CA both rejected.
The output is saved locally in `results/tls-container-probe.txt`. This validates
the deployed TLS topology independently of the suite's permissive client.
CI runs the same probe after the wrapper, including when conformance is red.

Preparation preserves existing keys. The leaf is issued for 90 days, CA for 365;
SANs cover localhost, suite.test, certify.test, verify.test, httpd and 127.0.0.1.
No private CA key is mounted in containers. Clock skew or an expired certificate
must fail validation; do not bypass it. Review expiry before longer-lived reuse.

For renewal, issue a new leaf using the retained development CA and matching SANs,
replace `local/tls/server.crt` and restart the gateway. If rotating the CA, also
replace the JKS's harness-ca entry, refresh application signing certificate chains
where applicable and restart all Java services. Preserve/archive private material
securely; preparation does not silently rotate it or migrate persisted issuer keys.
Rerun both the container probe and the Python/Java loopback test after renewal.
Trust only this isolated development CA, never an unrelated downloaded certificate.
