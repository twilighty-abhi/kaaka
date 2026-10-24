# Kaaka Call App 📱

A modern cross-platform Capacitor app featuring a phone dialer input box with the placeholder `9995283835` and an instant call button.

## ✨ Features

- **Phone Number Input**: Number input with `placeholder="9995283835"`. Accepts numeric input, `+`, `*`, and `#`.
- **Direct Dial Button**: One-tap Call button that triggers the native phone dialer for the entered number or falls back to `9995283835`.
- **Integrated Keypad**: On-screen keypad (1-9, *, 0, #) with tactile feedback, backspace, and quick-clear controls.
- **Capacitor Mobile Ready**: Pre-configured for Android (`@capacitor/android`) and Web/PWA.
- **Cross-Platform Support**: Works seamlessly on Web, Android WebView, and iOS.

---

## 🚀 Getting Started

### 1. Run Development Server (Web / Browser)
```bash
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

### 2. Build the Web App
```bash
npm run build
```

### 3. Sync with Capacitor (Android)
```bash
npm run cap:sync
```

### 4. Open in Android Studio
```bash
npm run cap:open
# or
npx cap open android
```

### 5. Run Directly on Connected Android Device or Emulator
```bash
npm run cap:android
```

---

## 🛠️ Project Structure

- [`src/App.tsx`](file:///home/sujith/kaaka/src/App.tsx): Main dialer component containing the phone input, placeholder `9995283835`, and call handling.
- [`src/index.css`](file:///home/sujith/kaaka/src/index.css): Responsive dark/modern styles optimized for mobile touchscreens and desktop.
- [`capacitor.config.ts`](file:///home/sujith/kaaka/capacitor.config.ts): Capacitor configuration file.
- [`android/`](file:///home/sujith/kaaka/android): Native Android Gradle project ready to build into an APK or AAB.
