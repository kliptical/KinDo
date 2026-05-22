---
category_id: cat-06
name: Manifest Mirror Consistency Verification
implementation_mode: deterministic
cadence: pre-routing
verification_mode: STRUCTURAL
python_predicate: fnsr_daemon.cat_06_manifest_mirror_consistency
canonical_source_keys: [manifest, fixtures]
ratification_status: ratified
---

# Cat 6 — Manifest Mirror Consistency Verification

Per FNSR Protocol Spec 02 §"Cat 6 — Manifest Mirror Consistency Verification".

## Inputs
- Manifest entries (canonical source key: `manifest`; Logic Team instance: `tests/corpus/manifest.json`)
- Fixture files (canonical source key: `fixtures`; value is a `{path: text}` dict of fixture file contents; Logic Team instance: `tests/corpus/*.fixture.js`)

## Verification mode
**STRUCTURAL only.** Does the manifest entry's `expectedOutcome` field mirror the fixture's `expectedOutcome` field? Same `expectedConsistencyResult`, same `canaryRole`, same `expectedRequiredPatternsCount`, etc.

## Veto criteria
Manifest entry diverges from fixture → ritual veto, pre-routing reconciliation required.

## Cadence
Single (pre-routing).

## Production history
Q-4-Step4-A Catch 3 contributed via the manifest-mirror dimension. Manifest entry for `bfo_disjointness_map_axiom_emission` was authored alongside fixture; Cat 6 verified consistency.

## Implementation note
The predicate parses the manifest text as JSON, walks each entry, and for each entry that names a fixture path it compares the entry's `expectedOutcome` (and related declared-mirror fields) against the corresponding fixture's `expectedOutcome` parsed from the fixture text. Returns `evidence` listing each entry's mirror status (matched / diverged / fixture_missing).

## Subject-project-specific note
The manifest schema (JSON with `expectedOutcome`, `expectedConsistencyResult`, `canaryRole`, `expectedRequiredPatternsCount`) is Logic Team's testing convention. Subject projects with different manifest schemas can override the predicate.
