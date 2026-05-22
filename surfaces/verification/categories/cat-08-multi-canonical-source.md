---
category_id: cat-08
name: Multi-Canonical-Source Verification
implementation_mode: hybrid
cadence: two-cadence
verification_mode: STRUCTURAL+SEMANTIC
python_predicate: fnsr_daemon.cat_08_multi_canonical_source
canonical_source_keys: [iri_registries]
ratification_status: ratified
---

# Cat 8 — Multi-Canonical-Source Verification

Per FNSR Protocol Spec 02 §"Cat 8 — Multi-Canonical-Source Verification".

## Inputs
- Path-fence-authored artifacts citing canonical sources (BFO-2020 OWL IRIs, CCO IRIs, ADR registries, spec sections)
- Vendored IRI registries (canonical source key: `iri_registries`; value is a `{registry_name: text}` dict)

## Verification mode
**STRUCTURAL+SEMANTIC** (hybrid).

- Pre-routing cadence: STRUCTURAL — do cited IRIs and canonical-source references resolve in at least one vendored registry?
- At-vendoring-analog-time cadence: STRUCTURAL+SEMANTIC — content-match against canonical-source entries (strict-equality deterministic in v2.8.0; semantic-equivalence LLM-deferred when `semantic_equivalence_acceptable` flag is present).

## Veto criteria
- Pre-routing: cited canonical source doesn't resolve → ritual veto.
- Activation-time: cited content diverges from canonical-source content under strict equality, AND no `semantic_equivalence_acceptable` flag → ritual veto. If the flag is present, status is `needs_llm_judgment` (deferred to v2.8.0 CP3 `verification-ritual-llm`).

## Cadence
**Two-cadence**:
- Pre-routing: structural verification (shape + cross-reference)
- At-vendoring-analog-time: canonical-value confirmation at Pass 2b commit-time fetch + `[VERIFY]` marker flip

## Production history
- Q-4-Step4-A Catch 3 + Q-4-Step5-A Catch 4 + Q-4-Step6-A Catch 5 contributed via Cat 8 dimension (IRI verification + ADR-registry verification + canonical-source-content verification).
- Q-4-Step6-A Catch 6 was attributed via Cat 8 for routing purposes (closest existing category) but the catch's failure mode actually surfaced the Cat 10 candidacy boundary — canonical attribution is Cat 10 candidacy.

## semantic_equivalence_acceptable flag (Gap B v2.8.0)

Per Aaron's adjudication: when the citing artifact carries:

```yaml
semantic_equivalence_acceptable:
  reason: <one-sentence rationale; e.g., "BFO IRI with explicit equivalentClass declaration in canonical source">
  scope: cat-8-only | all-applicable-cats
```

…and activation-time strict-equality fails for one or more cited IRIs, the predicate returns `status: needs_llm_judgment` with the unmatched IRIs and the SE-acceptable payload. The CP3 `verification-ritual-llm` worker agent runs the semantic-equivalence comparison.

The structured flag is opt-in: every operator that sets it is committing the rationale to the audit trail, mirroring the `editorial_verdict_reason` audit-surfacing pattern from v2.7.0 architect ratification.

## Implementation note
The predicate scans the artifact for absolute IRIs (`http://...`, `https://...`) and CURIE-style references (e.g., `bfo:Process`, `cco:Agent`). For each, it checks every vendored IRI registry in canonical_sources['iri_registries']. The activation-time cadence's content-comparison logic is the CP3 LLM-deferred branch; CP2 ships the structural-existence half + the deferral signal.
