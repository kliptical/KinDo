---
name: verification-ritual
description: Deterministic system agent (v2.8.0 Checkpoint 1). Orchestrates the verification ritual per FNSR Protocol Spec 02. Loads category specs from surfaces/verification/categories/ at dispatch time; runs deterministic predicates against the path-fence-authored artifact for each applicable category; aggregates results. LLM-required categories (Cat 9, Cat 8 semantic-equivalence) emit a needs_llm_judgment signal for downstream dispatch via verification-ritual-llm in Checkpoint 3.
required_outputs: [per_category_result, overall_status, new_candidacies, summary]
---

# verification-ritual — system agent (v2.8.0 Checkpoint 1)

Runs the verification ritual on path-fence-authored content per FNSR Protocol Spec 02. Catches references that drift from canonical sources at machine speed.

## Architecture (per Aaron's Call 1 adjudication)

Two-agent split:

1. **`verification-ritual`** (this agent; system, deterministic Python) runs Cat 1–7 + Cat 10 + Cat 8-pre-routing.
2. **`verification-ritual-llm`** (worker agent; Checkpoint 3) runs Cat 9 + Cat 8-semantic-equivalence cases when this agent emits `needs_llm_judgment` in `overall_status`.

The operator composes the chain: `verification-ritual → [verification-ritual-llm if needed] → [adversarial-critic for Cat 9 second-pass] → ratification → operator-applier (v2.7.0 interim) / commit-finalize (v2.8.0+)`.

## Inputs

```yaml
inputs:
  # One of these is required:
  artifact_text: <string content to verify>
  artifact_path: <path relative to repo root; file content is loaded>

  # Canonical sources the categories need; keys match each category spec's
  # canonical_source_keys frontmatter. Values may be inline strings OR file
  # paths (loaded automatically). Nested dicts are supported (e.g.,
  # cycle_artifacts: {path: text-or-path}).
  canonical_sources:
    spec: project/SPEC.md
    decisions: project/DECISIONS.md
    # ... per the categories in use

  # Optional. Defaults to "pre-routing". Other values:
  #   activation-time   — Cat 8 vendoring-analog-time cadence
  cadence: pre-routing

  # Optional. The artifact's own path; Cat 7 uses this to detect reciprocal
  # cross-references. Defaults to artifact_path when present.
  artifact_self_path: project/reviews/Q-4-Step5-A.md

  # Optional. Surface name; defaults to "verification". Future surfaces
  # may register additional surface-specs.
  surface: verification
```

## Outputs

```yaml
outputs:
  per_category_result:
    - category_id: cat-01
      name: Spec-Section-Existence Verification
      status: pass | veto | miss
      evidence: { ... category-specific ... }
    - category_id: cat-02
      ...
  overall_status: pass | veto | needs_llm_judgment
  new_candidacies: []   # populated in Checkpoint 3+ when patterns no category covers surface
  summary: "verification ritual: N pass, M veto, K miss (cadence=...)"
```

`overall_status: pass` when every applicable category passed. `overall_status: veto` when one or more vetoed. `overall_status: needs_llm_judgment` (Checkpoint 3+) when deterministic categories all passed but LLM-required categories are queued for the next step.

`status: miss` on a category indicates the predicate couldn't run (required canonical source absent, predicate raised an exception, etc.). Misses do NOT veto in v2.8.0 alpha; they signal "the category was not evaluated this run." The operator audits misses to decide whether to provide missing inputs and re-run.

## Category-spec format

Each category lives under `surfaces/verification/categories/cat-NN-name.md` with the format documented in `surfaces/verification/surface-spec.md`. Adding a new ratified category = drop a new file + implement the named `python_predicate` (for deterministic categories) or prompt template (for LLM categories) — no substrate release.

## CPS integration

Operators queue verification-ritual upstream of ratification and (for Cat 8 activation-time) upstream of commit-finalize. The architect's ratification ruling references the verification-ritual task @id in its `referenced_evidence` field. CPS enforces the `depends_on` graph; veto routing is the architect's responsibility (the architect agent's prompt should refuse ratification when UPSTREAM verification-ritual.overall_status is `veto`).

This matches the v2.7.0 pattern: substrate provides primitives; operator composes chains; agents reason from UPSTREAM.

## Checkpoint scope

- **Checkpoint 1** (v2.8.0-alpha.1, this release): Cat 1–7 deterministic predicates + orchestrator + spec loader.
- **Checkpoint 2** (v2.8.0-alpha.2): Cat 8 hybrid + Cat 10 hook framework + two-cadence handling.
- **Checkpoint 3** (v2.8.0-alpha.3 or rc.1): `verification-ritual-llm` worker agent + Cat 9 + adversarial-critic Cat 9 second-pass + `new_candidacies` operator-decision routing.
- **Checkpoint 4** (v2.8.0): forward-track transition/list/aging + final docs + tag.
