#!/usr/bin/env bash
# Records a Kaaka demo: both phones' screens (adb screenrecord) and the Mac dashboard (headless Chrome
# screenshots), then stitches them side by side into one MP4 with labels.
#
# Usage: scripts/record-demo.sh <gateway-adb-serial> <caller-adb-serial> [seconds=170] [dashboard-url]
#   adb devices -l   # lists serials
# Output: demo/kaaka-demo-<timestamp>.mp4 (demo/ is ignored by Git)
# Needs: adb, ffmpeg, Google Chrome. Phone screen recording stops at 180 s (Android limit).
set -euo pipefail

GATEWAY="${1:?gateway phone adb serial}"
CALLER="${2:?caller phone adb serial}"
SECONDS_TOTAL="${3:-170}"
DASHBOARD="${4:-http://127.0.0.1:8080}"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FRAME_EVERY=2

if [ "$SECONDS_TOTAL" -gt 180 ]; then echo "max 180 s (Android screenrecord limit)"; exit 1; fi
for tool in adb ffmpeg; do command -v "$tool" >/dev/null || { echo "missing: $tool"; exit 1; }; done
[ -x "$CHROME" ] || { echo "missing: Google Chrome"; exit 1; }

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
WORK="$ROOT/demo/work-$STAMP"
OUT="$ROOT/demo/kaaka-demo-$STAMP.mp4"
mkdir -p "$WORK/dash"

echo "Recording ${SECONDS_TOTAL}s: gateway=$GATEWAY caller=$CALLER dashboard=$DASHBOARD"
# Keep both screens on while recording (a sleeping screen records no frames); restored on exit.
for d in "$GATEWAY" "$CALLER"; do adb -s "$d" shell svc power stayon usb >/dev/null 2>&1 || true; adb -s "$d" shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1 || true; done
trap 'for d in "$GATEWAY" "$CALLER"; do adb -s "$d" shell svc power stayon false >/dev/null 2>&1 || true; done' EXIT
adb -s "$GATEWAY" shell screenrecord --time-limit "$SECONDS_TOTAL" --bit-rate 6000000 /sdcard/kaaka_gateway.mp4 &
P1=$!
adb -s "$CALLER" shell screenrecord --time-limit "$SECONDS_TOTAL" --bit-rate 6000000 /sdcard/kaaka_caller.mp4 &
P2=$!

# Dashboard: one headless screenshot every FRAME_EVERY seconds (page reloads from /api each time).
END=$(( $(date +%s) + SECONDS_TOTAL ))
i=0
while [ "$(date +%s)" -lt "$END" ]; do
  t0=$(date +%s)
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --window-size=1280,1600 \
    --virtual-time-budget=4000 --screenshot="$WORK/dash/f$(printf %04d $i).png" "$DASHBOARD" >/dev/null 2>&1 || true
  i=$((i + 1))
  sleep $(( FRAME_EVERY - ( $(date +%s) - t0 ) > 0 ? FRAME_EVERY - ( $(date +%s) - t0 ) : 0 ))
done
echo "Recording done ($i dashboard frames); waiting for phones..."
wait "$P1" "$P2" || true
sleep 2
adb -s "$GATEWAY" pull /sdcard/kaaka_gateway.mp4 "$WORK/gateway.mp4" >/dev/null
adb -s "$CALLER" pull /sdcard/kaaka_caller.mp4 "$WORK/caller.mp4" >/dev/null
adb -s "$GATEWAY" shell rm -f /sdcard/kaaka_gateway.mp4
adb -s "$CALLER" shell rm -f /sdcard/kaaka_caller.mp4

# Dashboard frames → video in real time.
ffmpeg -loglevel error -y -framerate "1/$FRAME_EVERY" -i "$WORK/dash/f%04d.png" -vf "fps=30,format=yuv420p" "$WORK/dashboard.mp4"

# Normalize every clip to exactly SECONDS_TOTAL at 30 fps. A clip with almost no frames (e.g. the
# screen was off) becomes a still of its last frame; shorter clips hold their last frame.
normalize() { # $1 in, $2 out
  local frames
  frames=$(ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of csv=p=0 "$1" || echo 0)
  if [ "${frames:-0}" -lt 2 ]; then
    ffmpeg -loglevel error -y -i "$1" -frames:v 1 "$1.still.png"
    ffmpeg -loglevel error -y -loop 1 -t "$SECONDS_TOTAL" -i "$1.still.png" -vf "fps=30,format=yuv420p" "$2"
  else
    ffmpeg -loglevel error -y -i "$1" -vf "tpad=stop_mode=clone:stop_duration=$SECONDS_TOTAL,fps=30,format=yuv420p" -t "$SECONDS_TOTAL" "$2"
  fi
}
normalize "$WORK/gateway.mp4" "$WORK/gateway_n.mp4"
normalize "$WORK/caller.mp4" "$WORK/caller_n.mp4"
normalize "$WORK/dashboard.mp4" "$WORK/dashboard_n.mp4"

# Labels: rendered as images with headless Chrome (this ffmpeg may lack the drawtext filter).
H=1280
label_png() { # $1 text, $2 width, $3 output
  local html="data:text/html,<body style='margin:0;background:%23000;color:%23fff;font:bold 34px -apple-system,Helvetica;display:flex;align-items:center;justify-content:center;height:80px'>$1</body>"
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --window-size="$2,80" --screenshot="$3" "${html// /%20}" >/dev/null 2>&1
}
width_at_h() { ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0 "$1" | awk -F, -v h=$H '{w=int($1*h/$2); print w-(w%2)}'; }
WG=$(width_at_h "$WORK/gateway_n.mp4"); WC=$(width_at_h "$WORK/caller_n.mp4"); WD=$(width_at_h "$WORK/dashboard_n.mp4")
label_png "Kaaka number (gateway phone)" "$WG" "$WORK/l1.png"
label_png "Caller (Kaaka Sensors)" "$WC" "$WORK/l2.png"
label_png "Control room (Mac dashboard)" "$WD" "$WORK/l3.png"

ffmpeg -loglevel error -y -i "$WORK/gateway_n.mp4" -i "$WORK/caller_n.mp4" -i "$WORK/dashboard_n.mp4" \
  -loop 1 -t "$SECONDS_TOTAL" -i "$WORK/l1.png" -loop 1 -t "$SECONDS_TOTAL" -i "$WORK/l2.png" -loop 1 -t "$SECONDS_TOTAL" -i "$WORK/l3.png" -filter_complex "\
[0:v]scale=$WG:$H,setsar=1[g];[3:v]scale=$WG:80,setsar=1[lg];[lg][g]vstack[a];\
[1:v]scale=$WC:$H,setsar=1[c];[4:v]scale=$WC:80,setsar=1[lc];[lc][c]vstack[b];\
[2:v]scale=$WD:$H,setsar=1[d];[5:v]scale=$WD:80,setsar=1[ld];[ld][d]vstack[e];\
[a][b][e]hstack=inputs=3,format=yuv420p[v]" \
  -map "[v]" -t "$SECONDS_TOTAL" -c:v libx264 -preset veryfast -crf 23 -movflags +faststart "$OUT"

echo "Demo video: $OUT"
