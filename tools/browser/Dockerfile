# Published Selenium standalone-chromium 155.0, looked up in Docker Hub metadata.
FROM selenium/standalone-chromium@sha256:c7c17cd79c62819a8329df00e610dbc4073c279da034a6f37135d454eb0d8870
USER root
COPY ca.crt /usr/local/share/ca-certificates/harness-dev.crt
RUN update-ca-certificates && \
    if ! command -v certutil; then apt-get update && apt-get install -y --no-install-recommends libnss3-tools; fi && \
    mkdir -p /home/seluser/.pki/nssdb && \
    certutil -N -d sql:/home/seluser/.pki/nssdb --empty-password && \
    certutil -A -d sql:/home/seluser/.pki/nssdb -n harness-development-ca -t 'C,,' -i /usr/local/share/ca-certificates/harness-dev.crt && \
    chown -R seluser:seluser /home/seluser/.pki
USER seluser
