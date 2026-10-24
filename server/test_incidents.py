"""Unit checks for server/incidents.py (IncidentStore persistence). Run: cd server && python -m unittest -q"""

import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from incidents import IncidentStore  # noqa: E402


def event(kind, number, epoch, **extra):
    return {"kind": kind, "number": number, "received_epoch": epoch,
            "received": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(epoch)), **extra}


class IncidentStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "events.jsonl")

    def write_lines(self, *lines):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("".join(line + "\n" for line in lines))

    def test_replay_from_file_skips_damaged_lines(self):
        now = time.time()
        self.write_lines(
            json.dumps(event("call", "+919800000001", now - 300, state="rejected", sms="sent", token="tok_replay_1")),
            '{"kind": "call", "number": "+91980',          # truncated write
            "",                                            # blank line
            json.dumps({"not": "an event"}),               # valid JSON without "kind"
            json.dumps(event("resolve", "+919800000001", now - 100, by="dashboard", note="ok")),
            json.dumps(event("call", "+919800000002", now - 50, state="allowed", sms="skipped")),
        )
        store = IncidentStore(self.path)
        self.assertEqual(len(store.events_snapshot()), 3)
        self.assertEqual(store.status_of("+919800000001"), "resolved")
        self.assertEqual(store.status_of("919800000002"), "open")  # matched on the last 10 digits
        self.assertEqual(store.token_number("tok_replay_1"), "+919800000001")
        self.assertIsNone(store.token_number("tok_missing_1"))
        self.assertEqual([i["number"] for i in store.incidents()], ["+919800000002", "+919800000001"])

    def test_events_are_appended_and_replayed(self):
        store = IncidentStore(self.path)
        store.add_call("+919800000003", "rejected", "sent", "2026-10-25T10:00:00", token="tok_persist_3")
        store.add_location("tok_persist_3", 10.0, 76.0, 20)
        store.add_resolve("+919800000003", "caller", "", "")
        with open(self.path, encoding="utf-8") as f:
            self.assertEqual([json.loads(line)["kind"] for line in f], ["call", "location", "resolve"])
        again = IncidentStore(self.path)
        inc = again.detail("9800000003")
        self.assertEqual(inc["status"], "resolved")
        self.assertTrue(inc["closed_by_caller"])
        self.assertEqual(inc["latest_location"]["lat"], 10.0)

    def test_missing_file_is_empty_store(self):
        store = IncidentStore(self.path)
        self.assertEqual(store.incidents(), [])
        self.assertFalse(os.path.exists(self.path))


if __name__ == "__main__":
    unittest.main()
