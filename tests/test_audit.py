import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fnsr_daemon as d


class TestHiriSign(unittest.TestCase):
    def test_deterministic(self):
        h1 = d.hiri_sign("0" * 64, {"event": "e", "payload": {"a": 1}})
        h2 = d.hiri_sign("0" * 64, {"event": "e", "payload": {"a": 1}})
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)  # SHA-256 hex

    def test_chain_distinct(self):
        h1 = d.hiri_sign("0" * 64, {"event": "e1", "payload": {}})
        h2 = d.hiri_sign(h1, {"event": "e2", "payload": {}})
        self.assertNotEqual(h1, h2)

    def test_payload_change_changes_hash(self):
        h1 = d.hiri_sign("0" * 64, {"event": "e", "payload": {"a": 1}})
        h2 = d.hiri_sign("0" * 64, {"event": "e", "payload": {"a": 2}})
        self.assertNotEqual(h1, h2)


class TestLastHash(unittest.TestCase):
    def test_empty_task_returns_zeros(self):
        self.assertEqual(d._last_hash({}), "0" * 64)

    def test_prefers_chain_hash(self):
        task = {"history": [{"chain_hash": "c" * 64, "hash": "h" * 64}]}
        self.assertEqual(d._last_hash(task), "c" * 64)

    def test_legacy_hash_fallback(self):
        task = {"history": [{"hash": "h" * 64}]}
        self.assertEqual(d._last_hash(task), "h" * 64)


class TestRecord(unittest.TestCase):
    def test_appends_chained_entry(self):
        task = {"history": []}
        d._record(task, "0" * 64, "started", {"agent": "x"})
        d._record(task, task["history"][-1]["chain_hash"],
                  "completed", {"result": "ok"})
        self.assertEqual(len(task["history"]), 2)
        self.assertEqual(task["history"][1]["prev_hash"],
                         task["history"][0]["chain_hash"])

    def test_entry_has_required_fields(self):
        task = {}
        d._record(task, "0" * 64, "started", {"agent": "x"})
        entry = task["history"][0]
        for key in ("ts", "event", "payload", "prev_hash", "chain_hash"):
            self.assertIn(key, entry)

    def test_no_legacy_sig_field(self):
        task = {}
        d._record(task, "0" * 64, "started", {"agent": "x"})
        self.assertNotIn("sig", task["history"][0])


if __name__ == "__main__":
    unittest.main()
