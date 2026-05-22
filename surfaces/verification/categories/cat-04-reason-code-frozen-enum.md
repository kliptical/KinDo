---
category_id: cat-04
name: Reason-Code-Against-Frozen-Enum Verification
implementation_mode: deterministic
cadence: pre-routing
verification_mode: STRUCTURAL
python_predicate: fnsr_daemon.cat_04_reason_code_frozen_enum
canonical_source_keys: [reason_codes]
ratification_status: ratified
---

# Cat 4 — Reason-Code-Against-Frozen-Enum Verification

Per FNSR Protocol Spec 02 §"Cat 4 — Reason-Code-Against-Frozen-Enum Verification".

## Inputs
- Path-fence-authored artifacts citing `expectedReason: "X"` values
- The frozen reason-code enum (canonical source key: `reason_codes`; Logic Team instance: `src/kernel/reason-codes.ts`, an `Object.freeze`'d canonical 16-member set)

## Verification mode
**STRUCTURAL only.** Is reason code "X" a member of the frozen 16-member set?

## Veto criteria
Cited reason code not in frozen enum → ritual veto.

## Cadence
Single (pre-routing).

## Production history
Phase 3 Step 4 — `naf_residue` cited in `cwa_open_predicate` fixture's `expectedReason`; reason did NOT exist (it was a LossType, not a reason code). Routed Q-3-Step4-A; architect ratified Option β (reuse of `open_world_undetermined`). Reason-enum-stability discipline preserved.

## Implementation note
The predicate scans the artifact text for `"expectedReason"\s*:\s*"X"` patterns. The frozen enum is extracted from the canonical source text by matching the `Object.freeze([...])` or equivalent pattern; Logic Team's instance uses TypeScript syntax. Returns `evidence` listing all cited reason codes, with which are matched vs unmatched.

## Subject-project-specific note
The `Object.freeze([...])` pattern for declaring the canonical enum is Logic Team's TypeScript convention. Subject projects with different reason-code surfaces can override the predicate by editing the `python_predicate` field. For non-TypeScript subject projects, the predicate logic generalizes if you can extract the canonical enum members as strings.
