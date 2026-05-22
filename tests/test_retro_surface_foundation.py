"""Tests for v3.0-alpha.1 retro-surface foundation.

Covers:
- BAO substrate-primitive doc exists and declares the four bounds
- Retro surface loader (_load_retro_role_bindings) parses role stubs
- Retro phase loader (_load_retro_phase_specs) parses phase stubs
- Generalized synthesist multi-mode required_outputs (classic + generalized)
- synthesist.md declares bao_pattern: true + bao_surface: synthesis
- Graceful degradation when surfaces/retro/ is absent
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fnsr_daemon as d


class TestBaoSubstratePrimitiveDoc(unittest.TestCase):
    """The BAO substrate primitive document exists and is well-formed."""

    @property
    def primitive_path(self):
        return (Path(__file__).resolve().parent.parent
                / "surfaces" / "_primitives"
                / "bounded-authority-orchestrator.md")

    def test_doc_exists(self):
        self.assertTrue(self.primitive_path.exists(),
                         f"BAO primitive doc missing at {self.primitive_path}")

    def test_doc_declares_four_bounds(self):
        text = self.primitive_path.read_text(encoding="utf-8")
        # The four bounds must be present and numbered
        self.assertIn("### 1. Surface scope", text)
        self.assertIn("### 2. Substrate enforcement", text)
        self.assertIn("### 3. Audit-chain visibility", text)
        self.assertIn("### 4. No substrate-level privilege", text)

    def test_doc_frontmatter_declares_metadata(self):
        text = self.primitive_path.read_text(encoding="utf-8")
        fm = d._parse_category_frontmatter(text)
        self.assertEqual(fm["primitive_id"], "bounded-authority-orchestrator")
        self.assertEqual(fm["short_name"], "BAO")
        self.assertEqual(fm["introduced_in"], "v3.0-alpha.1")


class TestRetroSurfaceFoundation(unittest.TestCase):
    """v3.0-alpha.1 ships the surfaces/retro/ foundation: surface-spec,
    role binding stubs, phase spec stubs. Full MAREP integration lands
    in v3.0-alpha.2 + final v3.0."""

    def test_retro_surface_spec_exists(self):
        path = (Path(__file__).resolve().parent.parent
                / "surfaces" / "retro" / "surface-spec.md")
        self.assertTrue(path.exists())
        fm = d._parse_category_frontmatter(path.read_text(encoding="utf-8"))
        self.assertEqual(fm["surface_id"], "retro")

    def test_role_bindings_load(self):
        bindings = d._load_retro_role_bindings()
        # v3.0-alpha.1 shipped 5 role stubs; v3.0-alpha.2 added
        # @QA, @DeliveryManager, @RiskAnalyst. Total: 8.
        self.assertEqual(len(bindings), 8)
        for role in ("@Orchestrator", "@Architect", "@Developer",
                     "@UserAdvocate", "@Skeptic",
                     "@QA", "@DeliveryManager", "@RiskAnalyst"):
            self.assertIn(role, bindings,
                          f"role {role!r} stub missing")

    def test_orchestrator_is_marked_as_bao(self):
        bindings = d._load_retro_role_bindings()
        orchestrator = bindings.get("@Orchestrator")
        self.assertIsNotNone(orchestrator)
        # bao_pattern flag is "true" string from frontmatter parser
        self.assertEqual(orchestrator.get("bao_pattern"), "true")
        self.assertEqual(orchestrator.get("bao_surface"), "retro")

    def test_non_bao_roles_marked_correctly(self):
        bindings = d._load_retro_role_bindings()
        for role in ("@Architect", "@Developer", "@UserAdvocate",
                     "@Skeptic"):
            binding = bindings.get(role)
            self.assertEqual(binding.get("bao_pattern"), "false",
                             f"{role} should not be a BAO instance")

    def test_phase_specs_load_in_order(self):
        phases = d._load_retro_phase_specs()
        # v3.0-alpha.1 ships all 6 MAREP phases as stubs
        self.assertEqual(len(phases), 6)
        phase_ids = [p["phase_id"] for p in phases]
        self.assertEqual(phase_ids, [
            "01-gathering", "02-merge", "03-analysis",
            "04-consensus", "05-actions", "06-compression",
        ])

    def test_phase_specs_have_entry_exit_criteria(self):
        phases = d._load_retro_phase_specs()
        for p in phases:
            self.assertIn("entry_criteria", p)
            self.assertIn("exit_criteria", p)
            self.assertIn("name", p)

    def test_graceful_degradation_when_directory_absent(self):
        """Substrate gracefully degrades when surfaces/retro/ doesn't
        exist (e.g., for a subject project that doesn't use retros)."""
        with tempfile.TemporaryDirectory(prefix="fnsr-no-retro-") as tmp:
            with patch.object(d, "SURFACES_DIR", Path(tmp)):
                self.assertEqual(d._load_retro_role_bindings(), {})
                self.assertEqual(d._load_retro_phase_specs(), [])


class TestGeneralizedSynthesistBaoInstance(unittest.TestCase):
    """v3.0-alpha.1 extends synthesist to multi-mode; generalized mode
    is the first concrete BAO instance per surfaces/_primitives/
    bounded-authority-orchestrator.md."""

    def test_synthesist_default_mode_is_classic(self):
        # default_mode mechanism: existing dispatch tasks without
        # inputs.mode keep working under the classic contract
        result = d._agent_required_outputs("synthesist")
        self.assertEqual(result, ["issues", "recommendation", "summary"])

    def test_classic_mode_required_outputs(self):
        result = d._agent_required_outputs("synthesist", mode="classic")
        self.assertEqual(result, ["issues", "recommendation", "summary"])

    def test_generalized_mode_required_outputs(self):
        result = d._agent_required_outputs("synthesist", mode="generalized")
        self.assertEqual(result, [
            "synthesized_findings", "conflicts", "recommendation",
            "source_provenance", "summary",
        ])

    def test_synthesist_frontmatter_declares_bao(self):
        agents_dir = Path(__file__).resolve().parent.parent / ".claude" / "agents"
        text = (agents_dir / "synthesist.md").read_text(encoding="utf-8")
        fm = d._parse_category_frontmatter(text)
        self.assertEqual(fm.get("bao_pattern"), "true")
        self.assertEqual(fm.get("bao_surface"), "synthesis")
        self.assertEqual(fm.get("contract_class"), "read-only")

    def test_classic_mode_cps_check_passes_existing_shape(self):
        # Back-compat: a synthesist task dispatched WITHOUT inputs.mode
        # MUST still have its required_outputs enforced under classic.
        task = {"agent": "synthesist"}  # no inputs.mode
        outputs = {
            "issues": [],
            "recommendation": "accept",
            "summary": "x",
        }
        d.cps_check(task, outputs)  # MUST NOT raise

    def test_classic_mode_missing_recommendation_vetoes(self):
        task = {"agent": "synthesist"}
        outputs = {"issues": [], "summary": "x"}  # missing recommendation
        with self.assertRaises(d.ContainmentVeto) as ctx:
            d.cps_check(task, outputs)
        self.assertIn("recommendation", str(ctx.exception))

    def test_generalized_mode_full_payload_passes(self):
        task = {"agent": "synthesist",
                "inputs": {"mode": "generalized"}}
        outputs = {
            "synthesized_findings": [],
            "conflicts": [],
            "recommendation": "accept",
            "source_provenance": {},
            "summary": "x",
        }
        d.cps_check(task, outputs)  # MUST NOT raise

    def test_generalized_mode_missing_source_provenance_vetoes(self):
        # source_provenance is the audit-trail-honesty discipline; CPS
        # enforces it.
        task = {"agent": "synthesist",
                "inputs": {"mode": "generalized"}}
        outputs = {
            "synthesized_findings": [],
            "conflicts": [],
            "recommendation": "accept",
            "summary": "x",
            # source_provenance omitted
        }
        with self.assertRaises(d.ContainmentVeto) as ctx:
            d.cps_check(task, outputs)
        self.assertIn("source_provenance", str(ctx.exception))

    def test_generalized_mode_missing_conflicts_vetoes(self):
        # Conflicts must be declared (empty list is fine); omission
        # suggests the synthesist failed to acknowledge potential
        # disagreement.
        task = {"agent": "synthesist",
                "inputs": {"mode": "generalized"}}
        outputs = {
            "synthesized_findings": [],
            "recommendation": "accept",
            "source_provenance": {},
            "summary": "x",
        }
        with self.assertRaises(d.ContainmentVeto):
            d.cps_check(task, outputs)


class TestBaoBoundsValidation(unittest.TestCase):
    """Cross-instance validation: every agent declaring bao_pattern: true
    in its frontmatter MUST satisfy the four BAO bounds. v3.0-alpha.1
    has one such agent (synthesist generalized mode); future BAO
    instances must pass this validation too."""

    def _bao_agents(self):
        """Find every agent .md file declaring bao_pattern: true."""
        agents_dir = Path(__file__).resolve().parent.parent / ".claude" / "agents"
        bao_agents = []
        for path in sorted(agents_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            fm = d._parse_category_frontmatter(text)
            if not fm:
                continue
            if fm.get("bao_pattern") == "true":
                bao_agents.append((path.name, fm, text))
        return bao_agents

    def test_at_least_one_bao_instance_exists(self):
        bao_agents = self._bao_agents()
        self.assertGreaterEqual(len(bao_agents), 1,
                                 "v3.0-alpha.1 ships at least one BAO instance "
                                 "(generalized synthesist)")

    def test_every_bao_instance_declares_surface(self):
        # Bound #1: surface scope.
        for name, fm, _text in self._bao_agents():
            self.assertIn("bao_surface", fm,
                          f"BAO agent {name} missing bao_surface declaration")

    def test_every_bao_instance_declares_contract_class_read_only(self):
        # Bound #4: no substrate-level privilege; expressed as
        # contract_class: read-only.
        for name, fm, _text in self._bao_agents():
            self.assertEqual(fm.get("contract_class"), "read-only",
                             f"BAO agent {name} must declare "
                             f"contract_class: read-only")

    def test_every_bao_instance_uses_read_only_tools(self):
        # Bound #4: no Edit/Write/Bash tools.
        for name, fm, _text in self._bao_agents():
            tools = fm.get("tools", "")
            # Bound: no Edit, Write, Bash in the tools list
            for forbidden in ("Edit", "Write", "Bash"):
                self.assertNotIn(forbidden, tools,
                                  f"BAO agent {name} declares forbidden "
                                  f"tool {forbidden!r}; violates bound #4")

    def test_every_bao_instance_references_primitive_doc(self):
        # Bound discipline: the agent's prompt SHOULD reference the
        # canonical primitive doc so the bounds are operator-discoverable.
        for name, fm, text in self._bao_agents():
            # Either references the doc path, the term "BAO", or the
            # phrase "Bounded-Authority Orchestrator"
            references = (
                "bounded-authority-orchestrator" in text.lower()
                or "BAO" in text
                or "Bounded-Authority Orchestrator" in text
            )
            self.assertTrue(references,
                             f"BAO agent {name} should reference the "
                             f"BAO primitive (by name or path) in its prompt")


if __name__ == "__main__":
    unittest.main()
