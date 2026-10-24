package com.kaaka.callapp;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.provider.Telephony;
import android.telephony.SmsMessage;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/**
 * Listens for incoming SMS (this app is not the default SMS app, so it only reads them), in this order:
 * responder commands (ACK, STATUS, RESOLVE), Kaaka sensor alerts (logged, texted to responders, forwarded),
 * other responder texts (ignored), and help requests (HELP / SOS / KAAKA / സഹായം), handled like a call.
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
                String response = GatewayStore.postToDashboardForResponse(appContext, "/api/telemetry", payload);
                dispatchResponders(appContext, from, response);
            } catch (JSONException ignored) {
            } finally {
                pending.finish();
            }
        }).start();
    }

    /**
     * The dashboard answers an alert with the nearest available responders ("dispatch"); text each one.
     * Nothing happens without a dashboard, without responders registered there, or for later reports of
     * an incident the dashboard already dispatched (it then returns an empty list).
     */
    private static void dispatchResponders(Context context, String caller, String response) {
        if (response == null) return;
        JSONArray dispatch;
        try {
            dispatch = new JSONObject(response).optJSONArray("dispatch");
        } catch (JSONException e) {
            return;
        }
        if (dispatch == null || dispatch.length() == 0) return;
        JSONArray texted = new JSONArray();
        int failed = 0;
        for (int i = 0; i < dispatch.length(); i++) {
            JSONObject r = dispatch.optJSONObject(i);
            if (r == null || r.optString("number").isEmpty()) continue;
            String message = GatewayText.dispatchMessage(caller, r.optDouble("distance_km", 0), r.optInt("eta_min", 1),
                r.optString("maps_url"));
            if (GatewayStore.sendSms(context, r.optString("number"), message)) {
                texted.put(r.optString("name", r.optString("number")));
            } else {
                failed++;
            }
        }
        try {
            JSONObject event = new JSONObject();
            event.put("type", "dispatch");
            event.put("number", caller);
            event.put("responderNames", texted);
            event.put("responders", texted.length());
            if (failed > 0) event.put("respondersFailed", failed);
            event.put("timestamp", GatewayStore.nowIso());
            GatewayStore.appendEvent(context, event);
        } catch (JSONException ignored) {
        }
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
