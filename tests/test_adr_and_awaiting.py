"""Tests for v2.6.0 v2.6.0 additions:
- ADR-citation CPS check (registry parser + canonical-docs scoping)
- `awaiting_operator_decision` output-shape validation
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fnsr_daemon as d


SAMPLE_DECISIONS = """\
# Architecture Decision Records

## ADR-001: First decision

**Date:** 2026-05-15
**Decision:** Use the template.
**Context:** Need.
**Consequences:**
- Things follow.

---

## ADR-002: Second decision

**Date:** 2026-05-16
**Decision:** Excise §31 item 14.
**Context:** No second implementation planned.
**Consequences:**
- Phase 6 simpler.

---

## ADR-005: Skipped numbering on purpose

**Date:** 2026-05-17
**Decision:** Demonstrate non-contiguous numbering.
**Context:** Possible to skip.
**Consequences:**
- Registry handles this fine.
"""


class TestAdrRegistry(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="fnsr-adr-test-"))
        self.decisions = self.tmpdir / "DECISIONS.md"
        self.decisions.write_text(SAMPLE_DECISIONS, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_registry_parses_adr_headers(self):
        registry = d._load_adr_registry(self.decisions)
        self.assertEqual(registry, {"001", "002", "005"})

    def test_registry_missing_file_returns_empty(self):
        self.assertEqual(
            d._load_adr_registry(self.tmpdir / "nope.md"),
            set(),
        )

    def test_registry_ignores_inline_adr_mentions(self):
        # The CPS check uses HEADERS only — inline mentions like "see ADR-007"
        # in the BODY of an ADR don't count as registry entries.
        self.decisions.write_text(SAMPLE_DECISIONS +
                                   "\nThis paragraph mentions ADR-007 inline.",
                                   encoding="utf-8")
        registry = d._load_adr_registry(self.decisions)
        self.assertNotIn("007", registry)


class TestIsCanonicalDoc(unittest.TestCase):
    def test_default_canonical_paths_match(self):
        self.assertTrue(d._is_canonical_doc("project/DECISIONS.md"))
        self.assertTrue(d._is_canonical_doc("project/SPEC.md"))
        self.assertTrue(d._is_canonical_doc("project/IMPLEMENTATION_PLAN.md"))

    def test_normalizes_windows_separators(self):
        self.assertTrue(d._is_canonical_doc("project\\DECISIONS.md"))

    def test_default_prefix_arc(self):
        self.assertTrue(d._is_canonical_doc("arc/anything.md"))
        self.assertTrue(d._is_canonical_doc("arc/nested/dir/file.md"))

    def test_unrelated_path_is_not_canonical(self):
        self.assertFalse(d._is_canonical_doc("src/kernel/transform.ts"))
        self.assertFalse(d._is_canonical_doc("notes.txt"))
        self.assertFalse(d._is_canonical_doc(""))


class TestAdrCitationCheck(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="fnsr-cps-adr-test-"))
        self.decisions = self.tmpdir / "DECISIONS.md"
        self.decisions.write_text(SAMPLE_DECISIONS, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_valid_citation_passes(self):
        outputs = {
            "changes": [{
                "id": "C1",
                "file": "project/SPEC.md",
                "before": "x",
                "after": "see ADR-001 and ADR-002 for context.",
            }],
            "summary": "x",
            "self_assessment": "confident",
        }
        # Should NOT raise
        d._check_adr_citations(outputs, decisions_path=self.decisions)

    def test_missing_adr_in_canonical_doc_vetoes(self):
        outputs = {
            "changes": [{
                "id": "C1",
                "file": "project/SPEC.md",
                "before": "x",
                "after": "see ADR-012 for routing.",  # ADR-012 doesn't exist
            }],
        }
        with self.assertRaises(d.ContainmentVeto) as ctx:
            d._check_adr_citations(outputs, decisions_path=self.decisions)
        self.assertIn("ADR-012", str(ctx.exception))

    def test_missing_adr_outside_canonical_doc_passes(self):
        outputs = {
            "changes": [{
                "id": "C1",
                "file": "src/kernel/transform.ts",
                "before": "x",
                "after": "// see ADR-999 elsewhere.",  # not canonical doc
            }],
        }
        # No raise — not a canonical doc, no check.
        d._check_adr_citations(outputs, decisions_path=self.decisions)

    def test_no_decisions_file_skips_check(self):
        outputs = {
            "changes": [{
                "id": "C1",
                "file": "project/SPEC.md",
                "before": "x",
                "after": "ADR-999 referenced",
            }],
        }
        # No DECISIONS.md to check against — registry empty, check skipped.
        d._check_adr_citations(outputs, decisions_path=self.tmpdir / "nope.md")

    def test_no_changes_field_no_op(self):
        # Output isn't change-shaped (e.g., spec-reviewer findings)
        outputs = {
            "findings": [{"id": "F1", "claim": "see ADR-999"}],
            "summary": "x",
            "recommendation": "revise",
        }
        d._check_adr_citations(outputs, decisions_path=self.decisions)

    def test_multiple_missing_adrs_listed(self):
        outputs = {
            "changes": [{
                "id": "C1",
                "file": "project/DECISIONS.md",
                "after": "ADR-007 cites ADR-010; both new.",
            }],
        }
        with self.assertRaises(d.ContainmentVeto) as ctx:
            d._check_adr_citations(outputs, decisions_path=self.decisions)
        msg = str(ctx.exception)
        self.assertIn("ADR-007", msg)
        self.assertIn("ADR-010", msg)

    def test_canonical_prefix_arc_triggers_check(self):
        outputs = {
            "changes": [{
                "id": "C1",
                "file": "arc/protocol/v1.md",
                "after": "see ADR-099",
            }],
        }
        with self.assertRaises(d.ContainmentVeto):
            d._check_adr_citations(outputs, decisions_path=self.decisions)

    def test_mixed_valid_and_invalid_citations(self):
        # Valid ADR-001 in same after as invalid ADR-099 — should still veto.
        outputs = {
            "changes": [{
                "id": "C1",
                "file": "project/SPEC.md",
                "after": "ADR-001 governs this; supersedes ADR-099.",
            }],
        }
        with self.assertRaises(d.ContainmentVeto) as ctx:
            d._check_adr_citations(outputs, decisions_path=self.decisions)
        self.assertIn("ADR-099", str(ctx.exception))


GHOST_DECISIONS = """\
# Architecture Decision Records

## ADR-012: Cardinality routing — Direct Mapping with n-tuple matching (Option β)

**Date:** 2026-05-07
**Decision:** Adopt Option β: Direct Mapping with n-tuple matching for cardinality patterns. Cardinality projects as native OWL Restriction axioms with the appropriate cardinality field (minCardinality / maxCardinality / cardinality) and qualified onClass filler if present. No Loss Signature emitted; the round-trip is byte-clean.
**Context:** Phase 2 spec-binding routing cycle Q-E ruling.
**Consequences:**
- Cardinality fixture's reversible regime is preserved.
"""


GHOST_ARCHITECT_RULING = (
    "Per ADR-012 banked principle (Phase 2 close + reaffirmed across cycles): "
    "'Spec interpretation defaults to literal framing, not conservative emission "
    "strategy.' Spec-literal framing means the ratified axiom set is the binding "
    "source; mathematically-valid-but-unspec'd axioms route as fresh ratification."
)


class TestAdr012GhostFixture(unittest.TestCase):
    """Spec 06 anchor: ADR-012 ghost case.

    v2.6.0's _check_adr_citations performs Cat 2 (ADR cross-reference EXISTENCE)
    per Spec 02. The ghost-case structure (Spec 06):

      - ADR-012 IS registered in DECISIONS.md (as 'Cardinality routing')
      - The architect's verbatim citation carries framing that matches NO
        registry entry ('Spec interpretation defaults to literal framing,
        not conservative emission strategy')
      - The citation is structurally valid (the reference exists)
        AND semantically invalid (the cited content doesn't match the
        registered content)

    v2.6.0 expected behavior: PASS (no veto). The framing mismatch is
    Cat 9 candidacy territory (cited-content consistency) per Spec 02,
    NOT in v2.6.0 scope.

    This fixture LOCKS the v2.6.0 behavior in regression-style and serves
    as the anchor case for v2.7.0+ Cat 9 implementation (where the same
    architect output WILL veto on cited-content-consistency grounds).

    Provenance: project/Routing/06-adr-citation-mismatch-fixture.md
    """

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="fnsr-adr-012-ghost-test-"))
        self.decisions = self.tmpdir / "DECISIONS.md"
        self.decisions.write_text(GHOST_DECISIONS, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_registry_recognizes_adr_012(self):
        # Precondition: ADR-012 is registered. The ghost case depends on
        # existence at the structural level.
        registry = d._load_adr_registry(self.decisions)
        self.assertIn("012", registry)

    def test_v260_passes_ghost_citation_in_canonical_doc(self):
        # Canonical doc destination (project/SPEC.md). v2.6.0 Cat 2 check
        # evaluates: ADR-012 exists in registry -> PASS.
        # The framing mismatch is invisible to existence-only checking.
        outputs = {
            "changes": [{
                "id": "C1",
                "file": "project/SPEC.md",
                "before": "x",
                "after": GHOST_ARCHITECT_RULING,
            }],
        }
        # MUST NOT raise. v2.6.0 correctly passes the ghost case at the
        # existence-check level; Cat 9 (cited-content consistency) is v2.7.0+.
        d._check_adr_citations(outputs, decisions_path=self.decisions)

    def test_v260_passes_ghost_citation_in_decisions_destination(self):
        # Same architect framing landed directly into DECISIONS.md
        # (canonical-doc destination). Still passes at v2.6.0 because
        # ADR-012 is structurally registered.
        outputs = {
            "changes": [{
                "id": "C1",
                "file": "project/DECISIONS.md",
                "before": "x",
                "after": GHOST_ARCHITECT_RULING,
            }],
        }
        d._check_adr_citations(outputs, decisions_path=self.decisions)

    def test_v260_passes_ghost_citation_in_arc_prefix(self):
        # Same ghost framing in arc/ prefix (canonical by prefix per
        # CANONICAL_DOC_PREFIXES). Still passes at v2.6.0.
        outputs = {
            "changes": [{
                "id": "C1",
                "file": "arc/AUTHORING_DISCIPLINE.md",
                "before": "x",
                "after": GHOST_ARCHITECT_RULING,
            }],
        }
        d._check_adr_citations(outputs, decisions_path=self.decisions)

    def test_v260_vetoes_companion_unregistered_adr_in_same_payload(self):
        # Mixing the ghost (ADR-012, registered) with a genuinely missing
        # ADR (ADR-099) in the same after-payload: v2.6.0's existence
        # check still catches the missing one. The ghost passes; the
        # missing one is the veto cause.
        outputs = {
            "changes": [{
                "id": "C1",
                "file": "project/SPEC.md",
                "before": "x",
                "after": GHOST_ARCHITECT_RULING + " See also ADR-099.",
            }],
        }
        with self.assertRaises(d.ContainmentVeto) as ctx:
            d._check_adr_citations(outputs, decisions_path=self.decisions)
        msg = str(ctx.exception)
        self.assertIn("ADR-099", msg)
        # And critically, ADR-012 is NOT in the veto message — the ghost
        # passed structural existence.
        self.assertNotIn("ADR-012", msg)


class TestAwaitingDecisionShape(unittest.TestCase):
    def test_valid_shape_returns_none(self):
        outputs = {
            "status": "awaiting_operator_decision",
            "options": ["option A", "option B", "option C"],
            "recommendation": "Recommend A because ...",
        }
        self.assertIsNone(d._validate_awaiting_decision_shape(outputs))

    def test_options_can_be_dicts(self):
        outputs = {
            "status": "awaiting_operator_decision",
            "options": [
                {"label": "A", "tradeoff": "..."},
                {"label": "B", "tradeoff": "..."},
            ],
            "recommendation": "A — lower risk",
        }
        self.assertIsNone(d._validate_awaiting_decision_shape(outputs))

    def test_empty_options_vetoes(self):
        outputs = {
            "status": "awaiting_operator_decision",
            "options": [],
            "recommendation": "...",
        }
        result = d._validate_awaiting_decision_shape(outputs)
        self.assertIsNotNone(result)
        self.assertIn("options", result)

    def test_missing_options_vetoes(self):
        outputs = {
            "status": "awaiting_operator_decision",
            "recommendation": "x",
        }
        self.assertIsNotNone(d._validate_awaiting_decision_shape(outputs))

    def test_missing_recommendation_vetoes(self):
        outputs = {
            "status": "awaiting_operator_decision",
            "options": ["A", "B"],
        }
        result = d._validate_awaiting_decision_shape(outputs)
        self.assertIsNotNone(result)
        self.assertIn("recommendation", result)

    def test_empty_recommendation_vetoes(self):
        outputs = {
            "status": "awaiting_operator_decision",
            "options": ["A", "B"],
            "recommendation": "   ",
        }
        result = d._validate_awaiting_decision_shape(outputs)
        self.assertIsNotNone(result)

    def test_non_list_options_vetoes(self):
        outputs = {
            "status": "awaiting_operator_decision",
            "options": "not a list",
            "recommendation": "x",
        }
        self.assertIsNotNone(d._validate_awaiting_decision_shape(outputs))


if __name__ == "__main__":
    unittest.main()
