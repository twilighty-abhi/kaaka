#!/usr/bin/env bash
# Boots two Android emulators and configures them for the Kaaka demo:
#   emulator-5554 = Kaaka number (Kaaka Call, call screening, dashboard http://10.0.2.2:$DASH_PORT)
#   emulator-5556 = caller (Kaaka Sensors, gateway number +15555215554)
# Usage: [DASH_PORT=8080] scripts/demo-setup-emulators.sh [avd-name=Pixel_9]
# Emulators run read-only (changes are discarded on shutdown), so run this after every boot.
# Installs the debug builds: the demo scripts drive the apps through run-as and WebView devtools,
# which the release-signed APKs do not allow (build them with ./gradlew assembleDebug).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AVD="${1:-Pixel_9}"
EMU="$HOME/Library/Android/sdk/emulator/emulator"
G=emulator-5554; C=emulator-5556
DASH_PORT="${DASH_PORT:-8080}"
GATEWAY_APK="$ROOT/gateway/android/app/build/outputs/apk/debug/app-debug.apk"
CLIENT_APK="$ROOT/client/android/app/build/outputs/apk/debug/app-debug.apk"

for port in 5554 5556; do
  if ! adb devices | grep -q "emulator-$port"; then
    # Host GPU rendering avoids the partial frames software rendering shows in screen recordings.
    nohup "$EMU" -avd "$AVD" -read-only -port "$port" -no-window -no-audio -no-boot-anim -no-snapshot -gpu host \
      > "/tmp/kaaka-emulator-$port.log" 2>&1 &
  fi
done
echo "Waiting for boot..."
for d in "$G" "$C"; do
  until [ "$(adb -s "$d" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = 1 ]; do sleep 3; done
done

adb -s "$G" install -r "$GATEWAY_APK" >/dev/null
adb -s "$C" install -r "$CLIENT_APK" >/dev/null

# Android asks before an app sends more than 30 SMS in 30 minutes; a 15 s beacon passes that in a demo.
# The limit is read when the phone process starts, so set it and reboot the guest (state survives this).
if [ "$(adb -s "$C" shell settings get global sms_outgoing_check_max_count | tr -d '\r')" != 10000 ]; then
  for d in "$G" "$C"; do
    adb -s "$d" shell settings put global sms_outgoing_check_max_count 10000
    adb -s "$d" shell settings put global sms_outgoing_check_interval_ms 60000
    adb -s "$d" reboot
  done
  sleep 10
  for d in "$G" "$C"; do
    adb -s "$d" wait-for-device
    until [ "$(adb -s "$d" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = 1 ]; do sleep 3; done
  done
fi

# Gateway: permissions, call-screening role, battery exemption, settings.
for p in SEND_SMS RECEIVE_SMS READ_PHONE_STATE READ_CALL_LOG ANSWER_PHONE_CALLS POST_NOTIFICATIONS; do
  adb -s "$G" shell pm grant com.kaaka.callapp "android.permission.$p"
done
adb -s "$G" shell cmd role add-role-holder android.app.role.CALL_SCREENING com.kaaka.callapp 0
adb -s "$G" shell cmd deviceidle whitelist +com.kaaka.callapp >/dev/null
adb -s "$G" shell monkey -p com.kaaka.callapp -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1; sleep 5
adb -s "$G" shell am force-stop com.kaaka.callapp
PREFS="$(mktemp)"
cat > "$PREFS" <<EOF
<?xml version='1.0' encoding='utf-8' standalone='yes' ?>
<map>
    <boolean name="reject_calls" value="true" />
    <string name="dashboard_url">http://10.0.2.2:$DASH_PORT</string>
    <string name="reply_message"></string>
    <string name="reply_language">en</string>
    <int name="escalate_minutes" value="5" />
    <int name="max_replies_per_hour" value="0" />
    <string name="responder_numbers">${RESPONDER_NUMBERS:-}</string>
    <string name="public_url"></string>
    <string name="dashboard_token"></string>
</map>
EOF
adb -s "$G" push "$PREFS" /data/local/tmp/kaaka_gateway.xml >/dev/null
adb -s "$G" shell "run-as com.kaaka.callapp sh -c 'mkdir -p shared_prefs && cp /data/local/tmp/kaaka_gateway.xml shared_prefs/kaaka_gateway.xml'"
rm -f "$PREFS"
adb -s "$G" shell monkey -p com.kaaka.callapp -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1

# Caller: permissions (incl. background location for the reply-triggered alert), settings via the WebView.
for p in SEND_SMS RECEIVE_SMS READ_PHONE_STATE ACCESS_FINE_LOCATION ACCESS_COARSE_LOCATION ACCESS_BACKGROUND_LOCATION POST_NOTIFICATIONS ACTIVITY_RECOGNITION; do
  adb -s "$C" shell pm grant com.kaaka.sensors "android.permission.$p"
done
adb -s "$C" shell cmd deviceidle whitelist +com.kaaka.sensors >/dev/null
adb -s "$C" shell monkey -p com.kaaka.sensors -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
# The first start after install can take longer; wait for the WebView's devtools socket.
until SOCK=$(adb -s "$C" shell cat /proc/net/unix | grep -oE "webview_devtools_remote_[0-9]+" | head -1) && [ -n "$SOCK" ]; do sleep 2; done
sleep 3
adb -s "$C" forward tcp:9223 "localabstract:$SOCK" >/dev/null
"$ROOT/.venv-mac/bin/python" - "$DASH_PORT" <<'PY'
import asyncio, json, sys, urllib.request, websockets
EXPR = """(async () => {
  const s = JSON.parse(localStorage.getItem('kaaka_settings') || '{}');
  Object.assign(s, { gatewayNumber: '+15555215554', serverUrl: '', backendUrl: 'http://10.0.2.2:%s' });
  localStorage.setItem('kaaka_settings', JSON.stringify(s));
  await window.Capacitor.Plugins.DefaultSms.setAuthorizedNumber({ number: '+15555215554' });
  location.reload();
  return 'ok';
})()""" % sys.argv[1]
async def main():
    page = [p for p in json.load(urllib.request.urlopen("http://127.0.0.1:9223/json")) if p["type"] == "page"][0]
    async with websockets.connect(page["webSocketDebuggerUrl"], max_size=None) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": EXPR, "awaitPromise": True}}))
        await ws.recv()
asyncio.run(main())
PY
echo "Emulators ready: $G (Kaaka number) and $C (caller)."
