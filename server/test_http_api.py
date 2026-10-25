"""HTTP API checks for server/server.py: the dashboard handler on a free port with a temporary data directory.
Run: cd server && python -m unittest -q   (standard library only)."""

import contextlib
import http.client
import io
import json
import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import server as kaaka  # noqa: E402

VERSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "VERSION")
LANDING_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site", "index.html")
SECURITY_HEADERS = {"X-Content-Type-Options": "nosniff", "Referrer-Policy": "strict-origin-when-cross-origin", "X-Frame-Options": "DENY"}


class HttpServerCase(unittest.TestCase):
    """Starts one TelemetryServer HTTP endpoint per class (http_port=0 picks a free port)."""
    admin_token = ""
    demo_pin = ""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        os.environ["KAAKA_DATA_DIR"] = cls.tmp.name
        cls.addClassCleanup(os.environ.pop, "KAAKA_DATA_DIR", None)
        quiet = contextlib.redirect_stdout(io.StringIO())  # the server prints a banner per event
        quiet.__enter__()
        cls.addClassCleanup(quiet.__exit__, None, None, None)
        cls.server = kaaka.TelemetryServer(host="127.0.0.1", port=0, http_port=0, admin_token=cls.admin_token, demo_pin=cls.demo_pin,
                                           notify=False, data_dir=cls.tmp.name, console=False)
        cls.httpd = cls.server.make_http_server()
        cls.port = cls.server.http_port
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.addClassCleanup(cls.httpd.server_close)
        cls.addClassCleanup(cls.httpd.shutdown)

    def request(self, method, path, body=None, headers=None):
        """(status, headers, body bytes); a dict body is sent as JSON."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            data = json.dumps(body).encode("utf-8") if isinstance(body, (dict, list)) else body
            conn.request(method, path, body=data, headers=headers or {})
            resp = conn.getresponse()
            return resp.status, resp.headers, resp.read()
        finally:
            conn.close()

    def get_json(self, path, headers=None):
        status, _, body = self.request("GET", path, headers=headers)
        return status, json.loads(body)

    def post_json(self, path, body, headers=None):
        status, _, out = self.request("POST", path, body, {"Content-Type": "application/json", **(headers or {})})
        return status, json.loads(out)

    def report_call(self, number, token=None):
        event = {"number": number, "state": "rejected", "sms": "sent", "timestamp": "2026-10-25T10:00:00"}
        if token:
            event["token"] = token
        status, out = self.post_json("/api/call-event", event)
        self.assertEqual((status, out), (200, {"success": True}))


class OpenServerTests(HttpServerCase):
    """No KAAKA_ADMIN_TOKEN: everything is reachable, as on a LAN."""

    def test_landing_page_is_served_at_root(self):
        with open(LANDING_FILE, "rb") as f:
            expected = f.read()
        for path in ("/", "/index.html"):
            status, headers, body = self.request("GET", path)
            self.assertEqual(status, 200, path)
            self.assertIn("text/html", headers["Content-Type"])
            self.assertEqual(body, expected)

    def test_docs_are_served(self):
        status, headers, _ = self.request("GET", "/docs")
        self.assertEqual((status, headers["Location"]), (301, "/docs/"))
        for path, kind in (("/docs/", "text/html"), ("/docs/sms-commands.html", "text/html"), ("/docs/docs.css", "text/css")):
            status, headers, body = self.request("GET", path)
            self.assertEqual(status, 200, path)
            self.assertIn(kind, headers["Content-Type"])
            self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        status, _, body = self.request("GET", "/docs/")
        self.assertIn(b"Kaaka docs", body)

    def test_icons_are_served(self):
        for path, kind in (("/favicon.ico", "image/x-icon"), ("/icons/favicon.svg", "image/svg+xml"),
                           ("/icons/apple-touch-icon.png", "image/png"), ("/icons/site.webmanifest", "application/manifest+json")):
            status, headers, body = self.request("GET", path)
            self.assertEqual(status, 200, path)
            self.assertEqual(headers["Content-Type"], kind, path)
            self.assertIn("max-age", headers["Cache-Control"], path)
            self.assertTrue(body, path)
        for path in ("/icons/../server/server.py", "/icons/x.html", "/icons/a/b.png", "/icons/nope.png"):
            self.assertEqual(self.request("GET", path)[0], 404, path)

    def test_docs_reject_traversal_and_unknown_pages(self):
        for path in ("/docs/../server/server.py", "/docs/%2e%2e/VERSION", "/docs/build_docs.py", "/docs/nope.html", "/docs/a/b.html"):
            status, _, _ = self.request("GET", path)
            self.assertEqual(status, 404, path)

    def test_admin_without_token_configured(self):
        status, headers, body = self.request("GET", "/admin")
        self.assertEqual(status, 200)
        self.assertIn(b"<title>kaaka / server</title>", body)
        self.assertIsNone(headers.get("Set-Cookie"))

    def test_health_is_public_and_minimal(self):
        status, headers, body = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/json")
        health = json.loads(body)
        with open(VERSION_FILE, encoding="utf-8") as f:
            version = f.read().strip()
        self.assertEqual(set(health), {"ok", "version", "uptime_seconds", "gateway_online"})
        self.assertIs(health["ok"], True)
        self.assertEqual(health["version"], version)
        self.assertEqual(version, kaaka.VERSION)
        self.assertGreaterEqual(health["uptime_seconds"], 0)
        self.assertIs(health["gateway_online"], False)

    def test_security_headers_on_every_response(self):
        for path, cached in (("/", None), ("/admin", "no-store"), ("/api/health", "no-store"),
                             ("/api/status", "no-store"), ("/l/unknowntoken1", None), ("/nope", None)):
            status, headers, _ = self.request("GET", path)
            for name, value in SECURITY_HEADERS.items():
                self.assertEqual(headers.get(name), value, f"{name} on {path} ({status})")
            if cached:
                self.assertEqual(headers.get("Cache-Control"), cached, path)
            self.assertLessEqual(len(headers.get_all("Cache-Control") or []), 1, f"duplicate Cache-Control on {path}")

    def test_call_event_creates_incident(self):
        self.report_call("+919800000011", token="tok_incident_1")
        status, data = self.get_json("/api/incidents")
        self.assertEqual(status, 200)
        inc = next(i for i in data["incidents"] if i["number"] == "+919800000011")
        self.assertEqual(inc["status"], "open")
        self.assertEqual(len(inc["calls"]), 1)
        self.assertTrue(inc["calls"][0]["location_link"])
        self.assertEqual(self.get_json("/api/incidents/9800000011")[1]["incident"]["number"], "+919800000011")
        self.assertEqual(self.get_json("/api/incidents?status=open&q=0011")[1]["total"], 1)
        self.assertEqual(self.post_json("/api/call-event", {"number": "+91", "state": "nope", "sms": "sent"})[0], 400)
        # The event is on disk in the temporary data directory, not in the server directory.
        with open(os.path.join(self.tmp.name, "events.jsonl"), encoding="utf-8") as f:
            self.assertTrue(any(json.loads(line).get("number") == "+919800000011" for line in f))

    def test_location_validation_and_rate_limit(self):
        self.report_call("+919800000022", token="tok_location_2")
        for bad in ({"token": "bad token!", "lat": 10.0, "lon": 76.0}, {"token": "tok_location_2", "lat": 95, "lon": 76.0},
                    {"token": "tok_location_2", "lat": 10.0, "lon": 76.0, "accuracy": -1}, [1, 2]):
            status, out = self.post_json("/api/location", bad)
            self.assertEqual(status, 400, bad)
            self.assertFalse(out["success"])
        status, _ = self.post_json("/api/location", {"token": "tok_unknown_99", "lat": 10.0, "lon": 76.0})
        self.assertEqual(status, 404)
        valid = {"token": "tok_location_2", "lat": 10.0123, "lon": 76.3456, "accuracy": 15}
        self.assertEqual(self.post_json("/api/location", valid), (200, {"success": True}))
        self.assertEqual(self.post_json("/api/location", valid)[0], 429)
        inc = self.get_json("/api/incidents/9800000022")[1]["incident"]
        self.assertEqual(inc["latest_location"]["lat"], 10.0123)
        self.assertEqual(inc["latest_location"]["source"], "location link")

    def test_resolve(self):
        self.report_call("+919800000033")
        self.assertEqual(self.post_json("/api/resolve", {"number": "+919800000044", "by": "dashboard"})[0], 404)
        self.assertEqual(self.post_json("/api/resolve", {"number": "+919800000033", "by": "dashboard", "note": "done"}),
                         (200, {"success": True}))
        inc = self.get_json("/api/incidents/9800000033")[1]["incident"]
        self.assertEqual(inc["status"], "resolved")
        self.assertEqual(inc["resolved"]["note"], "done")
        self.assertEqual(self.post_json("/api/resolve", {"number": "+919800000033", "note": "x" * 501})[0], 400)

    def test_incidents_csv(self):
        self.report_call("+919800000055")
        status, headers, body = self.request("GET", "/api/incidents.csv")
        self.assertEqual(status, 200)
        self.assertIn("text/csv", headers["Content-Type"])
        self.assertIn("attachment", headers["Content-Disposition"])
        lines = body.decode("utf-8").splitlines()
        self.assertEqual(lines[0].split(",")[:3], ["number", "status", "first_seen"])
        self.assertTrue(any(line.startswith("+919800000055,open,") for line in lines[1:]))


class TokenServerTests(HttpServerCase):
    """KAAKA_ADMIN_TOKEN set: dashboard and API need the token; landing, health and location links stay public."""
    admin_token = "s3cret-token"

    def test_admin_requires_token(self):
        status, headers, _ = self.request("GET", "/admin")
        self.assertEqual(status, 401)
        self.assertEqual(headers.get("Cache-Control"), "no-store")
        status, headers, body = self.request("GET", "/admin?token=s3cret-token")
        self.assertEqual(status, 200)
        self.assertIn(b"<title>kaaka / server</title>", body)
        cookie = headers.get("Set-Cookie")
        self.assertTrue(cookie.startswith("kaaka_token=s3cret-token;"), cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertEqual(self.request("GET", "/admin?token=wrong")[0], 401)

    def test_api_token_header_query_and_cookie(self):
        self.assertEqual(self.get_json("/api/status")[0], 401)
        self.assertEqual(self.get_json("/api/status", {"X-Kaaka-Token": "s3cret-token"})[0], 200)
        self.assertEqual(self.get_json("/api/incidents?token=s3cret-token")[0], 200)
        self.assertEqual(self.get_json("/api/incidents", {"Cookie": "kaaka_token=s3cret-token"})[0], 200)
        self.assertEqual(self.post_json("/api/call-event", {"number": "+91", "state": "rejected", "sms": "sent"})[0], 401)

    def test_public_routes_stay_public(self):
        self.assertEqual(self.request("GET", "/")[0], 200)
        self.assertEqual(self.request("GET", "/docs/")[0], 200)
        self.assertEqual(self.request("GET", "/docs/docs.css")[0], 200)
        self.assertEqual(self.request("GET", "/favicon.ico")[0], 200)
        self.assertEqual(self.request("GET", "/icons/favicon.svg")[0], 200)
        status, health = self.get_json("/api/health")
        self.assertEqual(status, 200)
        self.assertNotIn("admin_token", json.dumps(health))
        # Location sharing never needs the admin token: unknown link is 404, not 401.
        self.assertEqual(self.post_json("/api/location", {"token": "tok_unknown_99", "lat": 1.0, "lon": 1.0})[0], 404)
        self.assertEqual(self.request("GET", "/l/unknowntoken1")[0], 404)


    def test_login_page_and_login_with_admin_token(self):
        status, _, body = self.request("GET", "/admin")
        self.assertEqual(status, 401)
        self.assertIn(b"Enter the PIN", body)
        self.assertNotIn(b"Demo PIN", body)  # no demo PIN configured
        self.assertNotIn(b'class="demo-pin"', self.request("GET", "/")[2])
        status, headers, _ = self.request("POST", "/admin/login", "pin=" + self.admin_token,
                                          {"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual((status, headers["Location"]), (303, "/admin"))
        self.assertIn("HttpOnly", headers["Set-Cookie"])


class DemoPinTests(HttpServerCase):
    """KAAKA_DEMO_PIN only: the PIN is shown publicly and unlocks the control room; wrong guesses are limited."""
    demo_pin = "1234"
    FORM = {"Content-Type": "application/x-www-form-urlencoded"}

    def login(self, pin, headers=None):
        return self.request("POST", "/admin/login", f"pin={pin}", {**self.FORM, **(headers or {})})

    def test_pin_is_shown_on_landing_and_login_pages(self):
        status, _, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b'class="demo-pin"', body)
        self.assertIn(b"<b>1234</b>", body)
        status, _, body = self.request("GET", "/admin")
        self.assertEqual(status, 401)
        self.assertIn(b"Demo PIN <b>1234</b>", body)
        self.assertIn(b'data-pin="1234"', body)

    def test_pin_is_required_and_unlocks_dashboard_and_api(self):
        self.assertEqual(self.get_json("/api/status")[0], 401)
        status, headers, _ = self.login("1234", {"X-Forwarded-For": "10.0.0.1"})
        self.assertEqual((status, headers["Location"]), (303, "/admin"))
        cookie = headers["Set-Cookie"].split(";")[0]
        self.assertEqual(cookie, "kaaka_token=1234")
        self.assertEqual(self.request("GET", "/admin", headers={"Cookie": cookie})[0], 200)
        self.assertEqual(self.get_json("/api/status", {"Cookie": cookie})[0], 200)
        self.assertEqual(self.get_json("/api/status?token=1234")[0], 200)
        self.assertEqual(self.request("GET", "/api/health")[0], 200)  # still public

    def test_wrong_pin_and_logout(self):
        status, _, body = self.login("0000")
        self.assertEqual(status, 401)
        self.assertIn(b"not right", body)
        status, headers, _ = self.request("GET", "/admin/logout")
        self.assertEqual((status, headers["Location"]), (303, "/"))
        self.assertIn("Max-Age=0", headers["Set-Cookie"])

    def test_lockout_after_ten_wrong_guesses(self):
        client = {"X-Forwarded-For": "203.0.113.9"}  # test server sees 127.0.0.1, so the forwarded hop is the client
        for guess in range(10):
            self.assertEqual(self.login(f"9{guess:03d}", client)[0], 401)
        status, _, body = self.login("1234", client)  # right PIN, but this client is locked out
        self.assertEqual(status, 429)
        self.assertIn(b"Too many wrong attempts", body)
        self.assertEqual(self.get_json("/api/status?token=1234", client)[0], 401)
        self.assertEqual(self.login("1234", {"X-Forwarded-For": "203.0.113.10"})[0], 303)  # other clients unaffected


if __name__ == "__main__":
    unittest.main()
