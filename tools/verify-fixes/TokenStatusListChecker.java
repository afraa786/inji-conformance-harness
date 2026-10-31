package io.inji.verify.services.impl;

import com.nimbusds.jose.crypto.factories.DefaultJWSVerifierFactory;
import com.nimbusds.jose.jwk.JWK;
import com.nimbusds.jwt.SignedJWT;
import io.inji.verify.dto.core.ErrorDto;
import io.inji.verify.dto.verification.StatusCheckDto;
import java.io.ByteArrayInputStream;
import java.math.BigDecimal;
import java.net.URI;
import java.net.HttpURLConnection;
import java.nio.charset.StandardCharsets;
import java.security.Key;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.time.Instant;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.zip.InflaterInputStream;

/** Native SD-JWT Token Status List support for the reviewed same-issuer-key profile.
 * Called only after the existing credential signature/schema validation succeeds.
 * No cache; HTTPS uses the normal JVM trust/hostname policy. Failures fail closed.
 */
public final class TokenStatusListChecker {
    private TokenStatusListChecker() {}

    private static StatusCheckDto failure(String code) {
        return new StatusCheckDto("revocation", false, new ErrorDto(code, code));
    }

    private static Map<?, ?> object(Object value) {
        if (!(value instanceof Map<?, ?> map)) throw new IllegalArgumentException("STATUS_REFERENCE_INVALID");
        return map;
    }

    private static long integer(Object value) {
        if (!(value instanceof Number)) throw new IllegalArgumentException("STATUS_REFERENCE_INVALID");
        return new BigDecimal(value.toString()).longValueExact();
    }

    public static List<StatusCheckDto> check(String credential) {
        HttpURLConnection connection = null;
        try {
            SignedJWT issuerJwt = SignedJWT.parse(credential.split("~", -1)[0]);
            Object status = issuerJwt.getJWTClaimsSet().getClaim("status");
            if (status == null) return List.of(); // Status is optional; do not reject its absence.
            Map<?, ?> reference = object(object(status).get("status_list"));
            Object rawUri = reference.get("uri");
            if (!(rawUri instanceof String)) return List.of(failure("STATUS_REFERENCE_INVALID"));
            URI uri = URI.create((String)rawUri);
            if (!"https".equalsIgnoreCase(uri.getScheme()) || uri.getHost() == null || uri.getUserInfo() != null || uri.getFragment() != null)
                return List.of(failure("STATUS_REFERENCE_INVALID"));
            connection = (HttpURLConnection)uri.toURL().openConnection();
            connection.setConnectTimeout(10000);
            connection.setReadTimeout(10000);
            connection.setInstanceFollowRedirects(false); // Deliberately narrower same-endpoint trust policy.
            connection.setUseCaches(false);
            connection.setRequestProperty("Accept", "application/statuslist+jwt");
            connection.setRequestProperty("Cache-Control", "no-cache");
            if (connection.getResponseCode() != 200) return List.of(failure("STATUS_UNAVAILABLE"));
            String mime = connection.getContentType();
            if (mime == null || !mime.split(";", 2)[0].equalsIgnoreCase("application/statuslist+jwt"))
                return List.of(failure("STATUS_CONTENT_TYPE_INVALID"));
            byte[] bytes;
            try (var stream = connection.getInputStream()) { bytes = stream.readNBytes(1048577); }
            if (bytes.length > 1048576) return List.of(failure("STATUS_TOO_LARGE"));
            return List.of(validateToken(issuerJwt, reference, new String(bytes, StandardCharsets.US_ASCII)));
        } catch (IllegalArgumentException error) {
            return List.of(failure("STATUS_REFERENCE_INVALID"));
        } catch (Exception error) {
            return List.of(failure("STATUS_UNAVAILABLE"));
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    static StatusCheckDto validateToken(SignedJWT issuer, Map<?, ?> reference, String serialized) {
        try {
            var token = SignedJWT.parse(serialized);
            if (token.getHeader().getType() == null || !"statuslist+jwt".equals(token.getHeader().getType().toString()))
                return failure("STATUS_TOKEN_TYPE_INVALID");
            // The original verifier already authenticated this credential's issuer key.
            // Do not trust keys supplied by the fetched status token or remote jku/x5u.
            Key key;
            var chain = issuer.getHeader().getX509CertChain();
            if (chain != null && !chain.isEmpty()) {
                var certificate = (X509Certificate)CertificateFactory.getInstance("X.509")
                    .generateCertificate(new ByteArrayInputStream(chain.get(0).decode()));
                key = certificate.getPublicKey();
            } else {
                JWK jwk = issuer.getHeader().getJWK();
                if (jwk == null) return failure("STATUS_SIGNER_UNSUPPORTED");
                key = jwk instanceof com.nimbusds.jose.jwk.ECKey ec ? ec.toECPublicKey() : jwk.toRSAKey().toRSAPublicKey();
            }
            var factory = new DefaultJWSVerifierFactory();
            if (!issuer.verify(factory.createJWSVerifier(issuer.getHeader(), key)) ||
                !token.verify(factory.createJWSVerifier(token.getHeader(), key)))
                return failure("STATUS_SIGNATURE_INVALID");
            var claims = token.getJWTClaimsSet();
            long now = Instant.now().getEpochSecond();
            if (!reference.get("uri").equals(claims.getSubject())) return failure("STATUS_SUBJECT_INVALID");
            if (claims.getIssueTime() == null || claims.getIssueTime().toInstant().getEpochSecond() > now)
                return failure("STATUS_TIME_INVALID");
            if (claims.getExpirationTime() != null && claims.getExpirationTime().toInstant().getEpochSecond() <= now)
                return failure("STATUS_EXPIRED");
            if (claims.getNotBeforeTime() != null && claims.getNotBeforeTime().toInstant().getEpochSecond() > now)
                return failure("STATUS_TIME_INVALID");
            Object ttl = claims.getClaim("ttl");
            if (ttl != null && (integer(ttl) <= 0 || integer(ttl) <= now - claims.getIssueTime().toInstant().getEpochSecond()))
                return failure("STATUS_STALE");
            // Do not accept an unbounded freshness lifetime in this deployment profile.
            if (ttl == null && claims.getExpirationTime() == null) return failure("STATUS_FRESHNESS_UNBOUNDED");
            Map<?, ?> list = object(claims.getClaim("status_list"));
            long bits = integer(list.get("bits"));
            long index = integer(reference.get("idx"));
            if (!List.of(1L, 2L, 4L, 8L).contains(bits) || index < 0 || index > Integer.MAX_VALUE)
                return failure("STATUS_INDEX_INVALID");
            byte[] compressed = Base64.getUrlDecoder().decode((String)list.get("lst"));
            byte[] values;
            try (var stream = new InflaterInputStream(new ByteArrayInputStream(compressed))) {
                values = stream.readNBytes(16777217);
            }
            long bitIndex = Math.multiplyExact(index, bits);
            if (values.length > 16777216 || bitIndex / 8 >= values.length) return failure("STATUS_INDEX_INVALID");
            int value = ((values[(int)(bitIndex / 8)] & 255) >>> (int)(bitIndex % 8)) & ((1 << (int)bits) - 1);
            if (value == 0) return new StatusCheckDto("revocation", true, null);
            return failure(value == 1 ? "CREDENTIAL_REVOKED" : "CREDENTIAL_STATUS_NOT_VALID");
        } catch (Exception error) {
            return failure("STATUS_TOKEN_INVALID");
        }
    }
}
