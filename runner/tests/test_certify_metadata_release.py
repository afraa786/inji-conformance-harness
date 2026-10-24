"""Compile the actual alpha controller and exercise Spring MVC content negotiation.

Uses cached Maven jars only. SPI/DTO doubles isolate the controller from the
database and signing stack; this is not a full Certify/security-chain test.
"""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = "certify-service/src/main/java/io/mosip/certify/controller/WellKnownController.java"
SHA256 = "84a2cf4ff2a81e70a5158cc86c69ecee24a33d241e001b0e311e249d5324a0f4"


def cached_classpath():
    repositories = [ROOT / "local/m2", Path.home() / ".m2/repository"]
    if os.environ.get("CERTIFY_REGRESSION_M2"):
        repositories.insert(0, Path(os.environ["CERTIFY_REGRESSION_M2"]))
    coordinates = [("org/springframework", "spring-" + name, "6.1.4")
                   for name in ("webmvc", "web", "test", "core", "beans", "context", "expression", "jcl", "aop")]
    coordinates += [("io/micrometer", "micrometer-" + name, "1.12.3")
                    for name in ("observation", "commons")]
    coordinates += [("jakarta/servlet", "jakarta.servlet-api", "6.0.0")]
    coordinates += [("com/fasterxml/jackson/core", "jackson-" + name, "2.15.4")
                    for name in ("databind", "core", "annotations")]
    jars = []
    for group, artifact, version in coordinates:
        relative = Path(group) / artifact / version / (artifact + "-" + version + ".jar")
        jar = next((repo / relative for repo in repositories if (repo / relative).is_file()), None)
        if jar is None:
            pytest.skip("Offline MVC regression requires cached " + str(relative) +
                        "; set CERTIFY_REGRESSION_M2 to an existing Maven cache")
        jars.append(str(jar))
    return os.pathsep.join(jars)


@pytest.mark.parametrize("patched", [False, True], ids=["release-reproduces-406", "patch-returns-real-json"])
def test_release_metadata_negotiation(tmp_path, patched):
    for tool in ("git", "javac", "java"):
        if not shutil.which(tool):
            pytest.skip(tool + " is required for the offline MVC regression")
    classpath = cached_classpath()
    original = (ROOT / "runner/tests/fixtures/certify-alpha/WellKnownController.java").read_bytes()
    assert hashlib.sha256(original).hexdigest() == SHA256
    controller = tmp_path / CONTROLLER
    controller.parent.mkdir(parents=True)
    controller.write_bytes(original)
    if patched:
        subprocess.run(["git", "apply", str(ROOT / "patches/certify-alpha-unsigned-metadata.patch")],
                       cwd=tmp_path, check=True, capture_output=True, text=True)

    doubles = {
        "core/dto/CredentialIssuerMetadataDTO.java":
            "public class CredentialIssuerMetadataDTO extends java.util.LinkedHashMap<String,Object> {}",
        "core/spi/CredentialConfigurationService.java":
            "public interface CredentialConfigurationService { "
            "io.mosip.certify.core.dto.CredentialIssuerMetadataDTO fetchCredentialIssuerMetadata(); }",
        "core/spi/VCIssuanceService.java":
            "public interface VCIssuanceService { java.util.Map<String,Object> getDIDDocument(); }",
        "core/spi/JwksService.java":
            "public interface JwksService { java.util.Map<String,Object> getJwks(); }",
    }
    sources = [str(controller)]
    for name, body in doubles.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        package = "io.mosip.certify." + str(Path(name).parent).replace(os.sep, ".")
        path.write_text("package " + package + ";\n" + body, encoding="utf-8")
        sources.append(str(path))
    probe = tmp_path / "MetadataProbe.java"
    probe.write_text(PROBE, encoding="utf-8")
    classes = tmp_path / "classes"
    classes.mkdir()
    compiled = subprocess.run(["javac", "--release", "21", "-cp", classpath, "-d", str(classes)] +
                              sources + [str(probe)], capture_output=True, text=True, timeout=60)
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    result = subprocess.run(["java", "-cp", str(classes) + os.pathsep + classpath,
                             "MetadataProbe", str(patched).lower()],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "MVC metadata regression OK" in result.stdout


PROBE = r'''
import com.fasterxml.jackson.databind.ObjectMapper;
import io.mosip.certify.controller.WellKnownController;
import io.mosip.certify.core.dto.CredentialIssuerMetadataDTO;
import io.mosip.certify.core.spi.CredentialConfigurationService;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;

public class MetadataProbe {
    public static void main(String[] args) throws Exception {
        boolean patched = Boolean.parseBoolean(args[0]);
        var metadata = new CredentialIssuerMetadataDTO();
        // Synthetic service fixture, never exposed as live issuer metadata.
        metadata.put("credential_issuer", "https://issuer.example");
        metadata.put("credential_configurations_supported", java.util.Map.of("test", java.util.Map.of("format", "dc+sd-jwt")));
        int[] calls = {0};
        CredentialConfigurationService service = () -> { calls[0]++; return metadata; };
        var controller = new WellKnownController();
        var field = WellKnownController.class.getDeclaredField("credentialConfigurationService");
        field.setAccessible(true);
        field.set(controller, service);
        var mvc = MockMvcBuilders.standaloneSetup(controller).build();
        var mapper = new ObjectMapper();
        for (String accept : new String[]{"application/jwt", "application/json", "application/jwt, application/json", "*/*", ""}) {
            int before = calls[0];
            var request = get("/.well-known/openid-credential-issuer");
            if (!accept.isEmpty()) request.header("Accept", accept);
            var response = mvc.perform(request).andReturn().getResponse();
            if (!patched && accept.equals("application/jwt")) {
                if (response.getStatus() != 406 || calls[0] != before)
                    throw new AssertionError("Release must reject JWT before calling service");
                continue;
            }
            if (response.getStatus() != 200 || response.getContentType() == null ||
                !response.getContentType().startsWith("application/json") || calls[0] != before + 1)
                throw new AssertionError("Missing JSON response for Accept=" + accept);
            if (!mapper.readTree(response.getContentAsString()).equals(mapper.valueToTree(metadata)))
                throw new AssertionError("Controller changed metadata returned by service");
        }
        // No global negotiation change: an unrelated JSON-only endpoint still rejects JWT.
        if (mvc.perform(get("/.well-known/did.json").header("Accept", "application/jwt"))
                .andReturn().getResponse().getStatus() != 406)
            throw new AssertionError("Patch changed unrelated endpoint negotiation");
        System.out.println("MVC metadata regression OK");
    }
}
'''
