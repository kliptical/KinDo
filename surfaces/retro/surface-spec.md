---
surface_id: retro
question_scope: "What disciplined deliberation about a recent body of work surfaces the issues, decisions, and actions worth preserving — without conversational drift?"
audit_trail_unity: "One RETRO_STATE.jsonld per retro instance, chain-hashed, append-only. Sub-surfaces (consumer-closure-path vs internal-methodology-refinement per Spec 07) handle distinct audience semantics."
agents_path: surfaces/retro/agents/
phases_path: surfaces/retro/phases/
canonical_reference: ariadne/archive/specs/MAREP-v2.2/MAREP_v2.2.md
status: v3.0-alpha.1 (foundation only; full MAREP integration completes at v3.0)
---

# Retro Surface — surface specification

Per FNSR Spec 01's surface-registry pattern, the retro surface answers: **what disciplined deliberation about a recent body of work surfaces the issues, decisions, and actions worth preserving — without conversational drift?**

This is the second explicit surface registered under `surfaces/` (after `verification/` in v2.8.0). It instantiates MAREP v2.2 per `ariadne/archive/specs/MAREP-v2.2/MAREP_v2.2.md`.

## Audit-trail unity within this surface

Per MAREP v2.2 §7 + §16, retro state is canonical at `RETRO_STATE.jsonld` (one file per retro instance), chain-hashed via the substrate's `hiri_sign` mechanism, append-only. The `RETRO_STATE.jsonld` is the audit instance for that retro; subsequent references to the retro's findings/actions/decisions cite the retro's state, not the per-agent contributions in isolation.

When sub-surface distinctions matter (per Spec 07's Forward-Track Surface pattern), retros emit forward-track events with `sub_surface: consumer-closure-path | internal-methodology-refinement` rather than conflating audience-distinct outputs into a single artifact.

## Phases

Each phase is specified per-file under `surfaces/retro/phases/`. Per MAREP v2.2 §12, the canonical six phases:

| File | Phase | Entry → Exit summary |
|---|---|---|
| `01-gathering.md` | Independent Gathering | AGENTS.md finalized → every agent has submitted or declined |
| `02-merge.md` | Canonical Merge | Phase 1 done → no duplicate @ids; every issue schema-conformant |
| `03-analysis.md` | Structured Analysis | Phase 2 done → every issue confirmed/rejected/contested |
| `04-consensus.md` | Consensus Resolution | Phase 3 done → no issues remain contested |
| `05-actions.md` | Action Assignment | Phase 4 done → every confirmed issue has accepted action OR no_action_required decision |
| `06-compression.md` | Final Compression | Phase 5 done → all deliverables produced per MAREP §19 |

Phase ordering is operator-declared via the MAREP-Orchestrator's phase-transition dispatches. The filename `NN-` prefix is canonical-ordering-for-display only; the substrate doesn't enforce ordering via filenames.

Phase spec files are STUBS in v3.0-alpha.1; full per-phase entry/exit + permitted_sections specifications complete at v3.0-alpha.2 alongside the MAREP-Orchestrator dispatch.

## Agents (role bindings)

Per MAREP v2.2 §4.2 + §6.1, role bindings declare the agent file + mode + permitted_sections per role. Surface defaults live under `surfaces/retro/agents/<role>.md`; per-retro `AGENTS.md` overrides as needed.

| File | Role | Substrate agent | BAO? |
|---|---|---|---|
| `agents/orchestrator.md` | `@Orchestrator` | (TBD; v3.0-alpha.2) | YES |
| `agents/architect.md` | `@Architect` | `.claude/agents/architect.md` mode: review | no |
| `agents/developer.md` | `@Developer` | `.claude/agents/developer.md` | no |
| `agents/qa.md` | `@QA` | NEW v3.0-alpha.2 | no |
| `agents/delivery-manager.md` | `@DeliveryManager` | NEW v3.0-alpha.2 | no |
| `agents/risk-analyst.md` | `@RiskAnalyst` | NEW v3.0-alpha.2 | no |
| `agents/user-advocate.md` | `@UserAdvocate` | `.claude/agents/ux-sme.md` | no |
| `agents/skeptic.md` | `@Skeptic` | `.claude/agents/adversarial-critic.md` mode: review-second-pass | no |

Role bindings are STUBS in v3.0-alpha.1; the full per-role permitted_sections + mode specifications complete at v3.0-alpha.2.

## Substrate primitives this surface uses

- **Bounded-Authority Orchestrator (BAO)** — see `surfaces/_primitives/bounded-authority-orchestrator.md`. The `@Orchestrator` role is a BAO instance over the retro surface.
- **Three-stage permitted_sections enforcement** — per MAREP v2.2 §10.2 + MAREP_INTEGRATION_SPEC §5. Substrate-deterministic validation; LLM never makes authority decisions.
- **Forward-Track Surface (Spec 07)** — for Episodic→Semantic promotion path (deliberate, not automatic). The retro's outputs that warrant promotion to substrate canon (CLAUDE.md, ADRs, PLAYBOOK) emit forward-track events with `subject.type: candidacy`; promotion deliberation happens at phase-exit retro via the normal architect ratification + commit-finalize chain.

## What's in v3.0-alpha.1 (this release) vs later checkpoints

This release ships the **foundation only**: directory structure, surface-spec.md (this file), phase + role stub files, and the substrate-side loader for retro role bindings. It does not ship:

- Per-retro `AGENTS.md` schema/template (v3.0-alpha.2)
- MAREP-Orchestrator BAO agent (v3.0-alpha.2)
- Three new analytical agents `@QA`, `@DeliveryManager`, `@RiskAnalyst` (v3.0-alpha.2)
- Retro-applier system agent (v3.0-alpha.2)
- Anti-pattern CPS checks per MAREP §17 (v3.0-alpha.2)
- `state_admin retro` subcommand family (v3.0 final)
- Episodic→Semantic promotion machinery (v3.0 final)

See `ariadne/archive/specs/MAREP-v2.2/MAREP_INTEGRATION_SPEC.md` §17 for the full three-checkpoint plan.

## Loader

The substrate's `_load_retro_role_bindings()` (v3.0-alpha.1, fnsr_daemon.py) loads every `agents/<role>.md` under `surfaces/retro/agents/`. Same parser as `_parse_category_frontmatter` from the verification surface; the surface-registry primitive's reuse-without-modification property holds.

`_load_retro_phase_specs()` (v3.0-alpha.1) loads every `phases/<phase>.md`. Same pattern.

Both loaders return empty list when their respective directories don't exist (graceful degradation; substrate is back-compat with pre-v3.0 state).

## FNSR-relevance

The retro surface is where the substrate operates **deliberative reflection** at machine speed. After v2.8.0's verification-as-substrate move enabled evidence-gated change, the retro surface adds disciplined reflection on completed work: what worked, what didn't, what discipline emerged, what should promote to canon.

This pair — evidence-gated change (Pass 2a/2b chain) + deliberative reflection (MAREP retros) — is the architecture's complete operating cycle. The synthetic moral person project will require both: forward-acting normative apparatus and backward-reviewing deliberative apparatus. v3.0 establishes the substrate-side precedent for both.
