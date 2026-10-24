# Troubleshooting

- **TLS / hostname:** run `python runner/prepare_local.py`, retain
  `REQUESTS_CA_BUNDLE=./local/tls/ca.crt`, and mount the generated Java truststore.
  Public Docker aliases must match certificate SANs and issuer metadata. Host
  Python uses localhost API URLs; browser access to aliases needs hosts entries
  and explicit trust of the development CA. Do not disable TLS globally.
- **Unhealthy service:** use `docker compose ps` and
  `python runner/capture_diagnostics.py troubleshooting`. Inspect redacted
  diagnostics privately. Health must contain JSON status UP; HTTP 200 alone can
  be an authentication error. Generated SQL initializes empty volumes only;
  apply reviewed migrations to existing data rather than deleting volumes.
- **WAITING timeout:** inspect the module log and saved actual Verify result.
  Screenshot review remains a real requirement even after successful backend
  verification. Increasing WAITING_TIMEOUT_SECONDS only provides more time; it
  does not automate evidence review.
- **Issuer interrupted:** inspect AS metadata. The native IAR contract is not
  interchangeable with authorization_endpoint; do not add a fictitious endpoint
  or unsupported client-authentication capability to make a plan start.
- **Image pull / startup:** defaults are documented alpha tags, with suite
  digests pinned to tested content. Run `docker compose pull`, then retry startup.
  STACK_START_TIMEOUT_SECONDS includes pulls; HEALTH_TIMEOUT_SECONDS bounds
  health waiting. Never substitute an unverified release tag.
- **Git Bash:** keep scripts LF using `.gitattributes`; run `bash -n
  run-full-stack-conformance.sh`. Execute from the repository root. Do not edit
  a shell script while that same script is running.
- **Python dependencies:** prefer Python 3.10+ and install requirements.txt.
  If using retained `.local-deps`, export PYTHONPATH to its absolute path.
  `git ls-files .local-deps` should print nothing; ignored files remain on disk.
- **Java reports:** the standalone POM emits TestNG reports. Extent requires
  the real MOSIP testrig bootstrap and listener; standalone results cannot
  demonstrate that integration.
