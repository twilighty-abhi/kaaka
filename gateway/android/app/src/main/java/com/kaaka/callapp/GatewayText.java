package com.kaaka.callapp;

import java.security.SecureRandom;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Plain-Java helpers (no Android APIs, so they can be unit-tested): location tokens, responder commands,
 * help-SMS keywords, reply texts, rate limiting and open-incident summaries.
 */
final class GatewayText {
    private static final String TOKEN_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
    private static final SecureRandom RANDOM = new SecureRandom();
    /** "ACK", optionally followed by a phone number. Anything else after ACK is ignored. */
    private static final Pattern ACK = Pattern.compile("(?is)^\\s*ack\\b[\\s:,-]*(\\+?[0-9][0-9 ()-]{5,})?.*$");
    /** "RESOLVE", optionally followed by a phone number and a free-text note. */
    private static final Pattern RESOLVE = Pattern.compile("(?is)^\\s*resolve\\b[\\s:,-]*(\\+?[0-9][0-9 ()-]{5,})?\\s*(.*)$");
    private static final Pattern STATUS = Pattern.compile("(?is)^\\s*status\\s*$");
    /** Latin help keywords as whole words ("helpful" or "kaakaa" do not match). */
    private static final Pattern HELP_WORDS = Pattern.compile("(?i)(?<![\\p{L}\\p{N}])(help|sos|kaaka)(?![\\p{L}\\p{N}])");
    private static final String HELP_MALAYALAM = "സഹായം";

    static final String REPLY_EN = "Kaaka received your call. Help is being arranged. If in immediate danger, call 112.";
    /** Malayalam reply; should be checked by a native speaker. */
    static final String REPLY_ML = "കാക്ക നിങ്ങളുടെ സന്ദേശം സ്വീകരിച്ചു. സഹായം ഏർപ്പാടാക്കുന്നു. അടിയന്തര അപകടത്തിലാണെങ്കിൽ 112-ൽ വിളിക്കുക.";

    static final long HOUR_MS = 60L * 60 * 1000;
    static final long DAY_MS = 24 * HOUR_MS;

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
        return cleanNumber(m.group(1));
    }

    /** True if the body is the responder command STATUS. */
    static boolean isStatus(String body) {
        return body != null && STATUS.matcher(body).matches();
    }

    /**
     * If the body is "RESOLVE [number] [note]", returns {number ("" = latest incident), note}; otherwise null.
     */
    static String[] parseResolve(String body) {
        if (body == null) return null;
        Matcher m = RESOLVE.matcher(body);
        if (!m.matches()) return null;
        String note = m.group(2) == null ? "" : m.group(2).trim();
        if (note.length() > 500) note = note.substring(0, 500);
        return new String[] { cleanNumber(m.group(1)), note };
    }

    private static String cleanNumber(String raw) {
        return raw == null ? "" : raw.replaceAll("[^0-9+]", "");
    }

    /**
     * True if an SMS asks for help: HELP, SOS or KAAKA as a word (any case), or the Malayalam word for help.
     * Texts that Kaaka gateways send themselves are excluded so two gateways can never answer each other.
     */
    static boolean isHelpRequest(String body) {
        if (body == null) return false;
        String text = body.trim();
        if (isOwnMessage(text)) return false;
        return text.contains(HELP_MALAYALAM) || HELP_WORDS.matcher(text).find();
    }

    /** Exact starts of the texts this app sends (replies, responder notifications, command answers). */
    private static final Pattern OWN_MESSAGE = Pattern.compile(
        "^(Kaaka received|Kaaka UNACKNOWLEDGED|A Kaaka responder|Kaaka alert from|കാക്ക നിങ്ങളുടെ"
            + "|Kaaka: (call from|help SMS from|ACK recorded|resolved|no recent incident|no open incidents|\\d+ open))");

    private static boolean isOwnMessage(String text) {
        return OWN_MESSAGE.matcher(text).find();
    }

    /** Default reply for a language setting: "en" (default), "ml" or "both". */
    static String defaultReply(String language) {
        if ("ml".equals(language)) return REPLY_ML;
        if ("both".equals(language)) return REPLY_EN + "\n" + REPLY_ML;
        return REPLY_EN;
    }

    /**
     * URL used for location links: the manually configured one wins; otherwise the URL the dashboard
     * reported in its heartbeat reply; "" when neither is set. Trailing slashes are dropped.
     */
    static String effectivePublicUrl(String manual, String auto) {
        String m = manual == null ? "" : manual.trim().replaceAll("/+$", "");
        if (!m.isEmpty()) return m;
        return auto == null ? "" : auto.trim().replaceAll("/+$", "");
    }

    /** True when a URL is set but not https: callers' browsers will refuse to share location on it. */
    static boolean isInsecurePublicUrl(String url) {
        String u = url == null ? "" : url.trim();
        return !u.isEmpty() && !u.toLowerCase().startsWith("https://");
    }

    /** Location link appended to the caller's reply, or "" when no public URL is set. */
    static String locationLine(String publicUrl, String token) {
        if (publicUrl == null || publicUrl.trim().isEmpty() || token == null || token.isEmpty()) return "";
        return "\nShare your location: " + publicUrl.trim().replaceAll("/+$", "") + "/l/" + token;
    }

    /** True if both numbers end with the same last 10 digits (ignores +91 / 0 prefixes). */
    static boolean sameNumber(String a, String b) {
        String da = a == null ? "" : a.replaceAll("\\D", "");
        String db = b == null ? "" : b.replaceAll("\\D", "");
        if (da.isEmpty() || db.isEmpty()) return false;
        String ta = da.length() > 10 ? da.substring(da.length() - 10) : da;
        String tb = db.length() > 10 ? db.substring(db.length() - 10) : db;
        return ta.equals(tb);
    }

    static String timeOfDay(long millis) {
        return new SimpleDateFormat("HH:mm", Locale.US).format(new Date(millis));
    }

    /** One logged event, reduced to what the rules below need. */
    static final class Ev {
        final String type;    // "call", "ack", "resolve", ...
        final String number;  // caller / acknowledged number
        final String state;   // for calls: "rejected", "allowed", "sms"
        final long at;        // epoch millis
        final boolean rateLimited;

        Ev(String type, String number, String state, long at, boolean rateLimited) {
            this.type = type;
            this.number = number == null ? "" : number;
            this.state = state == null ? "" : state;
            this.at = at;
            this.rateLimited = rateLimited;
        }

        String kind() {
            return "sms".equals(state) ? "help SMS" : "call";
        }
    }

    /**
     * True if this number already got {@code maxPerHour} replies in the last hour (rate-limited contacts
     * do not count). {@code maxPerHour} 0 means no limit.
     */
    static boolean isRateLimited(List<Ev> events, String number, long now, int maxPerHour) {
        if (maxPerHour <= 0 || number == null || number.isEmpty()) return false;
        int replied = 0;
        for (Ev e : events) {
            if ("call".equals(e.type) && !e.rateLimited && now - e.at < HOUR_MS && sameNumber(e.number, number)) replied++;
        }
        return replied >= maxPerHour;
    }

    /** True if an "ack" or "resolve" for this number was logged after {@code since}. */
    static boolean handledSince(List<Ev> events, String number, long since) {
        for (Ev e : events) {
            if (("ack".equals(e.type) || "resolve".equals(e.type)) && e.at >= since && sameNumber(e.number, number)) return true;
        }
        return false;
    }

    /**
     * Incidents from the last 24 h whose latest call / help SMS has no later ack or resolve,
     * one per number (its latest contact), newest first. {@code events} may be in any order.
     */
    static List<Ev> openIncidents(List<Ev> events, long now) {
        List<Ev> latest = new ArrayList<>();
        for (Ev e : events) {
            if (!"call".equals(e.type) || e.number.isEmpty() || now - e.at > DAY_MS) continue;
            Ev existing = null;
            for (Ev l : latest) {
                if (sameNumber(l.number, e.number)) existing = l;
            }
            if (existing == null) {
                latest.add(e);
            } else if (e.at > existing.at) {
                latest.set(latest.indexOf(existing), e);
            }
        }
        List<Ev> open = new ArrayList<>();
        for (Ev l : latest) {
            if (!handledSince(events, l.number, l.at)) open.add(l);
        }
        open.sort((x, y) -> Long.compare(y.at, x.at));
        return open;
    }

    /** STATUS reply, kept within about two SMS parts. */
    static String statusMessage(List<Ev> open) {
        if (open.isEmpty()) return "Kaaka: no open incidents";
        StringBuilder msg = new StringBuilder("Kaaka: ").append(open.size()).append(" open — ");
        int shown = 0;
        for (Ev e : open) {
            String item = e.number + " (" + e.kind() + " " + timeOfDay(e.at) + ")";
            if (msg.length() + item.length() > 260) break;
            if (shown > 0) msg.append(", ");
            msg.append(item);
            shown++;
        }
        if (shown < open.size()) msg.append(", +").append(open.size() - shown).append(" more");
        return msg.toString();
    }
}
