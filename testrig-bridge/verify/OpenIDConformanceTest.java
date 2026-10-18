package io.inji.testrig.apirig.injiverify.testscripts;

import com.github.openjson.JSONArray;
import com.github.openjson.JSONObject;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Locale;
import java.util.concurrent.TimeUnit;
import org.testng.Assert;
import org.testng.SkipException;
import org.testng.annotations.DataProvider;
import org.testng.annotations.Test;

/** Runs OpenID conformance modules and reports each module as a TestNG result. */
public class OpenIDConformanceTest {
    private static final String COMPONENT = "verify";

    @DataProvider(name = "conformanceResults")
    public Object[][] conformanceResults() throws IOException, InterruptedException {
        String endpoint = System.getProperty("env.endpoint");
        if (endpoint == null || endpoint.isBlank()) {
            endpoint = System.getenv("ENV_ENDPOINT");
        }
        if (endpoint == null || endpoint.isBlank()) {
            Assert.fail("Target endpoint is not configured");
        }

        String runner = System.getProperty("conformance.runner", "runner/conformance_runner.py");
        String resultsFile = System.getProperty(
                "conformance.results", "results/results-" + COMPONENT + ".json");
        Process process = new ProcessBuilder(
                "python", runner, "--component", COMPONENT, "--target", endpoint,
                "--out", resultsFile)
                .inheritIO()
                .start();

        if (!process.waitFor(60, TimeUnit.MINUTES)) {
            process.destroyForcibly();
            Assert.fail("Conformance runner timed out");
        }

        Path resultsPath = Path.of(resultsFile);
        Assert.assertTrue(Files.exists(resultsPath), "Conformance results file does not exist");

        JSONObject results = new JSONObject(Files.readString(resultsPath));
        JSONArray modules = results.getJSONArray("modules");
        Object[][] data = new Object[modules.length()][2];
        for (int i = 0; i < modules.length(); i++) {
            JSONObject module = modules.getJSONObject(i);
            data[i][0] = module.getString("name");
            data[i][1] = module.getString("status");
        }
        return data;
    }

    @Test(dataProvider = "conformanceResults")
    public void conformanceModule(String name, String status) {
        switch (status.toUpperCase(Locale.ROOT)) {
            case "PASSED":
            case "WARNING":
            case "EXPECTED_FAILURE":
                return;
            case "SKIPPED":
            case "EXPECTED_SKIP":
                throw new SkipException(name + " skipped");
            default:
                Assert.fail(name + " -> " + status);
        }
    }
}
