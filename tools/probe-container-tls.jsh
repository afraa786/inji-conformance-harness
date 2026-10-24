// Run through stdin in the suite container; normal JDK HTTPS, not suite HTTP helpers.
import java.net.*;
import javax.net.ssl.*;
import java.security.*;
import java.security.cert.X509Certificate;
int failures = 0;
var mode = System.getenv().getOrDefault("PROBE_COMPONENT", "combined");
if (!java.util.List.of("certify", "verify", "combined").contains(mode)) System.exit(2);
var endpoints = new java.util.ArrayList<String>(); endpoints.add("https://suite.test:8443/");
if (!mode.equals("verify")) endpoints.add("https://certify.test:8446/.well-known/openid-credential-issuer");
if (!mode.equals("certify")) endpoints.add("https://verify.test:8447/v1/verify/actuator/health");
for (var endpoint : endpoints) {
    try {
        var connection = (HttpsURLConnection)new URL(endpoint).openConnection();
        connection.setConnectTimeout(10000); connection.setReadTimeout(10000);
        int status = connection.getResponseCode();
        var leaf = (X509Certificate)connection.getServerCertificates()[0];
        leaf.checkValidity();
        System.out.println("TRUSTED " + endpoint + " HTTP " + status + " expires=" + leaf.getNotAfter());
        if (status != 200) failures++;
        connection.disconnect();
    } catch (Exception e) { failures++; System.out.println("FAILED " + endpoint + " " + e.getClass().getSimpleName()); }
}
var ip = InetAddress.getByName("httpd").getHostAddress();
try {
    var connection = (HttpsURLConnection)new URL("https://" + ip + ":8443/").openConnection();
    connection.getResponseCode(); failures++; System.out.println("ERROR hostname accepted");
} catch (SSLHandshakeException expected) { System.out.println("EXPECTED hostname mismatch rejected"); }
var empty = KeyStore.getInstance("JKS"); empty.load(null, null);
var factory = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm()); factory.init(empty);
var context = SSLContext.getInstance("TLS"); context.init(null, factory.getTrustManagers(), null);
try {
    var connection = (HttpsURLConnection)new URL("https://suite.test:8443/").openConnection();
    connection.setSSLSocketFactory(context.getSocketFactory()); connection.getResponseCode();
    failures++; System.out.println("ERROR untrusted CA accepted");
} catch (SSLException expected) { System.out.println("EXPECTED untrusted CA rejected"); }
System.exit(failures == 0 ? 0 : 1);
