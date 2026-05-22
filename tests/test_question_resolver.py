import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fnsr_daemon as d


SEED_DECISIONS = """﻿# Architecture Decision Records

## ADR-001: Use JSON-LD Deterministic Service Template

**Date:** 2026-05-15

**Decision:** Adopt the template as the base architecture.

**Context:** Need deterministic transformations.

**Consequences:**
- All transformation logic in `src/kernel/`
- Spec tests must pass

---
"""


class TestQuestionResolver(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="fnsr-qr-test-"))
        self.decisions_path = self.tmpdir / "DECISIONS.md"
        self.decisions_path.write_text(SEED_DECISIONS, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _task(self, source_id="urn:t:syn"):
        return {
            "@id": "urn:t:qr",
            "agent": "question-resolver",
            "inputs": {
                "source_task": source_id,
                "answers": [],
                "decisions_path": str(self.decisions_path),
            },
        }

    def _upstream(self, questions, source_id="urn:t:syn"):
        return {source_id: {"outstanding_questions": questions}}

    def test_single_answer_produces_adr_002(self):
        task = self._task()
        task["inputs"]["answers"] = [{
            "title": "Excise SPEC item 14",
            "decision": "Remove the second-implementation DoD requirement.",
            "context": "No second implementation is planned.",
            "consequences": ["Phase 6 simpler", "Interop deferred to v0.5"],
        }]
        r = d._question_resolver(task, self._upstream(["Q1?"]))
        self.assertNotIn("error", r.outputs)
        change = r.outputs["changes"][0]
        self.assertIn("## ADR-002:", change["after"])
        self.assertIn("Excise SPEC item 14", change["after"])
        self.assertIn("- Phase 6 simpler", change["after"])
        self.assertIn("- Interop deferred to v0.5", change["after"])
        # The before is the current file content
        self.assertEqual(change["before"], SEED_DECISIONS)

    def test_multiple_answers_numbered_sequentially(self):
        task = self._task()
        task["inputs"]["answers"] = [
            {"title": "First", "decision": "x", "context": "y",
             "consequences": ["a"]},
            {"title": "Second", "decision": "x", "context": "y",
             "consequences": ["b"]},
            {"title": "Third", "decision": "x", "context": "y",
             "consequences": ["c"]},
        ]
        r = d._question_resolver(task,
                                  self._upstream(["Q1", "Q2", "Q3"]))
        self.assertNotIn("error", r.outputs)
        after = r.outputs["changes"][0]["after"]
        self.assertIn("ADR-002:", after)
        self.assertIn("ADR-003:", after)
        self.assertIn("ADR-004:", after)
        self.assertIn("drafted 3 ADR(s) (ADR-002 through ADR-004)",
                      r.outputs["summary"])
        self.assertEqual(r.outputs["self_assessment"], "confident")

    def test_deferred_answer_skipped_and_marked_uncertain(self):
        task = self._task()
        task["inputs"]["answers"] = [
            {"title": "Answered", "decision": "x", "context": "y",
             "consequences": []},
            None,  # deferred
            {"title": "Also answered", "decision": "x", "context": "y",
             "consequences": []},
        ]
        r = d._question_resolver(task,
                                  self._upstream(["Q1", "Q2", "Q3"]))
        self.assertNotIn("error", r.outputs)
        after = r.outputs["changes"][0]["after"]
        # Two ADRs produced (ADR-002 and ADR-003), Q2 was deferred
        self.assertIn("ADR-002:", after)
        self.assertIn("ADR-003:", after)
        self.assertNotIn("ADR-004:", after)
        self.assertEqual(r.outputs["self_assessment"], "uncertain")
        self.assertIn("1 question(s) deferred", r.outputs["summary"])

    def test_missing_source_task(self):
        task = {"@id": "urn:t", "agent": "question-resolver", "inputs": {}}
        r = d._question_resolver(task, {})
        self.assertEqual(r.outputs["error"], "missing_source_task")

    def test_answers_must_be_list(self):
        task = self._task()
        task["inputs"]["answers"] = {"not": "a list"}
        r = d._question_resolver(task, self._upstream(["Q1"]))
        self.assertEqual(r.outputs["error"], "answers_must_be_list")

    def test_malformed_answer_in_list(self):
        task = self._task()
        task["inputs"]["answers"] = ["not a dict"]
        r = d._question_resolver(task, self._upstream(["Q1"]))
        self.assertEqual(r.outputs["error"], "malformed_answer")
        self.assertEqual(r.outputs["index"], 0)

    def test_answer_missing_required_fields(self):
        task = self._task()
        task["inputs"]["answers"] = [{"title": "T"}]  # missing decision+context
        r = d._question_resolver(task, self._upstream(["Q1"]))
        self.assertEqual(r.outputs["error"], "answer_missing_fields")
        self.assertEqual(set(r.outputs["missing"]), {"decision", "context"})

    def test_source_has_no_outstanding_questions(self):
        task = self._task()
        task["inputs"]["answers"] = [{"title": "T", "decision": "d",
                                       "context": "c", "consequences": []}]
        # Source upstream has no outstanding_questions
        r = d._question_resolver(task, {"urn:t:syn": {"summary": "x"}})
        self.assertEqual(r.outputs["error"],
                         "source_has_no_outstanding_questions")

    def test_no_answers_provided_returns_error(self):
        task = self._task()
        task["inputs"]["answers"] = [None, None]
        r = d._question_resolver(task,
                                  self._upstream(["Q1", "Q2"]))
        self.assertEqual(r.outputs["error"], "no_answers_provided")
        self.assertEqual(r.outputs["deferred"], 2)

    def test_decisions_file_not_found(self):
        task = self._task()
        task["inputs"]["answers"] = [{"title": "T", "decision": "d",
                                       "context": "c"}]
        task["inputs"]["decisions_path"] = str(self.tmpdir / "missing.md")
        r = d._question_resolver(task, self._upstream(["Q1"]))
        self.assertEqual(r.outputs["error"], "decisions_file_not_found")

    def test_adr_format_matches_existing_style(self):
        task = self._task()
        task["inputs"]["answers"] = [{
            "title": "Test Decision",
            "decision": "We will do X.",
            "context": "Because of Y.",
            "consequences": ["A happens", "B happens"],
        }]
        r = d._question_resolver(task, self._upstream(["Q1"]))
        after = r.outputs["changes"][0]["after"]
        self.assertIn("## ADR-002: Test Decision", after)
        self.assertIn("**Date:** 2026-", after)  # today's year
        self.assertIn("**Decision:** We will do X.", after)
        self.assertIn("**Context:** Because of Y.", after)
        self.assertIn("**Consequences:**\n- A happens\n- B happens", after)

    def test_registered_in_system_agents(self):
        self.assertIn("question-resolver", d.SYSTEM_AGENTS)
        self.assertIs(d.SYSTEM_AGENTS["question-resolver"],
                       d._question_resolver)

    def test_required_outputs_declared_for_cps(self):
        self.assertEqual(
            d._agent_required_outputs("question-resolver"),
            ["changes", "summary", "self_assessment"]
        )

    def test_before_preserves_bom(self):
        """The before snippet must include the BOM so it matches what the
        applier reads from the file (applier reads with utf-8 not utf-8-sig)."""
        task = self._task()
        task["inputs"]["answers"] = [{"title": "T", "decision": "d",
                                       "context": "c"}]
        r = d._question_resolver(task, self._upstream(["Q1"]))
        before = r.outputs["changes"][0]["before"]
        self.assertTrue(before.startswith("﻿"))


if __name__ == "__main__":
    unittest.main()
