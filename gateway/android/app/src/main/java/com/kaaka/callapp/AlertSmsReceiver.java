package com.kaaka.callapp;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.provider.Telephony;
import android.telephony.SmsMessage;
import org.json.JSONException;
import org.json.JSONObject;

/**
 * Listens for incoming SMS (this app is not the default SMS app, so it only reads them).
 * Messages that look like Kaaka sensor alerts are logged and forwarded to the optional dashboard.
 */
public class AlertSmsReceiver extends BroadcastReceiver {

    @Override
    public void onReceive(Context context, Intent intent) {
        if (!Telephony.Sms.Intents.SMS_RECEIVED_ACTION.equals(intent.getAction())) return;
        SmsMessage[] messages = Telephony.Sms.Intents.getMessagesFromIntent(intent);
        if (messages == null || messages.length == 0) return;

        StringBuilder body = new StringBuilder();
        for (SmsMessage message : messages) {
            if (message.getMessageBody() != null) body.append(message.getMessageBody());
        }
        String text = body.toString();
        if (!text.contains("Kaaka Alert") && !text.contains("Live Sensors")) return;

        String sender = messages[0].getOriginatingAddress();
        final String from = sender == null ? "" : sender;
        final Context appContext = context.getApplicationContext();
        final PendingResult pending = goAsync();
        new Thread(() -> {
            try {
                JSONObject event = new JSONObject();
                event.put("type", "alert");
                event.put("sender", from);
                event.put("text", text);
                event.put("timestamp", GatewayStore.nowIso());
                GatewayStore.appendEvent(appContext, event);

                JSONObject payload = new JSONObject();
                payload.put("report", text);
                payload.put("sender", from);
                GatewayStore.postToDashboard(appContext, "/api/telemetry", payload);
            } catch (JSONException ignored) {
            } finally {
                pending.finish();
            }
        }).start();
    }
}
