package com.kaaka.callapp;

import android.content.Context;
import android.Manifest;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;
import android.telephony.SmsManager;
import android.util.Log;
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
    private static final String KEY_EVENTS = "events";
    private static final String KEY_LAST_CALL = "last_call_number";
    private static final String KEY_LAST_CALL_AT = "last_call_at";
    private static final long CALL_DEDUPE_MS = 60_000;
    private static final int MAX_EVENTS = 50;

    public static final String DEFAULT_REPLY =
        "Kaaka received your call. Help is being arranged. If in immediate danger, call 112.";
    /** Earlier default; treated as unset so existing installs pick up the new default. */
    private static final String OLD_DEFAULT_REPLY = "received call. will get back to you shortly.";

    private GatewayStore() {}

    private static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public static boolean rejectCalls(Context context) {
        return prefs(context).getBoolean(KEY_REJECT, true);
    }

    public static String replyMessage(Context context) {
        String reply = prefs(context).getString(KEY_REPLY, DEFAULT_REPLY);
        if (reply == null || reply.trim().isEmpty() || reply.trim().equals(OLD_DEFAULT_REPLY)) return DEFAULT_REPLY;
        return reply;
    }

    public static String dashboardUrl(Context context) {
        String url = prefs(context).getString(KEY_DASHBOARD, "");
        return url == null ? "" : url.trim().replaceAll("/+$", "");
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

    public static void saveSettings(Context context, boolean rejectCalls, String replyMessage, String dashboardUrl, String responders) {
        prefs(context).edit()
            .putBoolean(KEY_REJECT, rejectCalls)
            .putString(KEY_REPLY, replyMessage == null ? "" : replyMessage)
            .putString(KEY_DASHBOARD, dashboardUrl == null ? "" : dashboardUrl.trim())
            .putString(KEY_RESPONDERS, responders == null ? "" : responders.trim())
            .apply();
    }

    /** True if both numbers end with the same last 10 digits (ignores +91 / 0 prefixes). */
    public static boolean sameNumber(String a, String b) {
        String da = a == null ? "" : a.replaceAll("\\D", "");
        String db = b == null ? "" : b.replaceAll("\\D", "");
        if (da.isEmpty() || db.isEmpty()) return false;
        String ta = da.length() > 10 ? da.substring(da.length() - 10) : da;
        String tb = db.length() > 10 ? db.substring(db.length() - 10) : db;
        return ta.equals(tb);
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
        return new SimpleDateFormat("HH:mm", Locale.US).format(new Date());
    }

    public static String nowIso() {
        return new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX", Locale.US).format(new Date());
    }

    /**
     * Returns true the first time a call from this number is seen within a minute.
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
        String base = dashboardUrl(context);
        if (base.isEmpty()) return;
        HttpURLConnection conn = null;
        try {
            conn = (HttpURLConnection) new URL(base + path).openConnection();
            conn.setConnectTimeout(3000);
            conn.setReadTimeout(3000);
            conn.setRequestMethod("POST");
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/json");
            try (OutputStream out = conn.getOutputStream()) {
                out.write(body.toString().getBytes(StandardCharsets.UTF_8));
            }
            int code = conn.getResponseCode();
            if (code >= 300) Log.w(TAG, "Dashboard " + path + " returned HTTP " + code);
        } catch (Exception e) {
            Log.w(TAG, "Dashboard " + path + " unreachable: " + e.getMessage());
        } finally {
            if (conn != null) conn.disconnect();
        }
    }
}
