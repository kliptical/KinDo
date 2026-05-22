---
surface_id: verification
question_scope: "Does path-fence-authored content correctly cite, mirror, or otherwise correspond to canonical sources?"
audit_trail_unity: "One verification ritual run per routing-cycle artifact"
categories_path: surfaces/verification/categories/
parent_spec: project/Routing/02-verification-ritual-spec.md
status: v2.8.0-alpha.1
---

# Verification Surface

Per FNSR Protocol Spec 01 §"Verification Surface", the verification surface answers: **does path-fence-authored content correctly cite, mirror, or otherwise correspond to canonical sources?**

This is the first explicit surface registered under `surfaces/`. Future surfaces (cycle, commit, bankings, forward-track) will follow the same directory layout: `surfaces/<surface>/<bucket-or-category>/`.

## Audit-trail unity within this surface

One verification ritual run per routing-cycle artifact. Each run produces a structured payload listing per-category results plus an overall status. The run is the audit instance for the artifact's verification; subsequent references to the artifact's verification status cite the run, not the per-category results in isolation.

## Categories

Categories instantiate the surface's verification question for specific cross-reference surfaces. The category set is **evidence-grounded, not pre-declared closed** (per Spec 01 §"Evidence-grounded extension"). New categories surface when:

1. Production cases reveal a verification surface no existing category covers
2. The pattern repeats (two or more cases at the same boundary)
3. Forward-tracking to phase-exit retro candidacy accumulates supporting evidence

Logic Team's accumulated history through Phase 4 produced the Cat 1–8 ratified categories plus Cat 9 and Cat 10 candidacies, documented per-category under `categories/`.

## Verification modes

- **STRUCTURAL**: reference-existence verification ("does the reference exist?")
- **SEMANTIC**: reference-consistency verification ("does the actual content at the reference match the citing artifact's framing?")
- **STRUCTURAL+SEMANTIC**: hybrid — structural primary, semantic secondary

Categories with STRUCTURAL-only mode have explicit gap candidacies for the SEMANTIC coverage they leave uncovered (this is the boundary Cat 9 candidacy surfaces).

## Cadences

- **Single (pre-routing)**: structural verification at SME pre-routing ritual run, binds immediately before architect routing.
- **Two-cadence**: pre-routing structural + at-vendoring-analog-time canonical-value confirmation. Required for categories where canonical sources are external (URLs, vendored IRIs, third-party registries). Cat 8 is the canonical two-cadence category.

## Category spec file format

Each category lives under `surfaces/verification/categories/cat-NN-name.md` with frontmatter:

```yaml
---
category_id: cat-NN
name: <human-readable name>
implementation_mode: deterministic | llm | hybrid
cadence: pre-routing | activation-time | two-cadence
verification_mode: STRUCTURAL | SEMANTIC | STRUCTURAL+SEMANTIC
python_predicate: <fully-qualified Python function reference>  # required for deterministic / hybrid
llm_prompt_template: <path or inline reference>  # required for llm / hybrid
canonical_source_keys: [<key>, ...]  # which canonical sources the predicate needs
ratification_status: ratified | candidacy
---
```

The body contains the Spec 02 four-field description (inputs, verification mode, veto criteria, production history) plus implementation notes.

## How the verification-ritual agent reads this

The `verification-ritual` system agent loads every `cat-NN-*.md` file at task-dispatch time, filters by:

- `cadence` matches the task's `inputs.cadence`
- `canonical_source_keys` are all present in `task.inputs.canonical_sources`

…then dispatches the named `python_predicate` for each matching category. Results are aggregated into the `per_category_result` output field.

Adding a new category = drop a new `cat-NN-*.md` file under `categories/` and (for deterministic categories) implement the named Python predicate. No substrate release required. This realizes Spec 01's "minimum viable architecture" recommendation for surface-registry primitives.
