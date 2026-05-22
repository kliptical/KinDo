---
category_id: cat-01
name: Spec-Section-Existence Verification
implementation_mode: deterministic
cadence: pre-routing
verification_mode: STRUCTURAL
python_predicate: fnsr_daemon.cat_01_spec_section_existence
canonical_source_keys: [spec]
ratification_status: ratified
---

# Cat 1 — Spec-Section-Existence Verification

Per FNSR Protocol Spec 02 §"Cat 1 — Spec-Section-Existence Verification".

## Inputs
- Path-fence-authored artifacts citing spec §N.M references
- The binding spec document (canonical source key: `spec`)

## Verification mode
**STRUCTURAL only.** Does §N.M exist? Grep matches the section header. Does **not** verify cited content matches the citing artifact's framing — that is Cat 9 candidacy.

## Veto criteria
Cited §N.M doesn't exist in the canonical spec → ritual veto, pre-routing correction required.

## Cadence
Single (pre-routing).

## Production history
Phase 3 Step 5 routing artifact 2026-05-08 cited spec §3.4.4 which did NOT exist (off-by-one; correct was §3.4.1). First production catch in engagement.

## Implementation note
The predicate scans the artifact text for `§N.M` and `§N.M.K` patterns and looks each one up as a section header in the canonical spec text. Returns `evidence` listing all citations found, with which are matched vs unmatched.

## Gap candidacy
This category is STRUCTURAL only. The semantic gap — does §N.M's content match the cited framing? — is **Cat 9 candidacy** (see `cat-09-cited-content-consistency.md`, candidacy in v2.8.0).
