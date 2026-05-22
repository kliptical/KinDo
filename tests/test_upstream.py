import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fnsr_daemon as d


class TestResolveUpstream(unittest.TestCase):
    def test_resolves_single_dep(self):
        state = {"tasks": [
            {"@id": "urn:t:1", "status": "done",
             "outputs": {"findings": [1, 2, 3]}},
            {"@id": "urn:t:2", "status": "ready",
             "depends_on": ["urn:t:1"]},
        ]}
        u = d._resolve_upstream(state, state["tasks"][1])
        self.assertEqual(u["urn:t:1"], {"findings": [1, 2, 3]})

    def test_no_deps_returns_empty(self):
        task = {"@id": "urn:t", "depends_on": []}
        self.assertEqual(d._resolve_upstream({"tasks": []}, task), {})

    def test_missing_task_emits_error_sentinel(self):
        task = {"@id": "urn:t", "depends_on": ["urn:missing"]}
        u = d._resolve_upstream({"tasks": []}, task)
        self.assertEqual(u["urn:missing"], {"_error": "task_not_found"})

    def test_unready_outputs_emits_sentinel(self):
        state = {"tasks": [
            {"@id": "urn:t:1", "status": "in_progress", "outputs": None},
        ]}
        task = {"@id": "urn:t:2", "depends_on": ["urn:t:1"]}
        u = d._resolve_upstream(state, task)
        self.assertEqual(u["urn:t:1"]["_error"], "outputs_not_ready")
        self.assertEqual(u["urn:t:1"]["status"], "in_progress")

    def test_resolves_multiple_deps_in_order(self):
        state = {"tasks": [
            {"@id": "urn:t:1", "status": "done", "outputs": {"a": 1}},
            {"@id": "urn:t:2", "status": "done", "outputs": {"b": 2}},
            {"@id": "urn:t:3", "status": "ready",
             "depends_on": ["urn:t:1", "urn:t:2"]},
        ]}
        u = d._resolve_upstream(state, state["tasks"][2])
        self.assertEqual(u["urn:t:1"], {"a": 1})
        self.assertEqual(u["urn:t:2"], {"b": 2})


if __name__ == "__main__":
    unittest.main()
