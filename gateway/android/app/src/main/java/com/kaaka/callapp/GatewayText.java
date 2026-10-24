package com.kaaka.callapp;

import java.security.SecureRandom;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Plain-Java helpers (no Android APIs) for location tokens and responder ACK messages. */
final class GatewayText {
    private static final String TOKEN_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    private static final SecureRandom RANDOM = new SecureRandom();
    /** "ACK", optionally followed by a phone number. Anything else after ACK is ignored. */
    private static final Pattern ACK = Pattern.compile("(?is)^\\s*ack\\b[\\s:,-]*(\\+?[0-9][0-9 ()-]{5,})?.*$");

    private GatewayText() {}

    /** Random URL-safe token for a location link; matches the server's ^[A-Za-z0-9_-]{6,32}$. */
    static String newToken() {
        StringBuilder token = new StringBuilder(12);
        for (int i = 0; i < 12; i++) token.append(TOKEN_CHARS.charAt(RANDOM.nextInt(TOKEN_CHARS.length())));
        return token.toString();
    }

    /**
     * If the SMS body is a responder acknowledgement, returns the caller number written after ACK
     * (digits and a leading +, "" when none was given). Returns null when the body is not an ACK.
     */
    static String parseAck(String body) {
        if (body == null) return null;
        Matcher m = ACK.matcher(body);
        if (!m.matches()) return null;
        String number = m.group(1);
        return number == null ? "" : number.replaceAll("[^0-9+]", "");
    }

    /** Location link appended to the caller's reply, or "" when no public URL is set. */
    static String locationLine(String publicUrl, String token) {
        if (publicUrl == null || publicUrl.trim().isEmpty() || token == null || token.isEmpty()) return "";
        return "\nShare your location: " + publicUrl.trim().replaceAll("/+$", "") + "/l/" + token;
    }
}
