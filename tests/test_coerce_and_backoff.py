import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fnsr_daemon as d


class TestEnvelopeCoerce(unittest.TestCase):
    """v2.4.2: when an agent returns a bare change-shape dict instead of
    the proper {changes:[...], summary, self_assessment} envelope, the
    daemon auto-wraps it and marks `_auto_coerced: True`."""

    def test_proper_envelope_unchanged(self):
        proper = {
            "changes": [{"file": "a.md", "before": "x", "after": "y"}],
            "summary": "ok", "self_assessment": "confident",
        }
        result = d._coerce_developer_envelope(proper, "urn:t:test")
        self.assertIs(result, proper)
        self.assertNotIn("_auto_coerced", result)

    def test_bare_change_dict_gets_wrapped(self):
        bare = {
            "id": "C1", "file": "a.md",
            "before": "old", "after": "new", "scope": "minimal",
        }
        result = d._coerce_developer_envelope(bare, "urn:t:test")
        self.assertIn("changes", result)
        self.assertEqual(len(result["changes"]), 1)
        self.assertEqual(result["changes"][0]["file"], "a.md")
        self.assertEqual(result["self_assessment"], "needs_review")
        self.assertTrue(result["_auto_coerced"])
        self.assertIn("auto-coerced", result["summary"])

    def test_passes_through_non_change_shape(self):
        # Looks like spec-reviewer output, not developer
        other = {"findings": [], "summary": "x", "recommendation": "accept"}
        result = d._coerce_developer_envelope(other, "urn:t:test")
        self.assertIs(result, other)

    def test_non_dict_passes_through(self):
        self.assertEqual(d._coerce_developer_envelope("string", "u"), "string")
        self.assertIsNone(d._coerce_developer_envelope(None, "u"))
        self.assertEqual(d._coerce_developer_envelope(42, "u"), 42)

    def test_partial_change_keys_not_coerced(self):
        # Has `file` but not `before` / `after` — not a change.
        partial = {"file": "a.md", "summary": "x"}
        result = d._coerce_developer_envelope(partial, "urn:t:test")
        self.assertIs(result, partial)

    def test_coerced_outputs_pass_cps_required_keys(self):
        """After coercion, CPS should accept the wrapped output as a valid
        developer envelope."""
        bare = {"id": "C1", "file": "a.md", "before": "x", "after": "y"}
        coerced = d._coerce_developer_envelope(bare, "urn:t:test")
        task = {"@id": "urn:t", "agent": "developer"}
        # CPS check should not raise.
        d.cps_check(task, coerced)


class TestApiTransientErrorDetection(unittest.TestCase):
    """v2.4.2: claude's JSON envelope on Anthropic 5xx errors includes
    `is_error:true` + `api_error_status: 5XX`. The daemon detects this
    and sleeps before letting the next retry fire."""

    def test_detects_500(self):
        stdout = (
            '{"type":"result","subtype":"success","is_error":true,'
            '"api_error_status":500,"duration_ms":412273,'
            '"result":"API Error: 500 Internal server error..."}'
        )
        self.assertTrue(d._is_api_transient_error(stdout))

    def test_detects_503(self):
        stdout = (
            '{"is_error":true,"api_error_status":503,'
            '"result":"Service unavailable"}'
        )
        self.assertTrue(d._is_api_transient_error(stdout))

    def test_does_not_match_400(self):
        stdout = (
            '{"is_error":true,"api_error_status":400,'
            '"result":"bad request"}'
        )
        self.assertFalse(d._is_api_transient_error(stdout))

    def test_does_not_match_success_envelope(self):
        stdout = (
            '{"type":"result","subtype":"success","is_error":false,'
            '"result":"{...agent json...}"}'
        )
        self.assertFalse(d._is_api_transient_error(stdout))

    def test_empty_stdout_returns_false(self):
        self.assertFalse(d._is_api_transient_error(""))
        self.assertFalse(d._is_api_transient_error(None))

    def test_handles_whitespace_around_colons(self):
        # JSON serializers occasionally produce spaced colons.
        stdout = (
            '{"is_error" : true, "api_error_status" : 502, "result": "x"}'
        )
        self.assertTrue(d._is_api_transient_error(stdout))


if __name__ == "__main__":
    unittest.main()
