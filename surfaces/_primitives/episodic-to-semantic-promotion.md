---
primitive_id: episodic-to-semantic-promotion
short_name: E→S Promotion
introduced_in: v3.0-alpha.2
first_explicit_instance: retro-surface phase-exit (MAREP §16.4)
prior_implicit_instances:
  - ADR drafting from operator decisions (v2.7.0)
  - PLAYBOOK additions from failure-mode recovery (v2.6.0+)
  - Forward-track creation from candidacy surfacing (v2.7.0+)
canonical_reference: ariadne/archive/specs/MAREP-v2.2/MAREP_v2.2.md §16.4
---

# Episodic → Semantic Promotion — substrate primitive

## What it is

A discipline for moving observations from **episodic memory** (recent, contextual, situated) to **semantic memory** (stable, canonical, normative) via **deliberate operator-mediated promotion** — never automatic accumulation.

The pattern is substrate-wide. It applies wherever the substrate accumulates observations that *might* warrant canonical status: retros (one instance), failure-mode discoveries during operation (another instance), banking events that surface enduring discipline (another), forward-track candidacies that resolve as substrate amendments (another). Every promotion boundary uses the same machinery.

This document is the substrate's canonical specification of the promotion pattern. Documents referencing "Episodic → Semantic promotion" or "deliberate promotion discipline" cite this primitive.

## Memory layers (substrate-wide; MAREP-retro is one instance)

| Layer | Storage | Access | Lifecycle |
|---|---|---|---|
| **Working memory** | active state.jsonld + active surface state files (RETRO_STATE.jsonld, active task histories) | read+write by participating agents within their permitted_sections | persists for current task / cycle / retro |
| **Episodic memory** | sealed past state in audit chain + FNSR archive (`<fnsr-archive>/archive/`) | read-only; surfaced to active agents only via Orchestrator/operator mediation | permanent; append-only; never destroyed |
| **Semantic memory** | CLAUDE.md, PLAYBOOK.md, ADRs in DECISIONS.md, FNSR Protocol Specs, `surfaces/<surface>/surface-spec.md` files, `surfaces/_primitives/<primitive>.md` files | read-only during active work; updates require deliberate process | evolves via deliberate operator action between cycles |

The three-layer model is FNSR Spec 01 + MAREP v2.2 §16 territory; this primitive doc specifies the **promotion mechanism** between layers, which is the part the substrate enforces.

## The two promotion boundaries

**Working → Episodic** (automatic, on cycle/task close):
- Active state seals into audit chain via the substrate's append-only invariant
- Surface state (e.g., RETRO_STATE.jsonld at retro close) writes to FNSR archive via operator action (`state_admin retro archive`, future analogous commands)
- No operator-deliberation gate — closing a cycle is the gate

**Episodic → Semantic** (deliberate, operator-mediated):
- Operator reviews episodic entries for promotion candidates
- For each candidate, operator queues the standard substrate ratification chain:
  ```
  reconnaissance → ratification → commit-finalize
  ```
- The ratification produces an architect ruling on whether the candidate promotes
- Commit-finalize lands the semantic-memory update (ADR, PLAYBOOK section, CLAUDE.md amendment, primitive doc, surface-spec revision)
- The promotion is itself a `forward_track` audit event with `subject.type: candidacy`, `sub_surface: internal-methodology-refinement`, `surfacing_task_id: <originating episodic task @id>` per FNSR Spec 07 — preserves provenance from observation to canon

## Why deliberate, never automatic

Automatic promotion fails three properties simultaneously:

1. **Audit-trail honesty.** Automatic promotion happens without operator review; the audit chain shows the promotion but not the deliberation. A future operator reviewing the promotion cannot re-derive whether the decision was sound — only that it happened.
2. **Backward stability.** Semantic memory entries (ADRs, PLAYBOOK sections, primitive docs) get cited by downstream work. Automatic promotion means downstream work cites entries whose canonical status was not deliberated. Citation graphs degrade in trustworthiness.
3. **Substrate-vs-procedure distinction.** Automatic promotion makes the substrate the authority on what becomes canon. Deliberate promotion makes the operator the authority (via the ratification chain). The substrate's role is to make the deliberation auditable; the operator's role is to deliberate.

The substrate's job is to **make the promotion path tractable** — clean ratification chain, structured forward-track provenance, mechanical CPS gating — not to **decide what promotes**.

## How the substrate enforces the discipline

### Substrate-mechanical enforcement (per MAREP v2.2 §16.6)

The CPS hook `_check_no_semantic_memory_mutation` (lands in v3.0-alpha.2 with the anti-pattern CPS framework; first instantiation in retro-surface task validation) refuses retro-turn updates that would write to semantic-memory paths:

```python
_SEMANTIC_MEMORY_PATHS = (
    "surfaces/",                       # Surface specs (including this primitive doc)
    "project/DECISIONS.md",            # ADR registry
    "project/SPEC.md",                 # Subject project spec
    "project/ROADMAP.md",
    "project/IMPLEMENTATION_PLAN.md",
    "CLAUDE.md",
    "PLAYBOOK.md",
    "project/Routing/",                # FNSR Protocol Specifications
    ".claude/agents/",                 # Substrate-wide agent contracts
)
```

A retro turn (or any surface-task turn) that tries to mutate these paths gets `error: semantic_memory_immutable_from_retro` — substrate refuses without the deliberate ratification chain. The promotion path is the only path.

### Discovery → candidacy → ratification → canon (per surface)

The full chain for any episodic observation:

```
Observation surfaces in working memory
    ↓ (cycle/task close)
Observation seals into episodic memory (audit chain entry + optional FNSR archive)
    ↓ (operator review at phase-exit retro / ad-hoc review)
Candidate identified for promotion
    ↓ (operator runs `state_admin forward-track create --surfacing-task-id <episodic-task-id>`)
forward_track event in audit chain (subject.type: candidacy, sub_surface: internal-methodology-refinement)
    ↓ (operator queues ratification chain)
reconnaissance → ratification → commit-finalize
    ↓ (commit lands the semantic-memory update)
Semantic memory updated (ADR / PLAYBOOK section / primitive doc / spec)
    ↓ (forward-track transition to State C: ratified-into-spec)
Promotion complete; forward-track terminal state recorded
```

Every step lands in the audit chain. A future operator can re-derive every promotion's full path: what observation surfaced where, when it became a candidacy, who ratified it, what semantic-memory update resulted, how downstream work cited the result.

## Surfaces where this applies (substrate-wide pattern instances)

The pattern is one substrate primitive; multiple surfaces instantiate it. Each row below is an *instance* of E→S promotion, not a separate primitive:

| Surface | Episodic source | Semantic destination | Example |
|---|---|---|---|
| Retro (MAREP) | RETRO_STATE.jsonld at retro close | PLAYBOOK section + ADR | Phase-exit-retro observation → PLAYBOOK failure mode + operator-fix path |
| Verification | per-category `categorical_coverage_miss` history | New verification category file under `surfaces/verification/categories/` | Cat 9 candidacy observed multiple times → Cat 11 ratified |
| Banking lifecycle (Spec 05) | State 1 verbal-pending bankings | State 3 formalized entries in authoring-discipline doc | Pattern observed across cycles → AUTHORING_DISCIPLINE.md addition |
| Forward-track surface (Spec 07) | State A candidacies | Spec-level amendments, roadmap commitments | Long-lived candidacy → spec patch with rationale |
| Substrate primitive surface | substrate-development observations across releases | New primitive doc under `surfaces/_primitives/` | BAO pattern emerged in MAREP work → BAO primitive doc (v3.0-alpha.1) |

Every row uses the same machinery (ratification + commit-finalize). The substrate doesn't have N different promotion mechanisms; it has one mechanism applied to N surfaces.

## FNSR-relevance (why this matters beyond v3.0)

The synthetic moral person project will accumulate observations across years. Without a deliberate promotion discipline, observations either:

- **Stay episodic forever** (forgotten; no normative weight; substrate cannot reason from them)
- **Promote automatically** (canon becomes diluted by un-deliberated entries; backward stability degrades; audit-trail honesty fails)

The deliberate operator-mediated promotion path is the architecture's answer: observations accumulate freely in episodic memory; promotion to semantic canon requires explicit ratification; the ratification is auditable; the canon stays trustworthy because every entry has a citable promotion path.

This is FNSR-load-bearing in a way worth being explicit about. The synthetic moral person project requires normative apparatus that **evolves through deliberate promotion of considered observations, not through accumulation of un-deliberated ones**. The pattern's three properties (audit-trail honesty, backward stability, substrate-vs-procedure distinction) carry into the moral-deliberation domain unchanged.

The pattern's first explicit substrate instance is the v3.0 retro phase-exit. The prior implicit instances (ADR drafting from operator decisions in v2.7.0; PLAYBOOK additions from failure-mode recovery in v2.6.0+; forward-track creation in v2.7.0+) were doing the same thing without the primitive name. v3.0-alpha.2 makes the pattern explicit so future surfaces inherit it deliberately.

## Anti-patterns this primitive prevents

| Anti-pattern | Why it fails | This primitive's defense |
|---|---|---|
| Automatic accumulation | Audit-trail honesty + backward stability fail simultaneously | Ratification chain required; CPS refuses direct semantic mutation from working memory |
| Silent promotion | Operator deliberation not visible in audit chain | Every promotion has a `forward_track` event with `surfacing_task_id` provenance |
| Bypass-via-direct-edit | Operator hand-edits semantic memory without ratification | `_check_no_semantic_memory_mutation` CPS check refuses; deliberate process is the only path that goes through the substrate |
| Promotion without provenance | Semantic memory updates that cannot be traced back to evidence | `surfacing_task_id` field on the candidacy forward-track records the originating episodic task |

## Implementation status

- **v3.0-alpha.2 (THIS RELEASE)**: primitive doc authored; CPS check `_check_no_semantic_memory_mutation` lands as part of the anti-pattern enforcement framework; first explicit substrate instance (retro phase-exit) wired in v3.0 final.
- **v3.0 (final)**: `state_admin retro archive` operationalizes the promotion path end-to-end for retro-surface instances.
- **Future**: substrate-wide promotion automation hook (e.g., `state_admin promote --from-episodic <task-id> --to-semantic <path>`) may emerge; not in scope for v3.0.

## Cross-references

- MAREP v2.2 §16 (memory boundaries; explicit instance)
- MAREP_INTEGRATION_SPEC §12 (semantic-memory immutability enforcement)
- FNSR Spec 01 (surface-registry primitive; semantic memory as substrate-wide)
- FNSR Spec 05 (banking lifecycle; State 3 formalized is one promotion destination)
- FNSR Spec 07 (forward-track surface; candidacy → ratified resolution is the promotion mechanism)
- `surfaces/_primitives/bounded-authority-orchestrator.md` (BAO; companion primitive)

## Provenance

- MAREP v2.2 §16.4 (explicit deliberate-not-automatic adjudication)
- Aaron's CP3 adjudication (§16.4 confirmed; operator-mediated ratification chain is the promotion path)
- Aaron's v3.0-alpha.2 greenlight observation #3 (substrate-wide framing, not MAREP-specific)
- Prior implicit instances: v2.6.0 PLAYBOOK additions; v2.7.0 ADR drafting; v2.7.0+ forward-track creation; v2.8.0 verification ritual category extension
