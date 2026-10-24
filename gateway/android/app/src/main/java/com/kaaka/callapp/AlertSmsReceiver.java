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
 * "ACK" from a responder acknowledges an incident; messages that look like Kaaka sensor alerts are logged,
 * texted to the responders and forwarded to the optional dashboard.
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
        String sender = messages[0].getOriginatingAddress();
        final String from = sender == null ? "" : sender;
        final Context appContext = context.getApplicationContext();

        String ackTarget = GatewayText.parseAck(text);
        if (ackTarget != null && GatewayStore.isResponder(appContext, from)) {
            final PendingResult pending = goAsync();
            new Thread(() -> {
                try {
                    handleAck(appContext, from, ackTarget);
                } finally {
                    pending.finish();
                }
            }).start();
            return;
        }

        if (!text.contains("Kaaka Alert") && !text.contains("Live Sensors")) return;

        final PendingResult pending = goAsync();
        new Thread(() -> {
            try {
                JSONObject event = new JSONObject();
                event.put("type", "alert");
                event.put("sender", from);
                event.put("text", text);
                event.put("timestamp", GatewayStore.nowIso());
                GatewayStore.notifyResponders(appContext, responderMessage(from, text), from, event);
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

    /**
     * A responder replied "ACK" (optionally with the caller number): tell the caller, log it,
     * report it to the dashboard and confirm back to the responder. Never forwarded to other responders.
     */
    private static void handleAck(Context context, String responder, String target) {
        String number = target.isEmpty() ? GatewayStore.lastIncidentNumber(context) : target;
        if (number.isEmpty()) {
            GatewayStore.sendSms(context, responder, "Kaaka: no recent incident to acknowledge");
            return;
        }
        boolean toCaller = GatewayStore.sendSms(context, number, "A Kaaka responder has seen your call and will contact you soon.");
        String timestamp = GatewayStore.nowIso();
        try {
            JSONObject event = new JSONObject();
            event.put("type", "ack");
            event.put("number", number);
            event.put("responder", responder);
            event.put("smsToCaller", toCaller ? "sent" : "failed");
            event.put("timestamp", timestamp);
            GatewayStore.appendEvent(context, event);

            JSONObject payload = new JSONObject();
            payload.put("number", number);
            payload.put("responder", responder);
            payload.put("timestamp", timestamp);
            GatewayStore.postToDashboard(context, "/api/ack", payload);
        } catch (JSONException ignored) {
        }
        GatewayStore.sendSms(context, responder, "Kaaka: ACK recorded for " + number);
    }

    /** Short responder text: the alert's first line plus its Maps link when present, and how to acknowledge. */
    private static String responderMessage(String sender, String text) {
        String[] lines = text.split("\\n");
        StringBuilder msg = new StringBuilder("Kaaka alert from ").append(sender.isEmpty() ? "unknown" : sender).append(": ");
        msg.append(lines[0].trim());
        String maps = null;
        for (String line : lines) {
            if (line.contains("Maps:")) maps = line.trim();
        }
        if (maps != null) {
            msg.append("\n").append(maps);
        } else if (text.length() > lines[0].length()) {
            String rest = text.substring(lines[0].length()).trim();
            msg.append("\n").append(rest.length() > 200 ? rest.substring(0, 200) + "…" : rest);
        }
        if (!sender.isEmpty()) msg.append("\nReply ACK ").append(sender).append(" to confirm.");
        return msg.toString();
    }
}
