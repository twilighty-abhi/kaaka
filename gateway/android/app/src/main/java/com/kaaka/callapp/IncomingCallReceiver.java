package com.kaaka.callapp;

import android.Manifest;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.telecom.TelecomManager;
import android.telephony.TelephonyManager;
import android.util.Log;

/**
 * Fallback for incoming calls that Android does not pass to the call screening app:
 * calls from numbers saved in the phone's contacts. Uses the phone-state broadcast,
 * which needs READ_PHONE_STATE, plus READ_CALL_LOG for the caller number. If "reject calls"
 * is on and ANSWER_PHONE_CALLS is granted, the ringing call is ended.
 */
public class IncomingCallReceiver extends BroadcastReceiver {
    private static final String TAG = "KaakaGateway";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (!TelephonyManager.ACTION_PHONE_STATE_CHANGED.equals(intent.getAction())) return;
        if (!TelephonyManager.EXTRA_STATE_RINGING.equals(intent.getStringExtra(TelephonyManager.EXTRA_STATE))) return;

        // Android 9+ sends this broadcast twice while ringing: once without the number and,
        // for apps holding READ_CALL_LOG, once with it. Only the second one is useful.
        @SuppressWarnings("deprecation")
        String number = intent.getStringExtra(TelephonyManager.EXTRA_INCOMING_NUMBER);
        if (number == null || number.trim().isEmpty()) return;
        final String caller = number.trim();

        Context app = context.getApplicationContext();
        if (!GatewayStore.claimCall(app, caller)) return; // already handled by call screening

        boolean ended = GatewayStore.rejectCalls(app) && endRingingCall(app);
        PendingResult pending = goAsync();
        new Thread(() -> {
            try {
                CallHandler.handleCall(app, caller, ended, "phone_state");
            } finally {
                pending.finish();
            }
        }).start();
    }

    /** Ends the ringing call. TelecomManager.endCall is deprecated but is the only option outside call screening. */
    @SuppressWarnings("deprecation")
    private static boolean endRingingCall(Context context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.P) return false;
        if (context.checkSelfPermission(Manifest.permission.ANSWER_PHONE_CALLS) != PackageManager.PERMISSION_GRANTED) {
            Log.w(TAG, "ANSWER_PHONE_CALLS not granted; contact call keeps ringing");
            return false;
        }
        try {
            boolean ended = context.getSystemService(TelecomManager.class).endCall();
            Log.i(TAG, "endCall for contact call: " + ended);
            return ended;
        } catch (Exception e) {
            Log.w(TAG, "endCall failed: " + e.getMessage());
            return false;
        }
    }
}
