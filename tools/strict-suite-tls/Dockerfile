ARG SUITE_BASE=registry.gitlab.com/openid/conformance-suite@sha256:899265eabbe900a3583b2d18cca09e077a147ab1cc74dd5382c664c8a7577373
FROM ${SUITE_BASE}
USER root
WORKDIR /opt/harness-tls
COPY AbstractCondition.java /opt/harness-tls/AbstractCondition.java
COPY ConditionTlsProbe.java /opt/harness-tls/ConditionTlsProbe.java
# Compile against the exact shipped suite classes/libraries, not guessed dependencies.
RUN mkdir -p original compiled/BOOT-INF/classes && cd original && jar xf /server/fapi-test-suite.jar && \
    javac --release 21 -cp 'BOOT-INF/classes:BOOT-INF/lib/*' -d ../compiled/BOOT-INF/classes ../AbstractCondition.java ../ConditionTlsProbe.java && \
    cd ../compiled && jar uf /server/fapi-test-suite.jar BOOT-INF/classes
WORKDIR /
