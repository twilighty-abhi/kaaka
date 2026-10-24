package com.kaaka.callapp;

import android.Manifest;
import android.content.Context;
import android.content.pm.PackageManager;
import android.os.Build;
import android.telephony.SmsManager;
import android.util.Log;
import java.util.ArrayList;
import org.json.JSONException;
import org.json.JSONObject;

/**
 * What happens after an incoming call is detected, whichever path saw it
 * (call screening for unknown numbers, phone-state broadcast for saved contacts):
 * text the caller the reply message, log the event and report it to the optional dashboard.
 * Run on a background thread.
 */
final class CallHandler {
    private static final String TAG = "KaakaGateway";

    private CallHandler() {}

    static void handleCall(Context context, String number, boolean rejected, String via) {
        String smsResult = sendReply(context, number);
        JSONObject event = new JSONObject();
        try {
            event.put("type", "call");
            event.put("number", number);
            event.put("state", rejected ? "rejected" : "allowed");
            event.put("sms", smsResult);
            event.put("via", via);
            event.put("timestamp", GatewayStore.nowIso());
        } catch (JSONException ignored) {
        }
        GatewayStore.appendEvent(context, event);

        JSONObject payload = new JSONObject();
        try {
            payload.put("number", number);
            payload.put("state", rejected ? "rejected" : "allowed");
            payload.put("sms", smsResult);
            payload.put("timestamp", event.optString("timestamp"));
        } catch (JSONException ignored) {
        }
        GatewayStore.postToDashboard(context, "/api/call-event", payload);
    }

    /** Returns "sent", "failed" or "skipped" (hidden/unknown number: never texts a fallback). */
    private static String sendReply(Context context, String number) {
        if (number.isEmpty()) return "skipped";
        if (context.checkSelfPermission(Manifest.permission.SEND_SMS) != PackageManager.PERMISSION_GRANTED) {
            Log.w(TAG, "SEND_SMS not granted; no auto-reply");
            return "failed";
        }
        try {
            SmsManager sms = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
                ? context.getSystemService(SmsManager.class)
                : SmsManager.getDefault();
            String message = GatewayStore.replyMessage(context);
            ArrayList<String> parts = sms.divideMessage(message);
            if (parts.size() > 1) {
                sms.sendMultipartTextMessage(number, null, parts, null, null);
            } else {
                sms.sendTextMessage(number, null, message, null, null);
            }
            return "sent";
        } catch (Exception e) {
            Log.w(TAG, "Auto-reply SMS failed: " + e.getMessage());
            return "failed";
        }
    }
}
