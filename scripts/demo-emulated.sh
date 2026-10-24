#!/usr/bin/env bash
# Records a captioned demo of the full Kaaka flow on two Android emulators plus the Mac dashboard.
#
# Prerequisites (see docs/TESTING.md, "Emulated demo"):
#   - emulator-5554 runs Kaaka Call (call-screening role, SMS/phone permissions, dashboard http://10.0.2.2:8080)
#   - emulator-5556 runs Kaaka Sensors (permissions incl. background location, gateway number +15555215554)
#   - the dashboard runs on this Mac: .venv-mac/bin/python server/server.py (no --bt-mac)
# The phone network is simulated: the incoming call via the emulator console (`gsm call`), SMS between
# the emulators by scripts/emulator-network.py, and GPS by `geo fix`. Everything else is the real apps and server.
#
# Usage: scripts/demo-emulated.sh   → demo/kaaka-demo-<timestamp>.mp4
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
G=emulator-5554           # Kaaka number (gateway)
C=emulator-5556           # caller with Kaaka Sensors
CALLER_NUMBER=15555215556
DASH=http://127.0.0.1:8080
DURATION=165
LAT=9.9312; LON=76.2673  # Kochi

CAPTIONS="$(mktemp)"
cat > "$CAPTIONS" <<'EOF'
0 11 Kaaka: the Kaaka number, a caller with Kaaka Sensors, and the control room dashboard. A person in trouble calls the Kaaka number.
12 42 The call is rejected at once. The caller gets an SMS reply that also says: in immediate danger, call 112.
42 62 The reply starts Kaaka Sensors on the caller's phone: it sends a Kaaka Alert with GPS. The dashboard shows the incident and a map pin.
62 92 The caller presses SOS: another report with live sensors and location reaches the Kaaka number and the dashboard.
92 122 Someone who cannot talk texts HELP to the Kaaka number. It is handled like a call: auto-reply and incident.
122 165 A responder resolves the incident from the dashboard. Every call, alert and location is kept per caller.
EOF

# Runs JavaScript inside an app's WebView (debug builds) — used to press buttons and save settings.
cdp() { # $1 serial, $2 local port, $3 expression
  local sock
  sock=$(adb -s "$1" shell cat /proc/net/unix | grep -oE "webview_devtools_remote_[0-9]+" | head -1)
  adb -s "$1" forward "tcp:$2" "localabstract:$sock" >/dev/null
  "$ROOT/.venv-mac/bin/python" - "$2" "$3" <<'PY' || true
import asyncio, json, sys, urllib.request, websockets
async def main(port, expr):
    page = [p for p in json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json")) if p["type"] == "page"][0]
    async with websockets.connect(page["webSocketDebuggerUrl"], max_size=None) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "awaitPromise": True}}))
        await ws.recv()
asyncio.run(main(sys.argv[1], sys.argv[2]))
PY
}
click() { cdp "$1" "$2" "[...document.querySelectorAll('button')].find(b => b.textContent.trim() === '$3')?.click(); 'ok'"; }

echo "Resetting demo state..."
# Gateway: clear its event log (keep settings), bring Kaaka Call to the front.
adb -s "$G" shell am force-stop com.kaaka.callapp
adb -s "$G" shell "run-as com.kaaka.callapp sh -c 'sed -i \"/name=\\\"events\\\"/d; /last_call/d\" shared_prefs/kaaka_gateway.xml'" || true
adb -s "$G" shell monkey -p com.kaaka.callapp -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
# Caller: fresh app start in the foreground.
adb -s "$C" shell am force-stop com.kaaka.sensors
adb -s "$C" shell monkey -p com.kaaka.sensors -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
sleep 6
# Caller: SMS + live sensor stream only (no WebSocket copy). Gateway: re-save settings, which sends a heartbeat.
cdp "$C" 9223 "(()=>{const s=JSON.parse(localStorage.getItem('kaaka_settings')||'{}');s.serverUrl='';localStorage.setItem('kaaka_settings',JSON.stringify(s));location.reload();return 1})()"
cdp "$G" 9224 "(async()=>{const g=window.Capacitor.Plugins.Gateway;await g.saveSettings(await g.getSettings());return 1})()"
sleep 4

# Background helpers for the whole recording: SMS relay and a GPS feed (real phones stream GPS continuously).
python3 "$ROOT/scripts/emulator-network.py" "$G" "$C" $((DURATION + 10)) &
RELAY=$!
( end=$(( $(date +%s) + DURATION )); while [ "$(date +%s)" -lt "$end" ]; do adb -s "$C" emu geo fix "$LON" "$LAT" >/dev/null 2>&1; sleep 2; done ) &
GPS=$!
trap 'kill $RELAY $GPS 2>/dev/null || true' EXIT

# Recording runs in parallel with the scenario below.
CAPTIONS="$CAPTIONS" "$ROOT/scripts/record-demo.sh" "$G" "$C" "$DURATION" "$DASH" &
REC=$!
START=$(date +%s)
at() { local wait=$(( $1 - ( $(date +%s) - START ) )); [ "$wait" -gt 0 ] && sleep "$wait"; }

at 12;  echo "[12s] incoming call";  adb -s "$G" emu gsm call "$CALLER_NUMBER" >/dev/null
at 64;  echo "[64s] SOS pressed"
        click "$C" 9223 SOS
at 95;  echo "[95s] help SMS";       adb -s "$G" emu sms send "$CALLER_NUMBER" "HELP stuck near the bridge, cannot talk" >/dev/null
at 118; echo "[118s] caller stops beacon (help arrived)"; click "$C" 9223 Stop
at 128; echo "[128s] resolve";       curl -s -X POST "$DASH/api/resolve" -H "Content-Type: application/json" \
          -d "{\"number\":\"$CALLER_NUMBER\",\"by\":\"dashboard\",\"note\":\"Responder reached the caller\"}" >/dev/null

wait "$REC"
rm -f "$CAPTIONS"
