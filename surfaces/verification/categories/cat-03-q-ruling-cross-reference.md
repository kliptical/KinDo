---
category_id: cat-03
name: Q-Ruling Cross-Reference Verification
implementation_mode: deterministic
cadence: pre-routing
verification_mode: STRUCTURAL
python_predicate: fnsr_daemon.cat_03_q_ruling_cross_reference
canonical_source_keys: [prior_cycle_artifacts]
ratification_status: ratified
---

# Cat 3 — Q-Ruling Cross-Reference Verification

Per FNSR Protocol Spec 02 §"Cat 3 — Q-Ruling Cross-Reference Verification".

## Inputs
- Path-fence-authored artifacts citing Q-N-X or Q-N-StepM-X references
- Prior cycle artifacts (canonical source key: `prior_cycle_artifacts`; value is a `{path: text}` dict of cycle artifact contents)

## Verification mode
**STRUCTURAL only.** Does the cited Q-ruling exist as a header / identifier anchor in a prior cycle artifact?

## Veto criteria
Cited Q-ruling doesn't exist, OR ruling exists but with a different identifier than cited (e.g., Q-4-A cited but actual ruling was Q-4-B).

## Cadence
Single (pre-routing).

## Production history
No notable production catch yet (no Q-ruling identifier mis-citation has surfaced); routine pass at every cycle's ritual run. The category has been actively running and discriminating, not no-op'd. Phase 4 has accumulated Q-4-A through Q-4-H plus Q-4-Step4-A, Q-4-Step5-A (with sub-rulings), and Q-4-Step6-A. Cat 3 verifies that cross-references between these hold.

## Implementation note
The predicate scans the artifact text for `Q-\d+(?:-Step\d+)?-[A-Z](?:\.\d+)?` patterns (e.g., `Q-4-A`, `Q-4-Step5-A`, `Q-4-Step5-A.1`) and checks each against the prior_cycle_artifacts dict. A Q-ruling is considered "found" if any prior cycle artifact contains the identifier as a header anchor (`## Q-...:` or as a `Q-...` identifier near a "ruling" section).

## Subject-project-specific note
The Q-ruling identifier convention (`Q-<phase>-<letter>` plus optional `-Step<N>` and `.N`) is Logic Team's. Subject projects with different identifier conventions can override the predicate by editing the `python_predicate` field in this category spec file.
