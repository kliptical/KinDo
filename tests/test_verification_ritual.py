"""Tests for the v2.8.0 Checkpoint 1 verification-ritual machinery.

Covers:
- Category spec loader (frontmatter parsing, file discovery)
- Predicate resolver
- Cat 1-7 deterministic predicates (happy + veto + miss paths each)
- verification-ritual system agent orchestration (cadence filtering,
  canonical-source resolution, predicate dispatch, aggregate status)
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fnsr_daemon as d


SAMPLE_SPEC = """\
# Example Spec

## 1. Introduction

Content.

## 3.4.1 Connected With (ratified axioms)

Reflexivity, symmetry, parthood-extension.

## §3.4.2 Mereotopology helpers

Definitions.

### 3.4.2.1 Sub-helper

Body.

## 5.0 Closing

Body.
"""

SAMPLE_DECISIONS = """\
# Architecture Decision Records

## ADR-001: First decision

Body.

## ADR-007: Seventh decision

Body.

## ADR-012: Cardinality routing

Body.
"""

SAMPLE_REASON_CODES_TS = """\
// src/kernel/reason-codes.ts

export const REASON_CODES = Object.freeze([
  "open_world_undetermined",
  "closed_world_falsified",
  "ontology_unsatisfiable",
  "domain_violation",
] as const);

export type ReasonCode = typeof REASON_CODES[number];
"""

SAMPLE_FOL_TYPES_TS = """\
// src/kernel/fol-types.ts

export type FolType =
  | "fol:Implication"
  | "fol:Conjunction"
  | "fol:Disjunction"
  | "fol:Negation"
  | "fol:Universal"
  | "fol:Existential"
  | "fol:Atom"
  | "fol:Equality"
  | "fol:False";
"""

SAMPLE_OWL_TYPES_TS = """\
// src/kernel/owl-types.ts

export type OwlType =
  | "owl:Class"
  | "owl:ObjectProperty"
  | "owl:Restriction"
  | "SubObjectPropertyOf"
  | "ObjectPropertyChain";
"""


class TestCategoryFrontmatterParser(unittest.TestCase):
    def test_parses_flat_fields(self):
        text = (
            "---\n"
            "category_id: cat-01\n"
            "name: Foo\n"
            "implementation_mode: deterministic\n"
            "---\n\nbody"
        )
        fm = d._parse_category_frontmatter(text)
        self.assertEqual(fm["category_id"], "cat-01")
        self.assertEqual(fm["name"], "Foo")
        self.assertEqual(fm["implementation_mode"], "deterministic")

    def test_parses_list_field(self):
        text = (
            "---\n"
            "category_id: cat-04\n"
            "canonical_source_keys: [reason_codes, spec]\n"
            "---\n"
        )
        fm = d._parse_category_frontmatter(text)
        self.assertEqual(fm["canonical_source_keys"], ["reason_codes", "spec"])

    def test_no_frontmatter_returns_none(self):
        self.assertIsNone(d._parse_category_frontmatter("plain body"))
        self.assertIsNone(d._parse_category_frontmatter(""))


class TestCategoryLoader(unittest.TestCase):
    def test_loads_all_cat_specs(self):
        # CP1 shipped cat-01..07. CP2 added cat-08 (hybrid two-cadence)
        # and cat-10 (subject-project-hook candidacy). CP3 adds cat-09
        # (LLM cited-content-consistency candidacy).
        specs = d._load_category_specs()
        ids = sorted({s["category_id"]
                       for s in specs if not s.get("_malformed")})
        self.assertEqual(ids, ["cat-01", "cat-02", "cat-03", "cat-04",
                                "cat-05", "cat-06", "cat-07", "cat-08",
                                "cat-09", "cat-10"])

    def test_each_spec_has_required_fields(self):
        specs = d._load_category_specs()
        for spec in specs:
            self.assertIn("category_id", spec)
            self.assertIn("name", spec)
            self.assertIn("implementation_mode", spec)
            self.assertIn("cadence", spec)
            self.assertIn("python_predicate", spec)
            self.assertIn("canonical_source_keys", spec)
            self.assertIsInstance(spec["canonical_source_keys"], list)


class TestPredicateResolver(unittest.TestCase):
    def test_resolves_within_module(self):
        pred = d._resolve_predicate("fnsr_daemon.cat_01_spec_section_existence")
        self.assertIsNotNone(pred)
        self.assertTrue(callable(pred))

    def test_rejects_external_modules(self):
        self.assertIsNone(d._resolve_predicate("other_module.predicate"))

    def test_rejects_bare_name(self):
        self.assertIsNone(d._resolve_predicate("predicate_only"))

    def test_unknown_attr_returns_none(self):
        self.assertIsNone(d._resolve_predicate("fnsr_daemon.no_such_predicate"))


# ---- Cat 1 ----

class TestCat01SpecSectionExistence(unittest.TestCase):
    def test_pass_existing_sections(self):
        artifact = "see §3.4.1 and §3.4.2 for context"
        result = d.cat_01_spec_section_existence(
            artifact, {"spec": SAMPLE_SPEC})
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["evidence"]["cited_sections"],
                         ["3.4.1", "3.4.2"])

    def test_veto_missing_section(self):
        artifact = "see §3.4.4 which does not exist"
        result = d.cat_01_spec_section_existence(
            artifact, {"spec": SAMPLE_SPEC})
        self.assertEqual(result["status"], "veto")
        self.assertIn("3.4.4", result["evidence"]["unmatched"])

    def test_miss_when_spec_absent(self):
        result = d.cat_01_spec_section_existence("§1.1", {})
        self.assertEqual(result["status"], "miss")

    def test_pass_no_citations(self):
        result = d.cat_01_spec_section_existence(
            "no section citations here", {"spec": SAMPLE_SPEC})
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["evidence"]["cited_sections"], [])

    def test_nested_sections_recognized(self):
        # 3.4.2.1 should be recognized when the spec has the header
        artifact = "see §3.4.2.1"
        result = d.cat_01_spec_section_existence(
            artifact, {"spec": SAMPLE_SPEC})
        self.assertEqual(result["status"], "pass")


# ---- Cat 2 ----

class TestCat02AdrCrossReference(unittest.TestCase):
    def test_pass_registered_adrs(self):
        artifact = "see ADR-001 and ADR-012 for context"
        result = d.cat_02_adr_cross_reference(
            artifact, {"decisions": SAMPLE_DECISIONS})
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["evidence"]["cited_adrs"], ["001", "012"])

    def test_veto_unregistered_adr(self):
        artifact = "see ADR-099 (does not exist)"
        result = d.cat_02_adr_cross_reference(
            artifact, {"decisions": SAMPLE_DECISIONS})
        self.assertEqual(result["status"], "veto")
        self.assertIn("099", result["evidence"]["unmatched"])

    def test_miss_when_decisions_absent(self):
        result = d.cat_02_adr_cross_reference("ADR-001", {})
        self.assertEqual(result["status"], "miss")

    def test_pass_no_citations(self):
        result = d.cat_02_adr_cross_reference(
            "no ADR citations", {"decisions": SAMPLE_DECISIONS})
        self.assertEqual(result["status"], "pass")


# ---- Cat 3 ----

class TestCat03QRulingCrossReference(unittest.TestCase):
    def setUp(self):
        self.prior = {
            "phase-3/Q-3-A.md": "# Q-3-A: Routing decision\nBody.",
            "phase-4/Q-4-Step5-A.md": (
                "# Q-4-Step5-A: Step 5 ruling\n"
                "## Q-4-Step5-A.1 sub-ruling\nBody."
            ),
        }

    def test_pass_existing_q_rulings(self):
        artifact = "per Q-3-A and Q-4-Step5-A.1, ratify"
        result = d.cat_03_q_ruling_cross_reference(
            artifact, {"prior_cycle_artifacts": self.prior})
        self.assertEqual(result["status"], "pass")

    def test_veto_missing_q_ruling(self):
        artifact = "per Q-9-Z (doesn't exist), ratify"
        result = d.cat_03_q_ruling_cross_reference(
            artifact, {"prior_cycle_artifacts": self.prior})
        self.assertEqual(result["status"], "veto")
        self.assertIn("Q-9-Z", result["evidence"]["unmatched"])

    def test_miss_when_prior_absent(self):
        result = d.cat_03_q_ruling_cross_reference("Q-3-A", {})
        self.assertEqual(result["status"], "miss")


# ---- Cat 4 ----

class TestCat04ReasonCodeFrozenEnum(unittest.TestCase):
    def test_pass_known_reason(self):
        artifact = '"expectedReason": "open_world_undetermined"'
        result = d.cat_04_reason_code_frozen_enum(
            artifact, {"reason_codes": SAMPLE_REASON_CODES_TS})
        self.assertEqual(result["status"], "pass")

    def test_veto_unknown_reason(self):
        artifact = '"expectedReason": "naf_residue"'
        result = d.cat_04_reason_code_frozen_enum(
            artifact, {"reason_codes": SAMPLE_REASON_CODES_TS})
        self.assertEqual(result["status"], "veto")
        self.assertIn("naf_residue", result["evidence"]["unmatched"])

    def test_miss_when_reason_codes_absent(self):
        result = d.cat_04_reason_code_frozen_enum(
            '"expectedReason": "x"', {})
        self.assertEqual(result["status"], "miss")

    def test_pass_no_citations(self):
        result = d.cat_04_reason_code_frozen_enum(
            "no expectedReason in this artifact",
            {"reason_codes": SAMPLE_REASON_CODES_TS})
        self.assertEqual(result["status"], "pass")


# ---- Cat 5 ----

class TestCat05FolOwlTypeDiscriminator(unittest.TestCase):
    def test_pass_known_fol_type(self):
        artifact = '"@type": "fol:Implication"'
        result = d.cat_05_fol_owl_type_discriminator(artifact, {
            "fol_types": SAMPLE_FOL_TYPES_TS,
            "owl_types": SAMPLE_OWL_TYPES_TS,
        })
        self.assertEqual(result["status"], "pass")

    def test_pass_known_owl_type(self):
        artifact = '"@type": "owl:Restriction"'
        result = d.cat_05_fol_owl_type_discriminator(artifact, {
            "fol_types": SAMPLE_FOL_TYPES_TS,
            "owl_types": SAMPLE_OWL_TYPES_TS,
        })
        self.assertEqual(result["status"], "pass")

    def test_veto_unknown_type(self):
        # fol:Biconditional is the Q-4-C amendment Catch 2 case
        artifact = '"@type": "fol:Biconditional"'
        result = d.cat_05_fol_owl_type_discriminator(artifact, {
            "fol_types": SAMPLE_FOL_TYPES_TS,
            "owl_types": SAMPLE_OWL_TYPES_TS,
        })
        self.assertEqual(result["status"], "veto")
        self.assertIn("fol:Biconditional", result["evidence"]["unmatched"])

    def test_miss_when_either_canonical_source_absent(self):
        result = d.cat_05_fol_owl_type_discriminator(
            '"@type": "fol:Atom"', {"fol_types": SAMPLE_FOL_TYPES_TS})
        self.assertEqual(result["status"], "miss")


# ---- Cat 6 ----

class TestCat06ManifestMirrorConsistency(unittest.TestCase):
    def setUp(self):
        self.manifest_text = json.dumps([
            {"fixture": "f1.json", "expectedOutcome": "consistent",
             "canaryRole": "positive"},
            {"fixture": "f2.json", "expectedOutcome": "inconsistent"},
        ])
        self.fixtures_matching = {
            "f1.json": '{"expectedOutcome": "consistent", "canaryRole": "positive"}',
            "f2.json": '{"expectedOutcome": "inconsistent"}',
        }
        self.fixtures_diverging = {
            "f1.json": '{"expectedOutcome": "INCONSISTENT", "canaryRole": "positive"}',
            "f2.json": '{"expectedOutcome": "inconsistent"}',
        }

    def test_pass_when_manifest_mirrors_fixtures(self):
        result = d.cat_06_manifest_mirror_consistency("", {
            "manifest": self.manifest_text,
            "fixtures": self.fixtures_matching,
        })
        self.assertEqual(result["status"], "pass")
        self.assertTrue(len(result["evidence"]["matched"]) > 0)

    def test_veto_on_divergence(self):
        result = d.cat_06_manifest_mirror_consistency("", {
            "manifest": self.manifest_text,
            "fixtures": self.fixtures_diverging,
        })
        self.assertEqual(result["status"], "veto")
        self.assertTrue(len(result["evidence"]["divergences"]) > 0)

    def test_miss_on_invalid_manifest_json(self):
        result = d.cat_06_manifest_mirror_consistency("", {
            "manifest": "not json", "fixtures": {},
        })
        self.assertEqual(result["status"], "miss")

    def test_miss_when_sources_absent(self):
        result = d.cat_06_manifest_mirror_consistency("", {})
        self.assertEqual(result["status"], "miss")


# ---- Cat 7 ----

class TestCat07CrossPhaseCrossReference(unittest.TestCase):
    def setUp(self):
        self.cycle_artifacts = {
            "phase-3/Q-3-A.md": "Body of Q-3-A.",
            "phase-4/Q-4-A.md": "Body of Q-4-A. See also phase-3/Q-3-A.md.",
        }

    def test_pass_existing_paths(self):
        artifact = "this references [Q-3-A](phase-3/Q-3-A.md)"
        result = d.cat_07_cross_phase_cross_reference(
            artifact, {"cycle_artifacts": self.cycle_artifacts})
        self.assertEqual(result["status"], "pass")
        self.assertIn("phase-3/Q-3-A.md", result["evidence"]["matched"])

    def test_veto_on_dangling_reference(self):
        artifact = "see [missing](phase-99/missing.md) please"
        result = d.cat_07_cross_phase_cross_reference(
            artifact, {"cycle_artifacts": self.cycle_artifacts})
        self.assertEqual(result["status"], "veto")
        self.assertIn("phase-99/missing.md", result["evidence"]["dangling"])

    def test_veto_on_asymmetric_when_reciprocity_implied(self):
        # phase-4/Q-4-B.md is the self_path; phase-3/Q-3-A.md exists but
        # doesn't reference back. Pass self_path via PredicateMetadata
        # (Gap H v2.8.0-alpha.2 signature).
        cycle = dict(self.cycle_artifacts)
        artifact = ("From phase-4/Q-4-B.md: see also phase-3/Q-3-A.md "
                    "for context.")
        metadata = d.PredicateMetadata(self_path="phase-4/Q-4-B.md")
        result = d.cat_07_cross_phase_cross_reference(
            artifact, {"cycle_artifacts": cycle}, metadata)
        self.assertEqual(result["status"], "veto")
        self.assertTrue(len(result["evidence"]["asymmetric"]) > 0)

    def test_miss_when_cycle_artifacts_absent(self):
        result = d.cat_07_cross_phase_cross_reference(
            "some text", {})
        self.assertEqual(result["status"], "miss")

    def test_self_reference_not_flagged(self):
        # The artifact's own path shouldn't count as a dangling reference
        artifact = "this is phase-4/Q-4-A.md content"
        metadata = d.PredicateMetadata(self_path="phase-4/Q-4-A.md")
        result = d.cat_07_cross_phase_cross_reference(
            artifact, {"cycle_artifacts": self.cycle_artifacts}, metadata)
        self.assertEqual(result["status"], "pass")


# ---- verification-ritual system agent ----

class TestVerificationRitualOrchestrator(unittest.TestCase):
    def _run(self, inputs):
        task = {"@id": "urn:test:verification", "agent": "verification-ritual",
                "inputs": inputs}
        return d._verification_ritual(task, {})

    def test_artifact_missing_returns_structured_error(self):
        result = self._run({})
        self.assertEqual(result.outputs.get("error"), "artifact_missing")

    def test_overall_pass_when_no_canonical_sources_provided(self):
        # No canonical sources -> every category misses on missing keys.
        # No vetoes, so overall_status is "pass" (with all-miss
        # per-category results).
        result = self._run({"artifact_text": "empty artifact"})
        self.assertEqual(result.outputs["overall_status"], "pass")
        # Every cat should be a miss
        for cat_result in result.outputs["per_category_result"]:
            self.assertEqual(cat_result["status"], "miss")

    def test_overall_needs_llm_judgment_when_cat_9_defers(self):
        # CP3: with cat-09 loaded and its required sources (spec +
        # decisions) provided, Cat 9 defers to verification-ritual-llm.
        # The deterministic verification-ritual emits overall_status =
        # needs_llm_judgment, even when every deterministic category
        # passes. Operator queues verification-ritual-llm next.
        result = self._run({
            "artifact_text": "see §3.4.1 and ADR-001 for context.",
            "canonical_sources": {
                "spec": SAMPLE_SPEC,
                "decisions": SAMPLE_DECISIONS,
            },
        })
        self.assertEqual(result.outputs["overall_status"],
                         "needs_llm_judgment")
        cat_results = {r["category_id"]: r
                       for r in result.outputs["per_category_result"]}
        self.assertEqual(cat_results["cat-01"]["status"], "pass")
        self.assertEqual(cat_results["cat-02"]["status"], "pass")
        self.assertEqual(cat_results["cat-09"]["status"], "deferred_llm")
        self.assertEqual(
            cat_results["cat-09"]["evidence"]["llm_dispatcher_agent"],
            "verification-ritual-llm")

    def test_overall_veto_propagates_from_any_category(self):
        result = self._run({
            "artifact_text": "see §3.4.1 (ok) and ADR-099 (missing)",
            "canonical_sources": {
                "spec": SAMPLE_SPEC,
                "decisions": SAMPLE_DECISIONS,
            },
        })
        self.assertEqual(result.outputs["overall_status"], "veto")
        cat_results = {r["category_id"]: r
                       for r in result.outputs["per_category_result"]}
        self.assertEqual(cat_results["cat-01"]["status"], "pass")
        self.assertEqual(cat_results["cat-02"]["status"], "veto")

    def test_cadence_pre_routing_runs_default_categories(self):
        result = self._run({
            "artifact_text": "x",
            "canonical_sources": {},
            "cadence": "pre-routing",
        })
        # CP3: Cat 1-7, Cat 8 (two-cadence applies in pre-routing),
        # Cat 9 (LLM candidacy; emits deferred_llm or miss-on-no-sources),
        # Cat 10 (subject-project-hook candidacy) all run at pre-routing.
        self.assertEqual(len(result.outputs["per_category_result"]), 10)

    def test_summary_string_format(self):
        result = self._run({
            "artifact_text": "see §3.4.1 and ADR-001",
            "canonical_sources": {"spec": SAMPLE_SPEC,
                                   "decisions": SAMPLE_DECISIONS},
        })
        self.assertIn("verification ritual", result.outputs["summary"])
        self.assertIn("pass", result.outputs["summary"])
        self.assertIn("veto", result.outputs["summary"])
        self.assertIn("miss", result.outputs["summary"])

    def test_new_candidacies_empty_in_cp1(self):
        # CP1 ships only deterministic categories; new_candidacies is
        # always empty until CP3+ when LLM categories can surface
        # patterns no current category covers.
        result = self._run({"artifact_text": "x"})
        self.assertEqual(result.outputs["new_candidacies"], [])

    def test_required_outputs_pass_cps_check(self):
        # The system agent's outputs satisfy the .md frontmatter's
        # required_outputs declaration.
        result = self._run({"artifact_text": "x"})
        task = {"agent": "verification-ritual"}
        # MUST NOT raise.
        d.cps_check(task, result.outputs)

    def test_artifact_path_loaded_from_disk(self):
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md",
                                          delete=False, encoding="utf-8") as f:
            f.write("see §3.4.1 for context")
            path = f.name
        try:
            result = self._run({
                "artifact_path": path,
                "canonical_sources": {"spec": SAMPLE_SPEC},
            })
            cat_results = {r["category_id"]: r
                           for r in result.outputs["per_category_result"]}
            self.assertEqual(cat_results["cat-01"]["status"], "pass")
        finally:
            os.unlink(path)

    def test_dispatch_via_invoke_agent(self):
        # End-to-end through invoke_agent (the daemon dispatcher).
        task = {
            "@id": "urn:test:verification",
            "agent": "verification-ritual",
            "inputs": {
                "artifact_text": "see ADR-001",
                "canonical_sources": {"decisions": SAMPLE_DECISIONS},
            },
        }
        result = d.invoke_agent("verification-ritual", task, {})
        self.assertTrue(result.ok)
        self.assertEqual(result.outputs["overall_status"], "pass")


class TestPredicateMetadata(unittest.TestCase):
    """Gap H v2.8.0-alpha.2: typed metadata structure for substrate-
    supplied predicate context (self_path, task_id, cycle_id,
    phase_context, cadence)."""

    def test_default_construction(self):
        meta = d.PredicateMetadata()
        self.assertIsNone(meta.self_path)
        self.assertIsNone(meta.task_id)
        self.assertEqual(meta.cadence, "pre-routing")

    def test_named_fields(self):
        meta = d.PredicateMetadata(
            self_path="x/y.md",
            task_id="urn:fnsr:task:t1",
            cycle_id="phase-4-entry",
            phase_context="phase-4",
            cadence="activation-time",
        )
        self.assertEqual(meta.self_path, "x/y.md")
        self.assertEqual(meta.task_id, "urn:fnsr:task:t1")
        self.assertEqual(meta.cycle_id, "phase-4-entry")
        self.assertEqual(meta.phase_context, "phase-4")
        self.assertEqual(meta.cadence, "activation-time")

    def test_metadata_threaded_to_cat_07(self):
        # Confirm the orchestrator builds PredicateMetadata correctly
        # for Cat 7's self_path lookup.
        task = {
            "@id": "urn:fnsr:task:verify",
            "agent": "verification-ritual",
            "inputs": {
                "artifact_text": "see [other](other.md) — see also other.md",
                "artifact_self_path": "self.md",
                "canonical_sources": {
                    "cycle_artifacts": {"other.md": "body without back-ref"},
                },
            },
        }
        result = d._verification_ritual(task, {})
        cat_results = {r["category_id"]: r
                       for r in result.outputs["per_category_result"]}
        # Cat 7 should run with self_path set; with reciprocity hint
        # ("see also") and no back-ref in other.md, it vetoes asymmetric.
        self.assertEqual(cat_results["cat-07"]["status"], "veto")


class TestMissTaxonomy(unittest.TestCase):
    """Gap G v2.8.0-alpha.2: per_category_result misses carry an
    evidence.miss_class field discriminating substrate-fixable from
    evidence-grounded-extension cases.
    """

    def test_missing_canonical_source_emits_split_miss_class(self):
        # Gap I split (v2.8.0-alpha.3): missing_canonical_source is its
        # own 4th miss class; was bucketed under unresolved_predicate
        # in CP2.
        task = {
            "@id": "urn:fnsr:task:verify",
            "agent": "verification-ritual",
            "inputs": {
                "artifact_text": "see §1.1",
                "canonical_sources": {},  # spec missing
            },
        }
        result = d._verification_ritual(task, {})
        cat01 = next(r for r in result.outputs["per_category_result"]
                     if r["category_id"] == "cat-01")
        self.assertEqual(cat01["status"], "miss")
        self.assertEqual(cat01["evidence"]["miss_class"],
                         d.MISS_MISSING_CANONICAL_SOURCE)
        self.assertIn("missing_canonical_source_keys", cat01["evidence"])
        self.assertIn("spec", cat01["evidence"]["missing_canonical_source_keys"])

    def test_four_miss_classes_are_distinct_constants(self):
        # Each operator-fix path has its own constant per Gap I split.
        classes = {
            d.MISS_MALFORMED_SPEC,
            d.MISS_UNRESOLVED_PREDICATE,
            d.MISS_MISSING_CANONICAL_SOURCE,
            d.MISS_CATEGORICAL_COVERAGE,
        }
        self.assertEqual(len(classes), 4)

    def test_categorical_coverage_miss_from_predicate(self):
        # Cat 10's stub returns miss with miss_class set by the predicate
        # itself (categorical_coverage_miss). The orchestrator preserves
        # the predicate-set miss_class.
        task = {
            "@id": "urn:fnsr:task:verify",
            "agent": "verification-ritual",
            "inputs": {
                "artifact_text": "x",
                "canonical_sources": {"interface_declarations": "stub"},
            },
        }
        result = d._verification_ritual(task, {})
        cat10 = next(r for r in result.outputs["per_category_result"]
                     if r["category_id"] == "cat-10")
        self.assertEqual(cat10["status"], "miss")
        self.assertEqual(cat10["evidence"]["miss_class"],
                         d.MISS_CATEGORICAL_COVERAGE)
        self.assertEqual(cat10["evidence"]["reason"],
                         "not_implemented_for_this_subject_project")


class TestMalformedSpecHandling(unittest.TestCase):
    """Gap G refinement: malformed category specs emit
    miss_class=malformed_spec entries rather than being silently
    skipped. Tested by writing a malformed file into a temp surfaces dir.
    """

    def setUp(self):
        import tempfile
        self.tmpdir = tempfile.mkdtemp(prefix="fnsr-malformed-spec-test-")
        self.categories_dir = (
            os.path.join(self.tmpdir, "verification", "categories")
        )
        os.makedirs(self.categories_dir, exist_ok=True)
        # One valid file (cat-99) so the loader has something well-formed
        # alongside the malformed file.
        with open(os.path.join(self.categories_dir, "cat-99-valid.md"),
                  "w", encoding="utf-8") as f:
            f.write(
                "---\n"
                "category_id: cat-99\n"
                "name: Valid Spec\n"
                "implementation_mode: deterministic\n"
                "cadence: pre-routing\n"
                "python_predicate: fnsr_daemon.cat_01_spec_section_existence\n"
                "canonical_source_keys: [spec]\n"
                "---\n\nbody"
            )
        # Malformed file: no frontmatter
        with open(os.path.join(self.categories_dir, "cat-malformed-1.md"),
                  "w", encoding="utf-8") as f:
            f.write("# Just a body, no frontmatter\n")
        # Malformed file: frontmatter present but no category_id
        with open(os.path.join(self.categories_dir, "cat-malformed-2.md"),
                  "w", encoding="utf-8") as f:
            f.write("---\nname: No category_id\n---\nbody")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _with_surfaces_dir(self):
        """Run the loader with a temp surfaces dir."""
        from pathlib import Path
        from unittest.mock import patch
        return patch.object(d, "SURFACES_DIR", Path(self.tmpdir))

    def test_loader_returns_malformed_sentinels(self):
        with self._with_surfaces_dir():
            specs = d._load_category_specs()
        # 1 valid + 2 malformed = 3 entries
        self.assertEqual(len(specs), 3)
        malformed = [s for s in specs if s.get("_malformed")]
        self.assertEqual(len(malformed), 2)
        valid = [s for s in specs if not s.get("_malformed")]
        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0]["category_id"], "cat-99")

    def test_orchestrator_emits_malformed_spec_misses(self):
        with self._with_surfaces_dir():
            task = {
                "@id": "urn:fnsr:task:verify",
                "agent": "verification-ritual",
                "inputs": {
                    "artifact_text": "x",
                    "canonical_sources": {"spec": "# 1.1 Section\n"},
                },
            }
            result = d._verification_ritual(task, {})
        per_cat = result.outputs["per_category_result"]
        malformed_entries = [
            r for r in per_cat
            if r.get("evidence", {}).get("miss_class") == d.MISS_MALFORMED_SPEC
        ]
        self.assertEqual(len(malformed_entries), 2)
        for entry in malformed_entries:
            self.assertEqual(entry["status"], "miss")
            self.assertIn("reason", entry["evidence"])
            self.assertIn("spec_path", entry["evidence"])


class TestSubjectHookLoader(unittest.TestCase):
    """Gap F v2.8.0-alpha.2: sibling .py files alongside category specs
    are auto-imported into a per-surface sandbox namespace at
    subject.<surface>.<module>. Defensive: ImportError records the
    failure; subsequent _resolve_predicate emits unresolved_predicate
    miss with details.import_error.
    """

    def test_cat_10_resolves_to_stub(self):
        # The shipped cat-10 .py stub should resolve through the
        # subject.verification.cat_10_type_field_structure path.
        pred = d._resolve_predicate(
            "subject.verification.cat_10_type_field_structure")
        self.assertTrue(callable(pred))

    def test_cat_10_stub_returns_not_implemented(self):
        pred = d._resolve_predicate(
            "subject.verification.cat_10_type_field_structure")
        result = pred("artifact", {"interface_declarations": "stub"},
                       d.PredicateMetadata())
        self.assertEqual(result["status"], "miss")
        self.assertEqual(result["evidence"]["miss_class"],
                         d.MISS_CATEGORICAL_COVERAGE)
        self.assertEqual(result["evidence"]["reason"],
                         "not_implemented_for_this_subject_project")

    def test_subject_hook_failure_surfaces_as_unresolved_predicate(self):
        # Inject a broken .py file into a temp surfaces dir; the loader
        # records the failure; the orchestrator emits unresolved_predicate
        # with details.import_error.
        import tempfile
        import shutil
        from pathlib import Path
        from unittest.mock import patch
        tmpdir = tempfile.mkdtemp(prefix="fnsr-broken-hook-test-")
        try:
            cat_dir = Path(tmpdir) / "verification" / "categories"
            cat_dir.mkdir(parents=True)
            # Spec referencing a subject-hook .py that has a syntax error
            (cat_dir / "cat-99-broken.md").write_text(
                "---\n"
                "category_id: cat-99\n"
                "name: Broken Hook Spec\n"
                "implementation_mode: deterministic\n"
                "cadence: pre-routing\n"
                "python_predicate: subject.verification.cat_99_broken\n"
                "canonical_source_keys: []\n"
                "---\n", encoding="utf-8")
            (cat_dir / "cat-99-broken.py").write_text(
                "this is not valid python !!\n", encoding="utf-8")
            with patch.object(d, "SURFACES_DIR", Path(tmpdir)):
                # Reset sandbox load cache so the temp dir actually loads
                d._SUBJECT_HOOKS_LOADED.discard("verification")
                d._SUBJECT_SANDBOXES.setdefault("verification", {}).clear()
                d._SUBJECT_HOOK_FAILURES.setdefault("verification", {}).clear()
                task = {
                    "@id": "urn:fnsr:task:verify",
                    "agent": "verification-ritual",
                    "inputs": {
                        "artifact_text": "x",
                        "canonical_sources": {},
                    },
                }
                result = d._verification_ritual(task, {})
            cat99 = next(r for r in result.outputs["per_category_result"]
                         if r["category_id"] == "cat-99")
            self.assertEqual(cat99["status"], "miss")
            self.assertEqual(cat99["evidence"]["miss_class"],
                             d.MISS_UNRESOLVED_PREDICATE)
            self.assertIn("import_error", cat99["evidence"])
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
            # Reset cache for subsequent tests so the GraphWrite-shipped
            # subject hooks reload cleanly.
            d._SUBJECT_HOOKS_LOADED.discard("verification")
            d._SUBJECT_SANDBOXES.setdefault("verification", {}).clear()
            d._SUBJECT_HOOK_FAILURES.setdefault("verification", {}).clear()

    def test_resolve_subject_predicate_unknown_surface(self):
        # Wrong surface in the qualified name returns None.
        self.assertIsNone(
            d._resolve_predicate("subject.wrongsurface.cat_10_type_field_structure"))

    def test_resolve_predicate_explicit_function_name(self):
        # subject.verification.<module>.<func> form
        pred = d._resolve_predicate(
            "subject.verification.cat_10_type_field_structure."
            "cat_10_type_field_structure")
        self.assertTrue(callable(pred))


class TestCat08MultiCanonicalSource(unittest.TestCase):
    """Cat 8 v2.8.0-alpha.2 — hybrid two-cadence."""

    def setUp(self):
        self.registries = {
            "bfo": "http://purl.obolibrary.org/obo/BFO_0000001\n"
                    "http://purl.obolibrary.org/obo/BFO_0000003\n",
            "cco": "bfo:Process\nbfo:Continuant\ncco:Agent\n",
        }

    def test_pre_routing_pass_with_known_iri(self):
        artifact = "see http://purl.obolibrary.org/obo/BFO_0000001 for context"
        result = d.cat_08_multi_canonical_source(
            artifact, {"iri_registries": self.registries},
            d.PredicateMetadata(cadence="pre-routing"))
        self.assertEqual(result["status"], "pass")

    def test_pre_routing_veto_on_unknown_iri(self):
        artifact = "see http://example.com/unknown/IRI_xyz"
        result = d.cat_08_multi_canonical_source(
            artifact, {"iri_registries": self.registries},
            d.PredicateMetadata(cadence="pre-routing"))
        self.assertEqual(result["status"], "veto")
        self.assertTrue(len(result["evidence"]["unmatched"]) > 0)

    def test_curie_recognition(self):
        artifact = "uses bfo:Process and cco:Agent"
        result = d.cat_08_multi_canonical_source(
            artifact, {"iri_registries": self.registries},
            d.PredicateMetadata(cadence="pre-routing"))
        self.assertEqual(result["status"], "pass")

    def test_activation_time_veto_without_se_flag(self):
        artifact = "see http://example.com/unknown/IRI_xyz"
        result = d.cat_08_multi_canonical_source(
            artifact, {"iri_registries": self.registries},
            d.PredicateMetadata(cadence="activation-time"))
        self.assertEqual(result["status"], "veto")
        self.assertEqual(result["evidence"]["cadence"], "activation-time")

    def test_activation_time_needs_llm_judgment_with_se_flag(self):
        artifact = (
            "see http://example.com/unknown/IRI_xyz\n\n"
            "semantic_equivalence_acceptable: {reason: \"BFO IRI with "
            "explicit equivalentClass declaration\", scope: cat-8-only}"
        )
        result = d.cat_08_multi_canonical_source(
            artifact, {"iri_registries": self.registries},
            d.PredicateMetadata(cadence="activation-time"))
        self.assertEqual(result["status"], "needs_llm_judgment")
        self.assertIn("semantic_equivalence_acceptable", result["evidence"])
        se = result["evidence"]["semantic_equivalence_acceptable"]
        self.assertEqual(se["scope"], "cat-8-only")
        self.assertIn("BFO", se["reason"])

    def test_miss_when_no_registries(self):
        result = d.cat_08_multi_canonical_source(
            "iri http://x", {}, d.PredicateMetadata())
        self.assertEqual(result["status"], "miss")

    def test_pass_no_iri_citations(self):
        result = d.cat_08_multi_canonical_source(
            "no IRIs here", {"iri_registries": self.registries},
            d.PredicateMetadata(cadence="pre-routing"))
        self.assertEqual(result["status"], "pass")


class TestTwoCadenceOrchestration(unittest.TestCase):
    """v2.8.0-alpha.2 two-cadence dispatch: activation-time runs ONLY
    two-cadence categories (per Aaron's Gap D implementation note —
    don't re-execute Cat 1-7 + Cat 10 at activation-time)."""

    def _run(self, cadence):
        task = {
            "@id": "urn:fnsr:task:verify",
            "agent": "verification-ritual",
            "inputs": {
                "artifact_text": "see ADR-001 and bfo:Process",
                "canonical_sources": {
                    "decisions": SAMPLE_DECISIONS,
                    "spec": SAMPLE_SPEC,
                    "iri_registries": {"bfo": "bfo:Process\n"},
                    "interface_declarations": "stub",
                    "fol_types": SAMPLE_FOL_TYPES_TS,
                    "owl_types": SAMPLE_OWL_TYPES_TS,
                },
                "cadence": cadence,
            },
        }
        return d._verification_ritual(task, {})

    def test_pre_routing_runs_all_applicable(self):
        result = self._run("pre-routing")
        cats_run = {r["category_id"]
                    for r in result.outputs["per_category_result"]}
        # Cat 1-7 + Cat 8 (two-cadence in pre-routing) + Cat 10 (candidacy)
        self.assertIn("cat-01", cats_run)
        self.assertIn("cat-02", cats_run)
        self.assertIn("cat-08", cats_run)
        self.assertIn("cat-10", cats_run)

    def test_activation_time_runs_only_two_cadence_categories(self):
        result = self._run("activation-time")
        cats_run = {r["category_id"]
                    for r in result.outputs["per_category_result"]}
        # Only Cat 8 (cadence: two-cadence) should appear; Cat 1-7
        # (cadence: pre-routing) and Cat 10 (cadence: pre-routing) are
        # filtered out at activation-time.
        self.assertIn("cat-08", cats_run)
        self.assertNotIn("cat-01", cats_run)
        self.assertNotIn("cat-02", cats_run)
        self.assertNotIn("cat-07", cats_run)
        self.assertNotIn("cat-10", cats_run)


class TestCat09SpecAndDeferral(unittest.TestCase):
    """v2.8.0-alpha.3: Cat 9 (cited-content consistency, LLM candidacy)
    spec loaded by the deterministic verification-ritual; LLM categories
    defer via overall_status=needs_llm_judgment when their canonical
    sources are present. The CP3 verification-ritual-llm consumes the
    deferred payload (LLM dispatch is operator-queued downstream)."""

    def _run(self, inputs):
        task = {"@id": "urn:test:verification", "agent": "verification-ritual",
                "inputs": inputs}
        return d._verification_ritual(task, {})

    def test_cat_09_spec_loads(self):
        specs = d._load_category_specs()
        cat9 = next((s for s in specs if s.get("category_id") == "cat-09"),
                     None)
        self.assertIsNotNone(cat9)
        self.assertEqual(cat9["implementation_mode"], "llm")
        self.assertEqual(cat9["ratification_status"], "candidacy")
        self.assertEqual(cat9["llm_dispatcher_agent"],
                         "verification-ritual-llm")
        self.assertEqual(cat9["llm_mode"], "cat-9-judge")

    def test_cat_09_misses_when_canonical_sources_absent(self):
        # No spec or decisions in canonical_sources -> Cat 9 misses with
        # missing_canonical_source. The deferral signal only fires when
        # there's content to judge.
        result = self._run({
            "artifact_text": "x",
            "canonical_sources": {},
        })
        cat9 = next(r for r in result.outputs["per_category_result"]
                     if r["category_id"] == "cat-09")
        self.assertEqual(cat9["status"], "miss")
        self.assertEqual(cat9["evidence"]["miss_class"],
                         d.MISS_MISSING_CANONICAL_SOURCE)

    def test_cat_09_defers_when_sources_present(self):
        result = self._run({
            "artifact_text": "see ADR-001 for context",
            "canonical_sources": {
                "spec": SAMPLE_SPEC,
                "decisions": SAMPLE_DECISIONS,
            },
        })
        cat9 = next(r for r in result.outputs["per_category_result"]
                     if r["category_id"] == "cat-09")
        self.assertEqual(cat9["status"], "deferred_llm")
        self.assertEqual(cat9["evidence"]["llm_dispatcher_agent"],
                         "verification-ritual-llm")
        self.assertEqual(cat9["evidence"]["llm_mode"], "cat-9-judge")
        # Overall status reflects the deferral
        self.assertEqual(result.outputs["overall_status"],
                         "needs_llm_judgment")


class TestAdversarialCriticMultiMode(unittest.TestCase):
    """v2.8.0-alpha.3: adversarial-critic gains a cat-9-second-pass mode
    per FNSR Spec 02 §"Open questions" + Aaron's CP3 observation 2
    (fires on Cat 9 vetoes only). default_mode=review-second-pass keeps
    existing CP2-and-earlier dispatch tasks working unchanged."""

    def test_default_mode_returns_review_second_pass_required_keys(self):
        # Existing tasks dispatching adversarial-critic without inputs.mode
        # should still get their required_outputs enforced per the
        # review-second-pass contract (default_mode mechanism, v2.8.0-
        # alpha.3 default_mode frontmatter field).
        result = d._agent_required_outputs("adversarial-critic")
        self.assertEqual(result, [
            "verdicts", "missed_findings", "overall_verdict", "summary",
        ])

    def test_explicit_review_second_pass_mode(self):
        result = d._agent_required_outputs(
            "adversarial-critic", mode="review-second-pass")
        self.assertEqual(result, [
            "verdicts", "missed_findings", "overall_verdict", "summary",
        ])

    def test_cat_9_second_pass_mode(self):
        result = d._agent_required_outputs(
            "adversarial-critic", mode="cat-9-second-pass")
        self.assertEqual(result, [
            "cat_9_verdicts", "overall_verdict", "summary",
        ])

    def test_cat_9_second_pass_cps_check(self):
        task = {"agent": "adversarial-critic",
                "inputs": {"mode": "cat-9-second-pass"}}
        outputs = {
            "cat_9_verdicts": [
                {"citation_reference": "ADR-012",
                 "judge_verdict": "inconsistent",
                 "second_pass_stance": "confirm_veto",
                 "second_pass_rationale": "..."}
            ],
            "overall_verdict": "vetoes_confirmed",
            "summary": "1 veto confirmed",
        }
        # MUST NOT raise.
        d.cps_check(task, outputs)

    def test_cat_9_second_pass_missing_cat_9_verdicts_vetoes(self):
        task = {"agent": "adversarial-critic",
                "inputs": {"mode": "cat-9-second-pass"}}
        outputs = {
            "overall_verdict": "vetoes_confirmed",
            "summary": "x",
        }
        with self.assertRaises(d.ContainmentVeto) as ctx:
            d.cps_check(task, outputs)
        self.assertIn("cat_9_verdicts", str(ctx.exception))

    def test_review_second_pass_back_compat_cps_check(self):
        # Existing task shape (no inputs.mode) still gets reviewed against
        # the review-second-pass required_outputs.
        task = {"agent": "adversarial-critic"}
        outputs = {
            "verdicts": [],
            "missed_findings": [],
            "overall_verdict": "reviewer_acceptable",
            "summary": "x",
        }
        d.cps_check(task, outputs)


class TestVerificationRitualLlmAgentContract(unittest.TestCase):
    """v2.8.0-alpha.3: verification-ritual-llm worker agent's frontmatter
    declares multi-mode required_outputs (cat-9-judge and
    cat-8-semantic-equivalence) per Aaron's two-agent-split call."""

    def test_agent_md_file_exists(self):
        # Located alongside other worker agents
        from pathlib import Path
        path = Path(__file__).resolve().parent.parent / ".claude" / "agents" \
            / "verification-ritual-llm.md"
        self.assertTrue(path.exists())

    def test_cat_9_judge_mode_required_outputs(self):
        result = d._agent_required_outputs(
            "verification-ritual-llm", mode="cat-9-judge")
        self.assertEqual(result, [
            "per_category_result", "overall_status", "summary",
        ])

    def test_cat_8_semantic_equivalence_mode_required_outputs(self):
        result = d._agent_required_outputs(
            "verification-ritual-llm", mode="cat-8-semantic-equivalence")
        self.assertEqual(result, [
            "per_category_result", "overall_status", "summary",
        ])

    def test_unknown_mode_returns_empty(self):
        # No default_mode declared; unknown mode yields empty list (no
        # required-keys enforcement). Caller is responsible for passing
        # a valid mode.
        result = d._agent_required_outputs(
            "verification-ritual-llm", mode="unknown-mode")
        self.assertEqual(result, [])


class TestParseSeAcceptable(unittest.TestCase):
    """v2.8.0-alpha.2 — _parse_se_acceptable handles both JSON-object
    inline and YAML-frontmatter-style form."""

    def test_json_object_form(self):
        text = ('semantic_equivalence_acceptable: '
                '{reason: "BFO equivalentClass declaration", '
                'scope: "cat-8-only"}')
        result = d._parse_se_acceptable(text)
        self.assertEqual(result["reason"], "BFO equivalentClass declaration")
        self.assertEqual(result["scope"], "cat-8-only")

    def test_absent_returns_none(self):
        self.assertIsNone(d._parse_se_acceptable("no flag here"))

    def test_malformed_missing_field_returns_none(self):
        text = 'semantic_equivalence_acceptable: {reason: "x"}'
        self.assertIsNone(d._parse_se_acceptable(text))


if __name__ == "__main__":
    unittest.main()
