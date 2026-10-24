# Kaaka Call App 📱

Capacitor (SvelteKit) gateway app for the phone that receives calls. It connects to the Kaaka server over WebSocket, and when the server reports an incoming call (`CALL_DETECTED`) it sends the caller an auto-reply SMS. Numbers can also be entered and texted manually.

## ✨ Features

- **Server link**: WebSocket connection to the Kaaka server, set under **[config] → endpoint** (`ws://<mac-ip>:8765`). Nothing is preset; the app shows "no server" until it is set.
- **Auto-reply SMS**: Sends the reply message to the caller number from `CALL_DETECTED` and reports `SMS_SENT` back to the server. No fallback number is ever used.
- **Manual SMS / call**: Enter a number and message and send.
- **Capacitor Mobile Ready**: Android (`@capacitor/android`) with native SMS and call plugins.

Permissions on the phone: SMS (asked on first send) and Phone (asked on first call).

---

## 🚀 Getting Started

### 1. Run Development Server (Web / Browser)
```bash
npm run dev
```

### 2. Build the Web App
```bash
npm run build
```

### 3. Sync with Capacitor (Android)
```bash
npx cap sync android
```

### 4. Build and install the APK
```bash
cd android && ./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```
A prebuilt debug APK is kept at `gateway/Kaaka.apk`.

---

## 🛠️ Project Structure

- `src/routes/+page.svelte`: Main screen: server connection, auto-reply SMS, manual send, settings.
- `capacitor.config.ts`: Capacitor configuration (app ID `com.kaaka.callapp`).
- `android/`: Native Android Gradle project, including the SMS and call plugins.
