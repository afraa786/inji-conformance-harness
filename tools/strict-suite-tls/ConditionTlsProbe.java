package net.openid.conformance.condition;

import java.net.URI;
import java.security.KeyStore;
import java.nio.file.Files;
import java.nio.file.Path;
import net.openid.conformance.testmodule.Environment;
import org.apache.hc.client5.http.classic.methods.HttpGet;
import org.apache.hc.client5.http.impl.classic.CloseableHttpClient;

/** Exercise the suite's actual AbstractCondition client, not a parallel JDK client. */
public final class ConditionTlsProbe extends AbstractCondition {
    @Override public Environment evaluate(Environment environment) { return environment; }

    public static void main(String[] args) throws Exception {
        if (args.length == 1 && args[0].equals("--empty-store")) {
            KeyStore empty = KeyStore.getInstance("JKS");
            empty.load(null, null);
            try (var stream = Files.newOutputStream(Path.of("/opt/harness-tls/empty.jks"))) {
                empty.store(stream, "DEV_ONLY".toCharArray());
            }
            return;
        }
        boolean rejectionExpected = args.length > 1 && args[0].equals("--reject");
        String endpoint = args[args.length - 1];
        try (var client = (CloseableHttpClient)new ConditionTlsProbe().createHttpClient(new Environment(), true)) {
            int status = client.execute(new HttpGet(URI.create(endpoint)), response -> response.getCode());
            if (rejectionExpected || status != 200) throw new AssertionError("Unexpected TLS acceptance/status: " + status);
            System.out.println("SUITE CLIENT TRUSTED " + endpoint + " HTTP " + status);
        } catch (javax.net.ssl.SSLException error) {
            if (!rejectionExpected) throw error;
            System.out.println("SUITE CLIENT EXPECTED TLS REJECTION");
        }
    }
}
