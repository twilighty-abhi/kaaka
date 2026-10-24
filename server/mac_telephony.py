#!/usr/bin/env python3
"""
macOS Bluetooth Hands-Free telephony client
===========================================
Replaces the Linux PipeWire / oFono D-Bus telephony layer on macOS.

Spawns the Swift `hfp-bridge` helper (mac/hfp-bridge), which connects to the phone
as a Bluetooth hands-free unit via IOBluetooth, and talks to it over pipes:
  - stdout: one JSON event per line ({"event": ..., "ts": ...})
  - stdin : text commands (answer, hangup, status, quit)

Call audio (SCO) is NOT available on macOS; this client only provides call
detection, caller ID, answer and hangup.
"""

import json
import os
import subprocess
import threading
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_BRIDGE_BIN = os.path.join(REPO_ROOT, "mac", "hfp-bridge", ".build", "release", "hfp-bridge")
RESTART_BACKOFF_SEC = 3


class HfpBridgeClient:
    def __init__(self, bt_mac, on_incoming_call=None, on_call_active=None, on_call_ended=None, log=print):
        self.bt_mac = bt_mac
        self.on_incoming_call = on_incoming_call
        self.on_call_active = on_call_active
        self.on_call_ended = on_call_ended
        self.log = log
        self.bin_path = os.environ.get("HFP_BRIDGE_BIN", DEFAULT_BRIDGE_BIN)
        self.proc = None
        self.connected = False
        self.call_active = False
        self.last_indicators = {}
        self.last_state = {}
        self._write_lock = threading.Lock()
        self._stopping = False
        self._thread = None

    # ---- lifecycle
    def start(self):
        if not os.path.isfile(self.bin_path) or not os.access(self.bin_path, os.X_OK):
            self.log(f"⚠️ hfp-bridge binary not found at {self.bin_path}. "
                     f"Build it with: cd mac/hfp-bridge && swift build -c release "
                     f"(or set HFP_BRIDGE_BIN). Call detection is disabled.")
            return False
        self._thread = threading.Thread(target=self._supervise, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._stopping = True
        self._send("quit")
        if self.proc:
            try:
                self.proc.wait(timeout=3)
            except Exception:
                self.proc.kill()

    def _supervise(self):
        while not self._stopping:
            try:
                self.log(f"📶 Starting hfp-bridge for {self.bt_mac} ({self.bin_path})")
                self.proc = subprocess.Popen(
                    [self.bin_path, self.bt_mac],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None,
                    text=True, bufsize=1,
                )
                for line in self.proc.stdout:
                    self._handle_line(line.strip())
                code = self.proc.wait()
            except Exception as e:
                code = f"spawn error: {e}"
            self.connected = False
            self.call_active = False
            if self._stopping:
                break
            self.log(f"⚠️ hfp-bridge exited ({code}); restarting in {RESTART_BACKOFF_SEC}s")
            time.sleep(RESTART_BACKOFF_SEC)

    # ---- commands
    def _send(self, cmd):
        with self._write_lock:
            try:
                if self.proc and self.proc.poll() is None:
                    self.proc.stdin.write(cmd + "\n")
                    self.proc.stdin.flush()
                    return True
            except Exception as e:
                self.log(f"⚠️ hfp-bridge command '{cmd}' failed: {e}")
        return False

    def answer(self):
        return self._send("answer")

    def hangup(self):
        return self._send("hangup")

    def request_status(self):
        return self._send("status")

    # ---- events
    def _handle_line(self, line):
        if not line:
            return
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            self.log(f"[hfp-bridge] {line}")
            return
        kind = ev.get("event")
        if kind == "log":
            self.log(f"[hfp-bridge] {ev.get('message', '')}")
        elif kind == "error":
            self.log(f"⚠️ [hfp-bridge] {ev.get('message', '')}")
        elif kind == "connecting":
            self.log(f"📶 hfp-bridge connecting to {self.bt_mac}…")
        elif kind == "connected":
            self.connected = True
            self.log(f"✅ Bluetooth Hands-Free connected to {self.bt_mac} (AG features {ev.get('ag_features')})")
        elif kind == "disconnected":
            self.connected = False
            self.call_active = False
            self.log(f"🔌 Bluetooth Hands-Free disconnected (status {ev.get('status')})")
        elif kind == "indicator":
            self.last_indicators[str(ev.get("name"))] = ev.get("value")
        elif kind == "incoming_call":
            if self.on_incoming_call:
                self.on_incoming_call(str(ev.get("number") or ""), str(ev.get("name") or ""))
        elif kind == "call_active":
            self.call_active = True
            if self.on_call_active:
                self.on_call_active()
        elif kind == "call_ended":
            self.call_active = False
            if self.on_call_ended:
                self.on_call_ended()
        elif kind == "state":
            self.last_state = ev
            self.connected = bool(ev.get("connected", self.connected))
            self.call_active = bool(ev.get("call_active", self.call_active))
        else:
            self.log(f"[hfp-bridge] unknown event: {ev}")
