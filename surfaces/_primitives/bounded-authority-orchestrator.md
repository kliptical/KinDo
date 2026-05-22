---
primitive_id: bounded-authority-orchestrator
short_name: BAO
introduced_in: v3.0-alpha.1
first_instance: synthesist (mode: generalized)
canonical_reference: ariadne/archive/specs/MAREP-v2.2/MAREP_v2.2.md §4.1.1
---

# Bounded-Authority Orchestrator (BAO) — substrate primitive

## What it is

A **Bounded-Authority Orchestrator (BAO)** is an LLM worker agent with elevated responsibility within an assigned surface but no substrate-level privileges. The pattern's value is auditable elevated-authority coordination: the agent can do work that requires LLM judgment AND elevated scope within its surface, while remaining bounded by the substrate's existing enforcement machinery.

The pattern was first named in MAREP v2.2 §4.1.1 (the retro-surface Orchestrator role). It generalizes beyond MAREP: the v3.0 generalized synthesist is the second instance; future BAO instances include the eventual phase-exit retro finalizer, the verification-ritual-llm in some modes, and FNSR moral-person deliberative coordinators.

This document is the substrate's canonical specification of the pattern. Documents referencing "the BAO pattern" cite this primitive.

## The four bounds (MUST hold for every BAO instance)

When the BAO pattern is invoked in agent contracts or substrate documentation, the four bounding properties MUST be consistently listed. Readings of "bounded-authority" that omit any of these four risk under-specifying the pattern; readers may interpret "bounded" more narrowly than intended.

### 1. Surface scope

The BAO's elevated authority extends only within its assigned surface. A BAO over the retro surface (MAREP-Orchestrator) cannot make decisions about the verification surface. A BAO over the synthesis surface (generalized synthesist) cannot make ratification decisions in the architect's place.

Cross-surface action requires standard dispatch through the substrate: the BAO emits a structured output proposing action on another surface; the operator (or a subsequent dispatched agent) acts on that proposal. The BAO does not reach across.

### 2. Substrate enforcement

All BAO outputs pass through the substrate's standard enforcement machinery:

- CPS `required_outputs` check
- Structured-error veto (the four-class miss taxonomy: `malformed_spec`, `unresolved_predicate`, `missing_canonical_source`, `categorical_coverage_miss`)
- Surface-specific anti-pattern detection (MAREP §17 for retro-surface BAOs; analogous patterns for future surfaces)
- Per-mutation lock + permitted_sections scope enforcement

The BAO cannot bypass any of these. It cannot extend its own scope. It cannot mutate state outside the permitted_sections declared in its role binding.

### 3. Audit-chain visibility

Every BAO decision lands in the audit chain via the normal dispatch path. There are no hidden BAO state transitions; the chain-hashed audit array captures every BAO action as a versioned mutation. The substrate's `hiri_sign` + prev_hash/chain_hash mechanism applies to BAO dispatches identically to non-BAO dispatches.

A future operator (or auditor) reading the audit chain can re-derive every BAO decision: what state was at dispatch, what the BAO emitted, what mutations resulted, what subsequent dispatches consumed. The "elevated authority" is elevated within the surface; it is NOT opaque to the audit chain.

### 4. No substrate-level privilege

The BAO is a worker agent. It cannot:

- Bypass the daemon's dispatch ordering (state.jsonld.lock + per-mutation atomic write)
- Write directly to state.jsonld
- Acquire locks outside the dispatch protocol
- Extend its dispatch authority beyond what its frontmatter declares
- Trigger system-agent operations directly (only via dispatched system-agent tasks)

Authority decisions — lock granting, scope enforcement, schema validation, anti-pattern detection — belong to the deterministic substrate. The BAO triggers sequencing within its surface; it does not own substrate-level enforcement.

## Why these four together (not just three of them)

The four bounds together distinguish a BAO from naive "give the LLM control" patterns where elevated responsibility comes with privilege escalation. Each bound prevents a specific failure mode that the others don't cover:

| Bound omitted | Failure mode that opens |
|---|---|
| Surface scope | A retro Orchestrator could make decisions about ratification, verification, or substrate-wide state. Cross-surface coupling becomes opaque. |
| Substrate enforcement | The BAO's outputs could bypass CPS, violate `required_outputs`, or emit anti-pattern content. Substrate's safety guarantees degrade. |
| Audit-chain visibility | The BAO's decisions could happen "off-chain" — not auditable, not reviewable, not challengeable. Substrate-vs-procedure distinction collapses. |
| No substrate-level privilege | The BAO could bypass dispatch ordering, mutate state directly, or trigger system-agent operations without going through the normal contract. Substrate's deterministic-where-possible guarantee fails. |

Implementers SHOULD treat these four as a unit. Naming a single one (e.g., "BAO has surface scope") in documentation without naming the others risks under-specifying the contract and leaving open one of the failure modes above.

## How to instantiate a BAO

For an LLM worker agent to be a BAO instance:

### Frontmatter declarations

```yaml
---
name: <agent-name>
description: <description noting BAO status and assigned surface>
tools: Read, Grep, Glob          # Read-only-by-contract; no Edit/Write/Bash
bao_pattern: true                # Explicit declaration; future substrate validators may require this
bao_surface: <surface-name>       # Surface scope per bound #1
required_outputs: [...]           # Substrate enforcement per bound #2
contract_class: read-only         # Aligns with no-substrate-privilege per bound #4
---
```

### Prompt-level discipline

The agent's prompt MUST encode the four bounds as agent-side discipline:

- Surface scope: agent's prompt explicitly limits its analysis and recommendations to its assigned surface.
- Substrate enforcement: agent's prompt instructs it to emit structured outputs (`required_outputs` field shape) rather than free-text; do not attempt to bypass CPS via prose.
- Audit-chain visibility: agent's prompt names that every output lands in the audit chain; agent SHOULD treat the audit chain as part of its operating environment and write accordingly (no off-chain side-channels).
- No substrate-level privilege: agent's prompt explicitly forbids tool-use beyond declared tools; if the agent identifies an action that requires substrate-level privilege, it surfaces the action as a structured proposal in its outputs and returns control to the operator.

### Refusal contract

A BAO MUST refuse (via structured-error path) when:

- It's asked to perform actions outside its surface scope (`error: scope_violation`)
- It's asked to bypass CPS or anti-pattern enforcement (`error: substrate_enforcement_bypass_requested`)
- It's asked to mutate state outside its permitted_sections (`error: out_of_scope_mutation`, also caught by deterministic substrate enforcement)
- It's asked to escalate authority (`error: privilege_escalation_requested`)

The refusal lands in the audit chain like any other structured error, with the operator-fix path being "rescope the task" or "dispatch a different agent."

## Substrate validation

A future substrate primitive MAY add a `_validate_bao_instance(agent_name)` check that verifies an agent's frontmatter declares `bao_pattern: true`, has `tools` restricted to read-only set, has `contract_class: read-only`, and references the four bounds in its prompt. Not implemented in v3.0-alpha.1; recommended for v3.0-alpha.2 or later if BAO instances multiply.

For v3.0-alpha.1, the validation is operator-discipline: every BAO instance is hand-reviewed to confirm the four bounds are honored. The first instance (generalized synthesist) is the reference implementation.

## First instance: generalized synthesist (v3.0-alpha.1)

The `synthesist` agent extended to `generalized` mode is the first concrete BAO instance. It reconciles N parallel input streams (instead of the existing two-stream reviewer+critic reconciliation) over the **synthesis surface**.

- Surface scope: synthesis only. Does not propose changes to subject code, ADRs, or other surfaces.
- Substrate enforcement: subject to `required_outputs` per its mode; subject to CPS structured-error veto.
- Audit-chain visibility: every synthesis output appended to the audit chain via the dispatching task.
- No substrate-level privilege: read-only tools; no direct state mutation.

See [.claude/agents/synthesist.md](../../.claude/agents/synthesist.md) for the full contract.

## Future instances (planned)

| Instance | Surface | Release |
|---|---|---|
| Generalized synthesist | synthesis | v3.0-alpha.1 (THIS RELEASE) |
| MAREP-Orchestrator | retro | v3.0-alpha.2 |
| Phase-exit retro finalizer | phase-exit-deliberation | v3.0 (final) |
| Verification-ritual-llm (mode: cat-9-judge) | verification | v2.8.0 — RETROACTIVELY a BAO instance (predates the named pattern; satisfies all four bounds; classify under bao_pattern in v3.0 frontmatter sweep) |
| FNSR moral-person deliberative coordinator | (eventual deliberation surface) | future |

## FNSR-relevance

The BAO pattern is the substrate's answer to a recurring requirement: **normative apparatus often needs elevated-authority coordination without elevated-substrate-privilege**. A retrospective needs an orchestrator with authority over the retro surface; a synthesis needs an agent with authority over the synthesis surface; eventually, a moral deliberation will need a coordinator with authority over the deliberation surface. In every case, the substrate's existing audit-chain + CPS + permitted_sections enforcement must hold.

Naive "give the LLM elevated permissions" patterns fail this property — they make the LLM's decisions opaque to the audit chain, or let the LLM bypass substrate safety, or extend scope beyond what the operator can review. The BAO pattern's four bounds prevent all four failure modes simultaneously.

The synthetic moral person project will require this exact shape at every level where moral judgment requires coordinator-style authority over a deliberation. The BAO pattern in v3.0-alpha.1 establishes the substrate-side precedent; later FNSR work adopts it.

## Provenance

- MAREP v2.2 §4.1 + §4.1.1 (BAO Bounds) — `ariadne/archive/specs/MAREP-v2.2/MAREP_v2.2.md`
- MAREP_INTEGRATION_SPEC §11 (BAO pattern formalization) — `ariadne/archive/specs/MAREP-v2.2/MAREP_INTEGRATION_SPEC.md`
- Aaron's CP3 adjudication confirming the pattern name and the four-bounds requirement (turn record in retrospective archive)
