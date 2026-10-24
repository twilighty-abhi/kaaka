# Kaaka Call App 📱

Capacitor (SvelteKit) gateway app for the phone whose number people call (the "112 alternative"). It works on its own, without the Mac or a Bluetooth link:

1. **Call screening** (Android 10+): when a call comes in, the app's `CallScreeningService` reads the caller's number and, if "reject incoming calls" is on (default), rejects the call. The call still appears in the call log and as a missed-call notification.
   Calls from numbers saved in the phone's contacts are not passed to call screening by Android; `IncomingCallReceiver` handles those from the phone-state broadcast and ends the call (needs the *calls from contacts* permissions). Events from this path show "(contact)".
2. **Auto-reply SMS**: the caller gets the auto-reply message by SMS. The default is "Kaaka received your call. Help is being arranged. If in immediate danger, call 112." (editable; the earlier default "received call. will get back to you shortly." is replaced automatically). Hidden or unknown numbers get no SMS; there is no fallback number.
3. **Alert SMS**: incoming SMS containing "Kaaka Alert" or "Live Sensors" (sent by the Kaaka Sensors client app) are recorded as alerts. The app only reads SMS; it does not need to be the default SMS app.
4. **Responder alerts**: every call and every alert is also texted to the responder numbers set in **[config]** (comma or new line separated; empty by default). Calls: "Kaaka: call from <number> at <HH:mm> — rejected/allowed, reply sent/failed/skipped". Alerts: "Kaaka alert from <sender>: " plus the alert's first line and its Maps link. Both end with "Reply ACK <number> to confirm." (not for hidden numbers). The caller or sender is never texted as a responder.
5. **Recent events**: calls (number, rejected/allowed, SMS sent/failed/skipped, responders texted) and alerts are kept on the phone (last 50) and shown in the app.
6. **Dashboard (optional)**: if a dashboard server is set (e.g. `http://<mac-ip>:8080`), each call is posted to `/api/call-event` and each alert to `/api/telemetry`. Leave it empty to run phone-only.
7. **Heartbeat**: while a dashboard server is set, the phone posts `/api/heartbeat` every 15 minutes (WorkManager, when online) and right after settings are saved: `{"timestamp", "battery", "charging", "screeningRole", "smsGranted", "contactCalls"}`. The dashboard can then warn when the gateway goes quiet.
8. **Responder ACK**: a configured responder replies "ACK" (or "ACK +91XXXXXXXXXX" for a specific caller; a bare "ACK" means the most recent call or alert). The caller is texted "A Kaaka responder has seen your call and will contact you soon.", an `ack` event is logged, `/api/ack` `{"number", "responder", "timestamp"}` is posted to the dashboard, and the responder gets "Kaaka: ACK recorded for <number>" (or "Kaaka: no recent incident to acknowledge"). ACK messages from non-responders are ignored, and an ACK is never forwarded to other responders.
9. **Location link (optional)**: every call with a caller number gets a random token. If **public link URL** is set (an **https** address that reaches the dashboard server, e.g. a tunnel), the reply SMS ends with "Share your location: <public URL>/l/<token>"; the caller opens it in any browser and shares GPS with the dashboard. The token is sent in `/api/call-event` either way. Browsers block location sharing on plain http pages, so the app warns if the URL is not https.
10. **Dashboard token (optional)**: if the server sets `KAAKA_ADMIN_TOKEN`, enter the same value as **dashboard token**; every request to the dashboard (call events, alerts, heartbeat, ACK) then carries it in the `X-Kaaka-Token` header.
11. **Manual SMS**: enter a number and message and send.

## Setup on the phone

1. Install the APK (`gateway/Kaaka.apk`) and open **Kaaka Call**.
2. Tap **[enable]** next to *call screening* and choose Kaaka Call as the call screening (caller ID & spam) app. This replaces any other app in that role.
3. Tap **[allow]** next to *sms send / receive* and allow SMS.
4. Tap **[allow]** next to *calls from contacts* (phone, call log and call management permissions) so saved contacts are handled too.
5. Tap **[exempt]** next to *battery optimisation* so Android does not put the gateway to sleep.
6. The header shows **active** when screening and SMS sending are both on.
7. **[config]** → reject on/off, auto-reply text, responder numbers, dashboard server, optional public link URL and dashboard token → **save**.

Settings are stored natively, so screening and replies work while the app is closed.

## Notes and limits

- Call screening needs Android 10 or newer and the call screening role; without it nothing happens on incoming calls.
- Ending calls from contacts uses `TelecomManager.endCall`, which Android has deprecated; if it stops working, those calls keep ringing but still get the SMS, responder texts and dashboard event.
- Responder alerts, ACK confirmations and location links are ordinary SMS from this phone's SIM and cost the same; the link makes the reply longer (possibly two SMS parts).
- The location link only works if the public URL is https and actually reaches the dashboard server; the dashboard is not reachable from the internet by default.
- Rejecting a call sends the caller to busy/voicemail, depending on the carrier.
- Phone calls cannot be answered with audio by an app; this app only screens, rejects and texts.

## Build

```bash
npm install
npm run build
npx cap sync android
cd android && ./gradlew testDebugUnitTest assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```
A prebuilt debug APK is kept at `gateway/Kaaka.apk`.

## Project structure

- `src/routes/+page.svelte`: setup status, settings, recent events, manual SMS.
- `android/app/src/main/java/com/kaaka/callapp/KaakaCallScreeningService.java`: screens incoming calls (unknown numbers).
- `android/app/src/main/java/com/kaaka/callapp/IncomingCallReceiver.java`: handles calls from saved contacts.
- `android/app/src/main/java/com/kaaka/callapp/CallHandler.java`: auto-reply, responder texts, event log and dashboard report for a call.
- `android/app/src/main/java/com/kaaka/callapp/AlertSmsReceiver.java`: records Kaaka alert SMS, texts responders, handles responder ACK replies.
- `android/app/src/main/java/com/kaaka/callapp/GatewayText.java`: location tokens, ACK parsing, location link text (unit-tested in `android/app/src/test`).
- `android/app/src/main/java/com/kaaka/callapp/GatewayStore.java`: settings, event log, SMS sending, responders, dashboard forwarding.
- `android/app/src/main/java/com/kaaka/callapp/Heartbeat.java`, `HeartbeatWorker.java`: 15-minute dashboard heartbeat and setup checks.
- `android/app/src/main/java/com/kaaka/callapp/GatewayPlugin.java`: bridge between the UI and native code (role, permissions, settings, events).
- `capacitor.config.ts`: Capacitor configuration (app ID `com.kaaka.callapp`).
