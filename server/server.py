#!/usr/bin/env python3
"""
Kaaka Bluetooth Call & Telemetry WebSocket + Dashboard Server
=================================================================
1. Monitors Bluetooth handsfree phone calls in PipeWire/Helvum.
   When an active call is detected, extracts the phone number and
   broadcasts it over WebSockets to trigger automatic SMS dispatch.
2. Monitors Bluetooth BLE / Message Access Profile (MAP) notifications
   from the connected gateway phone (--bt-mac). When an incoming
   sensor telemetry SMS alert arrives from the client phone, extracts the
   payload and prints the live readings in the exact requested format.
3. Hosts a real-time web dashboard UI on HTTP (default port 8080) displaying
   live sensor cards, visual compass needle, telephony status, and alert logs.
4. Accepts direct WebSocket telemetry streams from connected client apps.
"""

import argparse
import asyncio
import csv
import io
import hmac
import http.server
import json
import os
import re
import signal
import socket
import socketserver
import sys
import tempfile
import threading
import time
from datetime import datetime
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, quote, unquote, urlparse
import subprocess
import websockets

IS_MAC = sys.platform == "darwin"

# Linux-only: BlueZ / PipeWire / oFono over D-Bus. Imported lazily by load_linux_dbus() when --bt-mac
# is set, so the server starts on plain Linux / in a container with only `websockets` installed.
dbus = None
DBusGMainLoop = None
GLib = None


def load_linux_dbus():
    """Import python-dbus and PyGObject (GLib) into this module; exits with a clear message if missing."""
    global dbus, DBusGMainLoop, GLib
    if dbus is not None:
        return
    try:
        import dbus as _dbus
        from dbus.mainloop.glib import DBusGMainLoop as _DBusGMainLoop
        from gi.repository import GLib as _GLib
    except ImportError as e:
        sys.exit(f"--bt-mac on Linux needs the D-Bus/GLib bindings (missing: {e.name or e}). "
                 "Install them with: sudo apt install python3-dbus python3-gi  (Debian/Ubuntu), "
                 "or run without --bt-mac so the gateway app reports calls over HTTP.")
    dbus, DBusGMainLoop, GLib = _dbus, _DBusGMainLoop, _GLib

try:
    from server.audio_bridge import AudioConversationBridge, ensure_audio_sinks
except ImportError:
    from audio_bridge import AudioConversationBridge, ensure_audio_sinks

try:
    from server.incidents import IncidentStore, TOKEN_RE, number_key
    from server.responders import ResponderRegistry
    from server import analytics
except ImportError:
    from incidents import IncidentStore, TOKEN_RE, number_key
    from responders import ResponderRegistry
    import analytics

if IS_MAC:
    try:
        from server.mac_telephony import HfpBridgeClient
    except ImportError:
        from mac_telephony import HfpBridgeClient

MAX_TEXT = 500  # help-SMS message and resolution note limit

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))
# Runtime data (events.jsonl, responders.json, last_call.json, latest_telemetry.json): KAAKA_DATA_DIR
# or the server directory, so a service or container can keep it on a volume.
DEFAULT_DATA_DIR = os.environ.get("KAAKA_DATA_DIR") or SERVER_DIR


def write_json_atomic(path, obj, indent=None):
    """Write JSON to a temp file in the same directory and rename it over `path`, so a crash
    or a concurrent reader never sees a half-written file."""
    fd, tmp = tempfile.mkstemp(prefix=os.path.basename(path) + ".", suffix=".tmp", dir=os.path.dirname(path) or ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=indent)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

CSV_COLUMNS = ["number", "status", "first_seen", "last_seen", "calls", "help_sms", "alerts", "latest_lat", "latest_lon",
               "acknowledged_by", "acknowledged_at", "resolved_by", "resolved_at", "resolved_note"]


def incidents_csv(incidents) -> str:
    """GET /api/incidents.csv: one row per incident."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(CSV_COLUMNS)
    for inc in incidents:
        loc, ack, res = inc.get("latest_location") or {}, inc.get("acknowledged") or {}, inc.get("resolved") or {}
        writer.writerow([inc["number"], inc["status"], inc["first_seen"], inc["last_seen"], len(inc["calls"]),
                         len(inc["help_sms"]), len(inc["alerts"]), loc.get("lat", ""), loc.get("lon", ""),
                         ack.get("responder", ""), ack.get("timestamp", ""), res.get("by", ""),
                         res.get("timestamp", ""), res.get("note", "")])
    return out.getvalue()


INCIDENT_QUERY_PARAMS = ("status", "q", "from", "to", "outcome", "limit", "offset")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_incident_query(query, default_limit=50):
    """Keyword arguments for IncidentStore.query from /api/incidents query parameters; raises ValueError."""
    def one(name, default=""):
        return (query.get(name) or [default])[0].strip()
    status = one("status", "all")
    if status not in ("open", "resolved", "all"):
        raise ValueError('"status" must be open, resolved or all')
    outcome = one("outcome")
    if outcome not in ("", "closed_by_caller", "resolved_by_responder"):
        raise ValueError('"outcome" must be closed_by_caller or resolved_by_responder')
    q = one("q")
    if len(q) > 40:
        raise ValueError('"q" must be at most 40 characters')
    date_from, date_to = one("from"), one("to")
    for name, value in (("from", date_from), ("to", date_to)):
        if value and not DATE_RE.match(value):
            raise ValueError(f'"{name}" must be a date YYYY-MM-DD')
    try:
        limit = int(one("limit", str(default_limit)))
        offset = int(one("offset", "0"))
    except ValueError:
        raise ValueError('"limit" and "offset" must be integers')
    if not 0 <= limit <= max(500, default_limit) or offset < 0:
        raise ValueError('"limit" must be 0-500 and "offset" at least 0')
    return {"status": status, "q": q, "date_from": date_from, "date_to": date_to, "outcome": outcome,
            "limit": limit, "offset": offset}


def notify_mac(text):
    """Native macOS notification in a background thread. The text is passed as an osascript argument,
    never pasted into the script, because callers control parts of it. Failures are ignored."""
    def _run():
        try:
            subprocess.run(["osascript", "-e", "on run argv", "-e",
                            "display notification (item 2 of argv) with title (item 1 of argv)",
                            "-e", "end run", "Kaaka", text[:200]],
                           capture_output=True, timeout=10)
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


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

def format_sensor_report(sensors: dict) -> str:
    """Turn the client app's sensor JSON into the report text the dashboard parses."""
    def num(group, key, default=0.0):
        try:
            return float((sensors.get(group) or {}).get(key, default))
        except (TypeError, ValueError):
            return default
    mag = sensors.get("magnetometer") or {}
    return "\n".join([
        "Kaaka Live: sensor stream",
        "",
        "Live Sensors (5/5):",
        f"• Pedometer: {int(num('pedometer', 'steps'))} steps ({num('pedometer', 'distanceKm'):.2f} km)",
        f"• Light: {round(num('ambientLight', 'lux'))} lx",
        f"• Accelerometer: {num('accelerometer', 'magnitude'):.1f} m/s²",
        f"• Gyroscope: {num('gyroscope', 'rate'):.1f} rad/s",
        f"• Magnetometer: {round(num('magnetometer', 'heading'))}° {mag.get('cardinal', '')}".rstrip(),
    ])

def cookie_token(cookie_header):
    """Admin token from the dashboard's kaaka_token cookie ("" if absent)."""
    if not cookie_header:
        return ""
    jar = SimpleCookie()
    try:
        jar.load(cookie_header)
    except Exception:
        return ""
    morsel = jar.get("kaaka_token")
    return unquote(morsel.value) if morsel else ""

NOT_FOUND_LOCATE_PAGE = (b"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width, initial-scale=1'>"
                         b"<title>Link not found</title><body style='font:17px system-ui;margin:1.5rem'>"
                         b"<h1>Link not found</h1><p>This location link is unknown or has expired (links last 24 hours).</p>"
                         b"<p>If you are in immediate danger, call 112.</p></body>")

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, server_instance=None, **kwargs):
        self.server_instance = server_instance
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        # Suppress routine HTTP request logging to keep console clean
        pass

    def send_json(self, status, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, status, content):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def read_json_body(self, max_bytes=65536):
        length = int(self.headers.get("Content-Length", 0))
        if length > max_bytes:
            raise ValueError("request body too large")
        return json.loads(self.rfile.read(length).decode("utf-8") or "null")

    def authorized(self, query):
        """Admin token check (only when KAAKA_ADMIN_TOKEN is set): header, ?token= or dashboard cookie."""
        token = (self.headers.get("X-Kaaka-Token") or (query.get("token") or [""])[0]
                 or cookie_token(self.headers.get("Cookie")))
        return self.server_instance.check_admin_token(token)

    def serve_locate_page(self, token):
        """Public page behind the SMS location link: asks the caller's browser for its location."""
        if not TOKEN_RE.match(token) or self.server_instance.incidents.token_number(token) is None:
            self.send_html(404, NOT_FOUND_LOCATE_PAGE)
            return
        with open(os.path.join(os.path.dirname(__file__), "locate.html"), "r", encoding="utf-8") as f:
            page = f.read().replace("{{TOKEN}}", token)  # token matched TOKEN_RE, safe to embed
        self.send_html(200, page.encode("utf-8"))

    def serve_landing_page(self):
        """Public landing page (site/index.html in the repository)."""
        landing = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site", "index.html")
        try:
            with open(landing, "rb") as f:
                page = f.read()
        except OSError:
            page = (b"<!doctype html><meta charset=utf-8><title>Kaaka</title>"
                    b"<p>Kaaka help line. The control room is at <a href=/admin>/admin</a>.</p>")
        self.send_html(200, page)

    def handle_location(self):
        """POST /api/location (public): a caller shares their location through the SMS link."""
        try:
            data = self.read_json_body(max_bytes=4096)
            if not isinstance(data, dict):
                raise ValueError("body must be a JSON object")
            token = data.get("token")
            if not isinstance(token, str) or not TOKEN_RE.match(token):
                raise ValueError('"token" is missing or malformed')
            lat, lon, accuracy = data.get("lat"), data.get("lon"), data.get("accuracy")
            for name, value, low, high in (("lat", lat, -90, 90), ("lon", lon, -180, 180)):
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
                    raise ValueError(f'"{name}" must be a number between {low} and {high}')
            if accuracy is not None and (isinstance(accuracy, bool) or not isinstance(accuracy, (int, float))
                                         or not 0 <= accuracy < 1e7):
                raise ValueError('"accuracy" must be a non-negative number of metres')
        except (ValueError, UnicodeDecodeError) as e:
            self.send_json(400, {"success": False, "error": str(e)})
            return
        if self.server_instance.incidents.token_number(token) is None:
            self.send_json(404, {"success": False, "error": "unknown or expired location link"})
            return
        if not self.server_instance.accept_location_update(token):
            self.send_json(429, {"success": False, "error": "too many updates: at most one every 10 seconds"})
            return
        self.server_instance.on_location(token, float(lat), float(lon), None if accuracy is None else float(accuracy))
        self.send_json(200, {"success": True})

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)
        if path.startswith("/l/"):
            self.serve_locate_page(path[3:])
            return
        if path in ("/", "/index.html"):
            self.serve_landing_page()  # public: what Kaaka is; the dashboard lives at /admin
            return
        if path == "/admin/":
            self.send_response(301)
            self.send_header("Location", "/admin" + (("?" + parsed.query) if parsed.query else ""))
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if not self.authorized(query):
            if path == "/admin":
                self.send_html(401, b"<!doctype html><meta charset=utf-8><title>Kaaka</title>"
                                    b"<p>Admin token required: open the dashboard as /admin?token=...</p>")
            else:
                self.send_json(401, {"success": False, "error": "admin token required"})
            return
        if path == "/admin":
            dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
            if not os.path.exists(dashboard_path):
                self.send_error(404, "dashboard.html not found")
                return
            try:
                with open(dashboard_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                if self.server_instance.admin_token and query.get("token"):
                    # Remember the token so later page loads, API calls and the WebSocket need no ?token=
                    self.send_header("Set-Cookie", f"kaaka_token={quote(self.server_instance.admin_token)}; Path=/; HttpOnly; SameSite=Strict")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self.send_error(500, f"Error loading dashboard: {e}")
        elif path == "/api/incidents":
            if not any(k in query for k in INCIDENT_QUERY_PARAMS):
                # Unchanged default (gateway and other callers): the 50 most recent incidents.
                self.send_json(200, {"incidents": self.server_instance.incidents_with_nearest()})
                return
            try:
                params = parse_incident_query(query)
            except ValueError as e:
                self.send_json(400, {"success": False, "error": str(e)})
                return
            result = self.server_instance.incidents.query(**params)
            self.server_instance.add_nearest(result["incidents"])
            self.send_json(200, {**result, "limit": params["limit"], "offset": params["offset"]})
        elif path.startswith("/api/incidents/") and path != "/api/incidents.csv":
            inc = self.server_instance.incidents.detail(unquote(path[len("/api/incidents/"):]))
            if inc is None:
                self.send_json(404, {"success": False, "error": "no incident with this key"})
                return
            self.server_instance.add_nearest([inc])
            self.send_json(200, {"incident": inc})
        elif path == "/api/responders/activity":
            self.send_json(200, {"activity": self.server_instance.incidents.responder_activity()})
        elif path == "/api/responders":
            self.send_json(200, {"responders": self.server_instance.responders.list()})
        elif path == "/api/analytics":
            range_key = (query.get("range") or [analytics.DEFAULT_RANGE])[0]
            if range_key not in analytics.RANGES:
                self.send_json(400, {"success": False, "error": f'range must be one of {", ".join(analytics.RANGES)}'})
                return
            self.send_json(200, analytics.compute(self.server_instance.incidents.events_snapshot(),
                                                  self.server_instance.responders.list(), range_key, time.time()))
        elif path == "/api/incidents.csv":
            if any(k in query for k in INCIDENT_QUERY_PARAMS):
                # Same filters as /api/incidents (History page), without the 50-incident cap.
                try:
                    params = parse_incident_query(query, default_limit=100000)
                except ValueError as e:
                    self.send_json(400, {"success": False, "error": str(e)})
                    return
                rows = self.server_instance.incidents.query(**params)["incidents"]
            else:
                rows = self.server_instance.incidents.incidents()
            body = incidents_csv(rows).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="kaaka-incidents.csv"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/status":
            phone_clients = self.server_instance.phone_client_ips()
            bt_connected = self.server_instance.check_bluetooth_connected()
            telephony_ag_online = self.server_instance.check_telephony_ag_online()
            gateway_online = (bt_connected and telephony_ag_online) or (len(phone_clients) > 0)
            if not self.server_instance.bt_enabled:
                gateway_mode = "gateway_app"
            else:
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
                "bluetooth_enabled": self.server_instance.bt_enabled,
                "last_gateway_event": self.server_instance.last_gateway_event,
                "last_heartbeat": self.server_instance.last_heartbeat,
                "public_url": self.server_instance.public_url,
                "admin_token_enabled": bool(self.server_instance.admin_token),
                "gateway_stale": self.server_instance.gateway_stale(),
                "phone_app_connected": len(phone_clients) > 0,
                "gateway_ips": phone_clients,
                "clients_count": len(self.server_instance.connected_clients),
                "last_call_number": self.server_instance.last_detected_number,
                "telemetry_count": self.server_instance.telemetry_count,
                "latest_telemetry": self.server_instance.latest_telemetry,
                "webhook_url": self.server_instance.audio_bridge.primary_url,
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

    def do_OPTIONS(self):
        # CORS preflight: the client app's WebView posts JSON from another origin.
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Kaaka-Token")
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)
        if path == "/api/location":
            self.handle_location()
            return
        if not self.authorized(query):
            self.send_json(401, {"success": False, "error": "admin token required"})
            return
        if path == "/api/responders":
            # Register a responder: {"name", "number", "lat", "lon", "available"?}
            try:
                responder = self.server_instance.responders.add(self.read_json_body(max_bytes=4096))
            except (ValueError, UnicodeDecodeError) as e:
                self.send_json(400, {"success": False, "error": str(e)})
                return
            print(f"[{format_timestamp()}] 🧑‍🚒 Responder added: {responder['name']} ({responder['number']})", flush=True)
            self.send_json(200, {"success": True, "responder": responder})
        elif path == "/api/trigger-call":
            # Optional JSON body {"number": "..."}; without it the simulated call has no caller number.
            number = ""
            length = int(self.headers.get("Content-Length", 0))
            if length:
                try:
                    number = str(json.loads(self.rfile.read(length).decode("utf-8")).get("number", ""))
                except Exception:
                    number = ""
            self.server_instance.on_call_detected(number, name="Simulated Caller", state="active")
            body = b'{"success":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/audio-bridge/toggle":
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
        elif path == "/api/audio-bridge/mode":
            self.server_instance.auto_answer_mode = not self.server_instance.auto_answer_mode
            status = {"auto_answer_mode": self.server_instance.auto_answer_mode}
            body = json.dumps(status).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/trigger-telemetry":
            sample_alert = (
                "Kaaka Alert: Emergency assistance requested\n\n"
                "Live Sensors (5/5):\n"
                "• Pedometer: 0 steps (0.00 km)\n"
                "• Light: 53 lx\n"
                "• Accelerometer: 9.7 m/s²\n"
                "• Gyroscope: 0.2 rad/s\n"
                "• Magnetometer: 186° S\n"
                "• Location: unavailable"
            )
            self.server_instance.display_telemetry(sample_alert, sender="simulated", source="Simulated Test")
            body = b'{"success":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/call-event":
            status, result = 200, {"success": True}
            try:
                length = int(self.headers.get("Content-Length", 0))
                event = json.loads(self.rfile.read(length).decode("utf-8") or "null")
                if not isinstance(event, dict):
                    raise ValueError("body must be a JSON object")
                number = event.get("number", "")
                state = event.get("state")
                sms = event.get("sms")
                timestamp = event.get("timestamp", "")
                if not isinstance(number, str):
                    raise ValueError('"number" must be a string ("" if hidden)')
                if state not in ("rejected", "allowed", "sms"):
                    raise ValueError('"state" must be "rejected", "allowed" or "sms" (help by SMS)')
                if sms not in ("sent", "failed", "skipped"):
                    raise ValueError('"sms" must be "sent", "failed" or "skipped"')
                if not isinstance(timestamp, str):
                    raise ValueError('"timestamp" must be an ISO-8601 string')
                token = event.get("token")
                if token is not None and (not isinstance(token, str) or not TOKEN_RE.match(token)):
                    raise ValueError('"token" must be 6-32 letters, digits, "_" or "-"')
                message = event.get("message")
                if message is not None and (not isinstance(message, str) or len(message) > MAX_TEXT):
                    raise ValueError(f'"message" must be a string of at most {MAX_TEXT} characters')
                self.server_instance.on_call_event(number.strip(), state, sms, timestamp, token or None,
                                                   (message or "").strip() or None)
            except (ValueError, UnicodeDecodeError) as e:  # json.JSONDecodeError is a ValueError
                status, result = 400, {"success": False, "error": str(e)}
            body = json.dumps(result).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/heartbeat":
            # The reply carries the public URL so the gateway app can build location links without manual setup.
            status, result = 200, {"success": True, "public_url": self.server_instance.public_url}
            try:
                length = int(self.headers.get("Content-Length", 0))
                beat = json.loads(self.rfile.read(length).decode("utf-8") or "null")
                if not isinstance(beat, dict):
                    raise ValueError("body must be a JSON object")
                timestamp = beat.get("timestamp", "")
                battery = beat.get("battery", -1)
                if not isinstance(timestamp, str):
                    raise ValueError('"timestamp" must be an ISO-8601 string')
                if isinstance(battery, bool) or not isinstance(battery, int) or not -1 <= battery <= 100:
                    raise ValueError('"battery" must be an integer 0-100 (-1 if unknown)')
                flags = {}
                for key in ("charging", "screeningRole", "smsGranted", "contactCalls"):
                    value = beat.get(key)
                    if value is not None and not isinstance(value, bool):
                        raise ValueError(f'"{key}" must be true or false')
                    flags[key] = value
                self.server_instance.on_heartbeat(timestamp, battery, flags)
            except (ValueError, UnicodeDecodeError) as e:  # json.JSONDecodeError is a ValueError
                status, result = 400, {"success": False, "error": str(e)}
            body = json.dumps(result).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/ack":
            # A responder acknowledged a caller's incident (gateway app: responder replied "ACK" by SMS).
            try:
                ack = self.read_json_body()
                if not isinstance(ack, dict):
                    raise ValueError("body must be a JSON object")
                number, responder, timestamp = ack.get("number"), ack.get("responder", ""), ack.get("timestamp", "")
                if not isinstance(number, str) or not number.strip():
                    raise ValueError('"number" (the caller being acknowledged) is required')
                if not isinstance(responder, str):
                    raise ValueError('"responder" must be a string')
                if not isinstance(timestamp, str):
                    raise ValueError('"timestamp" must be an ISO-8601 string')
                self.server_instance.on_ack(number.strip(), responder.strip(), timestamp)
                self.send_json(200, {"success": True})
            except (ValueError, UnicodeDecodeError) as e:
                self.send_json(400, {"success": False, "error": str(e)})
        elif path == "/api/resolve":
            # Close an incident (dashboard "resolve" button, or a responder's "RESOLVE <number>" SMS via the gateway).
            try:
                data = self.read_json_body()
                if not isinstance(data, dict):
                    raise ValueError("body must be a JSON object")
                number, by = data.get("number"), data.get("by", "dashboard")
                note, timestamp = data.get("note", ""), data.get("timestamp", "")
                if not isinstance(number, str) or not number.strip():
                    raise ValueError('"number" (the incident to resolve) is required')
                if not isinstance(by, str) or len(by) > 100:
                    raise ValueError('"by" must be a string of at most 100 characters')
                if not isinstance(note, str) or len(note) > MAX_TEXT:
                    raise ValueError(f'"note" must be a string of at most {MAX_TEXT} characters')
                if not isinstance(timestamp, str):
                    raise ValueError('"timestamp" must be an ISO-8601 string')
            except (ValueError, UnicodeDecodeError) as e:
                self.send_json(400, {"success": False, "error": str(e)})
                return
            if self.server_instance.incidents.status_of(number.strip()) is None:
                self.send_json(404, {"success": False, "error": "no incident for this number"})
                return
            self.server_instance.on_resolve(number.strip(), by.strip() or "dashboard", note.strip(), timestamp)
            self.send_json(200, {"success": True})
        elif path == "/api/telemetry":
            try:
                length = int(self.headers.get("Content-Length", 0))
                post_data = self.rfile.read(length).decode("utf-8")
                try:
                    payload = json.loads(post_data)
                except Exception:
                    payload = None
                if isinstance(payload, dict) and isinstance(payload.get("sensors"), dict):
                    # Live stream from the client app's backend sync (Settings → Telemetry backend).
                    self.server_instance.display_telemetry(format_sensor_report(payload["sensors"]),
                                                           sender=str(payload.get("deviceId", "")),
                                                           source="Live sensor stream", live=True)
                    body = b'{"success":true}'
                else:
                    report = (payload.get("report") or payload.get("content")) if isinstance(payload, dict) else None
                    sender = payload.get("sender", "") if isinstance(payload, dict) else ""
                    dispatch = self.server_instance.display_telemetry(report or post_data, sender=sender, source="HTTP REST /api/telemetry")
                    # The gateway app texts these responders ("you are the nearest responder ...").
                    body = json.dumps({"success": True, "dispatch": dispatch or []}).encode("utf-8")
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

    def responder_id_from_path(self, path):
        """'/api/responders/<id>' → id, else None."""
        prefix = "/api/responders/"
        if path.startswith(prefix) and re.fullmatch(r"[0-9a-f]{8}", path[len(prefix):]):
            return path[len(prefix):]
        return None

    def do_PATCH(self):
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)
        if not self.authorized(query):
            self.send_json(401, {"success": False, "error": "admin token required"})
            return
        responder_id = self.responder_id_from_path(path)
        if not responder_id:
            self.send_error(404, "Not Found")
            return
        try:
            responder = self.server_instance.responders.update(responder_id, self.read_json_body(max_bytes=4096))
        except (ValueError, UnicodeDecodeError) as e:
            self.send_json(400, {"success": False, "error": str(e)})
            return
        if responder is None:
            self.send_json(404, {"success": False, "error": "no such responder"})
            return
        self.send_json(200, {"success": True, "responder": responder})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)
        if not self.authorized(query):
            self.send_json(401, {"success": False, "error": "admin token required"})
            return
        responder_id = self.responder_id_from_path(path)
        if not responder_id:
            self.send_error(404, "Not Found")
            return
        if not self.server_instance.responders.delete(responder_id):
            self.send_json(404, {"success": False, "error": "no such responder"})
            return
        self.send_json(200, {"success": True})

class TelemetryServer:
    def __init__(self, host="0.0.0.0", port=8765, http_port=8080, bt_mac="", client_number="", adb_serial="",
                 admin_token="", public_url="", notify=True, data_dir=None, console=True):
        self.host = host
        self.data_dir = os.path.abspath(data_dir or DEFAULT_DATA_DIR)
        os.makedirs(self.data_dir, exist_ok=True)
        # Interactive console (Enter = test call, "t" = test telemetry): off with --no-console or when stdin is not a TTY.
        self.console_enabled = bool(console)
        self.stop_event = None  # asyncio.Event set by SIGTERM/SIGINT for a clean shutdown
        # macOS notifications for new/reopened incidents, acks, resolutions and a silent gateway phone.
        self.notify_enabled = notify and IS_MAC
        self.started_epoch = time.time()
        self.stale_state = "unknown"  # "unknown" until the first heartbeat or the stale period passes
        # Optional KAAKA_ADMIN_TOKEN protects the dashboard and gateway endpoints (location links stay public).
        self.admin_token = admin_token
        self.public_url = public_url.rstrip("/")
        self.incidents = IncidentStore(os.path.join(self.data_dir, "events.jsonl"))
        # Responders (volunteers with a home position) for nearest-responder routing; <data dir>/responders.json.
        self.responders = ResponderRegistry(os.path.join(self.data_dir, "responders.json"))
        self.port = port
        self.http_port = http_port
        self.bt_mac = bt_mac
        # Client (sensor) phone number: its SMS are treated as telemetry. Matched on the last 10 digits.
        client_digits = re.sub(r"\D", "", client_number or "")
        self.client_suffix = client_digits[-10:]
        self.adb_serial = adb_serial
        self.local_ip = get_local_ip()
        self.connected_clients = set()
        self.loop = None
        self.telephony_service = "org.pipewire.Telephony"
        self.last_detected_number = None
        self.last_call_file = os.path.join(self.data_dir, "last_call.json")
        if os.path.exists(self.last_call_file):
            try:
                with open(self.last_call_file, "r") as f:
                    self.last_detected_number = json.load(f).get("number") or None
            except Exception:
                pass
        self.last_call_time = 0
        self.last_call_number = None
        self.telemetry_file = os.path.join(self.data_dir, "latest_telemetry.json")
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
        # Real-time voice AI conversation enabled on Linux. On macOS there is no call audio
        # (IOBluetooth refuses SCO), so default to 1-ring hangup mode; the toggle still works.
        self.auto_answer_mode = not IS_MAC
        if not IS_MAC:
            ensure_audio_sinks()
        self.audio_bridge = AudioConversationBridge(on_event=self.on_audio_bridge_event)
        # Without --bt-mac the phone's gateway app handles calls and reports them via /api/call-event.
        self.bt_enabled = bool(bt_mac)
        if self.bt_enabled and not IS_MAC:
            load_linux_dbus()
        self.last_gateway_event = None
        self.last_heartbeat = None  # latest POST /api/heartbeat from the gateway phone
        self.location_last_accepted = {}  # token -> epoch of the last accepted /api/location update
        self.hfp = None
        if IS_MAC and self.bt_enabled:
            self.hfp = HfpBridgeClient(
                bt_mac,
                on_incoming_call=self.on_mac_incoming_call,
                on_call_active=lambda: print(f"[{format_timestamp()}] 📞 Call active (answered).", flush=True),
                on_call_ended=self.on_mac_call_ended,
                log=lambda m: print(f"[{format_timestamp()}] {m}", flush=True),
            )

    def on_mac_incoming_call(self, number, name=""):
        """hfp-bridge incoming_call event (macOS)."""
        self.on_call_detected(number, name=name, state="incoming")

    def on_mac_call_ended(self):
        print(f"[{format_timestamp()}] 📴 Call ended. Stopping audio conversation bridge.", flush=True)
        self.audio_bridge.notify_call_ended()

    def on_audio_bridge_event(self, event):
        if self.loop:
            asyncio.run_coroutine_threadsafe(self.broadcast(event), self.loop)

    def check_bluetooth_connected(self) -> bool:
        """Check if Phone A (bt_mac) is connected to BlueZ."""
        if not self.bt_enabled:
            return False
        if IS_MAC:
            return bool(self.hfp and self.hfp.connected)
        try:
            bus = dbus.SystemBus()
            dev = bus.get_object("org.bluez", f"/org/bluez/hci0/dev_{self.bt_mac.replace(':', '_')}")
            props = dbus.Interface(dev, "org.freedesktop.DBus.Properties")
            return bool(props.Get("org.bluez.Device1", "Connected"))
        except Exception:
            return False

    def check_telephony_ag_online(self) -> bool:
        """Check if PipeWire Telephony Handsfree Audio Gateway service is online."""
        if not self.bt_enabled:
            return False
        if IS_MAC:
            return bool(self.hfp and self.hfp.connected)
        try:
            bus = dbus.SessionBus()
            bus.get_object(self.telephony_service, "/org/pipewire/Telephony/ag1")
            return True
        except Exception:
            return False

    def display_telemetry(self, raw_content: str, sender: str = "", source: str = "BLE / Bluetooth MAP", live: bool = False):
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

        if live:
            # Continuous stream (about once a second): no console banner, no disk write.
            self.latest_telemetry = {"content": clean_text, "sender": sender, "source": source,
                                     "timestamp": ts, "update_count": self.telemetry_count}
            if self.loop and self.connected_clients:
                asyncio.run_coroutine_threadsafe(self.broadcast({"type": "TELEMETRY_RECEIVED", **self.latest_telemetry}), self.loop)
            return

        print("\n" + "=" * 65, flush=True)
        print(f"\033[1;31m[{ts}] 🚨 KAAKA SENSOR TELEMETRY RECEIVED (Update #{self.telemetry_count})\033[0m", flush=True)
        print(f"\033[1;36m  Channel Source  : \033[0m{source_label}", flush=True)
        print("=" * 65, flush=True)
        print(f"\033[1;32m{clean_text}\033[0m", flush=True)
        print("=" * 65 + "\n", flush=True)

        before = self.incidents.status_of(sender)
        dispatch = []
        alert_event = self.incidents.add_alert(sender, clean_text, source)
        if alert_event:
            self.notify_if_opened(sender, before, f"alert from {sender or 'unknown sender'}")
            if "lat" in alert_event:
                dispatch = self.maybe_dispatch(sender)

        # Store latest telemetry in memory and persist to disk
        self.latest_telemetry = {
            "content": clean_text,
            "sender": sender,
            "source": source,
            "timestamp": ts,
            "update_count": self.telemetry_count
        }
        try:
            write_json_atomic(self.telemetry_file, self.latest_telemetry, indent=2)
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
        return dispatch

    def maybe_dispatch(self, number):
        """
        The first time an open incident has a location, ask the 1-2 nearest available responders to go.
        Later reports of the same open incident do not dispatch again; a resolved incident that reopens does.
        Returns the dispatch list (possibly empty).
        """
        inc = self.incidents._build().get(number_key(number))
        if not inc or inc["status"] == "resolved" or inc["dispatched"] or not inc["latest_location"]:
            return []
        loc = inc["latest_location"]
        nearest = self.responders.nearest(loc["lat"], loc["lon"], limit=2)
        if not nearest:
            return []
        dispatch = [{"name": r["name"], "number": r["number"], "distance_km": r["distance_km"],
                     "eta_min": r["eta_min"], "maps_url": loc["maps_url"]} for r in nearest]
        self.incidents.add_dispatch(inc["number"], dispatch)
        who = ", ".join(f"{d['name']} ({d['distance_km']} km, ~{d['eta_min']} min)" for d in dispatch)
        print(f"[{format_timestamp()}] 🚨 Dispatch for {inc['number']}: {who}", flush=True)
        self.notify(f"Dispatch for {inc['number']}: {who}")
        if self.loop:
            payload = {"type": "RESPONDER_DISPATCHED", "number": inc["number"], "dispatch": dispatch,
                       "timestamp": format_timestamp()}
            asyncio.run_coroutine_threadsafe(self.broadcast(payload), self.loop)
        return dispatch

    def incidents_with_nearest(self):
        """Incidents plus, for each one with a location, the 3 nearest available responders (distance, ETA)."""
        return self.add_nearest(self.incidents.incidents())

    def add_nearest(self, incidents):
        for inc in incidents:
            loc = inc.get("latest_location")
            inc["nearest_responders"] = (
                self.responders.nearest(loc["lat"], loc["lon"], limit=3) if loc else []
            )
        return incidents

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

    def save_last_caller(self, number, name=""):
        """Remember the last real caller across restarts (server/last_call.json, not committed)."""
        self.last_detected_number = number
        try:
            write_json_atomic(self.last_call_file, {"number": number, "name": str(name), "timestamp": format_timestamp()})
        except Exception:
            pass

    def check_admin_token(self, token) -> bool:
        if not self.admin_token:
            return True
        return hmac.compare_digest(str(token or "").encode("utf-8"), self.admin_token.encode("utf-8"))

    def notify(self, text):
        if self.notify_enabled:
            notify_mac(text)

    def notify_if_opened(self, number, before, what):
        """Notify when an incident becomes open: a new one, or a resolved/acknowledged one with new activity."""
        if before != "open" and self.incidents.status_of(number) == "open":
            label = "New incident" if before is None else "Incident reopened"
            self.notify(f"{label}: {what}")

    def on_call_event(self, number, state, sms, timestamp, token=None, message=None):
        """A call or help SMS the gateway app already handled (POST /api/call-event). Never hangs up or sends SMS here."""
        self.last_gateway_event = format_timestamp()
        before = self.incidents.status_of(number)
        self.incidents.add_call(number, state, sms, timestamp, token, message)
        if number:
            self.save_last_caller(number)
        sms_text = {"sent": "auto-reply sent", "failed": "auto-reply FAILED", "skipped": "no auto-reply"}[sms]
        who = number or "unknown (no caller ID)"
        if state == "sms":
            quoted = f": “{message}”" if message else ""
            print(f"[{format_timestamp()}] 💬 Help SMS from {who}{quoted} — {sms_text} (phone time {timestamp})", flush=True)
            self.notify_if_opened(number, before, f"help SMS from {who}{quoted}")
        else:
            print(f"[{format_timestamp()}] 📞 Gateway app call: {who} — {state}, {sms_text} (phone time {timestamp})", flush=True)
            self.notify_if_opened(number, before, f"call from {who} ({state}, {sms_text})")
        if self.loop:
            # Separate type from CALL_DETECTED so gateway apps don't treat it as a request to send another SMS.
            payload = {"type": "CALL_EVENT", "number": number, "name": "", "state": state, "sms": sms,
                       "source": "gateway_app", "timestamp": timestamp or format_timestamp()}
            if message:
                payload["message"] = message
            asyncio.run_coroutine_threadsafe(self.broadcast(payload), self.loop)

    # Live sharing from the location page: accept at most one update per token every 10 s.
    LOCATION_MIN_INTERVAL = 10.0

    def accept_location_update(self, token) -> bool:
        now = time.time()
        last = self.location_last_accepted.get(token, 0)
        if now - last < self.LOCATION_MIN_INTERVAL:
            return False
        self.location_last_accepted[token] = now
        return True

    def on_location(self, token, lat, lon, accuracy):
        """A caller shared their location through the SMS link (POST /api/location)."""
        event = self.incidents.add_location(token, lat, lon, accuracy)
        number = event["number"] or "unknown caller"
        acc_text = f" ±{round(accuracy)} m" if accuracy is not None else ""
        print(f"[{format_timestamp()}] 📍 Location shared by {number}: {lat:.6f}, {lon:.6f}{acc_text} {event['maps_url']}", flush=True)
        if self.loop:
            payload = {"type": "LOCATION_SHARED", "number": event["number"], "lat": lat, "lon": lon,
                       "accuracy": accuracy, "maps_url": event["maps_url"], "timestamp": event["received"]}
            asyncio.run_coroutine_threadsafe(self.broadcast(payload), self.loop)
        if event["number"]:
            self.maybe_dispatch(event["number"])

    def on_ack(self, number, responder, timestamp):
        """A responder acknowledged a caller's incident (POST /api/ack)."""
        event = self.incidents.add_ack(number, responder, timestamp)
        print(f"[{format_timestamp()}] ✅ Incident for {number} acknowledged by {responder or 'a responder'}", flush=True)
        self.notify(f"Acknowledged: {number} by {responder or 'a responder'}")
        if self.loop:
            payload = {"type": "INCIDENT_ACK", "number": number, "responder": responder, "timestamp": event["received"]}
            asyncio.run_coroutine_threadsafe(self.broadcast(payload), self.loop)

    def on_resolve(self, number, by, note, timestamp):
        """An incident was closed (POST /api/resolve)."""
        event = self.incidents.add_resolve(number, by, note, timestamp)
        note_text = f": {note}" if note else ""
        if by == "caller":
            print(f"[{format_timestamp()}] ☑️ Caller {number} reported safe — incident closed", flush=True)
            self.notify(f"Caller reported safe: {number}")
        else:
            print(f"[{format_timestamp()}] ☑️ Incident for {number} resolved by {by}{note_text}", flush=True)
            self.notify(f"Resolved: {number} by {by}{note_text}")
        if self.loop:
            payload = {"type": "INCIDENT_RESOLVED", "number": number, "by": by, "note": note, "timestamp": event["received"]}
            asyncio.run_coroutine_threadsafe(self.broadcast(payload), self.loop)

    # No heartbeat for this long = gateway phone silent (default 20 min; KAAKA_STALE_SECONDS for testing).
    HEARTBEAT_STALE_SECONDS = int(os.environ.get("KAAKA_STALE_SECONDS", "1200"))

    def check_gateway_stale(self):
        """Broadcast GATEWAY_STALE (and notify) when the gateway phone goes silent or comes back."""
        if self.last_heartbeat is None and time.time() - self.started_epoch <= self.HEARTBEAT_STALE_SECONDS:
            return  # just started: give the phone one heartbeat period before calling it silent
        state = "stale" if self.gateway_stale() else "fresh"
        previous, self.stale_state = self.stale_state, state
        if state == previous or (previous == "unknown" and state == "fresh"):
            return
        last_seen = self.last_heartbeat["received"] if self.last_heartbeat else None
        if state == "stale":
            print(f"[{format_timestamp()}] ⚠️ Gateway phone silent: no heartbeat since {last_seen or 'server start'}", flush=True)
            self.notify(f"Gateway phone silent: no heartbeat since {last_seen or 'server start'}")
        else:
            print(f"[{format_timestamp()}] 💚 Gateway phone back online", flush=True)
            self.notify("Gateway phone back online")
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast({"type": "GATEWAY_STALE", "stale": state == "stale", "last_seen": last_seen}), self.loop)

    async def stale_monitor(self):
        interval = max(1, min(60, self.HEARTBEAT_STALE_SECONDS // 3))
        while True:
            await asyncio.sleep(interval)
            try:
                self.check_gateway_stale()
            except Exception as e:
                print(f"[{format_timestamp()}] stale check error: {e}", flush=True)

    def gateway_stale(self) -> bool:
        """True when the gateway phone has not sent a heartbeat in the last 20 minutes (or none since start)."""
        if not self.last_heartbeat:
            return True
        return time.time() - self.last_heartbeat["received_epoch"] > self.HEARTBEAT_STALE_SECONDS

    def on_heartbeat(self, timestamp, battery, flags):
        """Periodic status from the gateway phone (POST /api/heartbeat)."""
        self.last_heartbeat = {
            "timestamp": timestamp,
            "received": format_timestamp(),
            "received_epoch": time.time(),
            "battery": battery,
            **flags,
        }
        battery_text = f"{battery}%" if battery >= 0 else "battery unknown"
        if flags.get("charging"):
            battery_text += " charging"
        print(f"[{format_timestamp()}] 💓 Gateway heartbeat: {battery_text}", flush=True)
        problems = [label for key, label in (("screeningRole", "call screening role"), ("smsGranted", "SMS permission"),
                                             ("contactCalls", "contact-call permissions")) if flags.get(key) is False]
        if 0 <= battery < 20 and not flags.get("charging"):
            problems.append(f"battery low ({battery}%)")
        if problems:
            print(f"[{format_timestamp()}] ⚠️ Gateway phone needs attention: {', '.join(problems)}", flush=True)
        if self.loop:
            asyncio.run_coroutine_threadsafe(self.broadcast({"type": "GATEWAY_HEARTBEAT", **self.last_heartbeat}), self.loop)
        self.check_gateway_stale()

    def is_local_ip(self, ip) -> bool:
        """Connections from this machine (e.g. the dashboard in a local browser) are not phones."""
        return ip in ("127.0.0.1", "::1", self.local_ip)

    def phone_client_ips(self):
        return sorted({str(c.remote_address[0]) for c in self.connected_clients if not self.is_local_ip(str(c.remote_address[0]))})

    def is_client_sender(self, sender) -> bool:
        """True if sender matches the configured client phone number (--client-number)."""
        return bool(self.client_suffix) and self.client_suffix in re.sub(r"\D", "", str(sender))

    def on_call_detected(self, number, name="", state="active", raw_path=""):
        """Called from D-Bus thread when a call is extracted."""
        clean_num = str(number).strip()
        if clean_num == "Unknown":
            clean_num = ""  # no caller ID: never substitute a number (the gateway would SMS it)

        now = time.time()
        # Deduplicate triggers for the same number within 3 seconds
        if self.last_call_number == clean_num and (now - self.last_call_time) < 3:
            print(f"[{format_timestamp()}] ⏳ Debounced: Duplicate trigger for {clean_num} ignored (<3s)")
            return

        self.last_call_time = now
        self.last_call_number = clean_num
        if clean_num:
            self.save_last_caller(clean_num, name)
        self.pending_call_trigger = {
            "number": clean_num,
            "name": str(name),
            "state": str(state),
            "timestamp": now
        }

        print("\n" + "=" * 60)
        print(f"[{format_timestamp()}] 📞 NEW CALL EXTRACTED FROM BLUETOOTH HANDSFREE")
        print("=" * 60)
        print(f"  📱 Phone Number : \033[1;32m{clean_num or 'unknown (no caller ID)'}\033[0m")
        if name:
            print(f"  👤 Contact Name : {name}")
        print(f"  ⚡ Call State   : {state}")

        phone_clients = self.phone_client_ips()
        if phone_clients:
            print(f"  📶 Gateway App Link : \033[1;32mConnected ({', '.join(phone_clients)})\033[0m")
        else:
            if IS_MAC:
                print("  ⚠️ Gateway App Link : \033[1;33mnot connected — no auto-reply SMS unless the app connects within 45 s\033[0m")
            else:
                print("  ℹ️ Gateway App is in background/standby (Direct Bluetooth MAP active)")
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
        if clean_num:
            threading.Thread(target=self.push_sms_via_bluetooth_map, args=(clean_num, "received call. will get back to you shortly."), daemon=True).start()
        else:
            print(f"[{format_timestamp()}] ℹ️ No caller number, so no auto-reply SMS.")

        # 3. WebSocket broadcast to connected apps
        if self.loop:
            asyncio.run_coroutine_threadsafe(self.broadcast(payload), self.loop)

    def auto_answer_call(self, raw_path=""):
        """Auto-answers incoming call so caller audio connects to Bluetooth Handsfree."""
        if IS_MAC:
            def _answer_mac():
                time.sleep(0.5)
                if self.hfp and self.hfp.answer():
                    print(f"[{format_timestamp()}] 📞 Call answered via hfp-bridge.")
                    print(f"[{format_timestamp()}] ℹ️ Call audio is unsupported on macOS (IOBluetooth SCO); AI audio bridge not started. Audio stays on the phone.")
                else:
                    print(f"[{format_timestamp()}] ℹ️ Simulated call test (hfp-bridge not running). Nothing to answer.")
            threading.Thread(target=_answer_mac, daemon=True).start()
            return

        def _answer():
            time.sleep(0.5)  # 500ms allows 1 ring setup and caller ID capture
            if dbus is None:
                print(f"[{format_timestamp()}] ℹ️ Simulated call test (no Bluetooth telephony: --bt-mac not set). Nothing to answer.")
                return
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
                print(f"[{format_timestamp()}] 🎙️ Real call connected on the gateway phone! Activating Real-Time AI Audio Conversation Bridge...")
                self.audio_bridge.notify_call_started()
            else:
                print(f"[{format_timestamp()}] ℹ️ Simulated call test (no hardware call). Audio bridge remains in standby.")

        threading.Thread(target=_answer, daemon=True).start()

    def auto_hangup_call(self, raw_path=""):
        """Terminates trigger call after 1 ring (< 0.5s) to release voice bearer and clear InCallUI on caller's phone."""
        if IS_MAC:
            def _hangup_mac():
                time.sleep(0.4)
                if self.hfp and self.hfp.hangup():
                    print(f"[{format_timestamp()}] ⚡ 1-Ring Trigger: hangup sent via hfp-bridge.")
                else:
                    print(f"[{format_timestamp()}] ℹ️ Hangup skipped (hfp-bridge not running).")
            threading.Thread(target=_hangup_mac, daemon=True).start()
            return

        def _hangup():
            time.sleep(0.4)  # 400ms allows 1 clean ring and caller ID capture
            if dbus is None:
                print(f"[{format_timestamp()}] ℹ️ Hangup skipped (no Bluetooth telephony: --bt-mac not set).")
                return
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
        if IS_MAC or dbus is None:
            return  # No MAP client on macOS / without --bt-mac; the Gateway app sends the SMS on CALL_DETECTED.
        try:
            bus = dbus.SessionBus()
            if not self.map_session_path:
                return
            mas_obj = bus.get_object("org.bluez.obex", self.map_session_path)
            mas = dbus.Interface(mas_obj, "org.bluez.obex.MessageAccess1")

            clean_target = str(target_number).strip().replace(" ", "")
            if not clean_target:
                return

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

    def ws_process_request(self, connection, request):
        """WebSocket handshake check when KAAKA_ADMIN_TOKEN is set (header, ?token= or dashboard cookie)."""
        if not self.admin_token:
            return None
        query = parse_qs(urlparse(request.path).query)
        token = (request.headers.get("X-Kaaka-Token") or (query.get("token") or [""])[0]
                 or cookie_token(request.headers.get("Cookie")))
        if self.check_admin_token(token):
            return None
        return connection.respond(401, "admin token required\n")

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
            "last_number": self.last_detected_number,
            "telemetry_count": self.telemetry_count,
            "latest_telemetry": self.latest_telemetry,
            "timestamp": format_timestamp()
        }
        await websocket.send(json.dumps(welcome_payload))

        # Replay any recent pending call trigger (<45s old) to newly connected phone
        if self.pending_call_trigger and not self.is_local_ip(client_addr[0]):
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
            if 'Kaaka' in subj or 'Sensors' in subj or 'Live Sensors' in subj or 'Pedometer' in subj or self.is_client_sender(sender) or subj.startswith('proto:'):
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
                latest_sender = ""
                for path, meta in msgs.items():
                    msg_id = str(path)
                    self.processed_msg_ids.add(msg_id)
                    subj = str(meta.get('Subject', ''))
                    sender = str(meta.get('SenderAddress', ''))
                    if latest_alert is None and (self.is_client_sender(sender) or 'Kaaka' in subj or subj.startswith('proto:')):
                        full_content = fetch_full_message(path)
                        if full_content and ('Kaaka' in full_content or 'Live Sensors' in full_content or 'Pedometer' in full_content):
                            latest_alert = full_content
                            latest_sender = sender
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
            print(f"[{format_timestamp()}] 🖥️ Web Dashboard UI active: \033[1;32mhttp://{self.local_ip}:{self.http_port}/admin\033[0m (landing page at /)")
            httpd.serve_forever()
        except Exception as e:
            print(f"[{format_timestamp()}] HTTP server error: {e}")

    def console_available(self) -> bool:
        """The interactive console needs a real terminal on stdin (not a service, pipe or /dev/null)."""
        if not self.console_enabled:
            return False
        try:
            return sys.stdin is not None and sys.stdin.isatty()
        except (AttributeError, ValueError):
            return False

    async def console_trigger_loop(self):
        """Allows testing in terminal: press Enter to test call, or type 't' to test telemetry."""
        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        try:
            await loop.connect_read_pipe(lambda: protocol, sys.stdin)
        except Exception as e:
            print(f"[{format_timestamp()}] ℹ️ Console disabled (stdin not readable: {e})", flush=True)
            return

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
                        "• Location: unavailable"
                    )
                    self.display_telemetry(sample_alert, sender="simulated", source="Simulated Test")
                else:
                    test_number = text
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
        Polls content://sms every 30 seconds, so SMS telemetry can take up to 30 s to appear.
        The client's direct WebSocket copy (CLIENT_TELEMETRY) is the faster path.
        """
        adb_seen_ids = set()
        initialized = False

        while True:
            try:
                target_cmd = ["adb", "-s", self.adb_serial] if self.adb_serial else ["adb"]
                where = "body LIKE '%Kaaka%'"
                if self.client_suffix:
                    where = f"address LIKE '%{self.client_suffix}%' OR " + where
                cmd = target_cmd + ["shell", f"content query --uri content://sms --where \"{where}\""]
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
                                s_addr = addr_m.group(1) if addr_m else ""
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
                                        s_addr = addr_m.group(1) if addr_m else ""
                                        self.display_telemetry(b_text, sender=s_addr, source="Phone ADB Telephony Ingest")
            except Exception:
                pass
            time.sleep(30)

    async def start(self):
        self.loop = asyncio.get_running_loop()

        if not self.bt_enabled:
            print(f"[{format_timestamp()}] ℹ️ Bluetooth call handling off: calls are reported by the gateway app.")
        elif IS_MAC:
            # macOS: Swift hfp-bridge (IOBluetooth) replaces the D-Bus telephony listener + HFP watchdog
            self.hfp.start()
            print(f"[{format_timestamp()}] ℹ️ PipeWire/oFono D-Bus telephony listener is Linux-only (replaced by hfp-bridge).")
            print(f"[{format_timestamp()}] ℹ️ Bluetooth MAP SMS listener is Linux-only (no MAP API on macOS); use ADB/HTTP/WebSocket telemetry.")
            print(f"[{format_timestamp()}] ℹ️ BlueZ Handsfree watchdog is Linux-only (hfp-bridge reconnects itself).")
        else:
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
        if self.bt_enabled and not IS_MAC:
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
        print(f"  🏠 Landing page    : \033[1;36m{self.http_port}\033[0m  (\033[1;32mhttp://{self.local_ip}:{self.http_port}/\033[0m)")
        print(f"  🖥️ Web Dashboard UI: \033[1;36m{self.http_port}\033[0m  (\033[1;32mhttp://{self.local_ip}:{self.http_port}/admin\033[0m)")
        print(f"  📶 Gateway BLE MAC : \033[1;36m{self.bt_mac or 'off (gateway app mode)'}\033[0m")
        print(f"  🔗 Public URL      : \033[1;36m{self.public_url or 'not set (location links off)'}\033[0m")
        print(f"  🔒 Admin token     : \033[1;36m{'on' if self.admin_token else 'off'}\033[0m")
        print(f"  🔔 Notifications   : \033[1;36m{'on (macOS)' if self.notify_enabled else 'off'}\033[0m")
        print("=" * 65)
        print(f"  📁 Data directory  : \033[1;36m{self.data_dir}\033[0m")
        print("=" * 65)
        print("  💡 Tip: Open /admin in a browser for the dashboard and live sensors.")
        console = self.console_available()
        if console:
            print("  💡 Tip: Press [Enter] to simulate a call test.")
            print("  💡 Tip: Type 't' + [Enter] to simulate sensor telemetry display.")
        else:
            print("  ℹ️ Console off (--no-console or stdin is not a terminal); use POST /api/trigger-call to test.")
        print("=" * 65 + "\n", flush=True)

        self.stop_event = asyncio.Event()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                self.loop.add_signal_handler(sig, self.request_stop, sig)
            except (NotImplementedError, RuntimeError, ValueError):
                pass  # not supported on this platform/thread: KeyboardInterrupt still stops the server
        async with websockets.serve(self.handle_client, self.host, self.port, process_request=self.ws_process_request):
            if console:
                asyncio.create_task(self.console_trigger_loop())
            asyncio.create_task(self.stale_monitor())
            await self.stop_event.wait()  # run until SIGTERM / Ctrl-C

    def request_stop(self, sig=None):
        """Signal handler (event-loop thread): stop the WebSocket server; the daemon threads exit with the process."""
        if self.stop_event and not self.stop_event.is_set():
            name = signal.Signals(sig).name if sig is not None else "stop"
            print(f"\n[{format_timestamp()}] {name} received, shutting down...", flush=True)
            self.stop_event.set()

def main():
    parser = argparse.ArgumentParser(description="Kaaka Bluetooth Call & Telemetry Server")
    parser.add_argument("--port", "-p", type=int, default=8765, help="WebSocket port (default: 8765)")
    parser.add_argument("--http-port", type=int, default=8080, help="Web Dashboard HTTP port (default: 8080)")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface (default: 0.0.0.0)")
    parser.add_argument("--bt-mac", default=os.environ.get("KAAKA_BT_MAC", ""), help="Gateway phone Bluetooth address (or KAAKA_BT_MAC); optional — without it the gateway app reports calls")
    parser.add_argument("--client-number", default=os.environ.get("KAAKA_CLIENT_NUMBER", ""), help="Client (sensor) phone number whose SMS are telemetry (or KAAKA_CLIENT_NUMBER); optional")
    parser.add_argument("--adb-serial", default=os.environ.get("KAAKA_ADB_SERIAL", ""), help="adb serial of the phone to read SMS from (or KAAKA_ADB_SERIAL); optional")
    parser.add_argument("--public-url", default=os.environ.get("KAAKA_PUBLIC_URL", ""), help="Public https URL of this server (or KAAKA_PUBLIC_URL); shown for reference, the gateway app builds the links")
    parser.add_argument("--no-notify", action="store_true", help="Disable macOS notifications (or KAAKA_NOTIFY=0)")
    parser.add_argument("--no-console", action="store_true",
                        help="Disable the interactive console (also off automatically when stdin is not a terminal, or KAAKA_CONSOLE=0)")
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR,
                        help="Directory for events.jsonl, responders.json and other runtime data (or KAAKA_DATA_DIR; default: the server directory)")
    parser.add_argument("--allow-unprotected-public", action="store_true",
                        help="Allow a public URL without KAAKA_ADMIN_TOKEN (not recommended)")
    args = parser.parse_args()
    # A public URL exposes the dashboard and gateway endpoints to the internet: require the admin token.
    if args.public_url and not os.environ.get("KAAKA_ADMIN_TOKEN") and not args.allow_unprotected_public:
        parser.error("a public URL (--public-url / KAAKA_PUBLIC_URL) needs KAAKA_ADMIN_TOKEN, otherwise anyone "
                     "on the internet can read callers' numbers and locations. Set KAAKA_ADMIN_TOKEN "
                     "(and the same token in Kaaka Call), or pass --allow-unprotected-public.")

    server = TelemetryServer(host=args.host, port=args.port, http_port=args.http_port, bt_mac=args.bt_mac,
                             client_number=args.client_number, adb_serial=args.adb_serial,
                             admin_token=os.environ.get("KAAKA_ADMIN_TOKEN", ""), public_url=args.public_url,
                             notify=not args.no_notify and os.environ.get("KAAKA_NOTIFY", "1") != "0",
                             data_dir=args.data_dir,
                             console=not args.no_console and os.environ.get("KAAKA_CONSOLE", "1") != "0")
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        pass
    print("Server stopped.", flush=True)

if __name__ == "__main__":
    main()
