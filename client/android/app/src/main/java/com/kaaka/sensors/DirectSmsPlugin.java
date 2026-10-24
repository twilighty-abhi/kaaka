package com.kaaka.sensors;

import android.Manifest;
import android.app.Activity;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.telephony.SmsManager;
import android.telephony.SubscriptionManager;
import android.util.Log;
import androidx.core.content.ContextCompat;
import java.util.ArrayList;
import java.util.concurrent.atomic.AtomicInteger;
import com.getcapacitor.JSObject;
import com.getcapacitor.PermissionState;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;

@CapacitorPlugin(
    name = "DirectSms",
    permissions = {
        @Permission(
            strings = { Manifest.permission.SEND_SMS },
            alias = "sms"
        )
    }
)
public class DirectSmsPlugin extends Plugin {

    @PluginMethod
    public void sendSms(PluginCall call) {
        String number = call.getString("number");
        String message = call.getString("message");

        if (number == null || number.trim().isEmpty()) {
            call.reject("Recipient phone number is required");
            return;
        }

        if (message == null || message.trim().isEmpty()) {
            call.reject("Message content cannot be empty");
            return;
        }

        if (getPermissionState("sms") != PermissionState.GRANTED) {
            requestPermissionForAlias("sms", call, "smsPermCallback");
        } else {
            sendDirectSms(number, message, call);
        }
    }

    @PermissionCallback
    private void smsPermCallback(PluginCall call) {
        if (getPermissionState("sms") == PermissionState.GRANTED) {
            String number = call.getString("number");
            String message = call.getString("message");
            sendDirectSms(number, message, call);
        } else {
            call.reject("Permission to send SMS was denied.");
        }
    }

    private static final String TAG = "KaakaSms";
    private static final long SEND_TIMEOUT_MS = 30_000;
    private static final AtomicInteger requestCodes = new AtomicInteger(1);

    /** SmsManager bound to the phone's default SMS SIM, so dual-SIM phones never have to guess. */
    private static SmsManager smsManager(Context context) {
        int subId = SubscriptionManager.getDefaultSmsSubscriptionId();
        if (subId != SubscriptionManager.INVALID_SUBSCRIPTION_ID) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                return context.getSystemService(SmsManager.class).createForSubscriptionId(subId);
            }
            return SmsManager.getSmsManagerForSubscriptionId(subId);
        }
        return Build.VERSION.SDK_INT >= Build.VERSION_CODES.S ? context.getSystemService(SmsManager.class) : SmsManager.getDefault();
    }

    private static String describe(int code) {
        switch (code) {
            case SmsManager.RESULT_ERROR_NO_SERVICE: return "no mobile service";
            case SmsManager.RESULT_ERROR_RADIO_OFF: return "mobile radio is off (airplane mode?)";
            case SmsManager.RESULT_ERROR_NULL_PDU: return "message could not be encoded";
            case SmsManager.RESULT_ERROR_LIMIT_EXCEEDED: return "SMS sending limit reached";
            case SmsManager.RESULT_ERROR_SHORT_CODE_NOT_ALLOWED: return "short code not allowed";
            case SmsManager.RESULT_ERROR_GENERIC_FAILURE: return "network rejected the SMS (no credit, wrong SIM or blocked)";
            default: return "error code " + code;
        }
    }

    /**
     * Sends the SMS and resolves only when the phone reports the real send result for every part
     * (previously it resolved immediately, so silent failures looked like success).
     */
    private void sendDirectSms(String number, String message, PluginCall call) {
        Context context = getContext().getApplicationContext();
        SmsManager sms;
        ArrayList<String> parts;
        try {
            sms = smsManager(context);
            parts = sms.divideMessage(message);
        } catch (Exception e) {
            call.reject("Failed to send SMS: " + e.getMessage(), e);
            return;
        }

        String action = context.getPackageName() + ".SMS_SENT." + System.nanoTime();
        Handler handler = new Handler(Looper.getMainLooper());
        int[] remaining = { parts.size() };
        int[] failure = { Activity.RESULT_OK };
        boolean[] done = { false };

        BroadcastReceiver receiver = new BroadcastReceiver() {
            @Override
            public void onReceive(Context c, Intent intent) {
                int code = getResultCode();
                if (code != Activity.RESULT_OK) failure[0] = code;
                if (--remaining[0] > 0 || done[0]) return;
                done[0] = true;
                handler.removeCallbacksAndMessages(null);
                try { context.unregisterReceiver(this); } catch (Exception ignored) {}
                if (failure[0] == Activity.RESULT_OK) {
                    Log.i(TAG, "SMS sent to " + number);
                    JSObject ret = new JSObject();
                    ret.put("success", true);
                    call.resolve(ret);
                } else {
                    Log.w(TAG, "SMS to " + number + " failed: " + describe(failure[0]));
                    call.reject("SMS not sent: " + describe(failure[0]));
                }
            }
        };
        ContextCompat.registerReceiver(context, receiver, new IntentFilter(action), ContextCompat.RECEIVER_NOT_EXPORTED);
        handler.postDelayed(() -> {
            if (done[0]) return;
            done[0] = true;
            try { context.unregisterReceiver(receiver); } catch (Exception ignored) {}
            Log.w(TAG, "SMS to " + number + ": no send confirmation within 30 s");
            call.reject("SMS not confirmed by the phone within 30 s (check SIM, signal and credit)");
        }, SEND_TIMEOUT_MS);

        ArrayList<PendingIntent> sentIntents = new ArrayList<>();
        for (int i = 0; i < parts.size(); i++) {
            Intent sent = new Intent(action).setPackage(context.getPackageName());
            sentIntents.add(PendingIntent.getBroadcast(context, requestCodes.getAndIncrement(), sent,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_ONE_SHOT));
        }
        try {
            if (parts.size() > 1) {
                sms.sendMultipartTextMessage(number, null, parts, sentIntents, null);
            } else {
                sms.sendTextMessage(number, null, message, sentIntents.get(0), null);
            }
        } catch (Exception e) {
            done[0] = true;
            handler.removeCallbacksAndMessages(null);
            try { context.unregisterReceiver(receiver); } catch (Exception ignored) {}
            call.reject("Failed to send SMS: " + e.getMessage(), e);
        }
    }
}
