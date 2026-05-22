"""Tests for v3.0-alpha.2 substrate additions.

Covers:
- Episodic→Semantic primitive doc presence
- Anti-pattern enforcement framework (4 generalizable patterns):
    persona theater, redundant affirmation, freeform brainstorm,
    + section-pattern matcher (substrate-deterministic permitted_sections)
- TestReadOnlyContractValidation: corpus-wide validation of every
  agent declaring contract_class: read-only (per Aaron's CP2 obs #1)
- Retro-applier system agent (deterministic merger)
- Phase-complete-declaration operator surface (operator-authoritative
  per Aaron's CP2 obs #4)
- MAREP-Orchestrator BAO contract (multi-mode required_outputs;
  cross-validated against TestBaoBoundsValidation from CP1)
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fnsr_daemon as d
import state_admin


# ---------- Episodic→Semantic primitive doc -----------------------------

class TestEpisodicToSemanticPrimitiveDoc(unittest.TestCase):
    @property
    def doc_path(self):
        return (Path(__file__).resolve().parent.parent
                / "surfaces" / "_primitives"
                / "episodic-to-semantic-promotion.md")

    def test_doc_exists(self):
        self.assertTrue(self.doc_path.exists(),
                         "Episodic→Semantic primitive doc must exist")

    def test_doc_declares_metadata(self):
        text = self.doc_path.read_text(encoding="utf-8")
        fm = d._parse_category_frontmatter(text)
        self.assertEqual(fm["primitive_id"], "episodic-to-semantic-promotion")
        self.assertEqual(fm["short_name"], "E→S Promotion")
        self.assertEqual(fm["introduced_in"], "v3.0-alpha.2")

    def test_doc_specifies_three_memory_layers(self):
        text = self.doc_path.read_text(encoding="utf-8")
        self.assertIn("Working memory", text)
        self.assertIn("Episodic memory", text)
        self.assertIn("Semantic memory", text)


# ---------- Anti-pattern enforcement framework --------------------------

class TestAntiPatternPersonaTheater(unittest.TestCase):
    def test_clean_output_passes(self):
        outputs = {
            "proposed_issues": [
                {"id": "QA-1", "title": "Test coverage gap",
                 "rationale": "Module X has no tests for branch Y."}
            ],
            "summary": "Found one coverage gap.",
        }
        # MUST NOT raise
        d._check_no_persona_theater({"agent": "qa"}, outputs)

    def test_persona_address_in_free_text_vetoes(self):
        outputs = {
            "proposed_issues": [{
                "id": "QA-1",
                "rationale": "Great point @Architect — coverage is low here.",
            }],
        }
        with self.assertRaises(d.ContainmentVeto) as ctx:
            d._check_no_persona_theater({"agent": "qa"}, outputs)
        self.assertIn("persona_theater_detected", str(ctx.exception))

    def test_designated_reference_fields_allow_addresses(self):
        # @-addresses are LEGITIMATE in designated reference fields
        # (votes.cast[*].agent, confirmed_by, contested_by, owner, etc.)
        outputs = {
            "proposed_issues": [{
                "id": "QA-1",
                "confirmed_by": ["@Architect", "@Skeptic"],
                "contested_by": [],
                "rationale": "Plain prose without persona theater.",
            }],
        }
        # MUST NOT raise
        d._check_no_persona_theater({"agent": "qa"}, outputs)


class TestAntiPatternRedundantAffirmation(unittest.TestCase):
    def test_no_prior_turn_is_no_op(self):
        outputs = {"summary": "First turn outputs."}
        # No prior_turn_outputs → no-op
        d._check_no_redundant_affirmation(
            {"agent": "qa"}, outputs, prior_turn_outputs=None)

    def test_substantial_overlap_vetoes(self):
        prior = {"summary": "Coverage gap in module X identified. "
                            "Three test files missing for the new feature. "
                            "Severity major."}
        current = {"summary": "Coverage gap in module X identified. "
                              "Three test files missing for the new feature. "
                              "Severity major."}
        with self.assertRaises(d.ContainmentVeto) as ctx:
            d._check_no_redundant_affirmation(
                {"agent": "qa"}, current,
                prior_turn_outputs=prior, threshold=0.85)
        self.assertIn("redundant_affirmation", str(ctx.exception))

    def test_substantively_different_passes(self):
        prior = {"summary": "Coverage gap in module X identified."}
        current = {"summary": "Delivery throughput dropped 30% this sprint "
                              "due to dependency thrash on the auth refactor."}
        # Different content → no veto
        d._check_no_redundant_affirmation(
            {"agent": "dm"}, current,
            prior_turn_outputs=prior, threshold=0.85)


class TestAntiPatternFreeformBrainstorm(unittest.TestCase):
    def test_within_length_budget_passes(self):
        outputs = {
            "summary": "Short summary within budget.",
        }
        budgets = {"summary": 500}
        d._check_no_freeform_brainstorm(
            {"agent": "qa"}, outputs, length_budgets=budgets)

    def test_length_overrun_vetoes(self):
        outputs = {
            "summary": "x" * 1000,
        }
        budgets = {"summary": 100}
        with self.assertRaises(d.ContainmentVeto) as ctx:
            d._check_no_freeform_brainstorm(
                {"agent": "qa"}, outputs, length_budgets=budgets)
        self.assertIn("freeform_brainstorm_drift", str(ctx.exception))

    def test_forbidden_connective_vetoes(self):
        outputs = {
            "summary": "As we discussed earlier, the test coverage is low.",
        }
        with self.assertRaises(d.ContainmentVeto) as ctx:
            d._check_no_freeform_brainstorm({"agent": "qa"}, outputs)
        self.assertIn("freeform_brainstorm_drift", str(ctx.exception))

    def test_default_forbidden_connectives_applied(self):
        # Default list includes "circling back" — should fire
        outputs = {"summary": "Circling back to the QA finding..."}
        with self.assertRaises(d.ContainmentVeto):
            d._check_no_freeform_brainstorm({"agent": "qa"}, outputs)


class TestSectionPatternMatcher(unittest.TestCase):
    """MAREP_INTEGRATION_SPEC §5.2 formal JSONPath subset."""

    def test_top_level_key_matches_subtree(self):
        self.assertTrue(d._section_pattern_matches("issues", "issues"))
        self.assertTrue(d._section_pattern_matches("issues.id", "issues"))
        self.assertTrue(d._section_pattern_matches("issues[0].title", "issues"))

    def test_dot_traversal_strict(self):
        self.assertTrue(d._section_pattern_matches("retro.phase", "retro.phase"))
        # retro alone does NOT match retro.phase pattern (pattern is more specific)
        self.assertFalse(d._section_pattern_matches("retro", "retro.phase"))

    def test_array_wildcard_matches_any_index(self):
        self.assertTrue(d._section_pattern_matches(
            "issues[0].qa_evidence", "issues[*].qa_evidence"))
        self.assertTrue(d._section_pattern_matches(
            "issues[5].qa_evidence", "issues[*].qa_evidence"))

    def test_array_wildcard_scopes_subkey(self):
        # pattern issues[*]/qa_evidence does NOT match a sibling field
        self.assertFalse(d._section_pattern_matches(
            "issues[0].dm_evidence", "issues[*]/qa_evidence"))


class TestAntiPatternRetroSurfaceScoping(unittest.TestCase):
    """Per MAREP_INTEGRATION_SPEC §7.5: anti-pattern checks fire only
    on retro-surface tasks (inputs.surface: retro)."""

    def test_non_retro_task_not_subject_to_anti_pattern_checks(self):
        # Non-retro task with persona-theater-shaped output: CPS
        # validates required_outputs but does NOT apply persona-theater
        # detection.
        task = {"agent": "nonexistent",
                "inputs": {}}  # no inputs.surface
        outputs = {
            "rationale": "Great point @QA — building on what you said...",
        }
        # MUST NOT raise — non-retro task; anti-pattern checks don't fire
        d.cps_check(task, outputs)

    def test_retro_task_with_explicit_surface_triggers_checks(self):
        task = {"agent": "nonexistent",
                "inputs": {"surface": "retro"}}
        outputs = {
            "rationale": "Great point @QA — building on what you said...",
        }
        with self.assertRaises(d.ContainmentVeto):
            d.cps_check(task, outputs)

    def test_is_retro_surface_task_detection(self):
        self.assertTrue(d._is_retro_surface_task(
            {"inputs": {"surface": "retro"}}))
        self.assertFalse(d._is_retro_surface_task(
            {"inputs": {"surface": "verification"}}))
        self.assertFalse(d._is_retro_surface_task({"inputs": {}}))
        self.assertFalse(d._is_retro_surface_task({}))


# ---------- TestReadOnlyContractValidation (Aaron's obs #1) -------------

class TestReadOnlyContractValidation(unittest.TestCase):
    """Corpus-wide validation: every agent declaring
    contract_class: read-only MUST satisfy the read-only-by-contract
    invariants. Generalizes the v3.0-alpha.1 TestBaoBoundsValidation
    pattern — substrate now mechanically validates conformance to two
    patterns (BAO and read-only-by-contract) across the agent corpus.
    """

    def _read_only_agents(self):
        """Find every agent .md file declaring contract_class: read-only."""
        agents_dir = Path(__file__).resolve().parent.parent / ".claude" / "agents"
        ro_agents = []
        for path in sorted(agents_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            fm = d._parse_category_frontmatter(text)
            if not fm:
                continue
            if fm.get("contract_class") == "read-only":
                ro_agents.append((path.name, fm, text))
        return ro_agents

    def test_corpus_has_read_only_agents(self):
        ro_agents = self._read_only_agents()
        # As of v3.0-alpha.2: reconnaissance (v2.7.0),
        # verification-ritual-llm (v2.8.0), adversarial-critic (v2.8.0),
        # synthesist (v3.0-alpha.1), qa, delivery-manager, risk-analyst,
        # marep-orchestrator (v3.0-alpha.2). Minimum 8.
        self.assertGreaterEqual(len(ro_agents), 8,
                                 "v3.0-alpha.2 should have at least 8 "
                                 "read-only-by-contract agents")

    def test_every_read_only_agent_uses_only_read_tools(self):
        # Read-only-by-contract: tools must be Read/Grep/Glob; no Edit,
        # Write, or Bash.
        for name, fm, _text in self._read_only_agents():
            tools = fm.get("tools", "")
            for forbidden in ("Edit", "Write", "Bash"):
                self.assertNotIn(forbidden, tools,
                                  f"read-only agent {name} declares "
                                  f"forbidden tool {forbidden!r}")

    def test_every_read_only_agent_declares_required_outputs(self):
        # Read-only agents produce structured observations; required_outputs
        # MUST be declared so CPS can enforce.
        for name, fm, _text in self._read_only_agents():
            # required_outputs may be flat list or per-mode dict — both fine
            has_required = (
                "required_outputs" in fm
                or any(k for k in fm.keys()
                       if k.startswith("required_outputs"))
            )
            # _parse_category_frontmatter only captures flat-list; multi-mode
            # is parsed by a separate helper. Cross-check by reading raw text.
            if not has_required:
                # Multi-mode agents have required_outputs as YAML dict;
                # confirm presence in raw text
                self.assertIn("required_outputs:", _text,
                               f"read-only agent {name} missing "
                               f"required_outputs declaration")

    def test_every_read_only_agent_documents_refusal_contract(self):
        # Read-only agents MUST document what they emit on error
        # (structured error envelope is the substrate contract). The
        # documented surface is what makes the contract operator-
        # discoverable; an agent whose prompt doesn't name its error
        # cases isn't honoring the contract surface.
        for name, _fm, text in self._read_only_agents():
            text_lower = text.lower()
            # Any documented error case satisfies this check —
            # "error:" envelope syntax OR refuse/refusal language OR
            # scope_violation marker.
            has_error_documentation = (
                "scope_violation" in text_lower
                or "structured error" in text_lower
                or "refusal contract" in text_lower
                or "refuse" in text_lower
                or '"error":' in text_lower
                or "error\":" in text_lower
                or "{ \"outputs\": { \"error\"" in text_lower
            )
            self.assertTrue(has_error_documentation,
                             f"read-only agent {name} should document "
                             f"its error envelope or refusal contract "
                             f"in the prompt")


# ---------- Retro-applier system agent ----------------------------------

class TestRetroApplier(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="fnsr-retro-applier-"))
        self.state_path = self.tmpdir / "RETRO_STATE.jsonld"
        self.state_path.write_text(json.dumps({
            "@context": "https://barcode.substrate/retro/v1",
            "retro": {"@id": "urn:retro:test", "sprint": "sprint-1",
                       "phase": "analysis", "version": 7,
                       "schema_version": "1.0"},
            "issues": [], "actions": [], "decisions": [],
            "votes": [], "audit": [],
        }, indent=2), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _dispatch(self, **inputs):
        task = {"@id": "urn:fnsr:task:retro-merge",
                "agent": "retro-applier",
                "inputs": {"retro_state_path": str(self.state_path),
                           **inputs}}
        return d._retro_apply(task, {})

    def test_happy_path_merges_proposals(self):
        result = self._dispatch(version_read=7, proposals={
            "urn:fnsr:task:qa-1": {"outputs": {"proposed_issues": [
                {"@id": "QA-1", "title": "Coverage gap"}
            ]}},
        })
        self.assertEqual(result.outputs["retro_state_version"], 8)
        self.assertEqual(len(result.outputs["applied"]), 1)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(len(state["issues"]), 1)
        self.assertEqual(state["issues"][0]["@id"], "QA-1")

    def test_version_mismatch_returns_error(self):
        result = self._dispatch(version_read=999, proposals={})
        self.assertEqual(result.outputs.get("error"), "version_mismatch")
        self.assertEqual(result.outputs.get("current_version"), 7)

    def test_audit_chain_appended(self):
        self._dispatch(version_read=7, proposals={
            "urn:fnsr:task:qa-1": {"outputs": {"proposed_issues": [
                {"@id": "QA-1", "title": "x"}
            ]}}})
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(len(state["audit"]), 1)
        entry = state["audit"][0]
        self.assertEqual(entry["version"], 8)
        self.assertIn("chain_hash", entry)
        self.assertIn("prev_hash", entry)
        # First entry's prev_hash is genesis (all zeros)
        self.assertEqual(entry["prev_hash"], "0" * 64)

    def test_idempotent_reapplication(self):
        proposal = {"urn:fnsr:task:qa-1": {"outputs": {"proposed_issues": [
            {"@id": "QA-1", "title": "x"}]}}}
        self._dispatch(version_read=7, proposals=proposal)
        # Second dispatch with same @id — should be no-op (already present)
        result = self._dispatch(version_read=8, proposals=proposal)
        # No new applies; but version still increments per substrate-mutation invariant
        self.assertEqual(result.outputs["retro_state_version"], 9)
        self.assertEqual(len(result.outputs["applied"]), 0)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        # Still only 1 issue (idempotent)
        self.assertEqual(len(state["issues"]), 1)

    def test_proposal_missing_id_goes_to_failed(self):
        result = self._dispatch(version_read=7, proposals={
            "urn:fnsr:task:qa-1": {"outputs": {"proposed_issues": [
                {"title": "no id"}  # missing @id
            ]}}})
        self.assertEqual(len(result.outputs["failed"]), 1)
        self.assertEqual(result.outputs["failed"][0]["reason"],
                          "schema_violation")

    def test_unreadable_state_returns_error(self):
        task = {"@id": "urn:test", "agent": "retro-applier",
                "inputs": {"retro_state_path": "/nonexistent/path.jsonld"}}
        result = d._retro_apply(task, {})
        self.assertEqual(result.outputs.get("error"),
                          "retro_state_unreadable")

    def test_missing_retro_state_path_returns_error(self):
        task = {"@id": "urn:test", "agent": "retro-applier", "inputs": {}}
        result = d._retro_apply(task, {})
        self.assertEqual(result.outputs.get("error"),
                          "retro_state_path_missing")

    def test_multiple_sources_merged_in_one_mutation(self):
        result = self._dispatch(version_read=7, proposals={
            "urn:fnsr:task:qa-1": {"outputs": {"proposed_issues": [
                {"@id": "QA-1", "title": "x"}]}},
            "urn:fnsr:task:dm-1": {"outputs": {"proposed_issues": [
                {"@id": "DM-1", "title": "y"}]}},
            "urn:fnsr:task:ra-1": {"outputs": {"proposed_risks": [
                {"@id": "RA-1", "title": "z"}]}},
        })
        self.assertEqual(len(result.outputs["applied"]), 3)
        # One mutation, one audit entry
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.assertEqual(len(state["audit"]), 1)


# ---------- Phase-complete-declaration ----------------------------------

class TestPhaseCompleteDeclaration(unittest.TestCase):
    """v3.0-alpha.2: operator-authoritative phase-complete event per
    Aaron's CP2 observation #4. NOT a predicate-derived assertion."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="fnsr-pcd-"))
        self.state_path = self.tmpdir / "state.jsonld"
        self.state_path.write_text(json.dumps({
            "@context": "x", "@id": "urn:test",
            "tasks": [{"@id": "urn:fnsr:task:t1", "agent": "x",
                        "status": "done", "depends_on": [], "history": []}],
        }, indent=2), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_happy_path_records_event(self):
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "phase-complete-declaration", "phase-3",
            "--anchor-task", "urn:fnsr:task:t1",
            "--rationale", "All ACs verified by operator review",
            "--acceptance-criteria-met", "AC-3.1,AC-3.2,AC-3.3",
        ])
        self.assertEqual(rc, 0)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        history = state["tasks"][0]["history"]
        self.assertEqual(len(history), 1)
        evt = history[0]
        self.assertEqual(evt["event"], "phase_complete_declared")
        self.assertEqual(evt["payload"]["phase"], "phase-3")
        self.assertEqual(evt["payload"]["acceptance_criteria_met"],
                          ["AC-3.1", "AC-3.2", "AC-3.3"])
        self.assertEqual(evt["payload"]["declaration_kind"],
                          "operator_authoritative")

    def test_rationale_required(self):
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "phase-complete-declaration", "phase-3",
            "--anchor-task", "urn:fnsr:task:t1",
            "--rationale", "   ",  # whitespace only
        ])
        self.assertEqual(rc, 1)

    def test_pending_acs_recorded(self):
        state_admin.main([
            "--state-path", str(self.state_path),
            "phase-complete-declaration", "phase-3",
            "--anchor-task", "urn:fnsr:task:t1",
            "--rationale", "Phase complete with known-pending ACs",
            "--acceptance-criteria-met", "AC-3.1,AC-3.2",
            "--acceptance-criteria-pending", "AC-3.4",
        ])
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        evt = state["tasks"][0]["history"][0]
        self.assertEqual(evt["payload"]["acceptance_criteria_pending"],
                          ["AC-3.4"])

    def test_declaration_kind_is_operator_authoritative(self):
        # Confirms Aaron's CP2 obs #4: NOT predicate-derived
        state_admin.main([
            "--state-path", str(self.state_path),
            "phase-complete-declaration", "phase-1",
            "--anchor-task", "urn:fnsr:task:t1",
            "--rationale", "Test rationale",
        ])
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        evt = state["tasks"][0]["history"][0]
        # The substrate records declaration_kind so future operators
        # can distinguish operator-declared from any future
        # predicate-derived phase-complete events.
        self.assertEqual(evt["payload"]["declaration_kind"],
                          "operator_authoritative")

    def test_chain_integrity_preserved(self):
        state_admin.main([
            "--state-path", str(self.state_path),
            "phase-complete-declaration", "phase-3",
            "--anchor-task", "urn:fnsr:task:t1",
            "--rationale", "test",
        ])
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "verify", "--quiet",
        ])
        self.assertEqual(rc, 0)

    def test_unknown_anchor_task_returns_error(self):
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "phase-complete-declaration", "phase-3",
            "--anchor-task", "urn:fnsr:task:nope",
            "--rationale", "x",
        ])
        self.assertEqual(rc, 1)


# ---------- MAREP-Orchestrator BAO contract -----------------------------

class TestMarepOrchestratorBaoContract(unittest.TestCase):
    """v3.0-alpha.2 ships the MAREP-Orchestrator agent contract.
    End-to-end LLM dispatch testing lands v3.0 final; CP2 validates
    the contract surface (multi-mode required_outputs; BAO bounds;
    cross-instance pattern conformance)."""

    @property
    def contract_path(self):
        return (Path(__file__).resolve().parent.parent / ".claude"
                / "agents" / "marep-orchestrator.md")

    def test_contract_exists(self):
        self.assertTrue(self.contract_path.exists())

    def test_declares_bao_pattern(self):
        text = self.contract_path.read_text(encoding="utf-8")
        fm = d._parse_category_frontmatter(text)
        self.assertEqual(fm.get("bao_pattern"), "true")
        self.assertEqual(fm.get("bao_surface"), "retro")
        self.assertEqual(fm.get("contract_class"), "read-only")

    def test_four_modes_declared(self):
        for mode in ("phase-transition", "conflict-detection",
                      "consensus-summary", "final-compression"):
            outputs = d._agent_required_outputs(
                "marep-orchestrator", mode=mode)
            self.assertGreater(len(outputs), 0,
                                f"mode {mode!r} should have required_outputs")
            self.assertIn("summary", outputs,
                           f"mode {mode!r} should require summary")

    def test_phase_transition_mode_required_outputs(self):
        result = d._agent_required_outputs(
            "marep-orchestrator", mode="phase-transition")
        for key in ("proposed_transition", "current_phase_status",
                    "rationale", "summary"):
            self.assertIn(key, result)


if __name__ == "__main__":
    unittest.main()
