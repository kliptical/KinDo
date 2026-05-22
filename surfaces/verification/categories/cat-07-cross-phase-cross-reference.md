---
category_id: cat-07
name: Cross-Phase Plus Cross-Amendment Cross-Reference Verification
implementation_mode: deterministic
cadence: pre-routing
verification_mode: STRUCTURAL
python_predicate: fnsr_daemon.cat_07_cross_phase_cross_reference
canonical_source_keys: [cycle_artifacts]
ratification_status: ratified
---

# Cat 7 — Cross-Phase + Cross-Amendment Cross-Reference Verification

Per FNSR Protocol Spec 02 §"Cat 7 — Cross-Phase + Cross-Amendment Cross-Reference Verification".

## Inputs
- Cycle artifacts citing prior cycle artifacts
- Cross-references between same-cycle artifacts (routing artifact ↔ verification ritual report ↔ entry packet § amendments)
- Canonical source key: `cycle_artifacts`; value is a `{path: text}` dict where keys are artifact paths and values are artifact contents

## Verification mode
**STRUCTURAL only.** Does the cited prior artifact exist at the named path? Does the cross-reference at one artifact match the cross-reference at the other? Does NOT verify the cited content's actual semantic match — that boundary is Cat 9 candidacy.

## Veto criteria
- Cross-reference dangles (cited artifact doesn't exist), OR
- Cross-references are asymmetric (artifact A claims B references A, but B doesn't reference A)

## Cadence
Single (pre-routing).

## Production history
Q-4-Step5-A Catch 4 contributed via Cat 7 dimension — the `relatedADRs` citation surface was a cross-reference verification surface; the conflation surfaced through multi-surface comparison.

## Implementation note
The predicate scans the artifact text for path-like cross-references (Markdown `[text](path)` links and plain `path/to/file.md` strings inside artifact bodies). For each cited path:

1. Existence check: is the cited path present in `cycle_artifacts`?
2. Symmetry check: when artifact A cites artifact B with a reciprocal-implying phrase ("see also", "referenced from", "captured in"), does B contain a reciprocal reference back to A?

Returns `evidence` listing all cross-references found, with each tagged as: matched (exists + symmetric) / dangling (cited path missing) / asymmetric (cited path exists but no reciprocal reference where one is expected).

## Subject-project-specific note
The reciprocal-implying-phrase heuristic ("see also", "referenced from", "captured in") is a starting set; subject projects may extend it via predicate override.
