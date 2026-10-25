#!/usr/bin/env bash
# Records a captioned walkthrough of the whole platform, all three screens side by side: a caller in a
# car calls the Kaaka number, gets the SMS reply, Kaaka Sensors beacons GPS while they drive, the nearest
# responder is dispatched and acknowledges, the caller presses SOS and later "I'm safe", and the control
# room is toured (live, incident timeline, history, analytics, responders, system) with a visible cursor.
#
# Prerequisites:
#   - the dashboard on this Mac with responders registered, e.g. on a spare port with its own data:
#       .venv-mac/bin/python server/server.py --http-port 8090 --port 8775 --data-dir demo/data-walkthrough
#   - DASH_PORT=8090 RESPONDER_NUMBERS=+919800000001 scripts/demo-setup-emulators.sh
# Phone taps are real touches (shown with "show touches"); the phone network is simulated as in
# scripts/demo-emulated.sh: the call by `gsm call`, SMS by scripts/emulator-network.py, GPS by `geo fix`.
#
# Usage: [DASH_PORT=8090] scripts/demo-walkthrough.sh <route.geojson-or-osrm.json>
# Output: demo/kaaka-demo-<timestamp>.mp4
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROUTE="${1:?route file}"
G=emulator-5554; C=emulator-5556
CALLER_NUMBER=15555215556; GATEWAY_NUMBER=+15555215554; RESPONDER=919800000001
DASH="http://127.0.0.1:${DASH_PORT:-8080}"
DURATION=176
DRIVE_FROM=24; DRIVE=108

POINTS="$(mktemp)"; CAPTIONS="$(mktemp)"; TOUR="$(mktemp)"
python3 - "$ROUTE" > "$POINTS" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
coords = d["routes"][0]["geometry"]["coordinates"] if "routes" in d else d.get("coordinates") or d["geometry"]["coordinates"]
for lon, lat in coords:
    print(lon, lat)
PY
read -r START_LON START_LAT < <(head -1 "$POINTS")
read -r END_LON END_LAT < <(tail -1 "$POINTS")

cat > "$CAPTIONS" <<'EOF'
0 7 Kaaka: the Kaaka number (left), a caller with Kaaka Sensors (middle) and the control room (right).
7 18 Someone in trouble in a car calls the Kaaka number. The call is rejected at once and logged.
18 30 The caller gets an SMS reply (in immediate danger, call 112). The reply starts Kaaka Sensors.
30 46 Kaaka Sensors beacons GPS every 15 s. The nearest available responder, Unit 3, is texted.
46 66 Unit 3 replies ACK. The Kaaka number records it and tells the caller a responder has seen the call.
66 84 The caller presses SOS: a report with live sensors and location reaches the control room.
84 128 The incident timeline shows every call, SMS, alert and location; the trail follows the car.
128 144 Unit 3 meets the car. The caller taps "I'm safe": SAFE closes the incident.
144 176 Every incident stays on record: history, analytics, responder dispatches and system health.
EOF

cat > "$TOUR" <<EOF
0 goto $DASH/
4 goto $DASH/admin
34 scroll #map-panel
58 scroll #incident-list
84 click #incident-list a[href^="#incident/"]
104 scroll #detail-map
118 scroll #detail-timeline
128 click a[href="#live"]
146 click a[href="#history"]
154 click a[href="#analytics"]
162 click a[href="#responders"]
170 click a[href="#system"]
EOF

# Runs JavaScript in an app's WebView (debug builds) and prints the result.
cdp() { # $1 serial, $2 local port, $3 expression
  local sock
  sock=$(adb -s "$1" shell cat /proc/net/unix | grep -oE "webview_devtools_remote_[0-9]+" | head -1)
  adb -s "$1" forward "tcp:$2" "localabstract:$sock" >/dev/null
  "$ROOT/.venv-mac/bin/python" - "$2" "$3" <<'PY' || true
import asyncio, json, sys, urllib.request, websockets
async def main(port, expr):
    page = [p for p in json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json")) if p["type"] == "page"][0]
    async with websockets.connect(page["webSocketDebuggerUrl"], max_size=None) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr, "awaitPromise": True, "returnByValue": True}}))
        print(json.loads(await ws.recv()).get("result", {}).get("result", {}).get("value", ""))
asyncio.run(main(sys.argv[1], sys.argv[2]))
PY
}
# Taps a WebView button on the screen (a visible touch): scrolls it into view, then taps its centre.
tap_button() { # $1 serial, $2 port, $3 text the button starts with
  local xy
  xy=$(cdp "$1" "$2" "(async () => {
    const b = [...document.querySelectorAll('button')].find(b => b.textContent.trim().startsWith(\"$3\"));
    if (!b) return '';
    b.scrollIntoView({behavior: 'smooth', block: 'center'});
    await new Promise(r => setTimeout(r, 900));
    const r = b.getBoundingClientRect();
    return Math.round((r.left + r.width / 2) * devicePixelRatio) + ' ' + Math.round((r.top + r.height / 2) * devicePixelRatio);
  })()")
  if [ -n "$xy" ]; then sleep 0.4; adb -s "$1" shell input tap $xy; else echo "  button not found: $3"; fi
}

echo "Resetting demo state..."
adb -s "$G" shell am force-stop com.kaaka.callapp
adb -s "$G" shell "run-as com.kaaka.callapp sh -c 'sed -i \"/name=\\\"events\\\"/d; /last_call/d\" shared_prefs/kaaka_gateway.xml'" || true
adb -s "$G" shell monkey -p com.kaaka.callapp -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
adb -s "$C" shell am force-stop com.kaaka.sensors
adb -s "$C" shell am force-stop com.google.android.dialer
adb -s "$C" emu geo fix "$START_LON" "$START_LAT" >/dev/null
adb -s "$C" shell monkey -p com.kaaka.sensors -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
for d in "$G" "$C"; do adb -s "$d" shell settings put system show_touches 1; done
sleep 7
# Caller: beacon every 15 s, SMS + live sensor stream only. Gateway: re-save settings (sends a heartbeat).
cdp "$C" 9223 "(()=>{localStorage.setItem('kaaka_beacon_interval','15');const s=JSON.parse(localStorage.getItem('kaaka_settings')||'{}');s.serverUrl='';localStorage.setItem('kaaka_settings',JSON.stringify(s));location.reload();return 1})()" >/dev/null
cdp "$G" 9224 "(async()=>{const g=window.Capacitor.Plugins.Gateway;await g.saveSettings(await g.getSettings());return 1})()" >/dev/null
sleep 5

python3 "$ROOT/scripts/emulator-network.py" "$G" "$C" $((DURATION + 10)) &
RELAY=$!
# GPS: parked at the start, then along the route over DRIVE seconds, then parked at the end.
(
  end=$(( $(date +%s) + DRIVE_FROM )); while [ "$(date +%s)" -lt "$end" ]; do adb -s "$C" emu geo fix "$START_LON" "$START_LAT" >/dev/null 2>&1; sleep 2; done
  python3 - "$POINTS" "$DRIVE" <<'PY' | while read -r lon lat; do adb -s "$C" emu geo fix "$lon" "$lat" >/dev/null 2>&1; sleep 1; done
import sys
pts = [tuple(map(float, l.split())) for l in open(sys.argv[1])]
steps = int(sys.argv[2])
for i in range(steps + 1):  # evenly spaced along the point list, one per second
    f = i * (len(pts) - 1) / steps
    a, b = pts[int(f)], pts[min(int(f) + 1, len(pts) - 1)]
    t = f - int(f)
    print(f"{a[0] + (b[0] - a[0]) * t:.6f} {a[1] + (b[1] - a[1]) * t:.6f}")
PY
  while true; do adb -s "$C" emu geo fix "$END_LON" "$END_LAT" >/dev/null 2>&1; sleep 2; done
) &
GPS=$!
trap 'kill $RELAY $GPS 2>/dev/null || true; pkill -P $GPS 2>/dev/null || true; rm -f "$POINTS" "$CAPTIONS" "$TOUR"' EXIT

CAPTIONS="$CAPTIONS" DASH_TOUR="$TOUR" "$ROOT/scripts/record-demo.sh" "$G" "$C" "$DURATION" "$DASH/admin" &
REC=$!
START=$(date +%s)
at() { local wait=$(( $1 - ( $(date +%s) - START ) )); [ "$wait" -gt 0 ] && sleep "$wait"; return 0; }

at 7;   echo "[7s] caller dials the Kaaka number"
        adb -s "$C" shell am start -a android.intent.action.DIAL -d "tel:$GATEWAY_NUMBER" >/dev/null
at 11;  echo "[11s] call"
        adb -s "$C" shell input tap 537 2081
        adb -s "$G" emu gsm call "$CALLER_NUMBER" >/dev/null
at 15;  echo "[15s] caller back in Kaaka Sensors (the reply arrives as a notification)"
        adb -s "$C" shell monkey -p com.kaaka.sensors -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
at 46;  echo "[46s] Unit 3 replies ACK"
        adb -s "$G" emu sms send "$RESPONDER" "ACK" >/dev/null
at 68;  echo "[68s] caller presses SOS"
        tap_button "$C" 9223 SOS
at 132; echo "[132s] caller taps I'm safe"
        tap_button "$C" 9223 "I'm safe"

wait "$REC"
