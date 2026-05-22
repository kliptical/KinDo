import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fnsr_daemon as d


def task(tid, status="ready", deps=None, priority=None):
    t = {"@id": tid, "status": status, "depends_on": deps or []}
    if priority is not None:
        t["priority"] = priority
    return t


class TestNextReadyTask(unittest.TestCase):
    def test_no_priority_lex_order(self):
        s = {"tasks": [task("urn:t:c"), task("urn:t:a"), task("urn:t:b")]}
        self.assertEqual(d.next_ready_task(s)["@id"], "urn:t:a")

    def test_priority_overrides_lex(self):
        s = {"tasks": [
            task("urn:t:a", priority=0),
            task("urn:t:z", priority=10),
            task("urn:t:m", priority=5),
        ]}
        self.assertEqual(d.next_ready_task(s)["@id"], "urn:t:z")

    def test_priority_tie_breaks_lex(self):
        s = {"tasks": [
            task("urn:t:c", priority=5),
            task("urn:t:a", priority=5),
            task("urn:t:b", priority=5),
        ]}
        self.assertEqual(d.next_ready_task(s)["@id"], "urn:t:a")

    def test_negative_priority(self):
        s = {"tasks": [
            task("urn:t:a", priority=-10),
            task("urn:t:z", priority=0),
        ]}
        self.assertEqual(d.next_ready_task(s)["@id"], "urn:t:z")

    def test_unsatisfied_dep_filtered_out(self):
        s = {"tasks": [
            task("urn:t:high", deps=["urn:t:dep"], priority=99),
            task("urn:t:dep", priority=0),
        ]}
        self.assertEqual(d.next_ready_task(s)["@id"], "urn:t:dep")

    def test_dep_done_priority_drives(self):
        s = {"tasks": [
            task("urn:t:high", deps=["urn:t:dep"], priority=99),
            task("urn:t:dep", status="done"),
        ]}
        self.assertEqual(d.next_ready_task(s)["@id"], "urn:t:high")

    def test_no_ready_tasks_returns_none(self):
        s = {"tasks": [task("urn:t:done", status="done")]}
        self.assertIsNone(d.next_ready_task(s))


if __name__ == "__main__":
    unittest.main()
