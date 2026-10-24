"""Unit checks for server/analytics.py. Run: python3 -m unittest server/test_analytics.py (from the repo root)."""

import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
import analytics  # noqa: E402

NOW = datetime(2026, 10, 25, 14, 30).timestamp()


def at(hour, minute=0, day=25):
    return datetime(2026, 10, day, hour, minute).timestamp()


def call(number, t, state="rejected", sms="sent"):
    return {"kind": "call", "number": number, "state": state, "sms": sms, "received_epoch": t}


def alert(number, t, lat=None, lon=None):
    e = {"kind": "alert", "number": number, "text": "Kaaka Alert", "received_epoch": t}
    if lat is not None:
        e.update(lat=lat, lon=lon)
    return e


EVENTS = [
    call("+919800000001", at(9)),                                   # A: call, reply sent
    alert("+919800000001", at(9, 2), 9.9800, 76.2800),             # A located
    {"kind": "dispatch", "number": "+919800000001", "received_epoch": at(9, 2),
     "responders": [{"name": "Ravi", "number": "+91 98470 00011", "distance_km": 2.0}]},
    {"kind": "ack", "number": "+919800000001", "responder": "9847000011", "received_epoch": at(9, 6)},   # A ack 6 min
    {"kind": "resolve", "number": "+919800000001", "by": "dashboard", "received_epoch": at(9, 30)},     # A closed 30 min
    call("+919800000002", at(11), state="sms", sms="failed"),       # B: help SMS, reply failed
    {"kind": "ack", "number": "+919800000002", "responder": "+919847000011", "received_epoch": at(11, 10)},  # B ack 10 min
    {"kind": "resolve", "number": "+919800000002", "by": "caller", "received_epoch": at(11, 20)},          # B safe 20 min
    call("+919800000003", at(13), sms="skipped"),                   # C: open, never acknowledged
    alert("+919800000003", at(13, 1), 9.9810, 76.2810),            # C in the same cell as A
    call("+919800000001", at(14)),                                  # A again: a new episode, open
    {"kind": "ack", "number": "+919800000004", "responder": "x", "received_epoch": at(12)},  # no episode: ignored
    call("+919800000005", at(10, day=10)),                         # E: two weeks ago, outside 7d
]

RESPONDERS = [{"name": "Ravi", "number": "+919847000011", "lat": 9.97, "lon": 76.27}]


class AnalyticsTest(unittest.TestCase):
    def setUp(self):
        self.r = analytics.compute(EVENTS, RESPONDERS, "7d", NOW)

    def test_kpis(self):
        k = self.r["kpis"]
        self.assertEqual(k["incidents"], 4)              # A, B, C, A-again (E is outside 7d)
        self.assertEqual(k["open_now"], 3)              # C, A-again, and E (never resolved)
        self.assertEqual(k["median_ack_minutes"], 8.0)  # 6 and 10
        self.assertEqual(k["p90_ack_minutes"], 9.6)     # 6 + 0.9 * 4
        self.assertEqual(k["median_close_minutes"], 25.0)  # 30 and 20
        self.assertEqual(k["located_pct"], 50.0)        # A and C of 4
        self.assertEqual(k["reply_sent_pct"], 66.7)     # sent 2 (A, A-again) of sent+failed 3
        self.assertEqual(k["closed_by_caller"], 1)

    def test_outcomes(self):
        self.assertEqual(self.r["outcomes"], {"resolved_by_responder": 1, "closed_by_caller": 1,
                                              "acknowledged_open": 0, "open": 2})

    def test_daily_and_hours(self):
        self.assertEqual(self.r["bucket"], "day")
        self.assertEqual(len(self.r["daily"]), 7)
        self.assertEqual(self.r["daily"][-1], {"date": "2026-10-25", "call": 3, "help_sms": 1, "app_alert": 2})
        self.assertEqual(sum(sum(d[c] for c in analytics.CHANNELS) for d in self.r["daily"][:-1]), 0)
        self.assertEqual(self.r["hours"][9], 2)
        self.assertEqual(sum(self.r["hours"]), 6)

    def test_hourly_range(self):
        r = analytics.compute(EVENTS, RESPONDERS, "24h", NOW)
        self.assertEqual(r["bucket"], "hour")
        self.assertEqual(len(r["daily"]), 24)
        self.assertEqual(r["daily"][-1]["date"], "2026-10-25 14:00")
        self.assertEqual(r["daily"][-1]["call"], 1)

    def test_all_range_and_empty(self):
        r = analytics.compute(EVENTS, RESPONDERS, "all", NOW)
        self.assertEqual(r["daily"][0]["date"], "2026-10-10")
        self.assertEqual(len(r["daily"]), 16)
        empty = analytics.compute([], [], "7d", NOW)
        self.assertIsNone(empty["kpis"]["median_ack_minutes"])
        self.assertIsNone(empty["kpis"]["located_pct"])
        self.assertIsNone(empty["kpis"]["reply_sent_pct"])
        self.assertEqual(empty["hotspots"], [])
        with self.assertRaises(ValueError):
            analytics.range_window("1y", NOW)

    def test_responders_and_hotspots(self):
        self.assertEqual(self.r["responders"], [{"name": "Ravi", "number": "+919847000011", "dispatches": 1,
                                                 "acks": 2, "avg_distance_km": 2.0}])
        # A-again has no location of its own; A (9.98, 76.28) and C (9.981, 76.281) share one cell.
        self.assertEqual(self.r["hotspots"], [{"lat": 9.9825, "lon": 76.2825, "count": 2}])


if __name__ == "__main__":
    unittest.main()
