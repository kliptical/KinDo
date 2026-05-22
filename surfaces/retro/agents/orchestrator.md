---
role: "@Orchestrator"
agent_file: .claude/agents/marep-orchestrator.md
bao_pattern: true
bao_surface: retro
permitted_sections:
  - retro.phase
  - issues
  - actions
  - decisions
  - votes
  - conflict_record
  - audit
status: v3.0-alpha.2 (agent contract authored; end-to-end dispatch testing lands v3.0 final)
canonical_reference: ariadne/archive/specs/MAREP-v2.2/MAREP_v2.2.md §4.1
---

# `@Orchestrator` — retro-surface BAO role binding

First Bounded-Authority Orchestrator instance for the retro surface per MAREP v2.2 §4.1. The full agent contract lives at [.claude/agents/marep-orchestrator.md](../../../.claude/agents/marep-orchestrator.md) (v3.0-alpha.2).

The agent operates in four modes (selected via `inputs.mode`):

- `phase-transition` — proposes advancing the retro to the next phase
- `conflict-detection` — surfaces unresolved disagreements with structured positions
- `consensus-summary` — synthesizes confirmed/rejected/contested outcomes
- `final-compression` — generates Phase 6 deliverables + Episodic→Semantic promotion candidates

See [surfaces/_primitives/bounded-authority-orchestrator.md](../../_primitives/bounded-authority-orchestrator.md) for the substrate primitive's four bounds. The Orchestrator MUST honor all four. The agent's frontmatter declares `bao_pattern: true` + `bao_surface: retro` + `contract_class: read-only`; cross-instance validation via `TestBaoBoundsValidation` enforces conformance.

## Permitted sections (default; per-retro AGENTS.md may override)

The Orchestrator has broad write authority across the retro state — it advances phases, merges findings, resolves conflicts, triggers votes, finalizes decisions. Per the BAO pattern, this elevated scope is bounded by:

- Surface scope: retro surface only (cross-surface action via `cross_surface_proposals[]`)
- Substrate enforcement: CPS check + anti-pattern detection apply to every output
- Audit-chain visibility: every Orchestrator decision lands in `audit[]`
- No substrate-level privilege: cannot bypass dispatch, cannot mutate state outside `permitted_sections`, cannot write to RETRO_STATE.jsonld directly (mutations flow through `retro-applier`)
