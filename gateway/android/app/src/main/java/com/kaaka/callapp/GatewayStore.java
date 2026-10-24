package com.kaaka.callapp;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Log;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
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
    private static final String KEY_EVENTS = "events";
    private static final int MAX_EVENTS = 50;

    public static final String DEFAULT_REPLY = "received call. will get back to you shortly.";

    private GatewayStore() {}

    private static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    public static boolean rejectCalls(Context context) {
        return prefs(context).getBoolean(KEY_REJECT, true);
    }

    public static String replyMessage(Context context) {
        String reply = prefs(context).getString(KEY_REPLY, DEFAULT_REPLY);
        return reply == null || reply.trim().isEmpty() ? DEFAULT_REPLY : reply;
    }

    public static String dashboardUrl(Context context) {
        String url = prefs(context).getString(KEY_DASHBOARD, "");
        return url == null ? "" : url.trim().replaceAll("/+$", "");
    }

    public static void saveSettings(Context context, boolean rejectCalls, String replyMessage, String dashboardUrl) {
        prefs(context).edit()
            .putBoolean(KEY_REJECT, rejectCalls)
            .putString(KEY_REPLY, replyMessage == null ? "" : replyMessage)
            .putString(KEY_DASHBOARD, dashboardUrl == null ? "" : dashboardUrl.trim())
            .apply();
    }

    public static String nowIso() {
        return new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ssXXX", Locale.US).format(new Date());
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
