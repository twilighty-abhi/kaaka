package com.kaaka.callapp;

import android.content.Context;
import org.json.JSONException;
import org.json.JSONObject;

/**
 * What happens after someone contacts the Kaaka number, whichever path saw it
 * (call screening for unknown numbers, phone-state broadcast for saved contacts, or a help SMS):
 * text the caller the reply message, text the responders, log the event, report it to the optional
 * dashboard and schedule the escalation reminder. Run on a background thread.
 */
final class CallHandler {
    private CallHandler() {}

    static void handleCall(Context context, String number, boolean rejected, String via) {
        handleIncident(context, number, rejected ? "rejected" : "allowed", via, "");
    }

    /** A help request by SMS is handled like a call with state "sms". */
    static void handleHelpSms(Context context, String number, String message) {
        handleIncident(context, number, "sms", "sms", message);
    }

    private static void handleIncident(Context context, String number, String state, String via, String message) {
        boolean helpSms = "sms".equals(state);
        // Over the hourly limit: still logged and reported, but nobody is texted (protects SMS credit and responders).
        boolean limited = GatewayStore.isRateLimited(context, number);
        // Token for the optional "share your location" link; the server maps it to this caller.
        String token = number.isEmpty() ? "" : GatewayText.newToken();
        String link = limited ? "" : GatewayText.locationLine(GatewayStore.effectivePublicUrl(context), token);
        String smsResult = limited ? "skipped" : sendReply(context, number, link);
        String excerpt = message.length() > 500 ? message.substring(0, 500) : message;

        JSONObject event = new JSONObject();
        try {
            event.put("type", "call");
            event.put("number", number);
            event.put("state", state);
            event.put("sms", smsResult);
            event.put("via", via);
            if (helpSms) event.put("message", excerpt);
            if (limited) event.put("rateLimited", true);
            if (!token.isEmpty()) event.put("token", token);
            if (!link.isEmpty()) event.put("locationLink", true);
            event.put("timestamp", GatewayStore.nowIso());
        } catch (JSONException ignored) {
        }

        if (!limited) {
            GatewayStore.notifyResponders(context, responderMessage(number, state, smsResult, message), number, event);
        }
        GatewayStore.appendEvent(context, event);

        JSONObject payload = new JSONObject();
        try {
            payload.put("number", number);
            payload.put("state", state);
            payload.put("sms", smsResult);
            payload.put("timestamp", event.optString("timestamp"));
            if (helpSms) payload.put("message", excerpt);
            if (!token.isEmpty()) payload.put("token", token);
        } catch (JSONException ignored) {
        }
        GatewayStore.postToDashboard(context, "/api/call-event", payload);

        if (!limited) EscalationWorker.schedule(context, number, helpSms ? "help SMS" : "call", event.optLong("at"));
    }

    private static String responderMessage(String number, String state, String smsResult, String message) {
        String time = GatewayStore.timeOfDay();
        String ack = number.isEmpty() ? "" : "\nReply ACK " + number + " to confirm.";
        if ("sms".equals(state)) {
            String quote = message.trim().replaceAll("\\s+", " ");
            if (quote.length() > 80) quote = quote.substring(0, 80) + "…";
            return "Kaaka: help SMS from " + number + " at " + time + ": \"" + quote + "\"" + ack;
        }
        return "Kaaka: call from " + (number.isEmpty() ? "hidden number" : number) + " at " + time
            + " — " + state + ", reply " + smsResult + ack;
    }

    /** Returns "sent", "failed" or "skipped" (hidden/unknown number: never texts a fallback). */
    private static String sendReply(Context context, String number, String locationLink) {
        if (number.isEmpty()) return "skipped";
        return GatewayStore.sendSms(context, number, GatewayStore.replyMessage(context) + locationLink) ? "sent" : "failed";
    }
}
