#!/usr/bin/env python3
"""
Records the dashboard as smooth video: headless Chrome's screencast (a frame on every repaint) while a
scripted tour clicks through the pages with a visible cursor, as an operator would.

Usage: record-dashboard.py <out.mp4> <seconds> <tour-file> [width=1440] [height=1280]
Tour file: one action per line, "<start-second> <action> <argument>", run in order:
  goto <url>            open a page
  click <css selector>  move the cursor to the element, then click it
  scroll <css selector> move the cursor there and scroll the element into view (smoothly)
  scrollby <pixels>     scroll the page smoothly by this much
  eval <javascript>     run JavaScript in the page
Lines starting with # are ignored. Needs Google Chrome, ffmpeg and the websockets package.
"""
import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

import websockets

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = 9333

# A pointer that glides between targets and pulses on click; drawn above the page, ignores input.
CURSOR_JS = """(() => {
  if (document.getElementById('demo-cursor')) return;
  const c = document.createElement('div');
  c.id = 'demo-cursor';
  c.innerHTML = '<svg width="28" height="28" viewBox="0 0 24 24"><path d="M4 2l16 11-7 1.5L9.5 21z" fill="#fff" stroke="#000" stroke-width="1.5" stroke-linejoin="round"/></svg><span></span>';
  c.style.cssText = 'position:fixed;left:' + (innerWidth * 0.6) + 'px;top:' + (innerHeight * 0.4) + 'px;z-index:2147483647;pointer-events:none;transition:left .9s cubic-bezier(.4,0,.2,1),top .9s cubic-bezier(.4,0,.2,1);filter:drop-shadow(0 2px 3px rgba(0,0,0,.6))';
  const ring = c.querySelector('span');
  ring.style.cssText = 'position:absolute;left:-14px;top:-14px;width:28px;height:28px;border-radius:50%;border:3px solid #ffd84d;opacity:0;transform:scale(.4)';
  document.documentElement.appendChild(c);
})()"""

MOVE_JS = """(async (sel, doClick) => {
  const el = document.querySelector(sel);
  if (!el) return 'missing: ' + sel;
  el.scrollIntoView({behavior: 'smooth', block: 'center'});
  await new Promise(r => setTimeout(r, 600));
  const r = el.getBoundingClientRect(), c = document.getElementById('demo-cursor');
  c.style.left = (r.left + Math.min(r.width / 2, 60)) + 'px';
  c.style.top = (r.top + r.height / 2) + 'px';
  await new Promise(r => setTimeout(r, 1000));
  if (doClick) {
    const ring = c.querySelector('span');
    ring.animate([{opacity: 1, transform: 'scale(.4)'}, {opacity: 0, transform: 'scale(1.8)'}], {duration: 500});
    await new Promise(r => setTimeout(r, 150));
    el.click();
  }
  return 'ok';
})"""


def load_tour(path):
    steps = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        at, action, arg = (line.split(None, 2) + [""])[:3]
        steps.append((float(at), action, arg))
    return steps


class Page:
    def __init__(self, ws):
        self.ws, self.next_id, self.pending, self.frames = ws, 0, {}, []

    async def call(self, method, **params):
        self.next_id += 1
        fut = asyncio.get_running_loop().create_future()
        self.pending[self.next_id] = fut
        await self.ws.send(json.dumps({"id": self.next_id, "method": method, "params": params}))
        return await fut

    async def evaluate(self, expression):
        res = await self.call("Runtime.evaluate", expression=expression, awaitPromise=True, returnByValue=True)
        return res.get("result", {}).get("value")

    async def pump(self, frame_dir, t0):
        async for raw in self.ws:
            msg = json.loads(raw)
            if "id" in msg and msg["id"] in self.pending:
                self.pending.pop(msg["id"]).set_result(msg.get("result", {}))
            elif msg.get("method") == "Page.screencastFrame":
                p = msg["params"]
                name = os.path.join(frame_dir, f"f{len(self.frames):06d}.jpg")
                with open(name, "wb") as f:
                    f.write(base64.b64decode(p["data"]))
                self.frames.append((time.monotonic() - t0, name))
                await self.ws.send(json.dumps({"id": 0, "method": "Page.screencastFrameAck",
                                               "params": {"sessionId": p["sessionId"]}}))


async def record(out, seconds, steps, width, height, work):
    profile = tempfile.mkdtemp(prefix="kaaka-dash-chrome-")
    chrome = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}",
                               f"--window-size={width},{height}", "--hide-scrollbars", "--no-first-run",
                               "--autoplay-policy=no-user-gesture-required", "about:blank"],
                              stdout=subprocess.DEVNULL, stderr=open(os.path.join(work, "chrome.log"), "w"))
    try:
        for _ in range(50):
            try:
                targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
                break
            except OSError:
                await asyncio.sleep(0.2)
        target = [t for t in targets if t["type"] == "page"][0]
        # No keepalive pings: Chrome's DevTools socket does not answer them, which would drop it after ~40 s.
        async with websockets.connect(target["webSocketDebuggerUrl"], max_size=None, ping_interval=None) as ws:
            t0 = time.monotonic()
            page = Page(ws)
            pump = asyncio.create_task(page.pump(work, t0))
            await page.call("Page.enable")
            await page.call("Emulation.setDeviceMetricsOverride", width=width, height=height,
                            deviceScaleFactor=1, mobile=False)
            await page.call("Page.addScriptToEvaluateOnNewDocument",
                            source=f"addEventListener('DOMContentLoaded', () => {CURSOR_JS})")
            await page.call("Page.startScreencast", format="jpeg", quality=85, maxWidth=width, maxHeight=height)
            for at, action, arg in steps:
                delay = at - (time.monotonic() - t0)
                if delay > 0:
                    await asyncio.sleep(delay)
                print(f"[dashboard {at:5.1f}s] {action} {arg}", flush=True)
                if action == "goto":
                    await page.call("Page.navigate", url=arg)
                elif action in ("click", "scroll"):
                    await page.evaluate(CURSOR_JS)
                    result = await page.evaluate(f"{MOVE_JS}({json.dumps(arg)}, {str(action == 'click').lower()})")
                    if result != "ok":
                        print(f"  {result}", flush=True)
                elif action == "scrollby":
                    await page.evaluate(f"scrollBy({{top: {int(arg)}, behavior: 'smooth'}})")
                elif action == "eval":
                    await page.evaluate(arg)
                else:
                    raise SystemExit(f"unknown tour action: {action}")
            remaining = seconds - (time.monotonic() - t0)
            if remaining > 0:
                await asyncio.sleep(remaining)
            await page.call("Page.stopScreencast")
            pump.cancel()
            return page.frames
    except websockets.ConnectionClosed:
        print(f"DevTools connection lost (Chrome exit code: {chrome.poll()}); log: {work}/chrome.log", flush=True)
        raise
    finally:
        chrome.terminate()
        chrome.wait()
        shutil.rmtree(profile, ignore_errors=True)


def main():
    out, seconds, tour = sys.argv[1], float(sys.argv[2]), sys.argv[3]
    width = int(sys.argv[4]) if len(sys.argv) > 4 else 1440
    height = int(sys.argv[5]) if len(sys.argv) > 5 else 1280
    work = tempfile.mkdtemp(prefix="kaaka-dash-frames-")
    frames = asyncio.run(record(out, seconds, load_tour(tour), width, height, work))
    if not frames:
        raise SystemExit("no dashboard frames captured")
    # Frames arrive only on repaint: each one lasts until the next (the last until the end).
    with open(os.path.join(work, "frames.txt"), "w") as f:
        for i, (t, name) in enumerate(frames):
            end = frames[i + 1][0] if i + 1 < len(frames) else seconds
            f.write(f"file '{name}'\nduration {max(end - t, 0.001):.3f}\n")
        f.write(f"file '{frames[-1][1]}'\n")
    start = frames[0][0]
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", os.path.join(work, "frames.txt"),
                    "-vf", f"tpad=start_duration={start:.3f}:start_mode=clone,fps=30,format=yuv420p",
                    "-t", str(seconds), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", out], check=True)
    shutil.rmtree(work, ignore_errors=True)
    print(f"dashboard video: {out} ({len(frames)} frames)")


if __name__ == "__main__":
    main()
