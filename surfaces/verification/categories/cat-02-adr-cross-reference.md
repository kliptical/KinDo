---
category_id: cat-02
name: ADR Cross-Reference Verification
implementation_mode: deterministic
cadence: pre-routing
verification_mode: STRUCTURAL
python_predicate: fnsr_daemon.cat_02_adr_cross_reference
canonical_source_keys: [decisions]
ratification_status: ratified
---

# Cat 2 — ADR Cross-Reference Verification

Per FNSR Protocol Spec 02 §"Cat 2 — ADR Cross-Reference Verification".

## Inputs
- Path-fence-authored artifacts citing ADR-NNN references
- Canonical ADR registries (canonical source key: `decisions`; optional secondary key: `spec_adr_registry` for subject projects that maintain a parallel spec §10 registry)

## Verification mode
**STRUCTURAL only.** Does ADR-NNN exist in the canonical registry? Does **not** verify the ADR's content matches the citing artifact's framing — that boundary is Cat 9 candidacy.

## Veto criteria
Cited ADR doesn't exist in the canonical registry, OR exists in only one registry when context implies both.

## Cadence
Single (pre-routing).

## Production history
- Q-4-Step5-A Catch 4 + Q-4-Step6-A Catch 5 — ADR-012 + ADR-011 mis-citations. ADRs existed in BOTH registries but with DIFFERENT content; the cited framing matched NEITHER (verbal-banked principle mis-attributed as numbered ADR). Pattern repetition strengthened parallel-registry-reconciliation forward-track candidacy.

## Implementation note
The predicate scans the artifact text for `ADR-NNN` patterns and looks each one up as a `## ADR-NNN:` header in the canonical decisions text. Returns `evidence` listing all citations found, with which are matched vs unmatched.

This is the same registry parser v2.6.0 uses for `_check_adr_citations`; the verification-ritual variant runs against arbitrary artifact text rather than the canonical-doc-scoped `changes[].after` content.

## Gap candidacy
The ADR-012 ghost case (FNSR Spec 06) is the canonical example: ADR-012 exists in registry (Cat 2 passes); the cited framing matches no registered content (Cat 9 vetoes). When v2.8.0 Checkpoint 3 ships Cat 9, the ADR-012 ghost is the anchor test case.
