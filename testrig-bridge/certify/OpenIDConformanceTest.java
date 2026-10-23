package io.inji.testrig.apirig.injicertify.testscripts;

import com.github.openjson.JSONArray;
import com.github.openjson.JSONObject;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.TimeUnit;
import org.testng.Assert;
import org.testng.Reporter;
import org.testng.SkipException;
import org.testng.annotations.DataProvider;
import org.testng.annotations.Test;

/** Java 21 api-testrig adapter; the Python subprocess remains the REST driver. */
public class OpenIDConformanceTest {
    private static final String COMPONENT = "certify";

    private static String setting(String property, String environment, String fallback) {
        String value = System.getProperty(property);
        if (value == null || value.isBlank()) value = System.getenv(environment);
        return value == null || value.isBlank() ? fallback : value;
    }

    private static String endpoint() {
        String endpoint = System.getProperty("env.endpoint");
        if (endpoint == null || endpoint.isBlank()) {
            try {
                // The real api-testrigs inherit ConfigManager.getproperty(). Reflection
                // lets this adapter also compile in the standalone Maven project.
                Class<?> manager = Class.forName("io.mosip.testrig.apirig.utils.ConfigManager");
                endpoint = (String) manager.getMethod("getproperty", String.class).invoke(null, "env.endpoint");
            } catch (ClassNotFoundException ignored) {
                // Standalone bridge: ENV_ENDPOINT is the explicit fallback.
            } catch (ReflectiveOperationException e) {
                throw new IllegalStateException("Could not read testrig env.endpoint", e);
            }
        }
        if (endpoint == null || endpoint.isBlank()) endpoint = System.getenv("ENV_ENDPOINT");
        Assert.assertTrue(endpoint != null && !endpoint.isBlank(), "Target endpoint is not configured");
        return setting("conformance.target", "CONFORMANCE_TARGET", endpoint);
    }

    @DataProvider(name = "conformanceResults")
    public Object[][] conformanceResults() throws IOException, InterruptedException {
        Path root = Path.of(setting("conformance.root", "CONFORMANCE_ROOT", ".")).toAbsolutePath();
        Path output = Path.of(setting("conformance.results", "CONFORMANCE_RESULTS", "results/results-" + COMPONENT + ".json"));
        if (!output.isAbsolute()) output = root.resolve(output);
        Files.createDirectories(output.getParent());
        Files.deleteIfExists(output); // Old output cannot turn a failed subprocess into a pass.
        List<String> command = new ArrayList<>(List.of(
            setting("conformance.python", "PYTHON", "python"),
            setting("conformance.runner", "CONFORMANCE_RUNNER", "runner/conformance_runner.py"),
            "--component", COMPONENT, "--target", endpoint(), "--out", output.toString(),
            "--suite-url", setting("conformance.suiteUrl", "SUITE_URL", "https://localhost:8443"),
            "--expected-failures", setting("conformance.expectedFailures", "CONFORMANCE_EXPECTED_FAILURES",
                "runner/expected-failures-" + COMPONENT + ".json")));
        String plan = setting("conformance.plan", "CONFORMANCE_PLAN", "");
        if (!plan.isBlank()) command.addAll(List.of("--plan", plan));
        Process process = new ProcessBuilder(command).directory(root.toFile()).inheritIO().start();
        try {
            if (!process.waitFor(65, TimeUnit.MINUTES)) {
                process.destroyForcibly();
                Assert.fail("Conformance runner timed out");
            }
        } catch (InterruptedException e) {
            process.destroyForcibly();
            Thread.currentThread().interrupt();
            throw e;
        }
        Assert.assertTrue(process.exitValue() == 0 || process.exitValue() == 1,
            "Conformance runner configuration/infrastructure failure (exit " + process.exitValue() + ")");
        Assert.assertTrue(Files.isRegularFile(output), "Conformance results file does not exist");
        JSONObject results = new JSONObject(Files.readString(output));
        Assert.assertEquals(results.getString("component"), COMPONENT, "Wrong results component");
        Assert.assertEquals(results.getJSONArray("errors").length(), 0, "Runner reported infrastructure errors");
        JSONArray modules = results.getJSONArray("modules");
        Assert.assertTrue(modules.length() > 0, "No conformance modules ran");
        Object[][] data = new Object[modules.length()][2];
        boolean unexpectedFailure = false;
        for (int i = 0; i < modules.length(); i++) {
            JSONObject module = modules.getJSONObject(i);
            data[i][0] = module.getString("name") + " " + module.optJSONObject("variant");
            data[i][1] = module.getString("status");
            unexpectedFailure |= List.of("FAILED", "INTERRUPTED").contains(data[i][1]);
        }
        Assert.assertEquals(process.exitValue(), unexpectedFailure ? 1 : 0, "Runner exit/result mismatch");
        return data;
    }

    @Test(dataProvider = "conformanceResults")
    public void conformanceModule(String name, String status) {
        Reporter.log(name + " -> " + status, true); // Existing TestNG/report listener receives this.
        switch (status.toUpperCase(Locale.ROOT)) {
            case "PASSED":
            case "WARNING":
            case "EXPECTED_FAILURE":
                return;
            case "SKIPPED":
            case "REVIEW":
            case "EXPECTED_SKIP":
                throw new SkipException(name + " -> " + status);
            default:
                Assert.fail(name + " -> " + status);
        }
    }
}
