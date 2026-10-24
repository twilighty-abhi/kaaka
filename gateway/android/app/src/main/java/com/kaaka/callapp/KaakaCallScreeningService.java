package com.kaaka.callapp;

import android.content.Context;
import android.net.Uri;
import android.os.Build;
import android.telecom.Call;
import android.telecom.CallScreeningService;
import androidx.annotation.RequiresApi;

/**
 * Screens incoming calls on this phone (requires the call screening role, Android 10+):
 * optionally rejects the call, texts the caller the reply message, logs the event and
 * forwards it to the optional dashboard server. No Mac or Bluetooth link involved.
 */
@RequiresApi(api = Build.VERSION_CODES.Q)
public class KaakaCallScreeningService extends CallScreeningService {
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
        // Shared with IncomingCallReceiver so a call that both see is handled only once.
        if (!GatewayStore.claimCall(context, caller)) return;
        new Thread(() -> CallHandler.handleCall(context, caller, reject, "screening")).start();
    }
}
