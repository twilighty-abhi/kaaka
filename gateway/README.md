# Kaaka Call App 📱

Capacitor (SvelteKit) gateway app for the phone whose number people call (the "112 alternative"). It works on its own, without the Mac or a Bluetooth link:

1. **Call screening** (Android 10+): when a call comes in, the app's `CallScreeningService` reads the caller's number and, if "reject incoming calls" is on (default), rejects the call. The call still appears in the call log and as a missed-call notification.
   Calls from numbers saved in the phone's contacts are not passed to call screening by Android; `IncomingCallReceiver` handles those from the phone-state broadcast and ends the call (needs the *calls from contacts* permissions). Events from this path show "(contact)".
2. **Auto-reply SMS**: the caller gets the auto-reply message by SMS. **Reply language** in [config]: English (default) "Kaaka received your call. Help is being arranged. If in immediate danger, call 112.", Malayalam "കാക്ക നിങ്ങളുടെ സന്ദേശം സ്വീകരിച്ചു. സഹായം ഏർപ്പാടാക്കുന്നു. അടിയന്തര അപകടത്തിലാണെങ്കിൽ 112-ൽ വിളിക്കുക.", or both. **The Malayalam text should be checked by a native speaker before real use.** A custom reply text overrides the language choice (leave it empty to use the default; the earlier default "received call. will get back to you shortly." counts as empty). Malayalam SMS use Unicode, so they split into more parts. Hidden or unknown numbers get no SMS; there is no fallback number.
3. **Help by SMS**: an SMS containing HELP, SOS or KAAKA as a word (any case) or "സഹായം" is handled like a call: auto-reply (with the location link if set), responders get "Kaaka: help SMS from <number> at <HH:mm>: "<first 80 characters>" Reply ACK <number> to confirm.", the event is logged with the message, and `/api/call-event` is posted with `"state": "sms"` and `"message"`. Ordinary SMS without these words are ignored, and texts Kaaka itself sends never count as help requests (so two gateways cannot answer each other).
4. **Alert SMS**: incoming SMS containing "Kaaka Alert" or "Live Sensors" (sent by the Kaaka Sensors client app) are recorded as alerts. The app only reads SMS; it does not need to be the default SMS app.
5. **Responder alerts**: every call and every alert is also texted to the responder numbers set in **[config]** (comma or new line separated; empty by default). Calls: "Kaaka: call from <number> at <HH:mm> — rejected/allowed, reply sent/failed/skipped". Alerts: "Kaaka alert from <sender>: " plus the alert's first line and its Maps link. Both end with "Reply ACK <number> to confirm." (not for hidden numbers). The caller or sender is never texted as a responder.
6. **Recent events**: calls, help SMS, alerts, ACKs, resolves and reminders are kept on the phone (last 200) and shown in the app.
7. **Dashboard (optional)**: if a dashboard server is set (e.g. `http://<mac-ip>:8080`), each call and help SMS is posted to `/api/call-event`, each alert to `/api/telemetry`, and ACK / RESOLVE to `/api/ack` / `/api/resolve`. Leave it empty to run phone-only.
8. **Heartbeat**: while a dashboard server is set, the phone posts `/api/heartbeat` every 15 minutes (WorkManager, when online) and right after settings are saved: `{"timestamp", "battery", "charging", "screeningRole", "smsGranted", "contactCalls"}`. The dashboard can then warn when the gateway goes quiet.
9. **Responder ACK**: a configured responder replies "ACK" (or "ACK +91XXXXXXXXXX" for a specific caller; a bare "ACK" means the most recent call or alert). The caller is texted "A Kaaka responder has seen your call and will contact you soon.", an `ack` event is logged, `/api/ack` `{"number", "responder", "timestamp"}` is posted to the dashboard, and the responder gets "Kaaka: ACK recorded for <number>" (or "Kaaka: no recent incident to acknowledge"). ACK messages from non-responders are ignored, and an ACK is never forwarded to other responders.
10. **Location link (optional)**: every call with a caller number gets a random token. If **public link URL** is set (an **https** address that reaches the dashboard server, e.g. a tunnel), the reply SMS ends with "Share your location: <public URL>/l/<token>"; the caller opens it in any browser and shares GPS with the dashboard. The token is sent in `/api/call-event` either way. Browsers block location sharing on plain http pages, so the app warns if the URL is not https.
11. **Dashboard token (optional)**: if the server sets `KAAKA_ADMIN_TOKEN`, enter the same value as **dashboard token**; every request to the dashboard (call events, alerts, heartbeat, ACK, RESOLVE) then carries it in the `X-Kaaka-Token` header.
12. **Escalation**: if an incident (call or help SMS with a number) is not acknowledged or resolved within **escalate after** minutes (default 5, 0 = off), every responder gets one reminder: "Kaaka UNACKNOWLEDGED: <call|help SMS> from <number> at <HH:mm>. Reply ACK <number> to confirm." One pending reminder per number (WorkManager); a newer contact from the same number restarts the timer. Needs responders and a visible number.
13. **Rate limiting**: at most **max replies per number per hour** (default 3, 0 = no limit) contacts from the same number get replies and responder texts. Further contacts within the hour are still logged ("rate-limited") and posted to the dashboard with `"sms": "skipped"`, but nobody is texted and no reminder is scheduled.
14. **Responder commands** (from configured responders only; other responder texts are ignored, never treated as help):
    - `STATUS`: reply with incidents from the last 24 h whose latest call/help SMS has no later ACK or RESOLVE, e.g. "Kaaka: 2 open — +91… (call 10:42), +91… (help SMS 10:50)" or "Kaaka: no open incidents".
    - `RESOLVE [number] [note]`: marks the incident resolved (bare RESOLVE = most recent incident): logs a `resolve` event, posts `/api/resolve` `{"number", "by", "note", "timestamp"}`, replies "Kaaka: resolved <number>".
    - `ACK [number]`: as above.
15. **Manual SMS**: enter a number and message and send.

## Setup on the phone

1. Install the APK (`gateway/Kaaka.apk`) and open **Kaaka Call**.
2. Tap **[enable]** next to *call screening* and choose Kaaka Call as the call screening (caller ID & spam) app. This replaces any other app in that role.
3. Tap **[allow]** next to *sms send / receive* and allow SMS.
4. Tap **[allow]** next to *calls from contacts* (phone, call log and call management permissions) so saved contacts are handled too.
5. Tap **[exempt]** next to *battery optimisation* so Android does not put the gateway to sleep.
6. The header shows **active** when screening and SMS sending are both on.
7. **[config]** → reject on/off, reply language, custom auto-reply (optional), escalation minutes, max replies per hour, responder numbers, dashboard server, optional public link URL and dashboard token → **save**.

Settings are stored natively, so screening and replies work while the app is closed.

## Notes and limits

- Call screening needs Android 10 or newer and the call screening role; without it nothing happens on incoming calls.
- Ending calls from contacts uses `TelecomManager.endCall`, which Android has deprecated; if it stops working, those calls keep ringing but still get the SMS, responder texts and dashboard event.
- Escalation reminders run through WorkManager; Android may delay them a little on a sleeping phone, more so without the battery-optimisation exemption.
- STATUS, rate limiting and escalation use the phone's own event log (last 200 events), not the dashboard.
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
