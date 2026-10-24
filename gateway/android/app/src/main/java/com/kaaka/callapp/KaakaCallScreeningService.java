package com.kaaka.callapp;

import android.Manifest;
import android.content.Context;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.telecom.Call;
import android.telecom.CallScreeningService;
import android.telephony.SmsManager;
import android.util.Log;
import androidx.annotation.RequiresApi;
import java.util.ArrayList;
import org.json.JSONException;
import org.json.JSONObject;

/**
 * Screens incoming calls on this phone (requires the call screening role, Android 10+):
 * optionally rejects the call, texts the caller the reply message, logs the event and
 * forwards it to the optional dashboard server. No Mac or Bluetooth link involved.
 */
@RequiresApi(api = Build.VERSION_CODES.Q)
public class KaakaCallScreeningService extends CallScreeningService {
    private static final String TAG = "KaakaGateway";

    @Override
    public void onScreenCall(Call.Details details) {
        if (details.getCallDirection() != Call.Details.DIRECTION_INCOMING) {
            respondToCall(details, new CallResponse.Builder().build());
            return;
        }

        Context context = getApplicationContext();
        boolean reject = GatewayStore.rejectCalls(context);
        Uri handle = details.getHandle();
        String number = handle == null ? "" : handle.getSchemeSpecificPart();
        if (number == null) number = "";

        CallResponse.Builder response = new CallResponse.Builder();
        if (reject) {
            // Keep the call in the call log and show the missed-call notification.
            response.setDisallowCall(true).setRejectCall(true).setSkipCallLog(false).setSkipNotification(false);
        }
        respondToCall(details, response.build());

        final String caller = number.trim();
        new Thread(() -> handleCall(context, caller, reject)).start();
    }

    private static void handleCall(Context context, String number, boolean rejected) {
        String smsResult = sendReply(context, number);
        JSONObject event = new JSONObject();
        try {
            event.put("type", "call");
            event.put("number", number);
            event.put("state", rejected ? "rejected" : "allowed");
            event.put("sms", smsResult);
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
