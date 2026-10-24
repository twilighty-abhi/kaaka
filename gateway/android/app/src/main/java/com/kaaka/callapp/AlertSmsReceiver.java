package com.kaaka.callapp;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.provider.Telephony;
import android.telephony.SmsMessage;
import org.json.JSONException;
import org.json.JSONObject;

/**
 * Listens for incoming SMS (this app is not the default SMS app, so it only reads them), in this order:
 * responder commands (ACK, STATUS, RESOLVE), Kaaka sensor alerts (logged, texted to responders, forwarded),
 * SAFE from a caller with an open incident (closes it), other responder texts (ignored), and help requests
 * (HELP / SOS / KAAKA / സഹായം), handled like a call.
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

        boolean responder = GatewayStore.isResponder(appContext, from);
        if (responder) {
            String ackTarget = GatewayText.parseAck(text);
            String[] resolve = GatewayText.parseResolve(text);
            if (ackTarget != null) {
                runAsync(() -> handleAck(appContext, from, ackTarget));
                return;
            }
            if (GatewayText.isStatus(text)) {
                runAsync(() -> GatewayStore.sendSms(appContext, from,
                    GatewayText.statusMessage(GatewayText.openIncidents(GatewayStore.eventList(appContext), System.currentTimeMillis()))));
                return;
            }
            if (resolve != null) {
                runAsync(() -> handleResolve(appContext, from, resolve[0], resolve[1]));
                return;
            }
        }

        if (!text.contains("Kaaka Alert") && !text.contains("Live Sensors")) {
            // A caller with an open incident says they are safe: close it (checked before help keywords).
            if (!from.isEmpty() && GatewayText.isSafeReport(text)) {
                runAsync(() -> handleSafe(appContext, from));
                return;
            }
            // Responders' other texts are never treated as help requests.
            if (!responder && !from.isEmpty() && GatewayText.isHelpRequest(text)) {
                runAsync(() -> CallHandler.handleHelpSms(appContext, from, text));
            }
            return;
        }

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

    /** Runs work off the main thread while keeping the broadcast alive until it finishes. */
    private void runAsync(Runnable work) {
        final PendingResult pending = goAsync();
        new Thread(() -> {
            try {
                work.run();
            } finally {
                pending.finish();
            }
        }).start();
    }

    /**
     * The caller texted SAFE: close their open incident, confirm to them, tell responders, report it.
     * A SAFE from a number without an open incident is ignored (no reply, nothing logged).
     */
    private static void handleSafe(Context context, String caller) {
        if (!GatewayText.hasOpenIncident(GatewayStore.eventList(context), caller, System.currentTimeMillis())) return;
        String timestamp = GatewayStore.nowIso();
        boolean toCaller = GatewayStore.sendSms(context, caller,
            "Kaaka: glad you are safe. Your alert is closed. If you need help again, call or text this number.");
        try {
            JSONObject event = new JSONObject();
            event.put("type", "safe");
            event.put("number", caller);
            event.put("smsToCaller", toCaller ? "sent" : "failed");
            event.put("timestamp", timestamp);
            GatewayStore.notifyResponders(context,
                "Kaaka: " + caller + " reported safe at " + GatewayStore.timeOfDay() + ". Incident closed.", caller, event);
            GatewayStore.appendEvent(context, event);

            JSONObject payload = new JSONObject();
            payload.put("number", caller);
            payload.put("by", "caller");
            payload.put("note", "Caller reported safe");
            payload.put("timestamp", timestamp);
            GatewayStore.postToDashboard(context, "/api/resolve", payload);
        } catch (JSONException ignored) {
        }
    }

    /** A responder sent "RESOLVE [number] [note]": log it, report it to the dashboard and confirm. */
    private static void handleResolve(Context context, String responder, String target, String note) {
        String number = target.isEmpty() ? GatewayStore.lastIncidentNumber(context) : target;
        if (number.isEmpty()) {
            GatewayStore.sendSms(context, responder, "Kaaka: no recent incident to resolve");
            return;
        }
        String timestamp = GatewayStore.nowIso();
        try {
            JSONObject event = new JSONObject();
            event.put("type", "resolve");
            event.put("number", number);
            event.put("responder", responder);
            if (!note.isEmpty()) event.put("note", note);
            event.put("timestamp", timestamp);
            GatewayStore.appendEvent(context, event);

            JSONObject payload = new JSONObject();
            payload.put("number", number);
            payload.put("by", responder);
            payload.put("note", note);
            payload.put("timestamp", timestamp);
            GatewayStore.postToDashboard(context, "/api/resolve", payload);
        } catch (JSONException ignored) {
        }
        GatewayStore.sendSms(context, responder, "Kaaka: resolved " + number);
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
