import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fnsr_daemon as d


class TestExtractOutputs(unittest.TestCase):
    def test_bare_single_line(self):
        s = '{"outputs": {"findings": [], "recommendation": "revise"}}'
        self.assertEqual(d._extract_outputs(s)["recommendation"], "revise")

    def test_bare_pretty_printed(self):
        s = '{\n  "outputs": {\n    "z": 3\n  }\n}'
        self.assertEqual(d._extract_outputs(s), {"z": 3})

    def test_envelope_wraps_outputs_string(self):
        envelope = json.dumps({
            "type": "result",
            "result": '{"outputs": {"x": 1}}'
        })
        self.assertEqual(d._extract_outputs(envelope), {"x": 1})

    def test_markdown_fenced_pretty(self):
        s = ('```json\n'
             '{\n'
             '  "outputs": {\n'
             '    "issues": [{"id": "I1"}]\n'
             '  }\n'
             '}\n'
             '```')
        self.assertEqual(d._extract_outputs(s), {"issues": [{"id": "I1"}]})

    def test_markdown_fenced_single_line(self):
        s = '```json\n{"outputs": {"x": 1}}\n```'
        self.assertEqual(d._extract_outputs(s), {"x": 1})

    def test_prose_with_embedded_outputs(self):
        s = 'here is the result: {"outputs": {"g": 7}} done'
        self.assertEqual(d._extract_outputs(s), {"g": 7})

    def test_pure_prose_returns_none(self):
        self.assertIsNone(d._extract_outputs("hello world"))

    def test_first_object_fallback_when_no_outputs_key(self):
        s = '{"issues": [], "summary": "x"}'
        self.assertEqual(d._extract_outputs(s),
                         {"issues": [], "summary": "x"})


if __name__ == "__main__":
    unittest.main()
