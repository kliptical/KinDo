---
category_id: cat-09
name: Cited-Content Consistency Verification
implementation_mode: llm
cadence: pre-routing
verification_mode: SEMANTIC
python_predicate: null
llm_dispatcher_agent: verification-ritual-llm
llm_mode: cat-9-judge
canonical_source_keys: [spec, decisions]
ratification_status: candidacy
---

# Cat 9 Candidacy — Cited-Content Consistency

Per FNSR Protocol Spec 02 §"Cat 9 Candidacy — Cited-Content Consistency".

## Status: Candidacy (Phase 4 exit retro candidate #1)

Forward-tracked per Q-4-Step5-A Pass 2b Banking 5. Cat 9 covers the **semantic** gap that the STRUCTURAL-only Cat 1, 2, 3, 7 leave uncovered: reference existence holds (the citation resolves to something in the canonical registry), but the framing the citing artifact attaches to the reference matches NO registry entry.

## Boundary that surfaces it

Reference-existence (Cat 1, 2, 3, 7) holds: reference target exists at named location. Reference-consistency (Cat 9) verifies that the actual content at that location matches what the citing artifact asserts.

- Cat 9 ≠ Cat 1: Cat 1 = does §N.M exist; Cat 9 = does §N.M's content match the cited framing?
- Cat 9 ≠ Cat 2: Cat 2 = does ADR-NNN exist in the registry; Cat 9 = does the registered ADR-NNN entry match the cited framing?
- Cat 9 ≠ Cat 3: Cat 3 = does Q-N-X exist as an identifier; Cat 9 = does the Q-N-X ruling text match the cited claim?

## Category-agnostic prompt shape

Per Aaron's CP3 implementation observation 1: Cat 9 is broader than any single citation surface. The LLM judge receives:

- **citation_reference**: the reference identifier (e.g., `ADR-012`, `§3.4.1`, `Q-4-Step5-A`)
- **citing_framing**: the text in the citing artifact that quotes or paraphrases the reference
- **canonical_content**: the actual content at the reference location in the canonical registry

…and judges semantic consistency without hard-coding any specific citation surface.

## Veto criteria

Cat 9 vetoes when the citing artifact's framing makes claims about the reference that are NOT supported by the actual canonical content at that reference.

## Cadence
Single (pre-routing). Cat 9 verdicts at activation-time would re-execute the LLM judge with the same inputs; the verdict could disagree with the pre-routing verdict due to LLM judge inconsistency. Per Aaron's Gap D implementation note, the activation-time cadence runs ONLY Cat 8; Cat 9 is pre-routing-only.

## Adversarial-critic second-pass (mitigation per Spec 02 §"Open questions")

LLM judges can disagree with themselves across runs. Per Aaron's CP3 implementation observation 2: any Cat 9 **veto** verdict requires a second-pass `adversarial-critic` dispatch (mode `cat-9-second-pass`). Cat 9 pass verdicts do not require second-pass — they don't uniquely change downstream state.

Operator-composes the second-pass chain:

```
verification-ritual          (system; Cat 1-8, 10)
    ↓
verification-ritual-llm      (worker; Cat 9 judge)
    ↓ (only if a Cat 9 verdict is veto)
adversarial-critic           (worker; mode: cat-9-second-pass)
```

The adversarial-critic's verdict confirms / disputes / extends the Cat 9 veto. If the critic disputes, the operator considers whether to honor the Cat 9 veto or proceed with ratification. This makes Cat 9's LLM judgment **auditable via paired-verdict machinery** rather than treated as oracular — the FNSR-relevant precedent for non-deterministic-but-auditable normative judgment.

## Production history

- **Q-4-Step5-A Miss 1 (2026-05-14)**: `canary_connected_with_overlap` cited spec §3.4.1 in `relatedSpecSections`; spec §3.4.1 exists (Cat 1 passes); but fixture's `requiredPatterns[1]` asserted `overlaps → connected_with` axiom NOT in §3.4.1's ratified axiom set (§3.4.1 ratifies reflexivity + symmetry + parthood-extension). Q-4-G phase-boundary retroactive batch ritual reported 0 Cat 7 findings on this fixture; reference-existence held; reference-consistency failed. Developer-side Step 5 implementation reconnaissance caught what ritual missed. **This is the spec-section flavor of the Cat 9 gap.**

- **ADR-012 ghost (Spec 06)**: architect's verbatim citation at Q-4-Step5-A claimed "Per ADR-012 banked principle: 'Spec interpretation defaults to literal framing'" but ADR-012's registered content is "Cardinality routing — Direct Mapping with n-tuple matching." Cat 2 passes (ADR-012 exists in registry); Cat 9 vetoes (cited framing matches no registered content). **This is the ADR-registry flavor of the Cat 9 gap.**

Both production cases exercise the same category-agnostic predicate: cited framing vs canonical content semantic consistency. Future Cat 9 firings will surface Q-ruling content cases (Cat 3 flavor), cross-reference content cases (Cat 7 flavor), and others. The prompt template handles all flavors uniformly.

## Implementation note

Cat 9 is **LLM-required**: semantic consistency comparison between citing framing and canonical content cannot be reduced to deterministic predicates. The `verification-ritual` system agent emits `status: deferred_llm` for Cat 9 entries; the operator queues a `verification-ritual-llm` worker agent task whose `cat-9-judge` mode handles the actual LLM dispatch.

The structured-flag-discipline analog (mirroring v2.7.0's `editorial_verdict_reason` and v2.8.0-alpha.2's `semantic_equivalence_acceptable: {reason, scope}`): the verification-ritual-llm's per-cat-9-verdict output includes a `rationale` field naming the specific mismatch (when verdict=inconsistent) or the specific match-points (when verdict=consistent). This makes Cat 9 judgments auditable separately from the verdict itself.
