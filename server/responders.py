"""
Kaaka responder registry
========================
Volunteers/responders with a home position, kept in server/responders.json (not committed).
Used to find who is nearest to a caller's latest location and to estimate how long they need
to get there.
"""

import json
import math
import os
import re
import threading
import uuid

EARTH_RADIUS_KM = 6371.0
# Average door-to-door speed in Indian city traffic (bike/auto/car mix). An assumption, not a measurement:
# the ETA is a rough planning number, not a promise.
CITY_SPEED_KMH = 25.0
MAX_NAME = 80


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in kilometres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def eta_minutes(distance_km, speed_kmh=CITY_SPEED_KMH):
    """Minutes to cover the distance at the assumed city speed, never less than 1."""
    return max(1, int(round(distance_km / speed_kmh * 60)))


def validate_responder(data, partial=False):
    """Returns the cleaned fields of a responder body; raises ValueError with a readable message."""
    if not isinstance(data, dict):
        raise ValueError("body must be a JSON object")
    out = {}
    if "name" in data or not partial:
        name = data.get("name")
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > MAX_NAME:
            raise ValueError(f'"name" is required (at most {MAX_NAME} characters)')
        out["name"] = name.strip()
    if "number" in data or not partial:
        number = data.get("number")
        if not isinstance(number, str) or len(re.sub(r"\D", "", number)) < 6:
            raise ValueError('"number" must be a phone number')
        out["number"] = number.strip()
    for key, low, high in (("lat", -90, 90), ("lon", -180, 180)):
        if key in data or not partial:
            value = data.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
                raise ValueError(f'"{key}" must be a number between {low} and {high}')
            out[key] = float(value)
    if "available" in data:
        if not isinstance(data["available"], bool):
            raise ValueError('"available" must be true or false')
        out["available"] = data["available"]
    elif not partial:
        out["available"] = True
    return out


class ResponderRegistry:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()
        self.responders = []
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self.responders = [r for r in data if isinstance(r, dict) and "id" in r]
        except (ValueError, OSError):
            self.responders = []  # a damaged file must not stop the server

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.responders, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def list(self):
        with self.lock:
            return [dict(r) for r in self.responders]

    def add(self, data):
        fields = validate_responder(data)
        responder = {"id": uuid.uuid4().hex[:8], **fields}
        with self.lock:
            self.responders.append(responder)
            self._save()
        return dict(responder)

    def update(self, responder_id, data):
        fields = validate_responder(data, partial=True)
        with self.lock:
            for r in self.responders:
                if r["id"] == responder_id:
                    r.update(fields)
                    self._save()
                    return dict(r)
        return None

    def delete(self, responder_id):
        with self.lock:
            before = len(self.responders)
            self.responders = [r for r in self.responders if r["id"] != responder_id]
            if len(self.responders) == before:
                return False
            self._save()
            return True

    def nearest(self, lat, lon, limit=3, available_only=True):
        """Responders sorted by distance to (lat, lon), each with distance_km and eta_min."""
        result = []
        for r in self.list():
            if available_only and not r.get("available", True):
                continue
            d = haversine_km(lat, lon, r["lat"], r["lon"])
            result.append({**r, "distance_km": round(d, 2), "eta_min": eta_minutes(d)})
        result.sort(key=lambda r: r["distance_km"])
        return result[:limit]
