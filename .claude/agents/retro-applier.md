---
name: retro-applier
description: Deterministic system agent (v3.0-alpha.2). Consumes analytical-agent proposals (proposed_issues, proposed_actions, proposed_risks, vote_casts) from UPSTREAM and merges them into RETRO_STATE.jsonld with chain-hashed audit entries. Analog to v2.6.0's applier system agent, scoped to retro state instead of code changes. No LLM in the path.
required_outputs: [applied, failed, retro_state_version, summary]
---

# retro-applier — system agent (v3.0-alpha.2)

Deterministic merger of analytical-agent proposals into canonical retro state. Same pattern as the v2.6.0 `applier` for code changes; scoped to `RETRO_STATE.jsonld` instead of the filesystem.

## Inputs

```json
{
  "@id": "urn:fnsr:task:retro-merge-X",
  "agent": "retro-applier",
  "inputs": {
    "retro_state_path": "RETRO_STATE.jsonld",
    "proposals": {
      "<source-task-id>": { "outputs": { "proposed_issues": [...], ... } },
      "<source-task-id-2>": { "outputs": { "proposed_actions": [...], ... } }
    },
    "version_read": 7,
    "surface": "retro"
  }
}
```

- `retro_state_path` — path to the active `RETRO_STATE.jsonld` (required).
- `proposals` — dict keyed by source-task @id; each value is the source agent's outputs envelope. Multiple sources supported; the applier merges them all in one mutation per CAS semantics.
- `version_read` — the retro state's version when the upstream tasks read it; per MAREP v2.2 §9 CAS semantics, applier rejects if current version differs.
- `surface: retro` — confirms retro-surface attribution per the anti-pattern enforcement framework's `_is_retro_surface_task` detection.

## Outputs

On success:

```json
{
  "applied": [
    {"section": "issues", "id": "QA-1", "source_task": "urn:..."}
  ],
  "failed": [
    {"section": "...", "id": "...", "reason": "version_collision | schema_violation | id_collision"}
  ],
  "retro_state_version": 8,
  "summary": "applied N proposals from M source tasks; retro state now at version 8"
}
```

On version mismatch (CAS rejection):

```json
{
  "error": "version_mismatch",
  "details": "current_version=8, expected_version=7",
  "current_version": 8,
  "expected_version": 7
}
```

On unreadable state:

```json
{
  "error": "retro_state_unreadable",
  "path": "...",
  "details": "..."
}
```

## Mutation discipline

Per MAREP v2.2 §11.2 deterministic + idempotent + schema-compliant:

- Every proposal must declare `@id` (or the applier generates one from source-task + sequence)
- Re-applying a proposal with an `@id` already present in retro state is a no-op (idempotency via @id key)
- Each accepted mutation increments `retro_state.retro.version` by exactly 1 (atomic; not per-proposal)
- Each accepted mutation appends a chain-hashed audit entry via `hiri_sign`
- Schema-violating proposals go to `failed[]` with `reason: schema_violation`; the applier continues with remaining proposals (partial-apply with explicit failure report)

## Audit chain semantics

The retro-applier emits ONE audit entry per dispatch (covering all proposals applied in that mutation), not one per proposal. Per MAREP v2.2 §9 + the substrate's append-only invariant:

```json
{
  "version": 8,
  "agent": "retro-applier",
  "task_id": "urn:fnsr:task:retro-merge-X",
  "timestamp": "...",
  "diff_summary": "merged 5 proposed_issues from @QA + 2 proposed_actions from @DeliveryManager",
  "affected_sections": ["issues", "actions"],
  "prev_hash": "...",
  "chain_hash": "..."
}
```

The diff_summary names sources + counts; per-proposal `@id` provenance lives in `applied[].source_task`.

## Anti-pattern detection (v3.0-alpha.2)

The retro-applier ITSELF doesn't go through the retro-surface anti-pattern checks (it's a system agent with structured JSON inputs/outputs; no free-text fields where persona theater or freeform brainstorm would apply). But the proposals it consumes from analytical agents (`@QA`, `@DeliveryManager`, `@RiskAnalyst`, etc.) DID go through those checks at their dispatching CPS gates. The applier trusts the upstream CPS validation.

If an upstream agent emitted free-text content that should have been rejected (e.g., CPS bypass) and the applier merges it, the substrate's audit chain records the merge attribution; a future operator review surfaces the chain-of-custody.

## Side-effect profile

Writes to `RETRO_STATE.jsonld` via atomic-write + lock per the substrate's v2.2.x invariants. Same shape as v2.6.0 `applier` for code changes:
- Atomic write (write to .tmp; rename)
- Lock on retro state file
- Failure cases: PermissionError, OneDrive sync conflicts (substrate retries up to 6 times per v2.2.1)

No external side effects; not in the v2.9.0 external-side-effect-agent class.

## Sequencing in the retro chain

Typical retro chain composition:

```
@QA, @DeliveryManager, @RiskAnalyst, @Architect, @Developer, @UserAdvocate, @Skeptic
    (analytical agents emit proposals in parallel; each is its own task)
    ↓
retro-applier
    (merges all proposals into RETRO_STATE.jsonld at the next version)
    ↓
@Orchestrator (BAO; phase-transition decision based on the merged state)
```

The retro-applier is the **single mutation point** for the retro surface during analysis phases. Analytical agents propose; the applier merges; the Orchestrator coordinates. Same pattern as v2.6.0 applier separating dispatch from mutation.
