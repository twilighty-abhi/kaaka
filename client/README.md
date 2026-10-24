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

## Build

```sh
npm install
npm run build
npx cap sync android
cd android && ./gradlew assembleDebug    # needs JDK 21 and the Android SDK
```

A prebuilt debug APK is kept at `client/KaakaSensors.apk`.
