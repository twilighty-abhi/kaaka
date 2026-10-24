# Kaaka Call App 📱

Capacitor (SvelteKit) gateway app for the phone whose number people call (the "112 alternative"). It works on its own, without the Mac or a Bluetooth link:

1. **Call screening** (Android 10+): when a call comes in, the app's `CallScreeningService` reads the caller's number and, if "reject incoming calls" is on (default), rejects the call. The call still appears in the call log and as a missed-call notification.
2. **Auto-reply SMS**: the caller gets the auto-reply message by SMS. Hidden or unknown numbers get no SMS; there is no fallback number.
3. **Alert SMS**: incoming SMS containing "Kaaka Alert" or "Live Sensors" (sent by the Kaaka Sensors client app) are recorded as alerts. The app only reads SMS; it does not need to be the default SMS app.
4. **Recent events**: calls (number, rejected/allowed, SMS sent/failed/skipped) and alerts are kept on the phone (last 50) and shown in the app.
5. **Dashboard (optional)**: if a dashboard server is set (e.g. `http://<mac-ip>:8080`), each call is posted to `/api/call-event` and each alert to `/api/telemetry`. Leave it empty to run phone-only.
6. **Manual SMS**: enter a number and message and send.

## Setup on the phone

1. Install the APK (`gateway/Kaaka.apk`) and open **Kaaka Call**.
2. Tap **[enable]** next to *call screening* and choose Kaaka Call as the call screening (caller ID & spam) app. This replaces any other app in that role.
3. Tap **[allow]** next to *sms send / receive* and allow SMS.
4. The header shows **active** when screening and SMS sending are both on.
5. Optional: **[config]** → reject on/off, auto-reply text, dashboard server → **save**.

Settings are stored natively, so screening and replies work while the app is closed.

## Notes and limits

- Call screening needs Android 10 or newer and the call screening role; without it nothing happens on incoming calls.
- Android may not ask the screening app about calls from numbers in your contacts; test with a number that is not a contact.
- Rejecting a call sends the caller to busy/voicemail, depending on the carrier.
- Phone calls cannot be answered with audio by an app; this app only screens, rejects and texts.

## Build

```bash
npm install
npm run build
npx cap sync android
cd android && ./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```
A prebuilt debug APK is kept at `gateway/Kaaka.apk`.

## Project structure

- `src/routes/+page.svelte`: setup status, settings, recent events, manual SMS.
- `android/app/src/main/java/com/kaaka/callapp/KaakaCallScreeningService.java`: screens incoming calls and sends the auto-reply.
- `android/app/src/main/java/com/kaaka/callapp/AlertSmsReceiver.java`: records Kaaka alert SMS.
- `android/app/src/main/java/com/kaaka/callapp/GatewayStore.java`: settings, event log, dashboard forwarding.
- `android/app/src/main/java/com/kaaka/callapp/GatewayPlugin.java`: bridge between the UI and native code (role, permissions, settings, events).
- `capacitor.config.ts`: Capacitor configuration (app ID `com.kaaka.callapp`).
