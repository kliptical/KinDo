import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fnsr_daemon as d


class TestApplyChanges(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="fnsr-apply-test-"))

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _task(self, source_id="urn:t:dev"):
        return {
            "@id": "urn:t:apply",
            "agent": "applier",
            "inputs": {
                "source_task": source_id,
                "apply_root": str(self.tmpdir),
            },
        }

    def _upstream(self, changes, source_id="urn:t:dev"):
        return {source_id: {"changes": changes}}

    def test_edit_unique_before_succeeds(self):
        (self.tmpdir / "a.py").write_text("return 1\n")
        r = d._apply_changes(self._task(), self._upstream([
            {"id": "C1", "file": "a.py",
             "before": "return 1", "after": "return 42"}
        ]))
        self.assertNotIn("error", r.outputs)
        self.assertEqual((self.tmpdir / "a.py").read_text(), "return 42\n")

    def test_new_file_create(self):
        r = d._apply_changes(self._task(), self._upstream([
            {"id": "C1", "file": "new.md",
             "before": None, "after": "# Hello"}
        ]))
        self.assertNotIn("error", r.outputs)
        # utf-8-sig strips the BOM the applier prepends.
        self.assertEqual(
            (self.tmpdir / "new.md").read_text(encoding="utf-8-sig"),
            "# Hello"
        )

    def test_new_file_writes_utf8_bom(self):
        d._apply_changes(self._task(), self._upstream([
            {"id": "C1", "file": "new.md",
             "before": None, "after": "# Hello"}
        ]))
        raw = (self.tmpdir / "new.md").read_bytes()
        # UTF-8 BOM is 0xEF 0xBB 0xBF.
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))

    def test_new_file_doesnt_double_bom(self):
        d._apply_changes(self._task(), self._upstream([
            {"id": "C1", "file": "new.md",
             "before": None, "after": "﻿# Already has BOM"}
        ]))
        raw = (self.tmpdir / "new.md").read_bytes()
        # Exactly one BOM at start.
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\xef\xbb\xbf", raw[3:])

    def test_new_file_in_subdir_creates_parent(self):
        r = d._apply_changes(self._task(), self._upstream([
            {"id": "C1", "file": "deep/nested/path.txt",
             "before": None, "after": "x"}
        ]))
        self.assertNotIn("error", r.outputs)
        self.assertEqual(
            (self.tmpdir / "deep" / "nested" / "path.txt").read_text(
                encoding="utf-8-sig"),
            "x"
        )

    def test_before_not_unique_fails_without_writing(self):
        (self.tmpdir / "a.py").write_text("xx\nxx\n")
        r = d._apply_changes(self._task(), self._upstream([
            {"id": "C1", "file": "a.py",
             "before": "xx", "after": "yy"}
        ]))
        self.assertEqual(r.outputs["error"], "apply_partial_failure")
        self.assertEqual(r.outputs["failed"][0]["reason"], "before_not_unique")
        self.assertEqual(r.outputs["failed"][0]["count"], 2)
        # File must be unchanged.
        self.assertEqual((self.tmpdir / "a.py").read_text(), "xx\nxx\n")

    def test_before_not_found_fails(self):
        (self.tmpdir / "a.py").write_text("foo\n")
        r = d._apply_changes(self._task(), self._upstream([
            {"id": "C1", "file": "a.py",
             "before": "bar", "after": "baz"}
        ]))
        self.assertEqual(r.outputs["error"], "apply_partial_failure")
        self.assertEqual(r.outputs["failed"][0]["reason"], "before_not_found")

    def test_file_missing_for_edit_fails(self):
        r = d._apply_changes(self._task(), self._upstream([
            {"id": "C1", "file": "missing.py",
             "before": "x", "after": "y"}
        ]))
        self.assertEqual(r.outputs["error"], "apply_partial_failure")
        self.assertEqual(r.outputs["failed"][0]["reason"], "file_not_found")

    def test_new_file_when_exists_fails(self):
        (self.tmpdir / "exists.py").write_text("already here\n")
        r = d._apply_changes(self._task(), self._upstream([
            {"id": "C1", "file": "exists.py",
             "before": None, "after": "new content"}
        ]))
        self.assertEqual(r.outputs["error"], "apply_partial_failure")
        self.assertEqual(r.outputs["failed"][0]["reason"], "new_file_exists")
        # Existing file untouched.
        self.assertEqual((self.tmpdir / "exists.py").read_text(),
                         "already here\n")

    def test_missing_required_field(self):
        r = d._apply_changes(self._task(), self._upstream([
            {"id": "C1", "before": "x", "after": "y"}  # no `file`
        ]))
        self.assertEqual(r.outputs["error"], "apply_partial_failure")
        self.assertEqual(r.outputs["failed"][0]["reason"],
                         "missing_required_field")

    def test_partial_success_some_succeed_some_fail(self):
        (self.tmpdir / "a.py").write_text("ok\n")
        r = d._apply_changes(self._task(), self._upstream([
            {"id": "C1", "file": "a.py", "before": "ok", "after": "good"},
            {"id": "C2", "file": "missing.py",
             "before": "x", "after": "y"},
        ]))
        self.assertEqual(r.outputs["error"], "apply_partial_failure")
        self.assertEqual(len(r.outputs["applied"]), 1)
        self.assertEqual(len(r.outputs["failed"]), 1)
        # Successful change persists; failed change doesn't.
        self.assertEqual((self.tmpdir / "a.py").read_text(), "good\n")
        self.assertFalse((self.tmpdir / "missing.py").exists())

    def test_missing_source_task_input(self):
        task = {"@id": "urn:t", "agent": "applier", "inputs": {}}
        r = d._apply_changes(task, {})
        self.assertEqual(r.outputs["error"], "missing_source_task")

    def test_source_not_in_upstream(self):
        r = d._apply_changes(self._task("urn:t:missing"), {})
        self.assertEqual(r.outputs["error"], "source_not_in_upstream")

    def test_source_has_no_changes(self):
        r = d._apply_changes(self._task(),
                              {"urn:t:dev": {"summary": "no changes"}})
        self.assertEqual(r.outputs["error"], "source_has_no_changes")


class TestMultiChangeAtomicApply(unittest.TestCase):
    """v2.3.0: multiple edits to the same file no longer cascade-fail.
    Each `before` is matched against the ORIGINAL file content; all
    non-overlapping edits land in one pass."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="fnsr-multi-test-"))

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _task(self, source_id="urn:t:dev"):
        return {
            "@id": "urn:t:apply",
            "agent": "applier",
            "inputs": {"source_task": source_id,
                       "apply_root": str(self.tmpdir)},
        }

    def _upstream(self, changes, source_id="urn:t:dev"):
        return {source_id: {"changes": changes}}

    def test_three_non_overlapping_edits_all_apply(self):
        (self.tmpdir / "a.txt").write_text("alpha\nbeta\ngamma\n")
        r = d._apply_changes(self._task(), self._upstream([
            {"id": "C1", "file": "a.txt", "before": "alpha", "after": "ALPHA"},
            {"id": "C2", "file": "a.txt", "before": "beta", "after": "BETA"},
            {"id": "C3", "file": "a.txt", "before": "gamma", "after": "GAMMA"},
        ]))
        self.assertNotIn("error", r.outputs)
        self.assertEqual((self.tmpdir / "a.txt").read_text(),
                         "ALPHA\nBETA\nGAMMA\n")

    def test_cascade_case_survives(self):
        """The bug that motivated v2.3.0: change C1's `after` contains
        text resembling C2's `before`. Pre-fix, C2's before was looked up
        in the post-C1 file and might fail. Post-fix, both are located in
        the ORIGINAL and applied end-to-start."""
        (self.tmpdir / "a.txt").write_text("foo\nbar\n")
        r = d._apply_changes(self._task(), self._upstream([
            {"id": "C1", "file": "a.txt", "before": "foo", "after": "bar"},
            {"id": "C2", "file": "a.txt", "before": "bar\n", "after": "BAR\n"},
        ]))
        self.assertNotIn("error", r.outputs)
        # C2 found 'bar\n' at original position 4-7 (the original 'bar\n').
        # C1 replaced 'foo' (pos 0-2) with 'bar'. End-to-start: C2 first
        # then C1 -> 'foo\nBAR\n' -> 'bar\nBAR\n'.
        self.assertEqual((self.tmpdir / "a.txt").read_text(), "bar\nBAR\n")

    def test_overlapping_edits_one_rejected(self):
        (self.tmpdir / "a.txt").write_text("hello world\n")
        r = d._apply_changes(self._task(), self._upstream([
            {"id": "C1", "file": "a.txt", "before": "hello world",
             "after": "GREETING"},
            {"id": "C2", "file": "a.txt", "before": "lo wor",
             "after": "LO WOR"},
        ]))
        # Both `before` snippets appear once. They overlap on positions
        # 3-9. Greedy: C1 starts earliest (pos 0), kept. C2 starts at
        # pos 3 (< C1's end at 11), rejected as overlap.
        self.assertEqual(r.outputs.get("error"), "apply_partial_failure")
        applied_ids = {a["id"] for a in r.outputs["applied"]}
        failed_reasons = {f["id"]: f["reason"] for f in r.outputs["failed"]}
        self.assertEqual(applied_ids, {"C1"})
        self.assertEqual(failed_reasons.get("C2"), "overlaps_other_change")
        # C1 must have actually been written.
        self.assertEqual((self.tmpdir / "a.txt").read_text(), "GREETING\n")

    def test_edits_to_different_files_independent(self):
        (self.tmpdir / "a.txt").write_text("aaa")
        (self.tmpdir / "b.txt").write_text("bbb")
        r = d._apply_changes(self._task(), self._upstream([
            {"id": "C1", "file": "a.txt", "before": "aaa", "after": "AAA"},
            {"id": "C2", "file": "b.txt", "before": "bbb", "after": "BBB"},
        ]))
        self.assertNotIn("error", r.outputs)
        self.assertEqual((self.tmpdir / "a.txt").read_text(), "AAA")
        self.assertEqual((self.tmpdir / "b.txt").read_text(), "BBB")

    def test_mix_of_create_and_edit(self):
        (self.tmpdir / "a.txt").write_text("existing\n")
        r = d._apply_changes(self._task(), self._upstream([
            {"id": "C1", "file": "a.txt", "before": "existing",
             "after": "MODIFIED"},
            {"id": "C2", "file": "new.txt", "before": None,
             "after": "freshly created"},
        ]))
        self.assertNotIn("error", r.outputs)
        # Edit mode doesn't add BOM; create mode does — utf-8-sig handles both.
        self.assertEqual(
            (self.tmpdir / "a.txt").read_text(encoding="utf-8-sig"),
            "MODIFIED\n"
        )
        self.assertEqual(
            (self.tmpdir / "new.txt").read_text(encoding="utf-8-sig"),
            "freshly created"
        )

    def test_position_preservation_under_end_to_start(self):
        """Apply order MUST be end-to-start so earlier positions don't
        shift after later replacements. Test with size-changing edits."""
        (self.tmpdir / "a.txt").write_text("xxxxx-----yyyyy")
        r = d._apply_changes(self._task(), self._upstream([
            {"id": "C1", "file": "a.txt", "before": "xxxxx",
             "after": "X"},   # shrinks
            {"id": "C2", "file": "a.txt", "before": "yyyyy",
             "after": "YYYYYYYYYY"},  # grows
        ]))
        self.assertNotIn("error", r.outputs)
        self.assertEqual((self.tmpdir / "a.txt").read_text(),
                         "X-----YYYYYYYYYY")


class TestApplyViaInvokeAgent(unittest.TestCase):
    """Verify the applier is correctly registered in SYSTEM_AGENTS and
    routed through invoke_agent (not invoke_subagent)."""

    def test_applier_in_system_agents(self):
        self.assertIn("applier", d.SYSTEM_AGENTS)
        self.assertIs(d.SYSTEM_AGENTS["applier"], d._apply_changes)

    def test_invoke_agent_routes_applier_to_system_handler(self):
        # Empty changes => clean success; no LLM call needed.
        tmp = Path(tempfile.mkdtemp(prefix="fnsr-route-test-"))
        try:
            task = {
                "@id": "urn:t:apply",
                "agent": "applier",
                "inputs": {"source_task": "urn:t:dev",
                           "apply_root": str(tmp)},
            }
            r = d.invoke_agent("applier", task,
                                {"urn:t:dev": {"changes": []}})
            self.assertTrue(r.ok)
            self.assertNotIn("error", r.outputs)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
