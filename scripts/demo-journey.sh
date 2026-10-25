#!/usr/bin/env bash
# Records a moving-caller demo: the caller (emulator-5556) calls the Kaaka number from a car, then its
# GPS follows a driving route while Kaaka Sensors' beacon reports every 15 s; the dashboard draws the trail.
#
# Prerequisites: scripts/demo-setup-emulators.sh, and the dashboard running on this Mac (no --bt-mac).
# Usage: scripts/demo-journey.sh <route.geojson-or-osrm.json> [drive-seconds=105]
#   The route file is an OSRM /route response (geometries=geojson) or a GeoJSON LineString.
# Output: demo/kaaka-demo-<timestamp>.mp4 (raw recording; edit afterwards)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROUTE="${1:?route file}"
DRIVE="${2:-105}"
G=emulator-5554; C=emulator-5556; CALLER_NUMBER=15555215556
DURATION=$((DRIVE + 40))

# Route points as "lon lat" lines.
POINTS="$(mktemp)"
python3 - "$ROUTE" > "$POINTS" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
coords = d["routes"][0]["geometry"]["coordinates"] if "routes" in d else d.get("coordinates") or d["geometry"]["coordinates"]
for lon, lat in coords:
    print(lon, lat)
PY
read -r START_LON START_LAT < <(head -1 "$POINTS")

echo "Preparing apps..."
adb -s "$G" shell am force-stop com.kaaka.callapp
adb -s "$G" shell "run-as com.kaaka.callapp sh -c 'sed -i \"/name=\\\"events\\\"/d; /last_call/d\" shared_prefs/kaaka_gateway.xml'" || true
adb -s "$G" shell monkey -p com.kaaka.callapp -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
adb -s "$C" emu geo fix "$START_LON" "$START_LAT" >/dev/null
adb -s "$C" shell am force-stop com.kaaka.sensors
adb -s "$C" shell monkey -p com.kaaka.sensors -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
sleep 7
# Beacon every 15 s (the app's "Update every" setting).
SOCK=$(adb -s "$C" shell cat /proc/net/unix | grep -oE "webview_devtools_remote_[0-9]+" | head -1)
adb -s "$C" forward tcp:9223 "localabstract:$SOCK" >/dev/null
"$ROOT/.venv-mac/bin/python" - <<'PY'
import asyncio, json, urllib.request, websockets
async def main():
    page = [p for p in json.load(urllib.request.urlopen("http://127.0.0.1:9223/json")) if p["type"] == "page"][0]
    async with websockets.connect(page["webSocketDebuggerUrl"], max_size=None) as ws:
        expr = "localStorage.setItem('kaaka_beacon_interval','15'); location.reload(); 'ok'"
        await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": expr}}))
        await ws.recv()
asyncio.run(main())
PY
sleep 5

python3 "$ROOT/scripts/emulator-network.py" "$G" "$C" $((DURATION + 10)) &
RELAY=$!
# GPS: hold at the start for 15 s, then move along the route over DRIVE seconds, then hold at the end.
(
  for _ in $(seq 1 8); do adb -s "$C" emu geo fix "$START_LON" "$START_LAT" >/dev/null 2>&1; sleep 2; done
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
  read -r END_LON END_LAT < <(tail -1 "$POINTS")
  for _ in $(seq 1 20); do adb -s "$C" emu geo fix "$END_LON" "$END_LAT" >/dev/null 2>&1; sleep 2; done
) &
GPS=$!
trap 'kill $RELAY $GPS 2>/dev/null || true; rm -f "$POINTS"' EXIT

"$ROOT/scripts/record-demo.sh" "$G" "$C" "$DURATION" &
REC=$!
sleep 8
echo "[8s] caller calls the Kaaka number from the car"
adb -s "$G" emu gsm call "$CALLER_NUMBER" >/dev/null
wait "$REC"
