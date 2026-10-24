#!/usr/bin/env python3
"""
Kaaka Real-Time Audio Conversation Bridge
=============================================
Records and processes 10-second audio segments ONLY DURING AN ACTIVE CALL on Redmi Note 10.

Workflow:
1. Dormant / Idle when no call is active.
2. Triggers ONLY when an active call is verified on Redmi Note 10 via D-Bus / PipeWire.
3. Records 10s audio chunk via ffmpeg from the Bluetooth call stream.
4. Dispatches to n8n AI webhook:
   curl -X POST http://192.168.2.69:5678/webhook-test/passive -F "data=@record.mp3"
   (Falls back to /webhook/passive if test mode is inactive).
5. Receives AI reply:
   - If MP3 binary: plays directly.
   - If JSON text: synthesizes neural Malayalam speech (ml-IN-SobhanaNeural) and plays.
6. Plays audio back to BOTH laptop speakers and Bluetooth phone call output.
7. Strictly stops recording immediately when the call ends. No background queue or repeated loops.
"""

import os
import sys
import time
import json
import shutil
import threading
import subprocess
from datetime import datetime
import requests

IS_MAC = sys.platform == "darwin"
MAC_UNSUPPORTED_STATUS = "unsupported on macOS (IOBluetooth SCO audio unsupported)"

try:
    import dbus  # Linux-only (PipeWire / oFono telephony)
except ImportError:
    dbus = None

PRIMARY_WEBHOOK_URL = "http://192.168.2.69:5678/webhook-test/passive"
FALLBACK_WEBHOOK_URL = "http://192.168.2.69:5678/webhook/passive"
TEMP_RECORD_PATH = "/tmp/record.mp3"
TEMP_REPLY_PATH = "/tmp/caller_reply.mp3"

def format_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def is_call_active():
    """Checks strictly if a phone call is currently active on Redmi Note 10 via PipeWire / oFono."""
    if IS_MAC or dbus is None:
        return False
    # Check 1: D-Bus oFono VoiceCallManager on PipeWire Telephony
    try:
        bus = dbus.SessionBus()
        telephony = bus.get_object("org.pipewire.Telephony", "/org/pipewire/Telephony/ag1")
        vcm = dbus.Interface(telephony, "org.ofono.VoiceCallManager")
        calls = vcm.GetCalls()
        if len(calls) > 0:
            return True
    except Exception:
        pass

    # Check 2: Active bluez call audio in pw-link
    try:
        links = subprocess.getoutput('pw-link -io')
        if any('bluez_output' in l or 'bluez_input' in l for l in links.splitlines()):
            return True
    except Exception:
        pass

    return False

def ensure_audio_sinks():
    """Ensures call_playback and call_record null-sinks exist in PulseAudio/PipeWire and are linked to laptop audio."""
    if IS_MAC:
        return
    try:
        sinks = subprocess.getoutput('pactl list sinks short')
        for name, desc in [('call_playback', 'KaakaCallPlayback'), ('call_record', 'KaakaCallRecord')]:
            if name not in sinks:
                subprocess.run(['pactl', 'load-module', 'module-null-sink', f'sink_name={name}', f'sink_properties=device.description={desc}'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Link call_playback monitor to laptop speakers so operator hears all played responses
        for ch in ['FL', 'FR']:
            subprocess.run(['pw-link', f'call_playback:monitor_{ch}', f'alsa_output.pci-0000_00_1f.3.analog-stereo:playback_{ch}'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def link_call_audio(max_wait_sec=2.5):
    """
    Dynamically routes bidirectional call audio streams:
    1. AI response + operator mic -> Cellular call (caller hears both AI reply and operator speaking).
    2. Incoming caller voice -> Laptop speakers (operator hears caller) + call_record sink (for pure 10s chunk recording).
    """
    if IS_MAC:
        return False
    ensure_audio_sinks()
    start_time = time.time()
    linked = False
    
    while time.time() - start_time < max_wait_sec:
        res = subprocess.getoutput('pw-link -io')
        bluez_in = [l for l in res.splitlines() if 'bluez_output' in l and ':input_' in l]
        bluez_out = [l for l in res.splitlines() if 'bluez_input' in l and ':output_' in l]
        
        if bluez_in or bluez_out:
            # 1. Route AI playback and laptop mic to the caller (Uplink)
            for p in bluez_in:
                ch = "FL" if "FL" in p else "FR"
                subprocess.run(['pw-link', f'call_playback:monitor_{ch}', p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(['pw-link', f'alsa_input.pci-0000_00_1f.3.analog-stereo:capture_{ch}', p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # 2. Route caller audio to record sink and laptop speakers (Downlink)
            for p in bluez_out:
                ch = "FL" if "FL" in p else "FR"
                subprocess.run(['pw-link', p, f'call_record:playback_{ch}'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(['pw-link', p, f'alsa_output.pci-0000_00_1f.3.analog-stereo:playback_{ch}'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            linked = True
            break
        time.sleep(0.2)

    return linked

def get_recording_source():
    """Finds active call_record.monitor sink or fallback."""
    try:
        sources = subprocess.getoutput('pactl list sources short')
        if 'call_record.monitor' in sources:
            return 'call_record.monitor'
        for line in sources.strip().splitlines():
            parts = line.split()
            if len(parts) >= 2 and 'bluez_input' in parts[1]:
                return parts[1]
    except Exception:
        pass
    return "default"

def play_audio(audio_path):
    """
    Plays audio through call_playback sink.
    Since call_playback is linked to both:
    1. alsa_output (laptop speakers)
    2. bluez_output (Bluetooth SCO cellular uplink to caller)
    BOTH the operator at the laptop and the caller on the phone hear the audio simultaneously!
    """
    if not os.path.exists(audio_path) or os.path.getsize(audio_path) < 100:
        return

    ensure_audio_sinks()
    link_call_audio(max_wait_sec=1.0)

    env = os.environ.copy()
    env["PULSE_SINK"] = "call_playback"
    try:
        p = subprocess.Popen(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "error", audio_path],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        p.wait(timeout=25)
    except Exception as e:
        print(f"[{format_timestamp()}] ⚠️ Audio playback error: {e}")

class AudioConversationBridge:
    def __init__(self, primary_url=PRIMARY_WEBHOOK_URL, fallback_url=FALLBACK_WEBHOOK_URL, on_event=None):
        self.primary_url = primary_url
        self.fallback_url = fallback_url
        self.on_event = on_event
        self.is_running = False
        self.call_in_progress = False
        self.thread = None
        self.record_proc = None
        self.chunk_count = 0
        self.last_status = MAC_UNSUPPORTED_STATUS if IS_MAC else "idle (no active call)"
        self.last_transcript = ""
        self.last_ai_reply = ""
        self.last_chunk_time = None

    def log(self, msg):
        print(f"[{format_timestamp()}] {msg}", flush=True)
        if self.on_event:
            try:
                self.on_event({
                    "type": "AUDIO_BRIDGE_LOG",
                    "status": self.last_status,
                    "chunk": self.chunk_count,
                    "call_active": is_call_active(),
                    "last_reply": self.last_ai_reply,
                    "timestamp": format_timestamp()
                })
            except Exception:
                pass

    def notify_call_started(self):
        """Called by server when a call on Redmi Note 10 starts."""
        self.call_in_progress = True
        self.log("📞 Call started on Redmi Note 10 -> Establishing bidirectional audio bridge & starting 10s AI recording loop.")
        link_call_audio(max_wait_sec=2.5)
        self.start()

    def notify_call_ended(self):
        """Called by server when a call on Redmi Note 10 ends."""
        self.call_in_progress = False
        self.log("📴 Call ended on Redmi Note 10 -> Stopping audio recording immediately.")
        self.stop()

    def record_chunk(self, duration=10, output_path=TEMP_RECORD_PATH):
        link_call_audio(max_wait_sec=0.5)
        source = get_recording_source()
        cmd = [
            "ffmpeg", "-y",
            "-f", "pulse",
            "-i", source,
            "-t", str(duration),
            "-acodec", "libmp3lame",
            "-ab", "128k",
            "-ar", "44100",
            "-ac", "1",
            output_path
        ]
        self.last_status = f"recording ({duration}s from {source})"
        self.record_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            self.record_proc.wait(timeout=duration + 3)
        except Exception:
            if self.record_proc:
                self.record_proc.kill()
        finally:
            self.record_proc = None

        return os.path.exists(output_path) and os.path.getsize(output_path) > 1000

    def send_to_webhook(self, mp3_path=TEMP_RECORD_PATH):
        """Sends MP3 to webhook-test/passive or fallback /webhook/passive."""
        for url in [self.primary_url, self.fallback_url]:
            try:
                self.last_status = f"sending to {url}"
                with open(mp3_path, "rb") as f:
                    files = {"data": ("record.mp3", f, "audio/mpeg")}
                    resp = requests.post(url, files=files, timeout=60)

                if resp.status_code == 200:
                    return resp
                elif resp.status_code == 404 and url == self.primary_url:
                    continue
                else:
                    self.log(f"⚠️ Webhook {url} returned HTTP {resp.status_code}")
            except Exception as e:
                self.log(f"⚠️ Webhook error on {url}: {e}")
        return None

    def process_response(self, response):
        """Extracts audio or synthesizes text reply, then plays back."""
        content_type = response.headers.get("Content-Type", "")
        raw_bytes = response.content

        # Check if response is raw binary audio
        is_audio = (
            "audio" in content_type or
            raw_bytes.startswith(b"ID3") or
            raw_bytes.startswith(b"\xff\xfb") or
            raw_bytes.startswith(b"RIFF")
        )

        if is_audio:
            with open(TEMP_REPLY_PATH, "wb") as f:
                f.write(raw_bytes)
            self.last_ai_reply = f"[Binary Audio: {len(raw_bytes)} bytes]"
            self.log(f"🔊 Received MP3 audio response ({len(raw_bytes)} bytes). Playing back to caller...")
            play_audio(TEMP_REPLY_PATH)
            return

        # Check if response is JSON
        try:
            data = response.json()
            # If JSON contains audio base64
            for audio_key in ["audio", "data", "mp3", "audio_base64"]:
                if audio_key in data and isinstance(data[audio_key], str) and len(data[audio_key]) > 500:
                    import base64
                    try:
                        audio_data = base64.b64decode(data[audio_key])
                        with open(TEMP_REPLY_PATH, "wb") as f:
                            f.write(audio_data)
                        self.last_ai_reply = f"[Decoded base64 audio: {len(audio_data)} bytes]"
                        self.log(f"🔊 Playing back base64 audio response...")
                        play_audio(TEMP_REPLY_PATH)
                        return
                    except Exception:
                        pass

            # If JSON contains text reply (e.g. {"content": "..."})
            text_reply = data.get("content") or data.get("text") or data.get("message") or data.get("output") or ""
            if text_reply:
                self.last_ai_reply = str(text_reply).strip()
                self.log(f"🤖 AI Response: \033[1;36m{self.last_ai_reply}\033[0m")
                # Synthesize neural Malayalam speech using edge-tts
                tts_cmd = [
                    "edge-tts",
                    "--voice", "ml-IN-SobhanaNeural",
                    "--text", self.last_ai_reply,
                    "--write-media", TEMP_REPLY_PATH
                ]
                res = subprocess.run(tts_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if res.returncode == 0 and os.path.exists(TEMP_REPLY_PATH):
                    self.log(f"🔊 Synthesized Neural Malayalam Voice. Playing back to caller...")
                    play_audio(TEMP_REPLY_PATH)
        except Exception as e:
            self.log(f"⚠️ Response parsing note: {e}")

    def loop(self):
        self.log("🎙️ Call audio monitor active: strictly checking for active call on Redmi Note 10...")
        while self.is_running:
            # Strictly verify that an active call exists on Redmi Note 10
            active = is_call_active()
            if not active:
                self.is_running = False
                self.call_in_progress = False
                self.last_status = "idle (no active call on Redmi Note 10)"
                self.log("📴 No active call on Redmi Note 10. Audio loop stopped immediately.")
                break

            self.chunk_count += 1
            self.last_chunk_time = format_timestamp()
            self.log(f"\n📞 [Active Call on Redmi Note 10 - Chunk #{self.chunk_count}] Recording 10s audio...")
            
            ok = self.record_chunk(duration=10)
            if not self.is_running or not is_call_active():
                self.is_running = False
                self.call_in_progress = False
                self.log("📴 Call ended during recording. Discarding chunk and stopping.")
                break

            if not ok:
                time.sleep(0.5)
                continue

            self.log("🚀 Dispatched 10s MP3 to AI Webhook (http://192.168.2.69:5678/webhook-test/passive)...")
            resp = self.send_to_webhook()
            if not self.is_running or not is_call_active():
                self.is_running = False
                self.call_in_progress = False
                self.log("📴 Call ended. Stopping loop.")
                break

            if resp:
                self.process_response(resp)
            else:
                self.log("⚠️ No response from n8n webhook.")

            # Pause briefly and re-verify before next chunk
            if not is_call_active():
                self.is_running = False
                self.call_in_progress = False
                self.log("📴 Call ended on Redmi Note 10. Stopping audio bridge.")
                break

            time.sleep(0.5)

    def start(self):
        if IS_MAC:
            self.is_running = False
            self.last_status = MAC_UNSUPPORTED_STATUS
            self.log(f"ℹ️ Audio conversation bridge {MAC_UNSUPPORTED_STATUS}. Call audio stays on the phone.")
            return
        if self.is_running:
            return
        if not is_call_active():
            self.log("ℹ️ No active call detected on Redmi Note 10. Audio bridge staying in standby.")
            self.last_status = "idle (no active call on Redmi Note 10)"
            return
        self.is_running = True
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False
        self.call_in_progress = False
        self.last_status = MAC_UNSUPPORTED_STATUS if IS_MAC else "idle (no active call on Redmi Note 10)"
        if self.record_proc:
            try:
                self.record_proc.kill()
            except Exception:
                pass
            self.record_proc = None
        self.log("🛑 Audio conversation loop stopped (standby).")

if __name__ == "__main__":
    bridge = AudioConversationBridge()
    print("=" * 65)
    print(" Kaaka Call-Activated Audio AI Conversation Bridge")
    print("=================================================================")
    print(" Active: STRICTLY ONLY DURING ACTIVE PHONE CALLS on Redmi Note 10")
    print(" Target: http://192.168.2.69:5678/webhook-test/passive")
    print(" Press Ctrl+C to stop.")
    print("=" * 65)
    bridge.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        bridge.stop()
        print("\nExiting.")
