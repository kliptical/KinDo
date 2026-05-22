import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fnsr_daemon as d


class TestCpsCheck(unittest.TestCase):
    def test_null_vetoes(self):
        with self.assertRaises(d.ContainmentVeto):
            d.cps_check({"agent": "spec-reviewer"}, None)

    def test_structured_error_vetoes(self):
        with self.assertRaises(d.ContainmentVeto):
            d.cps_check({"agent": "spec-reviewer"},
                        {"error": "insufficient_inputs", "needed": []})

    def test_error_null_value_passes(self):
        # error: None is legitimate uniform-schema; treat as not-error.
        d.cps_check({"agent": "nonexistent"},
                    {"random": "x", "error": None})

    def test_error_empty_string_passes(self):
        d.cps_check({"agent": "nonexistent"},
                    {"random": "x", "error": ""})

    def test_missing_required_key_vetoes(self):
        with self.assertRaises(d.ContainmentVeto):
            # spec-reviewer requires findings, summary, recommendation
            d.cps_check({"agent": "spec-reviewer"},
                        {"findings": [], "summary": "x"})

    def test_valid_full_outputs_pass(self):
        d.cps_check({"agent": "spec-reviewer"},
                    {"findings": [], "summary": "x",
                     "recommendation": "accept"})

    def test_applier_required_keys(self):
        d.cps_check({"agent": "applier"},
                    {"applied": [], "failed": [], "summary": "0 applied"})

    def test_unknown_agent_no_required_check(self):
        # No .md file => no required_outputs => only null/error checks apply.
        d.cps_check({"agent": "nonexistent"}, {"anything": "goes"})


class TestRequiredOutputsParsing(unittest.TestCase):
    def test_spec_reviewer(self):
        self.assertEqual(d._agent_required_outputs("spec-reviewer"),
                         ["findings", "summary", "recommendation"])

    def test_developer(self):
        self.assertEqual(d._agent_required_outputs("developer"),
                         ["changes", "summary", "self_assessment"])

    def test_applier_system_agent(self):
        self.assertEqual(d._agent_required_outputs("applier"),
                         ["applied", "failed", "summary"])

    def test_unknown_agent(self):
        self.assertEqual(d._agent_required_outputs("nonexistent"), [])


class TestMultiModeRequiredOutputs(unittest.TestCase):
    """v2.7.0 architect.md declares required_outputs by mode (review vs
    ratification per Spec 03). Parsing must return the correct list for
    each mode and return an empty list when the mode is unrecognized or
    omitted for a multi-mode agent."""

    def test_architect_review_mode(self):
        result = d._agent_required_outputs("architect", mode="review")
        self.assertEqual(result, [
            "findings", "recommendations", "summary", "recommendation",
        ])

    def test_architect_ratification_mode(self):
        result = d._agent_required_outputs("architect", mode="ratification")
        self.assertEqual(result, [
            "ruling", "editorial_verdict", "editorial_verdict_reason",
            "rationale", "referenced_evidence", "bankings",
        ])

    def test_architect_unknown_mode_returns_empty(self):
        # Mode the agent doesn't declare -> empty list (no required keys
        # enforced). Operator should know what mode the task is using.
        self.assertEqual(
            d._agent_required_outputs("architect", mode="nonexistent_mode"),
            [],
        )

    def test_architect_no_mode_passed_returns_empty(self):
        # Multi-mode agent invoked without a mode -> empty required list.
        # Callers (cps_check) MUST pass task inputs.mode to enforce.
        self.assertEqual(d._agent_required_outputs("architect"), [])

    def test_flat_list_agent_ignores_mode_arg(self):
        # Single-mode agents (flat-list required_outputs) ignore the mode
        # arg and return the full list regardless.
        self.assertEqual(
            d._agent_required_outputs("developer", mode="any-mode"),
            ["changes", "summary", "self_assessment"],
        )


class TestArchitectRatificationCpsCheck(unittest.TestCase):
    """CPS check picks the right required_outputs list based on
    task.inputs.mode for multi-mode agents. v2.7.0 architect is the
    first such agent."""

    def test_ratification_mode_full_payload_passes(self):
        task = {"agent": "architect", "inputs": {"mode": "ratification"}}
        outputs = {
            "ruling": "ratified",
            "editorial_verdict": "substantive",
            "editorial_verdict_reason": "modifies normative shall language",
            "rationale": "evidence supports the change",
            "referenced_evidence": [],
            "bankings": [],  # empty list is valid per Aaron's minor-item-1
        }
        # MUST NOT raise.
        d.cps_check(task, outputs)

    def test_ratification_mode_missing_ruling_vetoes(self):
        task = {"agent": "architect", "inputs": {"mode": "ratification"}}
        outputs = {
            "editorial_verdict": "substantive",
            "editorial_verdict_reason": "x",
            "rationale": "x",
            "referenced_evidence": [],
            "bankings": [],
        }
        with self.assertRaises(d.ContainmentVeto) as ctx:
            d.cps_check(task, outputs)
        self.assertIn("ruling", str(ctx.exception))

    def test_ratification_mode_missing_editorial_verdict_reason_vetoes(self):
        # The editorial_verdict_reason field is required even when the
        # editorial_verdict itself is provided — operator audit
        # requirement per Aaron's Gap 3 refinement.
        task = {"agent": "architect", "inputs": {"mode": "ratification"}}
        outputs = {
            "ruling": "denied",
            "editorial_verdict": "substantive",
            "rationale": "reconnaissance_required",
            "referenced_evidence": [],
            "bankings": [],
        }
        with self.assertRaises(d.ContainmentVeto) as ctx:
            d.cps_check(task, outputs)
        self.assertIn("editorial_verdict_reason", str(ctx.exception))

    def test_ratification_mode_empty_bankings_list_passes(self):
        # Aaron minor-item-1: bankings: [] is acceptable.
        task = {"agent": "architect", "inputs": {"mode": "ratification"}}
        outputs = {
            "ruling": "ratified",
            "editorial_verdict": "editorial",
            "editorial_verdict_reason": "typo fix",
            "rationale": "no substantive change",
            "referenced_evidence": [],
            "bankings": [],
        }
        d.cps_check(task, outputs)

    def test_review_mode_uses_review_required_keys(self):
        task = {"agent": "architect", "inputs": {"mode": "review"}}
        outputs = {
            "findings": [],
            "recommendations": [],
            "summary": "x",
            "recommendation": "accept",
        }
        d.cps_check(task, outputs)

    def test_review_mode_missing_recommendation_vetoes(self):
        task = {"agent": "architect", "inputs": {"mode": "review"}}
        outputs = {
            "findings": [], "recommendations": [], "summary": "x",
        }
        with self.assertRaises(d.ContainmentVeto):
            d.cps_check(task, outputs)


class TestReconnaissanceContract(unittest.TestCase):
    """v2.7.0 reconnaissance.md is the first instance of the
    read-only-by-contract agent pattern. Verifies the contract surface
    declared in frontmatter is what we expect; downstream agents
    (verification-ritual, future moral-person evidence-collection) can
    draw on this shape."""

    def test_reconnaissance_required_outputs(self):
        self.assertEqual(
            d._agent_required_outputs("reconnaissance"),
            ["findings", "summary", "evidence_paths"],
        )

    def test_reconnaissance_required_outputs_passes_cps(self):
        task = {"agent": "reconnaissance"}
        outputs = {
            "findings": [
                {"id": "F1", "claim": "...", "evidence": [],
                 "kind": "observation"}
            ],
            "summary": "...",
            "evidence_paths": ["src/x.ts"],
        }
        d.cps_check(task, outputs)

    def test_reconnaissance_scope_violation_error_vetoes(self):
        # Reconnaissance returning error=scope_violation should veto via
        # the structured-error path (existing v2.6.0 behavior).
        task = {"agent": "reconnaissance"}
        outputs = {
            "error": "scope_violation",
            "what_was_asked": "propose a fix",
            "why_it_violates_contract": "requires proposal, not observation",
            "what_i_can_do_instead": "observe current state of the affected files",
        }
        with self.assertRaises(d.ContainmentVeto) as ctx:
            d.cps_check(task, outputs)
        self.assertIn("scope_violation", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
