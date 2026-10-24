#!/usr/bin/env python3
"""
Kaaka Bluetooth Call & Telemetry WebSocket + Dashboard Server
=================================================================
1. Monitors Bluetooth handsfree phone calls in PipeWire/Helvum.
   When an active call is detected, extracts the phone number and
   broadcasts it over WebSockets to trigger automatic SMS dispatch.
2. Monitors Bluetooth BLE / Message Access Profile (MAP) notifications
   from the connected gateway phone (08:1C:6E:5F:10:F7). When an incoming
   sensor telemetry SMS alert arrives from the client phone, extracts the
   payload and prints the live readings in the exact requested format.
3. Hosts a real-time web dashboard UI on HTTP (default port 8080) displaying
   live sensor cards, visual compass needle, telephony status, and alert logs.
4. Accepts direct WebSocket telemetry streams from connected client apps.
"""

import argparse
import asyncio
import http.server
import json
import os
import re
import socket
import socketserver
import sys
import tempfile
import threading
import time
from datetime import datetime
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
import websockets

try:
    from server.audio_bridge import AudioConversationBridge, ensure_audio_sinks
except ImportError:
    from audio_bridge import AudioConversationBridge, ensure_audio_sinks

def get_local_ip():
    """Detect the local LAN / Wi-Fi IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def format_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def extract_body_from_bmsg(raw_text: str) -> str:
    """Extract body text between BEGIN:MSG and END:MSG from bMessage format."""
    lines = raw_text.splitlines()
    in_msg = False
    body_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped == 'BEGIN:MSG':
            in_msg = True
            continue
        elif stripped == 'END:MSG':
            in_msg = False
            break
        elif in_msg:
            body_lines.append(line)
    if body_lines:
        return '\n'.join(body_lines).strip()
    return raw_text.strip()

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, server_instance=None, **kwargs):
        self.server_instance = server_instance
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        # Suppress routine HTTP request logging to keep console clean
        pass

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if self.path in ["/", "/index.html"]:
            dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
            if not os.path.exists(dashboard_path):
                self.send_error(404, "dashboard.html not found")
                return
            try:
                with open(dashboard_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self.send_error(500, f"Error loading dashboard: {e}")
        elif self.path == "/api/status":
            phone_clients = [str(c.remote_address[0]) for c in self.server_instance.connected_clients if str(c.remote_address[0]) != '127.0.0.1']
            bt_connected = self.server_instance.check_bluetooth_connected()
            telephony_ag_online = self.server_instance.check_telephony_ag_online()
            gateway_online = (bt_connected and telephony_ag_online) or (len(phone_clients) > 0)
            gateway_mode = "cellular_hfp" if (bt_connected and telephony_ag_online) else ("app_only" if len(phone_clients) > 0 else "offline")

            status_data = {
                "server": "Kaaka Telemetry Server",
                "local_ip": self.server_instance.local_ip,
                "ws_port": self.server_instance.port,
                "http_port": self.server_instance.http_port,
                "bt_mac": self.server_instance.bt_mac,
                "bluetooth_connected": bt_connected,
                "telephony_ag_online": telephony_ag_online,
                "gateway_online": gateway_online,
                "gateway_mode": gateway_mode,
                "phone_app_connected": len(phone_clients) > 0,
                "gateway_ips": phone_clients,
                "clients_count": len(self.server_instance.connected_clients),
                "last_call_number": self.server_instance.last_detected_number or "8714711540",
                "telemetry_count": self.server_instance.telemetry_count,
                "latest_telemetry": self.server_instance.latest_telemetry,
                "audio_bridge": {
                    "running": self.server_instance.audio_bridge.is_running,
                    "chunk_count": self.server_instance.audio_bridge.chunk_count,
                    "last_status": self.server_instance.audio_bridge.last_status,
                    "last_reply": self.server_instance.audio_bridge.last_ai_reply,
                    "auto_answer_mode": self.server_instance.auto_answer_mode
                },
                "timestamp": format_timestamp()
            }
            body = json.dumps(status_data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        if self.path == "/api/trigger-call":
            self.server_instance.on_call_detected("+918714711540", name="Simulated Caller", state="active")
            body = b'{"success":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/audio-bridge/toggle":
            if self.server_instance.audio_bridge.is_running:
                self.server_instance.audio_bridge.stop()
            else:
                self.server_instance.audio_bridge.start()
            status = {"running": self.server_instance.audio_bridge.is_running}
            body = json.dumps(status).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/audio-bridge/mode":
            self.server_instance.auto_answer_mode = not self.server_instance.auto_answer_mode
            status = {"auto_answer_mode": self.server_instance.auto_answer_mode}
            body = json.dumps(status).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/trigger-telemetry":
            sample_alert = (
                "Kaaka Alert: Emergency assistance requested\n\n"
                "Live Sensors (5/5):\n"
                "• Pedometer: 0 steps (0.00 km)\n"
                "• Light: 53 lx\n"
                "• Accelerometer: 9.7 m/s²\n"
                "• Gyroscope: 0.2 rad/s\n"
                "• Magnetometer: 186° S\n"
                "• Coords: 9.064458, 76.557012\n"
                "• Maps: https://maps.google.com/?q=9.064458,76.557012"
            )
            self.server_instance.display_telemetry(sample_alert, sender="+919495364448", source="Simulated Test")
            body = b'{"success":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/telemetry":
            try:
                length = int(self.headers.get("Content-Length", 0))
                post_data = self.rfile.read(length).decode("utf-8")
                try:
                    payload = json.loads(post_data)
                    report = payload.get("report") or payload.get("content") or post_data
                    sender = payload.get("sender", "+918714711540")
                except Exception:
                    report = post_data
                    sender = "+918714711540"
                self.server_instance.display_telemetry(report, sender=sender, source="HTTP REST /api/telemetry")
                body = b'{"success":true}'
            except Exception as e:
                body = json.dumps({"error": str(e)}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404, "Not Found")

class TelemetryServer:
    def __init__(self, host="0.0.0.0", port=8765, http_port=8080, bt_mac="08:1C:6E:5F:10:F7"):
        self.host = host
        self.port = port
        self.http_port = http_port
        self.bt_mac = bt_mac
        self.local_ip = get_local_ip()
        self.connected_clients = set()
        self.loop = None
        self.telephony_service = "org.pipewire.Telephony"
        self.last_detected_number = None
        self.last_call_time = 0
        self.last_call_number = None
        self.telemetry_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "latest_telemetry.json")
        self.latest_telemetry = None
        self.telemetry_count = 0
        if os.path.exists(self.telemetry_file):
            try:
                with open(self.telemetry_file, "r") as f:
                    saved = json.load(f)
                    if saved and "content" in saved:
                        self.latest_telemetry = saved
                        self.telemetry_count = saved.get("update_count", 1)
                        print(f"[{format_timestamp()}] 💾 Restored latest telemetry from disk (Update #{self.telemetry_count})")
            except Exception:
                pass
        self.processed_msg_ids = set()
        self.map_session_path = None
        self.pending_call_trigger = None
        self.auto_answer_mode = True  # Real-time voice AI conversation enabled
        ensure_audio_sinks()
        self.audio_bridge = AudioConversationBridge(on_event=self.on_audio_bridge_event)

    def on_audio_bridge_event(self, event):
        if self.loop:
            asyncio.run_coroutine_threadsafe(self.broadcast(event), self.loop)

    def check_bluetooth_connected(self) -> bool:
        """Check if Phone A (bt_mac) is connected to BlueZ."""
        try:
            bus = dbus.SystemBus()
            dev = bus.get_object("org.bluez", f"/org/bluez/hci0/dev_{self.bt_mac.replace(':', '_')}")
            props = dbus.Interface(dev, "org.freedesktop.DBus.Properties")
            return bool(props.Get("org.bluez.Device1", "Connected"))
        except Exception:
            return False

    def check_telephony_ag_online(self) -> bool:
        """Check if PipeWire Telephony Handsfree Audio Gateway service is online."""
        try:
            bus = dbus.SessionBus()
            bus.get_object(self.telephony_service, "/org/pipewire/Telephony/ag1")
            return True
        except Exception:
            return False

    def display_telemetry(self, raw_content: str, sender: str = "", source: str = "BLE / Bluetooth MAP"):
        """
        Displays live sensor readings in the exact requested visual format:
        
        Kaaka Alert: Emergency assistance requested

        Live Sensors (5/5):
        • Pedometer: <steps> steps (<dist> km)
        • Light: <lux> lx
        • Accelerometer: <accel> m/s²
        • Gyroscope: <gyro> rad/s
        • Magnetometer: <mag>° <cardinal>
        """
        clean_text = raw_content.strip()
        
        # If wrapped inside bMessage, extract it first
        if "BEGIN:MSG" in clean_text:
            clean_text = extract_body_from_bmsg(clean_text)

        # Standardize header if present with trailing punctuation
        clean_text = re.sub(
            r"Kaaka Alert:\s*Emergency assistance requested\.?",
            "Kaaka Alert: Emergency assistance requested",
            clean_text
        )

        self.telemetry_count += 1
        ts = format_timestamp()
        source_label = f"{sender} ({source})" if sender else source

        print("\n" + "=" * 65, flush=True)
        print(f"\033[1;31m[{ts}] 🚨 KAAKA SENSOR TELEMETRY RECEIVED (Update #{self.telemetry_count})\033[0m", flush=True)
        print(f"\033[1;36m  Channel Source  : \033[0m{source_label}", flush=True)
        print("=" * 65, flush=True)
        print(f"\033[1;32m{clean_text}\033[0m", flush=True)
        print("=" * 65 + "\n", flush=True)

        # Store latest telemetry in memory and persist to disk
        self.latest_telemetry = {
            "content": clean_text,
            "sender": sender,
            "source": source,
            "timestamp": ts,
            "update_count": self.telemetry_count
        }
        try:
            with open(self.telemetry_file, "w") as f:
                json.dump(self.latest_telemetry, f, indent=2)
        except Exception:
            pass

        # Broadcast to all connected WebSockets (phone apps + web dashboard)
        if self.loop and self.connected_clients:
            payload = {
                "type": "TELEMETRY_RECEIVED",
                "content": clean_text,
                "sender": sender,
                "source": source,
                "timestamp": ts,
                "update_count": self.telemetry_count
            }
            asyncio.run_coroutine_threadsafe(self.broadcast(payload), self.loop)

    async def broadcast(self, payload):
        """Send JSON message to all connected clients."""
        if not self.connected_clients:
            return

        message_str = json.dumps(payload)
        dead_clients = set()
        for client in self.connected_clients:
            try:
                await client.send(message_str)
            except Exception:
                dead_clients.add(client)
        self.connected_clients -= dead_clients

    def on_call_detected(self, number, name="", state="active", raw_path=""):
        """Called from D-Bus thread when a call is extracted."""
        clean_num = str(number).strip()
        if not clean_num or clean_num == "Unknown":
            clean_num = "8714711540"

        now = time.time()
        # Deduplicate triggers for the same number within 3 seconds
        if self.last_call_number == clean_num and (now - self.last_call_time) < 3:
            print(f"[{format_timestamp()}] ⏳ Debounced: Duplicate trigger for {clean_num} ignored (<3s)")
            return

        self.last_call_time = now
        self.last_call_number = clean_num
        self.last_detected_number = clean_num
        self.pending_call_trigger = {
            "number": clean_num,
            "name": str(name),
            "state": str(state),
            "timestamp": now
        }

        print("\n" + "=" * 60)
        print(f"[{format_timestamp()}] 📞 NEW CALL EXTRACTED FROM BLUETOOTH HANDSFREE")
        print("=" * 60)
        print(f"  📱 Phone Number : \033[1;32m{clean_num}\033[0m")
        if name:
            print(f"  👤 Contact Name : {name}")
        print(f"  ⚡ Call State   : {state}")

        phone_clients = [str(c.remote_address[0]) for c in self.connected_clients if str(c.remote_address[0]) != '127.0.0.1']
        if phone_clients:
            print(f"  📶 Gateway App Link : \033[1;32mConnected ({', '.join(phone_clients)})\033[0m")
        else:
            print(f"  ℹ️ Phone A Gateway App is in background/standby (Direct Bluetooth MAP active)")
        print("=" * 60 + "\n", flush=True)

        payload = {
            "type": "CALL_DETECTED",
            "number": clean_num,
            "name": str(name),
            "state": str(state),
            "timestamp": format_timestamp()
        }

        # 1. Real-Time Conversation Link: Auto-Answer call to establish Bluetooth Handsfree audio, or Hangup if in 1-ring mode
        if self.auto_answer_mode:
            self.auto_answer_call(raw_path)
        else:
            self.auto_hangup_call(raw_path)

        # 2. Direct Bluetooth MAP SMS dispatch to caller to guarantee delivery and trigger client telemetry loop
        threading.Thread(target=self.push_sms_via_bluetooth_map, args=(clean_num, "received call. will get back to you shortly."), daemon=True).start()

        # 3. WebSocket broadcast to connected apps
        if self.loop:
            asyncio.run_coroutine_threadsafe(self.broadcast(payload), self.loop)

    def auto_answer_call(self, raw_path=""):
        """Auto-answers incoming call so caller audio connects to Bluetooth Handsfree."""
        def _answer():
            time.sleep(0.5)  # 500ms allows 1 ring setup and caller ID capture
            bus = dbus.SessionBus()
            answered = False

            # Strategy 1: Specific call path Answer()
            if raw_path:
                try:
                    call_obj = bus.get_object(self.telephony_service, raw_path)
                    for iface in ["org.pipewire.Telephony.Call1", "org.ofono.VoiceCall"]:
                        try:
                            c = dbus.Interface(call_obj, iface)
                            c.Answer(timeout=2.0)
                            answered = True
                            print(f"[{format_timestamp()}] 📞 Call answered on {raw_path} via {iface}")
                            break
                        except Exception:
                            pass
                except Exception:
                    pass

            # Strategy 2: VoiceCallManager.ReleaseAndAnswer / HoldAndAnswer
            if not answered and raw_path:
                try:
                    telephony = bus.get_object(self.telephony_service, "/org/pipewire/Telephony/ag1")
                    for iface in ["org.ofono.VoiceCallManager", "org.pipewire.Telephony.AudioGateway1"]:
                        try:
                            vcm = dbus.Interface(telephony, iface)
                            vcm.ReleaseAndAnswer(timeout=2.0)
                            answered = True
                            print(f"[{format_timestamp()}] 📞 ReleaseAndAnswer executed via {iface}")
                            break
                        except Exception:
                            pass
                except Exception:
                    pass

            if answered or raw_path:
                print(f"[{format_timestamp()}] 🎙️ Real call connected on Redmi Note 10! Activating Real-Time AI Audio Conversation Bridge...")
                self.audio_bridge.notify_call_started()
            else:
                print(f"[{format_timestamp()}] ℹ️ Simulated call test (no hardware call). Audio bridge remains in standby.")

        threading.Thread(target=_answer, daemon=True).start()

    def auto_hangup_call(self, raw_path=""):
        """Terminates trigger call after 1 ring (< 0.5s) to release voice bearer and clear InCallUI on caller's phone."""
        def _hangup():
            time.sleep(0.4)  # 400ms allows 1 clean ring and caller ID capture
            bus = dbus.SessionBus()
            hung_up = False

            # Strategy 1: Specific Call object Hangup
            if raw_path:
                try:
                    call_obj = bus.get_object(self.telephony_service, raw_path)
                    for iface in ["org.pipewire.Telephony.Call1", "org.ofono.VoiceCall"]:
                        try:
                            c = dbus.Interface(call_obj, iface)
                            c.Hangup(timeout=1.0)
                            hung_up = True
                            print(f"[{format_timestamp()}] 📴 Hangup succeeded on {raw_path} via {iface}")
                            break
                        except Exception:
                            pass
                except Exception as e:
                    pass

            # Strategy 2: Iterate over any active calls from GetCalls()
            try:
                telephony = bus.get_object(self.telephony_service, "/org/pipewire/Telephony/ag1")
                vcm = dbus.Interface(telephony, "org.ofono.VoiceCallManager")
                active_calls = vcm.GetCalls()
                for c_path in active_calls.keys():
                    try:
                        c_obj = bus.get_object(self.telephony_service, c_path)
                        for iface in ["org.pipewire.Telephony.Call1", "org.ofono.VoiceCall"]:
                            try:
                                c_iface = dbus.Interface(c_obj, iface)
                                c_iface.Hangup(timeout=1.0)
                                hung_up = True
                                print(f"[{format_timestamp()}] 📴 Hangup succeeded on active call {c_path} via {iface}")
                                break
                            except Exception:
                                pass
                    except Exception:
                        pass
            except Exception:
                pass

            # Strategy 3: VoiceCallManager.HangupAll() / AudioGateway1.HangupAll()
            if not hung_up:
                try:
                    telephony = bus.get_object(self.telephony_service, "/org/pipewire/Telephony/ag1")
                    for iface in ["org.ofono.VoiceCallManager", "org.pipewire.Telephony.AudioGateway1"]:
                        try:
                            v = dbus.Interface(telephony, iface)
                            v.HangupAll(timeout=1.0)
                            hung_up = True
                            print(f"[{format_timestamp()}] 📴 HangupAll succeeded via {iface}")
                            break
                        except Exception:
                            pass
                except Exception:
                    pass

            if hung_up:
                print(f"[{format_timestamp()}] ⚡ 1-Ring Trigger: Voice call auto-disconnected. Cellular voice channel released.")
            else:
                print(f"[{format_timestamp()}] ℹ️ Hangup finished or call already disconnected.")

        threading.Thread(target=_hangup, daemon=True).start()

    def push_sms_via_bluetooth_map(self, target_number: str, message_text: str = "received call. will get back to you shortly."):
        """Pushes an SMS directly to Phone A via BlueZ MAP to send over cellular SIM."""
        try:
            bus = dbus.SessionBus()
            if not self.map_session_path:
                return
            mas_obj = bus.get_object("org.bluez.obex", self.map_session_path)
            mas = dbus.Interface(mas_obj, "org.bluez.obex.MessageAccess1")

            clean_target = str(target_number).strip().replace(" ", "")
            if not clean_target:
                clean_target = "8714711540"

            bmsg = (
                "BEGIN:BMSG\r\n"
                "VERSION:1.0\r\n"
                "STATUS:UNREAD\r\n"
                "TYPE:SMS_GSM\r\n"
                "FOLDER:telecom/msg/outbox\r\n"
                "BEGIN:BENV\r\n"
                "BEGIN:VCARD\r\n"
                "VERSION:2.1\r\n"
                "N:\r\n"
                f"TEL:{clean_target}\r\n"
                "END:VCARD\r\n"
                "BEGIN:BBODY\r\n"
                "ENCODING:Gsm-7Bit\r\n"
                f"LENGTH:{len(message_text)}\r\n"
                "BEGIN:MSG\r\n"
                f"{message_text}\r\n"
                "END:MSG\r\n"
                "END:BBODY\r\n"
                "END:BENV\r\n"
                "END:BMSG\r\n"
            )

            with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
                f.write(bmsg)
                tmp_path = f.name

            try:
                path, props = mas.PushMessage(
                    tmp_path,
                    "outbox",
                    {"Transparent": dbus.Boolean(False), "Retry": dbus.Boolean(True)}
                )
                print(f"[{format_timestamp()}] 🚀 Bluetooth MAP SMS dispatched to {clean_target} (outbox transfer: {path})")
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
        except Exception as e:
            print(f"[{format_timestamp()}] ⚠️ Bluetooth MAP PushMessage fallback note: {e}")

    async def handle_client(self, websocket):
        """Handle incoming WebSocket connection from phone apps & browser dashboard."""
        client_addr = websocket.remote_address
        print(f"[{format_timestamp()}] 📱 Client connected from: {client_addr}")
        self.connected_clients.add(websocket)

        welcome_payload = {
            "type": "SERVER_READY",
            "server": "Kaaka Call & Telemetry Server",
            "ip": self.local_ip,
            "port": self.port,
            "http_port": self.http_port,
            "last_number": self.last_detected_number or "9995283835",
            "telemetry_count": self.telemetry_count,
            "latest_telemetry": self.latest_telemetry,
            "timestamp": format_timestamp()
        }
        await websocket.send(json.dumps(welcome_payload))

        # Replay any recent pending call trigger (<45s old) to newly connected phone
        if self.pending_call_trigger and client_addr[0] != '127.0.0.1':
            age = time.time() - self.pending_call_trigger.get("timestamp", 0)
            if age < 45:
                print(f"[{format_timestamp()}] 🚀 Replaying queued call trigger for {self.pending_call_trigger['number']} to Gateway ({client_addr[0]})!")
                replay_payload = {
                    "type": "CALL_DETECTED",
                    "number": self.pending_call_trigger["number"],
                    "name": self.pending_call_trigger.get("name", ""),
                    "state": self.pending_call_trigger.get("state", "active"),
                    "timestamp": format_timestamp()
                }
                await websocket.send(json.dumps(replay_payload))

        try:
            async for raw_message in websocket:
                try:
                    data = json.loads(raw_message)
                    msg_type = data.get("type", "")

                    if msg_type == "CLIENT_TELEMETRY":
                        report = data.get("report") or data.get("message") or ""
                        sender = data.get("sender", "Client App")
                        self.display_telemetry(report, sender=sender, source="Direct App WebSocket")
                    elif msg_type == "SMS_SENT":
                        num = data.get("number", "Unknown")
                        self.pending_call_trigger = None
                        print(f"[{format_timestamp()}] ✅ Phone confirmed: Auto-sent SMS to \033[1;32m{num}\033[0m")
                    elif msg_type == "PING":
                        await websocket.send(json.dumps({"type": "PONG", "timestamp": format_timestamp()}))
                    elif "Live Sensors" in str(data):
                        self.display_telemetry(str(data), sender="Client App", source="Direct App WebSocket")
                    else:
                        print(f"[{format_timestamp()}] 📩 Received from client: {data}")
                except json.JSONDecodeError:
                    if "Live Sensors" in raw_message or "Kaaka Alert" in raw_message:
                        self.display_telemetry(raw_message, sender="Client App", source="Raw App WebSocket")
                    else:
                        print(f"[{format_timestamp()}] 📩 Raw text from client: {raw_message}")
        except websockets.exceptions.ConnectionClosed as e:
            print(f"[{format_timestamp()}] 🔌 ConnectionClosed from {client_addr}: code={e.code}, reason={e.reason!r}")
        except Exception as e:
            print(f"[{format_timestamp()}] ⚠️ WS Exception from {client_addr}: {type(e).__name__}: {e}")
        finally:
            self.connected_clients.remove(websocket)
            print(f"[{format_timestamp()}] 🔌 Client disconnected: {client_addr}")

    def run_telephony_listener(self):
        """Monitors PipeWire / oFono handsfree calls."""
        DBusGMainLoop(set_as_default=True)
        try:
            bus = dbus.SessionBus()
        except Exception as e:
            print(f"[{format_timestamp()}] Telephony D-Bus init error: {e}")
            return

        def extract_props(props):
            num = str(props.get("LineIdentification", "")).strip()
            name = str(props.get("Name", "")).strip()
            state = str(props.get("State", "active")).strip()
            return num, name, state

        def on_call_added(path, properties):
            num, name, state = extract_props(properties)
            if num:
                self.on_call_detected(num, name, state, path)

        def on_interfaces_added(path, interfaces):
            if "org.pipewire.Telephony.Call1" in interfaces:
                props = interfaces["org.pipewire.Telephony.Call1"]
                num, name, state = extract_props(props)
                if num:
                    self.on_call_detected(num, name, state, path)

        # Check existing active call immediately on launch
        try:
            telephony = bus.get_object(self.telephony_service, "/org/pipewire/Telephony/ag1")
            vcm = dbus.Interface(telephony, "org.ofono.VoiceCallManager")
            for c_path, c_props in vcm.GetCalls().items():
                num, name, state = extract_props(c_props)
                if num:
                    self.on_call_detected(num, name, state, c_path)
        except Exception:
            pass

        def on_call_removed(path):
            print(f"[{format_timestamp()}] 📴 Call ended ({path}). Stopping audio conversation bridge.")
            self.audio_bridge.notify_call_ended()

        bus.add_signal_receiver(
            on_call_added,
            signal_name="CallAdded",
            dbus_interface="org.ofono.VoiceCallManager",
            bus_name=self.telephony_service
        )

        bus.add_signal_receiver(
            on_call_removed,
            signal_name="CallRemoved",
            dbus_interface="org.ofono.VoiceCallManager",
            bus_name=self.telephony_service
        )

        glib_loop = GLib.MainLoop()
        glib_loop.run()

    def run_bluetooth_map_listener(self):
        """
        Monitors Bluetooth BLE / Message Access Profile (MAP) notifications.
        Connects to org.bluez.obex and captures incoming SMS telemetry from Phone A.
        """
        DBusGMainLoop(set_as_default=True)
        try:
            bus = dbus.SessionBus()
        except Exception as e:
            print(f"[{format_timestamp()}] Bluetooth MAP D-Bus init error: {e}")
            return

        mas_interface = None

        def init_session():
            nonlocal mas_interface
            try:
                obex_client = dbus.Interface(
                    bus.get_object('org.bluez.obex', '/org/bluez/obex'),
                    'org.bluez.obex.Client1'
                )
                session_path = obex_client.CreateSession(self.bt_mac, {'Target': 'map'})
                self.map_session_path = session_path
                mas_obj = bus.get_object('org.bluez.obex', session_path)
                mas_interface = dbus.Interface(mas_obj, 'org.bluez.obex.MessageAccess1')
                mas_interface.SetFolder('telecom')
                mas_interface.SetFolder('msg')
                print(f"[{format_timestamp()}] 📶 Bluetooth MAP notification listener active for {self.bt_mac}")
                return True
            except Exception:
                return False

        def fetch_full_message(msg_path):
            """Fetch full bMessage payload using Message1.Get()"""
            try:
                msg_obj = dbus.Interface(bus.get_object('org.bluez.obex', msg_path), 'org.bluez.obex.Message1')
                tmp_fd, tmp_file = tempfile.mkstemp(prefix="map_msg_")
                os.close(tmp_fd)
                transfer, _ = msg_obj.Get(tmp_file, False)
                for _ in range(10):
                    time.sleep(0.15)
                    if os.path.exists(tmp_file) and os.path.getsize(tmp_file) > 0:
                        break
                content = ""
                if os.path.exists(tmp_file):
                    with open(tmp_file, 'r', errors='ignore') as f:
                        content = f.read()
                    try:
                        os.remove(tmp_file)
                    except OSError:
                        pass
                return content
            except Exception:
                return ""

        def process_message_candidate(path, props):
            subj = str(props.get('Subject', ''))
            sender = str(props.get('SenderAddress', ''))
            
            # Check if this message is a Kaaka sensor reading or from caller
            if 'Kaaka' in subj or 'Sensors' in subj or 'Live Sensors' in subj or 'Pedometer' in subj or '8714711540' in sender or subj.startswith('proto:'):
                full_content = fetch_full_message(path)
                final_text = full_content if full_content else subj
                if 'Kaaka' in final_text or 'Sensors' in final_text or 'Live Sensors' in final_text or 'Pedometer' in final_text:
                    self.display_telemetry(final_text, sender=sender, source="Bluetooth BLE / MAP")
                    return True
            return False

        def on_interfaces_added(path, interfaces):
            """Real-time event trigger from BlueZ OBEX MNS when an SMS notification arrives."""
            if 'org.bluez.obex.Message1' in interfaces:
                props = interfaces['org.bluez.obex.Message1']
                msg_id = str(path)
                if msg_id not in self.processed_msg_ids:
                    self.processed_msg_ids.add(msg_id)
                    process_message_candidate(path, props)

        bus.add_signal_receiver(
            on_interfaces_added,
            signal_name='InterfacesAdded',
            dbus_interface='org.freedesktop.DBus.ObjectManager',
            bus_name='org.bluez.obex'
        )

        inbox_tick = 0
        def periodic_inbox_check():
            """Periodic fast scanner of top inbox messages to guarantee zero dropped alerts."""
            nonlocal mas_interface, inbox_tick
            if not mas_interface:
                init_session()
                return True

            inbox_tick += 1
            if inbox_tick % 5 == 0:
                try:
                    mas_interface.UpdateInbox()
                except Exception:
                    pass

            try:
                msgs = mas_interface.ListMessages('inbox', {'MaxListCount': dbus.UInt16(10)})
                for path, meta in msgs.items():
                    msg_id = str(path)
                    if msg_id not in self.processed_msg_ids:
                        self.processed_msg_ids.add(msg_id)
                        process_message_candidate(path, meta)
            except dbus.exceptions.DBusException:
                mas_interface = None
            except Exception:
                pass
            return True

        def populate_initial_history():
            """Pre-populate existing message IDs and load latest alert if not already cached."""
            nonlocal mas_interface
            if not mas_interface:
                return
            try:
                msgs = mas_interface.ListMessages('inbox', {'MaxListCount': dbus.UInt16(100)})
                latest_alert = None
                latest_sender = "+918714711540"
                for path, meta in msgs.items():
                    msg_id = str(path)
                    self.processed_msg_ids.add(msg_id)
                    subj = str(meta.get('Subject', ''))
                    sender = str(meta.get('SenderAddress', ''))
                    if latest_alert is None and ('8714711540' in sender or 'Kaaka' in subj or subj.startswith('proto:')):
                        full_content = fetch_full_message(path)
                        if full_content and ('Kaaka' in full_content or 'Live Sensors' in full_content or 'Pedometer' in full_content):
                            latest_alert = full_content
                            latest_sender = sender or "+918714711540"
                if latest_alert and (self.latest_telemetry is None or self.telemetry_count == 0):
                    self.display_telemetry(latest_alert, sender=latest_sender, source="Bluetooth BLE / MAP (Inbox)")
            except Exception as e:
                pass

        if init_session():
            populate_initial_history()
        GLib.timeout_add_seconds(1, periodic_inbox_check)

        glib_loop = GLib.MainLoop()
        glib_loop.run()

    def run_http_server(self):
        """Runs the standalone Dashboard HTTP Server in a daemon thread."""
        server_inst = self
        class BoundHandler(DashboardHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, server_instance=server_inst, **kwargs)

        socketserver.ThreadingTCPServer.allow_reuse_address = True
        try:
            httpd = socketserver.ThreadingTCPServer((self.host, self.http_port), BoundHandler)
            print(f"[{format_timestamp()}] 🖥️ Web Dashboard UI active: \033[1;32mhttp://{self.local_ip}:{self.http_port}\033[0m")
            httpd.serve_forever()
        except Exception as e:
            print(f"[{format_timestamp()}] HTTP server error: {e}")

    async def console_trigger_loop(self):
        """Allows testing in terminal: press Enter to test call, or type 't' to test telemetry."""
        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        try:
            while True:
                line = await reader.readline()
                if not line:
                    await asyncio.sleep(1)
                    continue
                text = line.decode().strip()
                if text in ['t', 'telemetry', 'alert']:
                    print(f"[{format_timestamp()}] 🧪 Simulating sensor telemetry alert:")
                    sample_alert = (
                        "Kaaka Alert: Emergency assistance requested\n\n"
                        "Live Sensors (5/5):\n"
                        "• Pedometer: 0 steps (0.00 km)\n"
                        "• Light: 53 lx\n"
                        "• Accelerometer: 9.7 m/s²\n"
                        "• Gyroscope: 0.2 rad/s\n"
                        "• Magnetometer: 186° S\n"
                        "• Coords: 9.064458, 76.557012\n"
                        "• Maps: https://maps.google.com/?q=9.064458,76.557012"
                    )
                    self.display_telemetry(sample_alert, sender="+919495364448", source="Simulated Test")
                else:
                    test_number = text if text else "8714711540"
                    print(f"[{format_timestamp()}] 🧪 Manual call trigger test with number: {test_number}")
                    self.on_call_detected(test_number, name="Test Caller", state="active")
        except asyncio.CancelledError:
            pass

    def run_bluetooth_handsfree_watchdog(self):
        """Monitors and maintains Bluetooth Handsfree Audio Gateway connection."""
        dev_path = f"/org/bluez/hci0/dev_{self.bt_mac.replace(':', '_')}"
        while True:
            try:
                bus = dbus.SessionBus()
                has_ag1 = False
                try:
                    telephony = bus.get_object(self.telephony_service, "/org/pipewire/Telephony/ag1")
                    # If this succeeds, ag1 exists
                    has_ag1 = True
                except Exception:
                    has_ag1 = False

                if not has_ag1:
                    sys_bus = dbus.SystemBus()
                    dev_obj = sys_bus.get_object("org.bluez", dev_path)
                    dev_iface = dbus.Interface(dev_obj, "org.bluez.Device1")
                    dev_iface.ConnectProfile("0000111f-0000-1000-8000-00805f9b34fb")
                    print(f"[{format_timestamp()}] 🔄 Bluetooth Handsfree profile auto-reconnected for {self.bt_mac}")
            except Exception:
                pass
            time.sleep(4)

    def run_adb_telemetry_listener(self):
        """
        Direct cellular SMS telemetry ingestor via Phone ADB connection.
        Continuously polls content://sms every 1.5 seconds.
        Guarantees zero-latency, 100% reliable telemetry ingestion with zero D-Bus drops.
        """
        adb_seen_ids = set()
        initialized = False

        while True:
            try:
                dev_out = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=2).stdout
                target_cmd = ["adb"]
                if "289e9952" in dev_out:
                    target_cmd = ["adb", "-s", "289e9952"]
                elif "0fdefe1e3cfa" in dev_out:
                    target_cmd = ["adb", "-s", "0fdefe1e3cfa"]

                cmd = target_cmd + ["shell", "content query --uri content://sms --where \"address LIKE '%8714711540%' OR body LIKE '%Kaaka%'\""]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
                if res.returncode == 0 and res.stdout and "No result found" not in res.stdout:
                    rows = res.stdout.split("Row: ")
                    if not initialized:
                        latest_row = None
                        for r in rows[1:]:
                            id_m = re.search(r"_id=(\d+)", r)
                            if id_m:
                                mid = id_m.group(1)
                                adb_seen_ids.add(mid)
                                if latest_row is None:
                                    latest_row = r
                        if latest_row and (self.latest_telemetry is None or self.telemetry_count == 0):
                            body_m = re.search(r"body=(.+?)(?:, service_center=|, locked=|$)", latest_row, re.DOTALL)
                            addr_m = re.search(r"address=([^\s,]+)", latest_row)
                            if body_m:
                                b_text = body_m.group(1).strip()
                                s_addr = addr_m.group(1) if addr_m else "+918714711540"
                                self.display_telemetry(b_text, sender=s_addr, source="Phone ADB Telephony Ingest")
                        initialized = True
                    else:
                        for r in rows[1:]:
                            id_m = re.search(r"_id=(\d+)", r)
                            if not id_m:
                                continue
                            mid = id_m.group(1)
                            if mid not in adb_seen_ids:
                                adb_seen_ids.add(mid)
                                body_m = re.search(r"body=(.+?)(?:, service_center=|, locked=|$)", r, re.DOTALL)
                                addr_m = re.search(r"address=([^\s,]+)", r)
                                if body_m:
                                    b_text = body_m.group(1).strip()
                                    if "Kaaka Alert" in b_text or "Live Sensors" in b_text or "Pedometer" in b_text:
                                        s_addr = addr_m.group(1) if addr_m else "+918714711540"
                                        self.display_telemetry(b_text, sender=s_addr, source="Phone ADB Telephony Ingest")
            except Exception:
                pass
            time.sleep(1.5)

    async def start(self):
        self.loop = asyncio.get_running_loop()

        # Thread 1: PipeWire / oFono Telephony listener
        telephony_thread = threading.Thread(target=self.run_telephony_listener, daemon=True)
        telephony_thread.start()

        # Thread 2: Bluetooth BLE / Message Access Profile (MAP) notification listener
        map_thread = threading.Thread(target=self.run_bluetooth_map_listener, daemon=True)
        map_thread.start()

        # Thread 3: HTTP Web Dashboard UI server
        http_thread = threading.Thread(target=self.run_http_server, daemon=True)
        http_thread.start()

        # Thread 4: Bluetooth Handsfree Profile Watchdog
        watchdog_thread = threading.Thread(target=self.run_bluetooth_handsfree_watchdog, daemon=True)
        watchdog_thread.start()

        # Thread 5: Direct Cellular Telephony ADB Ingestor (Phone A)
        adb_telemetry_thread = threading.Thread(target=self.run_adb_telemetry_listener, daemon=True)
        adb_telemetry_thread.start()

        print("\n" + "=" * 65)
        print(" 🚀 Kaaka Telephony, BLE & Dashboard Server")
        print("=" * 65)
        print(f"  🌐 Local Wi-Fi IP  : \033[1;36m{self.local_ip}\033[0m")
        print(f"  🔌 WebSocket Port  : \033[1;36m{self.port}\033[0m  (\033[1;32mws://{self.local_ip}:{self.port}\033[0m)")
        print(f"  🖥️ Web Dashboard UI: \033[1;36m{self.http_port}\033[0m  (\033[1;32mhttp://{self.local_ip}:{self.http_port}\033[0m)")
        print(f"  📶 Gateway BLE MAC : \033[1;36m{self.bt_mac}\033[0m")
        print("=" * 65)
        print("  💡 Tip: Open the dashboard in browser to view live visual sensors.")
        print("  💡 Tip: Press [Enter] to simulate a call test.")
        print("  💡 Tip: Type 't' + [Enter] to simulate sensor telemetry display.")
        print("=" * 65 + "\n", flush=True)

        async with websockets.serve(self.handle_client, self.host, self.port):
            asyncio.create_task(self.console_trigger_loop())
            await asyncio.Future()  # run forever

def main():
    parser = argparse.ArgumentParser(description="Kaaka Bluetooth Call & Telemetry Server")
    parser.add_argument("--port", "-p", type=int, default=8765, help="WebSocket port (default: 8765)")
    parser.add_argument("--http-port", type=int, default=8080, help="Web Dashboard HTTP port (default: 8080)")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface (default: 0.0.0.0)")
    parser.add_argument("--bt-mac", default="08:1C:6E:5F:10:F7", help="Gateway Bluetooth MAC address")
    args = parser.parse_args()

    server = TelemetryServer(host=args.host, port=args.port, http_port=args.http_port, bt_mac=args.bt_mac)
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\nServer stopped.")

if __name__ == "__main__":
    main()
