"""
Kaaka incident log
==================
Every call event, help SMS, alert report, location share, responder acknowledgement and
resolution is appended
as one JSON line to server/events.jsonl (not committed) and replayed on start, so the
dashboard history survives restarts. Incidents group these events by phone number
(last 10 digits). Status: "open" until a responder acknowledges ("acknowledged") or someone
resolves it ("resolved"); a later call, help SMS or alert reopens it.
"""

import json
import os
import re
import threading
import time
from datetime import datetime

TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{6,32}$")
TOKEN_TTL_SECONDS = 24 * 3600
MAX_INCIDENTS = 50
MAX_EVENTS_IN_MEMORY = 5000

COORDS_RE = re.compile(r"Coords:\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)")
MAPS_RE = re.compile(r"Maps:\s*(\S+)")


def now_text(epoch=None):
    return datetime.fromtimestamp(epoch or time.time()).strftime("%Y-%m-%d %H:%M:%S")


def number_key(number):
    """Phone numbers match on their last 10 digits; anything else (hidden, 'simulated') on its text."""
    raw = str(number or "").strip()
    digits = re.sub(r"\D", "", raw)
    if len(digits) >= 6:
        return digits[-10:]
    return raw.lower() or "hidden"


def maps_url(lat, lon):
    return f"https://maps.google.com/?q={lat:.6f},{lon:.6f}"


def parse_coords(text):
    """(lat, lon, maps_url) from an alert's "Coords:" / "Maps:" lines, or (None, None, None)."""
    m = COORDS_RE.search(text or "")
    if not m:
        return None, None, None
    lat, lon = float(m.group(1)), float(m.group(2))
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None, None, None
    maps = MAPS_RE.search(text)
    return lat, lon, maps.group(1) if maps else maps_url(lat, lon)


class IncidentStore:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.events = []
        self.tokens = {}  # location-share token -> {"number", "created_epoch"}
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue  # skip a damaged line rather than losing the whole history
                if isinstance(event, dict) and "kind" in event:
                    self._apply(event)

    def _apply(self, event):
        self.events.append(event)
        if len(self.events) > MAX_EVENTS_IN_MEMORY:
            self.events = self.events[-MAX_EVENTS_IN_MEMORY:]
        if event["kind"] == "call" and event.get("token"):
            self.tokens[event["token"]] = {"number": event.get("number", ""), "created_epoch": event["received_epoch"]}

    def _record(self, event):
        event["received_epoch"] = time.time()
        event["received"] = now_text(event["received_epoch"])
        with self.lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
            self._apply(event)
        return event

    def add_call(self, number, state, sms, phone_timestamp, token=None, message=None):
        """A call (state rejected/allowed) or a help SMS (state "sms", with the message text)."""
        event = {"kind": "call", "number": number, "state": state, "sms": sms, "phone_timestamp": phone_timestamp}
        if token:
            event["token"] = token
        if message:
            event["message"] = message
        return self._record(event)

    def add_alert(self, sender, text, source):
        """Records an alert report; returns None for an exact repeat (same sender and text as the last alert)."""
        key = number_key(sender)
        with self.lock:
            for previous in reversed(self.events):
                if previous["kind"] == "alert" and number_key(previous.get("number")) == key:
                    if previous.get("text") == text:
                        return None
                    break
        lat, lon, maps = parse_coords(text)
        event = {"kind": "alert", "number": sender, "text": text, "source": source}
        if lat is not None:
            event.update({"lat": lat, "lon": lon, "maps_url": maps})
        return self._record(event)

    def token_number(self, token):
        """Caller number for a valid, unexpired location-share token, else None."""
        info = self.tokens.get(token)
        if not info or time.time() - info["created_epoch"] > TOKEN_TTL_SECONDS:
            return None
        return info["number"]

    def add_location(self, token, lat, lon, accuracy):
        event = {"kind": "location", "number": self.token_number(token) or "", "token": token,
                 "lat": lat, "lon": lon, "accuracy": accuracy, "maps_url": maps_url(lat, lon)}
        return self._record(event)

    def add_ack(self, number, responder, phone_timestamp):
        return self._record({"kind": "ack", "number": number, "responder": responder, "phone_timestamp": phone_timestamp})

    def add_dispatch(self, number, responders):
        """Records which responders were asked to go to this caller (nearest first)."""
        return self._record({"kind": "dispatch", "number": number, "responders": responders})

    def add_resolve(self, number, by, note, phone_timestamp):
        return self._record({"kind": "resolve", "number": number, "by": by, "note": note, "phone_timestamp": phone_timestamp})

    def events_snapshot(self):
        """A copy of the in-memory event list (oldest first), e.g. for analytics."""
        with self.lock:
            return list(self.events)

    def status_of(self, number):
        """Current status of the incident for this number, or None if there is none."""
        inc = self._build().get(number_key(number))
        return inc["status"] if inc else None

    def incidents(self):
        """Incidents grouped by number, newest activity first (at most MAX_INCIDENTS)."""
        result = sorted(self._build().values(), key=lambda i: i.pop("_last_epoch"), reverse=True)
        return result[:MAX_INCIDENTS]

    def _build(self):
        """All incidents keyed by number_key."""
        with self.lock:
            events = list(self.events)
        groups = {}
        for e in events:
            key = number_key(e.get("number"))
            inc = groups.get(key)
            if inc is None:
                inc = groups[key] = {
                    "key": key, "number": e.get("number") or "hidden", "first_seen": e["received"],
                    "calls": [], "help_sms": [], "alerts": [], "locations": [], "acknowledged": None,
                    "resolved": None, "dispatched": [], "latest_location": None, "_last_activity": 0, "_last_epoch": 0,
                }
            inc["last_seen"] = e["received"]
            inc["_last_epoch"] = e["received_epoch"]
            if e.get("number"):
                inc["number"] = e["number"]
            kind = e["kind"]
            if kind == "call":
                entry = {"sms": e.get("sms"), "timestamp": e["received"],
                         "phone_timestamp": e.get("phone_timestamp", ""), "location_link": bool(e.get("token"))}
                if e.get("state") == "sms":
                    entry["message"] = e.get("message", "")
                    inc["help_sms"].append(entry)
                else:
                    entry["state"] = e.get("state")
                    inc["calls"].append(entry)
                inc["_last_activity"] = e["received_epoch"]
            elif kind == "alert":
                alert = {"text": e.get("text", ""), "source": e.get("source", ""), "timestamp": e["received"]}
                if "lat" in e:
                    alert.update({"lat": e["lat"], "lon": e["lon"], "maps_url": e.get("maps_url")})
                    inc["latest_location"] = {"lat": e["lat"], "lon": e["lon"], "source": "alert",
                                              "timestamp": e["received"], "maps_url": e.get("maps_url")}
                inc["alerts"].append(alert)
                inc["_last_activity"] = e["received_epoch"]
            elif kind == "location":
                loc = {"lat": e["lat"], "lon": e["lon"], "accuracy": e.get("accuracy"),
                       "maps_url": e["maps_url"], "timestamp": e["received"]}
                inc["locations"].append(loc)
                inc["latest_location"] = {"lat": e["lat"], "lon": e["lon"], "source": "location link",
                                          "timestamp": e["received"], "maps_url": e["maps_url"]}
            elif kind == "ack":
                inc["acknowledged"] = {"responder": e.get("responder", ""), "timestamp": e["received"],
                                       "_epoch": e["received_epoch"]}
            elif kind == "dispatch":
                inc["dispatched"] = [{**r, "timestamp": e["received"]} for r in e.get("responders", [])]
            elif kind == "resolve":
                inc["resolved"] = {"by": e.get("by", ""), "note": e.get("note", ""), "timestamp": e["received"],
                                   "_epoch": e["received_epoch"]}
                inc["dispatched"] = []  # a reopened incident gets a fresh dispatch
        for inc in groups.values():
            # A new call, help SMS or alert after an acknowledgement/resolution reopens the incident.
            for field in ("acknowledged", "resolved"):
                mark = inc[field]
                if mark and mark.pop("_epoch") < inc["_last_activity"]:
                    inc[field] = None
            inc.pop("_last_activity")
            inc["status"] = "resolved" if inc["resolved"] else "acknowledged" if inc["acknowledged"] else "open"
            # The caller texted SAFE (gateway resolves with by="caller").
            inc["closed_by_caller"] = bool(inc["resolved"]) and inc["resolved"].get("by") == "caller"
        return groups
