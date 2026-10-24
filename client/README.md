# Kaaka Sensors (client app)

Android app (Capacitor + SvelteKit) for the phone of the person who may need help. It reads five sensors (accelerometer, gyroscope, magnetometer, ambient light, pedometer) plus GPS, and sends emergency reports to the Kaaka gateway phone.

## Role in the Kaaka flow

1. The person calls the Kaaka gateway number.
2. The gateway phone rejects the call and sends an auto-reply SMS.
3. This app receives that SMS. **Only an SMS from the configured gateway number** starts the emergency flow: the app comes to the front, vibrates, shows an urgent notification and starts the telemetry beacon.
4. The beacon sends a "Kaaka Alert: …" SMS report (sensors and GPS) **to the gateway number** immediately and then every 60 seconds. Reports never go to any other number.

SMS from any other sender is treated as a normal message, whatever it says. With no gateway number set, the beacon never starts.

## Which phone

Install this app on the **caller's phone**, not on the gateway phone. It asks to become the **default SMS app** (needed to receive the trigger SMS reliably and to show the full-screen alert), so it takes over SMS handling on the phone it runs on.

## Settings (Settings card on the main screen)

| Setting | Required | Purpose |
|---|---|---|
| Gateway phone number | Yes | The only number allowed to trigger the beacon, and the recipient of all alert SMS |
| Computer dashboard WebSocket | No | `ws://<mac-ip>:8765`: also copies each alert to the Kaaka server dashboard |
| Live sensor stream URL | No | `http://<mac-ip>:8080`: streams readings about once a second to the dashboard |

Kaaka works phone-to-phone with only the gateway number; the computer settings are extras.

## SOS, fall detection and the beacon

- **SOS button** (top of the main screen): immediately sends one "Kaaka Alert" SMS report to the gateway number and starts the beacon. Needs the gateway number set and SMS permission (asked on first send); errors are shown under the button.
- **Auto SOS on fall** (checkbox, default off): a simple heuristic in `src/lib/services/emergencyService.svelte.ts`. An acceleration spike above ~2.5 g, then about 2 s of near-stillness (|accel − g| < 1.5 m/s², gyro < 0.6 rad/s) within 6 s, starts a **15-second countdown** with an "I'm OK, cancel" button; if not cancelled it does the same as SOS. Untuned: expect false positives/negatives until tested on real phones.
- **Beacon**: sends a report every 60 s and stops by itself after the configured duration (default **30 minutes**, "Beacon duration" field) or when you tap Stop. The SOS card shows the trigger, reports sent, last sent time and minutes left.
- **Limits**: fall detection and the beacon run in the app's web view. They work while the app is open; with the app in the background or the screen off for long, Android may pause them. Keep the app open during an emergency.

## Report format

Every report starts with `Kaaka Alert:` (the gateway matches "Kaaka Alert" / "Live Sensors") and lists the five sensors, then:

- `• Coords: <lat>, <lon>` and `• Maps: https://maps.google.com/?q=<lat>,<lon>` when a GPS fix exists, otherwise `• Location: unavailable`. The first report is sent after at most ~5 s even without a fix; later reports include coordinates once GPS locks.
- `• Trigger: sos | fall | gateway reply | manual`.

## Build

```sh
npm install
npm run build
npx cap sync android
cd android && ./gradlew assembleDebug    # needs JDK 21 and the Android SDK
```

A prebuilt debug APK is kept at `client/KaakaSensors.apk`.
