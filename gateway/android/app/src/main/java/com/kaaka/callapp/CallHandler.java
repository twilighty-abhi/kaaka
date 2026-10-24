package com.kaaka.callapp;

import android.content.Context;
import org.json.JSONException;
import org.json.JSONObject;

/**
 * What happens after an incoming call is detected, whichever path saw it
 * (call screening for unknown numbers, phone-state broadcast for saved contacts):
 * text the caller the reply message, text the responders, log the event and report it to the optional dashboard.
 * Run on a background thread.
 */
final class CallHandler {
    private CallHandler() {}

    static void handleCall(Context context, String number, boolean rejected, String via) {
        // Token for the optional "share your location" link; the server maps it to this caller.
        String token = number.isEmpty() ? "" : GatewayText.newToken();
        String link = GatewayText.locationLine(GatewayStore.publicUrl(context), token);
        String smsResult = sendReply(context, number, link);
        JSONObject event = new JSONObject();
        try {
            event.put("type", "call");
            event.put("number", number);
            event.put("state", rejected ? "rejected" : "allowed");
            event.put("sms", smsResult);
            event.put("via", via);
            if (!token.isEmpty()) event.put("token", token);
            if (!link.isEmpty()) event.put("locationLink", true);
            event.put("timestamp", GatewayStore.nowIso());
        } catch (JSONException ignored) {
        }
        String responderMessage = "Kaaka: call from " + (number.isEmpty() ? "hidden number" : number)
            + " at " + GatewayStore.timeOfDay() + " — " + (rejected ? "rejected" : "allowed") + ", reply " + smsResult
            + (number.isEmpty() ? "" : "\nReply ACK " + number + " to confirm.");
        GatewayStore.notifyResponders(context, responderMessage, number, event);
        GatewayStore.appendEvent(context, event);

        JSONObject payload = new JSONObject();
        try {
            payload.put("number", number);
            payload.put("state", rejected ? "rejected" : "allowed");
            payload.put("sms", smsResult);
            payload.put("timestamp", event.optString("timestamp"));
            if (!token.isEmpty()) payload.put("token", token);
        } catch (JSONException ignored) {
        }
        GatewayStore.postToDashboard(context, "/api/call-event", payload);
    }

    /** Returns "sent", "failed" or "skipped" (hidden/unknown number: never texts a fallback). */
    private static String sendReply(Context context, String number, String locationLink) {
        if (number.isEmpty()) return "skipped";
        return GatewayStore.sendSms(context, number, GatewayStore.replyMessage(context) + locationLink) ? "sent" : "failed";
    }
}
