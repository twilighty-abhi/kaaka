package com.kaaka.callapp;

import android.content.Context;
import android.Manifest;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;
import android.telephony.SmsManager;
import android.util.Log;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/**
 * Settings and event log shared by the call screening service, the SMS receiver and the UI plugin.
 * Kept in SharedPreferences so the native parts work while the app is closed.
 */
public final class GatewayStore {
    private static final String TAG = "KaakaGateway";
    private static final String PREFS = "kaaka_gateway";
    private static final String KEY_REJECT = "reject_calls";
    private static final String KEY_REPLY = "reply_message";
    private static final String KEY_DASHBOARD = "dashboard_url";
    private static final String KEY_RESPONDERS = "responder_numbers";
    private static final String KEY_PUBLIC_URL = "public_url";
    private static final String KEY_AUTO_PUBLIC_URL = "auto_public_url"; // learned from the dashboard's heartbeat reply
    private static final String KEY_DASHBOARD_TOKEN = "dashboard_token";
    private static final String KEY_ESCALATE_MINUTES = "escalate_minutes";
    private static final String KEY_MAX_REPLIES = "max_replies_per_hour";
    private static final String KEY_REPLY_LANGUAGE = "reply_language";
    private static final String KEY_EVENTS = "events";
    private static final String KEY_LAST_CALL = "last_call_number";
    private static final String KEY_LAST_CALL_AT = "last_call_at";
    // Call screening and the phone-state receiver see the same call within about a second.
    // Keep this short: a real second call from the same number must not be swallowed.
    private static final long CALL_DEDUPE_MS = 10_000;
    // Enough history for the 24 h STATUS summary, rate limiting and escalation checks.
    private static final int MAX_EVENTS = 200;

    public static final String DEFAULT_REPLY = GatewayText.REPLY_EN;
    /** Earlier default; treated as unset so existing installs pick up the new default. */
    private static final String OLD_DEFAULT_REPLY = "received call. will get back to you shortly.";

    private GatewayStore() {}

    private static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public static boolean rejectCalls(Context context) {
        return prefs(context).getBoolean(KEY_REJECT, true);
    }

    /** Reply sent to callers: the custom text if one is set, otherwise the default for the reply language. */
    public static String replyMessage(Context context) {
        String custom = customReply(context);
        return custom.isEmpty() ? GatewayText.defaultReply(replyLanguage(context)) : custom;
    }

    /** The user's own reply text, or "" when the language default applies (built-in defaults count as unset). */
    public static String customReply(Context context) {
        String reply = prefs(context).getString(KEY_REPLY, "");
        String r = reply == null ? "" : reply.trim();
        if (r.equals(OLD_DEFAULT_REPLY) || r.equals(GatewayText.REPLY_EN) || r.equals(GatewayText.REPLY_ML)
            || r.equals(GatewayText.defaultReply("both"))) return "";
        return r;
    }

    /** "en" (default), "ml" or "both". */
    public static String replyLanguage(Context context) {
        String lang = prefs(context).getString(KEY_REPLY_LANGUAGE, "en");
        return "ml".equals(lang) || "both".equals(lang) ? lang : "en";
    }

    /** Minutes before unacknowledged incidents are re-sent to responders; 0 = off. */
    public static int escalateMinutes(Context context) {
        return Math.max(0, prefs(context).getInt(KEY_ESCALATE_MINUTES, 5));
    }

    /** Max replies (caller + responder texts) per number per hour; 0 = no limit. */
    public static int maxRepliesPerHour(Context context) {
        return Math.max(0, prefs(context).getInt(KEY_MAX_REPLIES, 3));
    }

    public static String dashboardUrl(Context context) {
        String url = prefs(context).getString(KEY_DASHBOARD, "");
        return url == null ? "" : url.trim().replaceAll("/+$", "");
    }

    /** Public https base URL for location links (e.g. a tunnel to the dashboard); "" when unset. */
    public static String publicUrl(Context context) {
        String url = prefs(context).getString(KEY_PUBLIC_URL, "");
        return url == null ? "" : url.trim().replaceAll("/+$", "");
    }

    /** Public URL reported by the dashboard server in its heartbeat reply; "" when it has none. */
    public static String autoPublicUrl(Context context) {
        String url = prefs(context).getString(KEY_AUTO_PUBLIC_URL, "");
        return url == null ? "" : url.trim().replaceAll("/+$", "");
    }

    public static void saveAutoPublicUrl(Context context, String url) {
        prefs(context).edit().putString(KEY_AUTO_PUBLIC_URL, url == null ? "" : url.trim()).apply();
    }

    /** The URL used for location links: the manual setting when set, else the one the dashboard reported. */
    public static String effectivePublicUrl(Context context) {
        return GatewayText.effectivePublicUrl(publicUrl(context), autoPublicUrl(context));
    }

    /** Sent as X-Kaaka-Token when the dashboard server requires KAAKA_ADMIN_TOKEN; "" when unset. */
    public static String dashboardToken(Context context) {
        String token = prefs(context).getString(KEY_DASHBOARD_TOKEN, "");
        return token == null ? "" : token.trim();
    }

    /** Responder numbers as entered (comma or new line separated). */
    public static String responderText(Context context) {
        String text = prefs(context).getString(KEY_RESPONDERS, "");
        return text == null ? "" : text;
    }

    /** Responder numbers, cleaned to digits and a leading +; empty entries dropped. */
    public static List<String> responderNumbers(Context context) {
        List<String> numbers = new ArrayList<>();
        for (String part : responderText(context).split("[,\\n]")) {
            String number = part.trim().replaceAll("[^0-9+]", "");
            if (!number.replace("+", "").isEmpty() && !numbers.contains(number)) numbers.add(number);
        }
        return numbers;
    }

    public static void saveSettings(Context context, boolean rejectCalls, String replyMessage, String dashboardUrl, String responders,
                                    String publicUrl, String dashboardToken, int escalateMinutes, int maxRepliesPerHour,
                                    String replyLanguage) {
        prefs(context).edit()
            .putInt(KEY_ESCALATE_MINUTES, Math.max(0, escalateMinutes))
            .putInt(KEY_MAX_REPLIES, Math.max(0, maxRepliesPerHour))
            .putString(KEY_REPLY_LANGUAGE, replyLanguage == null ? "en" : replyLanguage)
            .putBoolean(KEY_REJECT, rejectCalls)
            .putString(KEY_REPLY, replyMessage == null ? "" : replyMessage)
            .putString(KEY_DASHBOARD, dashboardUrl == null ? "" : dashboardUrl.trim())
            .putString(KEY_RESPONDERS, responders == null ? "" : responders.trim())
            .putString(KEY_PUBLIC_URL, publicUrl == null ? "" : publicUrl.trim())
            .putString(KEY_DASHBOARD_TOKEN, dashboardToken == null ? "" : dashboardToken.trim())
            .apply();
    }

    /** True if both numbers end with the same last 10 digits (ignores +91 / 0 prefixes). */
    public static boolean sameNumber(String a, String b) {
        return GatewayText.sameNumber(a, b);
    }

    /** True if the number is one of the configured responders. */
    public static boolean isResponder(Context context, String number) {
        for (String responder : responderNumbers(context)) {
            if (sameNumber(responder, number)) return true;
        }
        return false;
    }

    /** Number of the most recent call or alert in the event log (what a bare "ACK" refers to); "" if none. */
    public static synchronized String lastIncidentNumber(Context context) {
        JSONArray events = getEvents(context);
        for (int i = 0; i < events.length(); i++) {
            JSONObject event = events.optJSONObject(i);
            if (event == null) continue;
            String type = event.optString("type");
            String number = "call".equals(type) ? event.optString("number") : "alert".equals(type) ? event.optString("sender") : "";
            if (!number.isEmpty()) return number;
        }
        return "";
    }

    /** Sends an SMS (multipart if long). Needs SEND_SMS. Returns false on any failure. */
    public static boolean sendSms(Context context, String number, String message) {
        if (context.checkSelfPermission(Manifest.permission.SEND_SMS) != PackageManager.PERMISSION_GRANTED) {
            Log.w(TAG, "SEND_SMS not granted; SMS to " + number + " not sent");
            return false;
        }
        try {
            SmsManager sms = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
                ? context.getSystemService(SmsManager.class)
                : SmsManager.getDefault();
            ArrayList<String> parts = sms.divideMessage(message);
            if (parts.size() > 1) {
                sms.sendMultipartTextMessage(number, null, parts, null, null);
            } else {
                sms.sendTextMessage(number, null, message, null, null);
            }
            return true;
        } catch (Exception e) {
            Log.w(TAG, "SMS to " + number + " failed: " + e.getMessage());
            return false;
        }
    }

    /**
     * Texts every responder number except {@code exclude} (the caller or alert sender).
     * Records "responders" / "respondersFailed" on the event when any responder is configured.
     */
    public static void notifyResponders(Context context, String message, String exclude, JSONObject event) {
        int sent = 0;
        int failed = 0;
        for (String number : responderNumbers(context)) {
            if (sameNumber(number, exclude)) continue;
            if (sendSms(context, number, message)) sent++; else failed++;
        }
        if (sent + failed == 0) return;
        try {
            event.put("responders", sent);
            event.put("respondersFailed", failed);
        } catch (JSONException ignored) {
        }
    }

    public static String timeOfDay() {
        return GatewayText.timeOfDay(System.currentTimeMillis());
    }

    /** Epoch millis of an event ("at", or parsed from the older ISO "timestamp"); 0 if unknown. */
    static long eventMillis(JSONObject event) {
        long at = event.optLong("at", 0);
        if (at > 0) return at;
        try {
            Date d = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX", Locale.US).parse(event.optString("timestamp"));
            return d == null ? 0 : d.getTime();
        } catch (Exception e) {
            return 0;
        }
    }

    /** The event log as plain records for the rules in {@link GatewayText}. */
    public static synchronized List<GatewayText.Ev> eventList(Context context) {
        JSONArray events = getEvents(context);
        List<GatewayText.Ev> list = new ArrayList<>();
        for (int i = 0; i < events.length(); i++) {
            JSONObject e = events.optJSONObject(i);
            if (e == null) continue;
            // Alert events store the caller under "sender"; everything else under "number".
            String number = e.has("number") ? e.optString("number") : e.optString("sender");
            list.add(new GatewayText.Ev(e.optString("type"), number, e.optString("state"),
                eventMillis(e), e.optBoolean("rateLimited", false)));
        }
        return list;
    }

    /** True if replies to this number are over the hourly limit. */
    public static boolean isRateLimited(Context context, String number) {
        return GatewayText.isRateLimited(eventList(context), number, System.currentTimeMillis(), maxRepliesPerHour(context));
    }

    public static String nowIso() {
        return new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX", Locale.US).format(new Date());
    }

    /**
     * Returns true the first time a call from this number is seen within CALL_DEDUPE_MS.
     * Call screening and the phone-state receiver can both see the same call; only one may handle it.
     */
    public static synchronized boolean claimCall(Context context, String number) {
        SharedPreferences p = prefs(context);
        long now = System.currentTimeMillis();
        if (number.equals(p.getString(KEY_LAST_CALL, null)) && now - p.getLong(KEY_LAST_CALL_AT, 0) < CALL_DEDUPE_MS) {
            return false;
        }
        p.edit().putString(KEY_LAST_CALL, number).putLong(KEY_LAST_CALL_AT, now).commit();
        return true;
    }

    /** Appends an event (newest first) and keeps at most MAX_EVENTS. */
    public static synchronized void appendEvent(Context context, JSONObject event) {
        if (!event.has("at")) {
            try {
                event.put("at", System.currentTimeMillis());
            } catch (JSONException ignored) {
            }
        }
        JSONArray current = getEvents(context);
        JSONArray updated = new JSONArray();
        updated.put(event);
        for (int i = 0; i < current.length() && updated.length() < MAX_EVENTS; i++) {
            updated.put(current.opt(i));
        }
        prefs(context).edit().putString(KEY_EVENTS, updated.toString()).apply();
    }

    public static synchronized JSONArray getEvents(Context context) {
        try {
            return new JSONArray(prefs(context).getString(KEY_EVENTS, "[]"));
        } catch (JSONException e) {
            return new JSONArray();
        }
    }

    public static synchronized void clearEvents(Context context) {
        prefs(context).edit().putString(KEY_EVENTS, "[]").apply();
    }

    /** POSTs JSON to the optional dashboard server. Call from a background thread; failures are only logged. */
    public static void postToDashboard(Context context, String path, JSONObject body) {
        postToDashboardForReply(context, path, body);
    }

    /** Same as postToDashboard but returns the JSON reply, or null when there was no 2xx reply. */
    public static JSONObject postToDashboardForReply(Context context, String path, JSONObject body) {
        String base = dashboardUrl(context);
        if (base.isEmpty()) return null;
        HttpURLConnection conn = null;
        try {
            conn = (HttpURLConnection) new URL(base + path).openConnection();
            conn.setConnectTimeout(3000);
            conn.setReadTimeout(3000);
            conn.setRequestMethod("POST");
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/json");
            String token = dashboardToken(context);
            if (!token.isEmpty()) conn.setRequestProperty("X-Kaaka-Token", token);
            try (OutputStream out = conn.getOutputStream()) {
                out.write(body.toString().getBytes(StandardCharsets.UTF_8));
            }
            int code = conn.getResponseCode();
            if (code >= 300) {
                Log.w(TAG, "Dashboard " + path + " returned HTTP " + code);
                return null;
            }
            try (InputStream in = conn.getInputStream()) {
                byte[] buf = new byte[4096];
                ByteArrayOutputStream out = new ByteArrayOutputStream();
                int n;
                while ((n = in.read(buf)) > 0 && out.size() < 64 * 1024) out.write(buf, 0, n);
                String text = out.toString("UTF-8").trim();
                return text.isEmpty() ? new JSONObject() : new JSONObject(text);
            }
        } catch (Exception e) {
            Log.w(TAG, "Dashboard " + path + " unreachable: " + e.getMessage());
            return null;
        } finally {
            if (conn != null) conn.disconnect();
        }
    }
}
