import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fnsr_daemon as d


# Explicit Unicode escapes for mojibake patterns and their proper forms.
# Using literal characters in source can be unreliable through editors / Write
# tools that normalize curly quotes.
MOJI_EM_DASH = "â€”"      # mojibake for U+2014 em-dash
MOJI_SECTION = "Â§"             # mojibake for U+00A7 section sign
MOJI_DEGREE = "Â°"              # mojibake for U+00B0 degree sign
MOJI_RIGHT_ARROW = "â†’"  # mojibake for U+2192 right arrow (explicit codepoints)
EM_DASH = "—"
SECTION = "§"
DEGREE = "°"
RIGHT_ARROW = "→"


class TestRepairMojibake(unittest.TestCase):
    """Pure-function tests on the _repair_mojibake helper."""

    def test_section_sign(self):
        self.assertEqual(
            d._repair_mojibake(f"see {MOJI_SECTION}5.14"),
            f"see {SECTION}5.14",
        )

    def test_em_dash(self):
        self.assertEqual(
            d._repair_mojibake(f"hello {MOJI_EM_DASH} world"),
            f"hello {EM_DASH} world",
        )

    def test_right_arrow(self):
        self.assertEqual(
            d._repair_mojibake(f"v0.3 {MOJI_RIGHT_ARROW} v0.4"),
            f"v0.3 {RIGHT_ARROW} v0.4",
        )

    def test_mixed_proper_and_mojibake_preserves_proper(self):
        # 190+190 split scenario: mojibake gets repaired, proper stays.
        self.assertEqual(
            d._repair_mojibake(f"{SECTION} proper and {MOJI_SECTION} broken"),
            f"{SECTION} proper and {SECTION} broken",
        )

    def test_multiple_patterns_in_one_string(self):
        text = f"{MOJI_SECTION}1.2 covers {MOJI_EM_DASH} the {MOJI_DEGREE}C scale"
        expected = f"{SECTION}1.2 covers {EM_DASH} the {DEGREE}C scale"
        self.assertEqual(d._repair_mojibake(text), expected)

    def test_clean_text_unchanged(self):
        clean = f"no mojibake here, just {SECTION}, {EM_DASH}, {DEGREE}"
        self.assertEqual(d._repair_mojibake(clean), clean)

    def test_non_string_unchanged(self):
        self.assertIsNone(d._repair_mojibake(None))
        self.assertEqual(d._repair_mojibake(42), 42)
        self.assertEqual(d._repair_mojibake({"x": 1}), {"x": 1})


class TestMojibakeRepairAgent(unittest.TestCase):
    """System-agent tests on _mojibake_repair."""

    def _task(self, source_id="urn:t:dev"):
        return {
            "@id": "urn:t:repair",
            "agent": "mojibake-repair",
            "inputs": {"source_task": source_id},
        }

    def _upstream(self, changes, source_id="urn:t:dev"):
        return {source_id: {"changes": changes}}

    def test_repairs_before_and_after_fields(self):
        r = d._mojibake_repair(self._task(), self._upstream([
            {"id": "C1", "file": "a.md",
             "before": f"{MOJI_SECTION} old",
             "after": f"{MOJI_SECTION} new"}
        ]))
        self.assertNotIn("error", r.outputs)
        out_change = r.outputs["changes"][0]
        self.assertEqual(out_change["before"], f"{SECTION} old")
        self.assertEqual(out_change["after"], f"{SECTION} new")

    def test_preserves_clean_changes_untouched(self):
        r = d._mojibake_repair(self._task(), self._upstream([
            {"id": "C1", "file": "a.md",
             "before": "clean before", "after": "clean after"}
        ]))
        self.assertEqual(r.outputs["changes"][0]["before"], "clean before")
        self.assertEqual(r.outputs["changes"][0]["after"], "clean after")

    def test_summary_counts_replacements(self):
        r = d._mojibake_repair(self._task(), self._upstream([
            {"id": "C1", "file": "a.md",
             "before": f"{MOJI_SECTION}1 {MOJI_SECTION}2",
             "after": f"{MOJI_EM_DASH} then {MOJI_EM_DASH}"}
        ]))
        # 2 section-sign mojibakes in before + 2 em-dash mojibakes in after.
        self.assertIn("repaired 4 mojibake", r.outputs["summary"])

    def test_handles_missing_source_task(self):
        task = {"@id": "urn:t", "agent": "mojibake-repair", "inputs": {}}
        r = d._mojibake_repair(task, {})
        self.assertEqual(r.outputs["error"], "missing_source_task")

    def test_handles_source_not_in_upstream(self):
        r = d._mojibake_repair(self._task("urn:t:missing"), {})
        self.assertEqual(r.outputs["error"], "source_not_in_upstream")

    def test_handles_source_without_changes(self):
        r = d._mojibake_repair(
            self._task(),
            {"urn:t:dev": {"summary": "no changes here"}},
        )
        self.assertEqual(r.outputs["error"], "source_has_no_changes")

    def test_passes_through_non_dict_change_items(self):
        # Edge case: source.changes contains a non-dict entry.
        r = d._mojibake_repair(self._task(), self._upstream([
            "not a dict",
            {"id": "C1", "file": "a.md",
             "before": MOJI_SECTION, "after": SECTION},
        ]))
        # Non-dict entry preserved as-is; dict entry repaired.
        self.assertEqual(r.outputs["changes"][0], "not a dict")
        self.assertEqual(r.outputs["changes"][1]["before"], SECTION)

    def test_required_outputs_declared_for_cps(self):
        """The agent file must declare the required output keys so CPS
        enforces the contract on the agent's outputs."""
        self.assertEqual(
            d._agent_required_outputs("mojibake-repair"),
            ["changes", "summary", "self_assessment"],
        )

    def test_registered_in_system_agents(self):
        self.assertIn("mojibake-repair", d.SYSTEM_AGENTS)
        self.assertIs(d.SYSTEM_AGENTS["mojibake-repair"], d._mojibake_repair)


if __name__ == "__main__":
    unittest.main()
