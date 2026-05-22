# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## v3.0-alpha.2 — MAREP substrate primitives + Episodic→Semantic promotion + anti-pattern enforcement framework

Second checkpoint of v3.0. Six deliverables per the MAREP-on-Barcode integration spec §17, with four implementation-pattern observations from Aaron folded in. **42 new tests; full suite 411 (was 369 at v3.0-alpha.1).**

### Added — substrate primitives (second instance of pattern-conformance discipline)

- **Episodic→Semantic Promotion** substrate-primitive doc at [surfaces/_primitives/episodic-to-semantic-promotion.md](surfaces/_primitives/episodic-to-semantic-promotion.md). The second substrate-primitive document (after BAO in v3.0-alpha.1). Per Aaron's CP2 observation #3: framed as **substrate-wide promotion pattern** that MAREP-retro is one instance of, NOT as MAREP-specific operator workflow. Documents the three memory layers (working / episodic / semantic), the two promotion boundaries, why deliberate-never-automatic, and the five surfaces where the pattern instantiates (retro, verification, banking lifecycle, forward-track, substrate primitives themselves).

- **Anti-pattern enforcement framework** in `fnsr_daemon.py` (CP3 substrate-primitive doc will anchor on this section per Aaron's CP2 observation #2). Four generalizable patterns implemented:
  - `_check_no_persona_theater` — rejects `@<agent>` patterns outside designated reference fields (`confirmed_by`, `contested_by`, `owner`, `supporting_sources`, `dissenting_sources`)
  - `_check_no_redundant_affirmation` — Levenshtein-similarity-based rejection of substantive overlap with prior turn outputs (threshold configurable; default 0.85)
  - `_check_no_freeform_brainstorm` — length-budget enforcement + forbidden-conversational-connectives scan
  - `_section_pattern_matches` — JSONPath-subset matcher (formal subset per MAREP_INTEGRATION_SPEC §5.2; deterministic; substrate-vs-procedure pattern applied to scope authorization)
  - Plus retro-surface scoping via `_is_retro_surface_task` (explicit `inputs.surface: retro` attribution; the anti-pattern checks fire only on retro-surface tasks per MAREP_INTEGRATION_SPEC §7.5)
  - Plus length-budget frontmatter syntax: agents declare `length_budgets: {path: max_chars}` and `conversational_connectives_forbidden: [...]` in frontmatter; substrate parses via `_agent_anti_pattern_config`

### Added — three analytical agents (read-only-by-contract pattern instances)

- **`@QA`** ([.claude/agents/qa.md](.claude/agents/qa.md)) — Quality/verification perspective. Test coverage gaps, regression patterns, defect distribution, verification-scope drift, test-infrastructure friction.
- **`@DeliveryManager`** ([.claude/agents/delivery-manager.md](.claude/agents/delivery-manager.md)) — Sprint cadence and coordination. Predictability, throughput, blockers, coordination overhead, dependency thrash.
- **`@RiskAnalyst`** ([.claude/agents/risk-analyst.md](.claude/agents/risk-analyst.md)) — Latent risk surfacing. Hidden failure modes, systemic fragility, operational exposure, coupling brittleness, single-point-of-failure observations. Distinct from `@Skeptic` (which challenges existing findings); `@RiskAnalyst` surfaces risks that didn't fire this sprint but will under named trigger conditions.

All three follow the read-only-by-contract pattern (third / fourth / fifth substrate instances after reconnaissance, verification-ritual-llm, adversarial-critic, synthesist). Each declares `length_budgets` + frontmatter consistent with the anti-pattern enforcement framework. Plus retro-surface role binding stubs under `surfaces/retro/agents/`.

### Added — `retro-applier` system agent

[.claude/agents/retro-applier.md](.claude/agents/retro-applier.md) + `_retro_apply` in fnsr_daemon.py. Deterministic merger of analytical-agent proposals into RETRO_STATE.jsonld. Per MAREP_INTEGRATION_SPEC §8:

- Inputs: `retro_state_path`, `proposals` dict keyed by source-task @id, `version_read` (CAS check), `surface: retro`
- Outputs: `applied`, `failed`, `retro_state_version`, `summary`
- CAS semantics per MAREP v2.2 §9: rejects on version_mismatch
- Idempotent via @id key: re-applying a proposal with an existing @id is a no-op
- Single audit-chain entry per dispatch (atomic mutation across all proposals)
- Reuses substrate v2.8.0 hash-chain via `hiri_sign`

Analog to v2.6.0 `applier` for code changes; scoped to retro state instead of filesystem.

### Added — `state_admin phase-complete-declaration` operator surface

Per Aaron's CP2 observation #4: **operator-authoritative**, NOT predicate-derived. The future automation hook (AC-pass rollup via test-runner or similar) remains future work. CP2 ships only the operator-declared event mechanism. Audit entries carry `declaration_kind: operator_authoritative` so future operators (and the eventual automation hook) can distinguish operator-declared from predicate-derived events.

CLI shape: `state_admin phase-complete-declaration <phase> --anchor-task <id> --rationale "<...>" [--acceptance-criteria-met ...] [--acceptance-criteria-pending ...]`. Rationale is required (recorded in audit chain); empty/whitespace rationale refused.

The three phase-related commands (phase-complete-declaration, phase-boundary, forward-track inherit) are deliberately separate — the operator may declare phase-complete without immediately transitioning the boundary (e.g., to allow phase-exit retro deliberation first per the E→S promotion discipline).

### Added — MAREP-Orchestrator BAO agent contract

[.claude/agents/marep-orchestrator.md](.claude/agents/marep-orchestrator.md) — first retro-surface BAO instance per MAREP v2.2 §4.1. Four-mode multi-mode contract:

- `phase-transition` — proposes advancing the retro to the next phase
- `conflict-detection` — surfaces unresolved disagreements with structured positions
- `consensus-summary` — synthesizes confirmed/rejected/contested outcomes
- `final-compression` — generates Phase 6 deliverables + Episodic→Semantic promotion candidates

Each mode declares its `required_outputs` + `length_budgets` per the anti-pattern enforcement framework. Honors all four BAO bounds. End-to-end LLM dispatch testing lands at v3.0 final; CP2 ships the contract surface (validated by `TestBaoBoundsValidation` from v3.0-alpha.1).

### Added — `TestReadOnlyContractValidation` (corpus-wide pattern conformance)

Per Aaron's CP2 observation #1: the substrate's pattern-conformance discipline extended to the read-only-by-contract pattern. `TestReadOnlyContractValidation` walks all agents declaring `contract_class: read-only` and validates:

- No `Edit` / `Write` / `Bash` tools (read-only invariant)
- `required_outputs` declared (CPS-enforceable contract surface)
- Refusal contract documented in prompt (operator-discoverable error envelope)

This is the second cross-instance pattern-conformance test (after CP1's `TestBaoBoundsValidation`). The substrate now mechanically validates conformance to **two** architectural patterns across the agent corpus.

**The test caught a real gap during CP2 development:** verification-ritual-llm (shipped in v2.8.0-alpha.3) lacked a documented refusal contract. The test surfaced it; CP2 added the missing section. This is the pattern-conformance discipline working as designed — substrate self-validates during development, not just at release time.

### Changed

- CLAUDE.md §3 Agent Roster: marep-orchestrator + qa + delivery-manager + risk-analyst + retro-applier added.
- CLAUDE.md §10 Key Files: state_admin.py row enumerates v3.0-alpha.2 phase-complete-declaration subcommand.
- surfaces/retro/agents/ gains 3 new role binding stubs (qa, delivery-manager, risk-analyst); orchestrator stub upgraded to point at the v3.0-alpha.2 agent contract.
- v3.0-alpha.1 `TestRetroSurfaceFoundation.test_role_bindings_load` updated for the new role count (8 total, up from 5).
- Template-sync default manifest extended with 18 new v3.0-alpha.2 files. **Third ouroboros instance**: v3.0-alpha.2 shipped using v2.9.0's `template-sync` command + v2.9.0's `test-runner` validation of the substrate's own test suite.

### Substrate self-documentation continues to scale

v3.0-alpha.1 introduced `surfaces/_primitives/` directory convention + `TestBaoBoundsValidation` cross-instance validation. v3.0-alpha.2 extends both:

- `surfaces/_primitives/` gains its second primitive doc (Episodic→Semantic)
- Pattern-conformance validation extends to a second pattern (read-only-by-contract)

Two patterns documented as substrate primitives + two cross-instance validation tests means the substrate now tracks four invariants mechanically: BAO surface scope, BAO substrate enforcement, BAO audit visibility, BAO no-privilege; plus read-only tools, required_outputs, refusal-contract docs. Future patterns inherit the same discipline.

### What's still pending for v3.0 final

- Phase-exit retro end-to-end (operator chain: gathering → merge → analysis → consensus → actions → compression, dispatching marep-orchestrator at each transition)
- `state_admin retro` subcommand family (init / phase-transition / vote / archive / verify / list)
- Episodic→Semantic promotion path operationalized end-to-end
- Substrate-mechanical anti-pattern enforcement framework formalized as the third substrate-primitive doc (anchoring on the fnsr_daemon.py section established in CP2)
- Final docs sweep + v3.0 tag + alpha series retires

## v3.0-alpha.1 — First checkpoint of v3.0: BAO pattern formalization + generalized synthesist + retro surface foundation

First checkpoint of v3.0 per the MAREP-on-Barcode integration spec (`ariadne/archive/specs/MAREP-v2.2/MAREP_INTEGRATION_SPEC.md` §17). Establishes the foundation for v3.0's two architectural moves: deliberative reflection (MAREP retros) operating alongside evidence-gated change (v2.8.0's Pass 2a/2b chain), and the **Bounded-Authority Orchestrator (BAO) substrate primitive** as a reusable pattern for elevated-authority LLM agents.

24 new tests; full suite 369 (was 345 at v2.9.0). Three CP1 deliverables shipped as one bundle (the deliverables are interdependent — BAO doc is referenced by synthesist + retro surface; retro surface references both).

### Added

- **BAO substrate primitive doc** at [surfaces/_primitives/bounded-authority-orchestrator.md](surfaces/_primitives/bounded-authority-orchestrator.md). Specifies the four bounding properties every BAO instance MUST satisfy:
  1. Surface scope (elevated authority limited to assigned surface)
  2. Substrate enforcement (CPS + permitted_sections + anti-pattern detection apply)
  3. Audit-chain visibility (every decision lands in chain via normal dispatch)
  4. No substrate-level privilege (worker agent; cannot bypass dispatch/lock/state)

  Per Aaron's CP3 adjudication, the four bounds are non-negotiable; readings of "bounded-authority" that omit any of them risk under-specifying the contract. The primitive doc is the substrate's canonical reference; future BAO instances cite it.

  New directory `surfaces/_primitives/` for substrate-primitive documentation (cross-surface patterns; distinct from surface-specific specs under `surfaces/<surface>/`).

- **`surfaces/retro/` foundation** — second explicit surface registered under `surfaces/` (after `verification/` in v2.8.0). Contains:
  - `surface-spec.md` documenting the retro-surface generalized layer + sub-surface relationship to FNSR Spec 07 forward-tracks
  - 5 role binding stubs under `agents/`: `@Orchestrator` (BAO; full agent in v3.0-alpha.2), `@Architect`, `@Developer`, `@UserAdvocate`, `@Skeptic` (existing substrate agents mapped to retro roles)
  - 6 phase spec stubs under `phases/`: Independent Gathering through Final Compression per MAREP v2.2 §12
  - Three new analytical agents (`@QA`, `@DeliveryManager`, `@RiskAnalyst`) land in v3.0-alpha.2

- **`generalized` mode added to synthesist** (`.claude/agents/synthesist.md`). The **first concrete BAO instance**. Reconciles N parallel input streams over the synthesis surface (vs the existing two-stream `classic` reviewer+critic synthesis). New required_outputs: `synthesized_findings`, `conflicts`, `recommendation`, `source_provenance`, `summary`. Cross-surface proposals surfaced via `cross_surface_proposals[]` field — does NOT mutate other surfaces directly (BAO bound #1).

  `classic` mode preserved as `default_mode` for back-compat with existing v2.5.0+ dispatch tasks. Multi-mode `required_outputs` mechanism (v2.7.0+) + `default_mode` field (v2.8.0-alpha.3) make the extension additive.

- **Daemon-side retro-surface loaders** (`fnsr_daemon.py`):
  - `_load_retro_role_bindings(surface="retro")` parses `surfaces/<surface>/agents/<role>.md` files into role→binding dict
  - `_load_retro_phase_specs(surface="retro")` parses `surfaces/<surface>/phases/<phase>.md` files into ordered list
  - Both gracefully degrade when their respective directories don't exist (substrate stays back-compat with subject projects that don't use retros)
  - Reuse the verification-surface category loader pattern unchanged — the Spec 01 surface-registry primitive's reuse-without-modification property holds

- **24 new unit tests** in `tests/test_retro_surface_foundation.py`. Coverage:
  - BAO substrate-primitive doc presence + four-bounds declaration + frontmatter
  - Retro role bindings loader (5 expected roles; orchestrator marked as BAO; others not)
  - Retro phase specs loader (6 phases in canonical order; entry/exit criteria present)
  - Graceful degradation when directory absent
  - Multi-mode synthesist (classic default + generalized + CPS enforcement of both modes' required_outputs)
  - Cross-instance BAO bounds validation: every agent declaring `bao_pattern: true` MUST have `bao_surface`, `contract_class: read-only`, read-only tools (no Edit/Write/Bash), and reference the primitive doc

### Changed

- `state_admin template-sync` default manifest extended with the 14 new v3.0-alpha.1 files. Verified end-to-end: v3.0-alpha.1 itself shipped using the v2.9.0 template-sync command (the substrate's own ouroboros tooling pattern, second instance).

### BAO pattern instances (substrate-wide)

| Instance | Surface | First shipped |
|---|---|---|
| Generalized synthesist | synthesis | v3.0-alpha.1 (THIS RELEASE) |
| MAREP-Orchestrator | retro | v3.0-alpha.2 |
| Phase-exit retro finalizer | phase-exit-deliberation | v3.0 (final) |
| Verification-ritual-llm (cat-9-judge mode) | verification | Retroactively classified (v2.8.0; predates the named pattern but satisfies all four bounds) |
| FNSR moral-person deliberative coordinator | (eventual deliberation surface) | future |

### FNSR-relevance

The BAO pattern is the substrate's answer to "normative apparatus often needs elevated-authority coordination without elevated-substrate-privilege." A naive "give the LLM permissions" approach fails because it loses one or more of the four bounds. The BAO pattern preserves all four simultaneously; the synthetic moral person project will adopt this pattern at every level where moral judgment requires coordinator-style authority over a deliberation.

The retro surface establishes the second canonical surface (after verification). After v3.0 final ships, the substrate operates two complete deliberative cycles: evidence-gated change (Pass 2a/2b) and reflective deliberation (MAREP retros). Both under the same architecture pattern.

### What's still pending for v3.0

- **v3.0-alpha.2**: MAREP substrate primitives (retro-applier system agent; three new analytical agents `@QA`, `@DeliveryManager`, `@RiskAnalyst`; three anti-pattern CPS checks; length-budget frontmatter syntax; phase-complete-declaration operator surface)
- **v3.0 (final)**: phase-exit retro end-to-end; `state_admin retro` subcommand family; Episodic→Semantic promotion path; final docs sweep; v3.0 tag (alpha series retires)

## v2.9.0 — Operator workflow tools: test-runner + template-sync + git-committer

Lead-in release between v2.8.0 (verification-as-substrate) and v3.0 (MAREP integration + generalized synthesist + phase-exit retro). Ships three substrate-side operator workflow primitives that have been deferred since v2.7.0 planning, completing the subject-work tooling surface before v3.0's larger architectural moves.

**51 new tests across three deliverables; full suite 345 (was 294 at v2.8.0).** Single checkpoint, single tag. The three deliverables are independent; each lands as its own commit in the release for clearer audit history.

### Added

- **`test-runner` system agent** ([.claude/agents/test-runner.md](.claude/agents/test-runner.md); 19 new tests). Runs the configured test suite via subprocess; returns structured `passed`/`failed`/`skipped`/`total`/`status`/`first_n_failures`/`raw_stdout_tail`/`exit_code`. Subject-project-agnostic — test command via `FNSR_TEST_RUNNER_CMD` env var or `inputs.cmd` task input. Built-in parsers: `python_unittest`, `npm`, `raw` fallback. Auto-detected from command string; explicit override via `inputs.parser`. Configurable timeout (default 300s via `FNSR_TEST_RUNNER_TIMEOUT_S`). Per the v2.9.0 self-validation: test-runner runs the substrate's own test suite and correctly reports 345/0/345.
- **`state_admin template-sync` subcommand** (12 new tests). Automates the dual-track-workflow manifest's "files that must stay identical across all three repos" sync step. Two modes: `verify` (report drift only) and `sync` (copy source → targets then verify). Manifest configurable via `--manifest <path>` flag or `FNSR_TEMPLATE_SYNC_MANIFEST` env var; default is the substrate-shared file list (currently 92 files). Multiple targets supported via comma-separated `--targets`. Idempotent: second-run-on-clean-state exits 0. Replaces ad-hoc `cp -f` operator commands with a deterministic + verifiable workflow.
- **`git-committer` system agent** ([.claude/agents/git-committer.md](.claude/agents/git-committer.md); 20 new tests). **First substrate agent with externally-visible side effects** — a commit lands in a repository that other systems (remotes, CI, collaborators) can see. Per Aaron's adjudication, safety-by-default with explicit-opt-in bypass:
  - Default refuses dirty working tree (changes outside operator-specified `paths`)
  - Default refuses commits to branches in `protected_branches` (default: main, master; configurable via `FNSR_PROTECTED_BRANCHES` env var)
  - Default refuses bypass-hooks
  - Each can be overridden via `allow_dirty`, `allow_protected_branch`, `allow_bypass_hooks` flags PAIRED with required `bypass_reason` recorded in audit chain. Every bypass becomes a citable audit event.
  - Two-class failure discrimination (per Aaron's CP4 adjudication): `hook_failure` (pre-commit hook rejected; operator fixes code) vs `git_command_failure` (git itself rejected for non-hook reason; operator fixes substrate/environment). Both under `unresolved_predicate` miss class; `evidence.reason` discriminates downstream tooling filtering.
  - Multi-line commit messages preserved via stdin (HEREDOC-safe; no shell escaping).
  - Does NOT push. Push is a separate operator action; intentionally keeps the externally-visible cross-system step under explicit operator control.

### Changed

- CLAUDE.md §3 Agent Roster — `test-runner` and `git-committer` added.
- CLAUDE.md §10 Key Files — `state_admin.py` row enumerates v2.9.0 `template-sync` subcommand.
- PLAYBOOK.md §1 gains three new failure-mode entries (test-runner unresolvable command; git-committer refused_unsafe_commit; git-committer hook_failure vs git_command_failure discrimination).
- PLAYBOOK.md gains §4.10 ("Operator-review-before-queuing for external-side-effect agents") — the pattern established by `git-committer` for the substrate's first externally-visible-side-effect agent; documents the discipline for future external-side-effect agents (git-pusher, email-sender, api-caller, webhook-emitter) and the FNSR-relevant precedent for normative apparatus that produces external effects.

### Substrate primitive: external-side-effect agent pattern (FNSR-relevant)

`git-committer` establishes the substrate's pattern for agents that act unrecoverably in the world:

1. **Default refuse under judgment conditions.** Safety-critical defaults (`allow_dirty: false`, `allow_protected_branch: false`, `allow_bypass_hooks: false`) push toward conservative refusals.
2. **Opt-in bypass requires explicit operator flag + bypass_reason.** Every bypass becomes a citable audit event recording operator intent at the moment of override.
3. **No auto-chaining to further external operations.** `git-committer` does not push; future external-side-effect agents do not auto-chain to subsequent external steps. Each externally-visible step is its own dispatched agent under separate operator review.
4. **Operator-review-before-queuing pattern documented in PLAYBOOK** as substrate discipline for this class of agent.

The synthetic moral person project will eventually require normative apparatus that produces external effects (decisions communicated to stakeholders; commitments made; resources allocated). The pattern established here for `git-committer` is the substrate's precedent: external-side-effect agents are bounded by operator review, not just by substrate validation.

### Why v2.9.0 as a distinct lead-in release

The build order has v2.9.0 (test-runner + git-committer + template-sync) preceding v3.0 (MAREP integration + generalized synthesist + phase-exit retro). v2.9.0 is small enough to ship as a single checkpoint (~450 LOC + ~90 tests; came in at ~700 LOC + 51 tests). Shipping it distinctly clears subject-work tooling out of the way before v3.0's larger architectural moves, gives operators time to adopt the new tools (especially the `template-sync` and `git-committer` patterns) before v3.0's MAREP retros begin using them in operator chains.

After v2.9.0 ships, v3.0-alpha.1 starts against the integrated MAREP scope per the v3.0 specs filed to FNSR archive (`ariadne/archive/specs/MAREP-v2.2/`).

## v2.8.0 — Verification-as-substrate: full verification ritual + Pass 2a/2b chain

The substrate's biggest single-version delta in its history. v2.8.0 implements the verification-ritual surface per FNSR Protocol Spec 02, completes the Pass 2a / Pass 2b chain per Spec 03 with `commit-finalize` retiring the v2.7.0 operator-applier interim, ships the four-class miss taxonomy with operator-fix path discrimination, and adds the full forward-track operating surface (create / inherit / transition / list / aging) per Spec 07.

Shipped in four checkpoints (v2.8.0-alpha.1 through v2.8.0-alpha.3, finalized in this release). Each checkpoint preserved the green-suite invariant; gaps surfaced at each checkpoint were adjudicated and folded into the next before building on the foundation.

### What v2.8.0 means for the substrate

After v2.6.0 (substrate move: verbal discipline → audit events), v2.7.0 (discipline-pass move: reconnaissance + ratification chain), and now v2.8.0, the substrate is no longer a thin coordinator with discipline added on top. It's a substrate that operates **protocol depth at machine speed across the full Pass 2a/Pass 2b chain**, with deterministic-where-possible / LLM-where-necessary / adversarial-critic-where-LLM-judgment-changes-state, audit-chain-for-all-of-it.

This is the FNSR-relevant milestone. The synthetic moral person project requires substrates that operate normative depth at machine speed without losing audit-trail honesty. v2.8.0 demonstrates that's achievable in the verification surface; the architecture generalizes to other normative surfaces v2.9.0+ will introduce.

### Added — verification ritual (Cat 1–10)
- **`surfaces/verification/` directory layout** (Spec 01 surface-registry primitive). `surface-spec.md` + `categories/cat-NN-*.md` per ratified category. Future surfaces follow `surfaces/<surface>/<bucket-or-category>/` pattern.
- **Cat 1–7 deterministic predicates** (CP1). Structural lookups against frozen contracts: spec section existence, ADR cross-reference, Q-ruling cross-reference, reason-code frozen enum, FOL/OWL @type discriminator, manifest mirror consistency, cross-phase + cross-amendment cross-reference.
- **Cat 8 hybrid two-cadence** (CP2). Pre-routing structural (IRI/CURIE existence) + activation-time strict-equality with `needs_llm_judgment` deferral when artifact carries `semantic_equivalence_acceptable: {reason, scope}` structured flag.
- **Cat 9 LLM candidacy** (CP3). Cited-content consistency judging via `verification-ritual-llm` worker agent's `cat-9-judge` mode. Category-agnostic prompt: receives `citation_reference` + `citing_framing` + `canonical_content`; verdicts `consistent | inconsistent`. ADR-012 ghost (FNSR Spec 06) AND Q-4-Step5-A spec §3.4.1 case as parallel examples in the prompt — Cat 9 covers any STRUCTURAL-only lower category's semantic gap.
- **Cat 10 candidacy** (CP2). Subject-project-hook framework. Substrate ships `.md` spec + `.py` stub returning `not_implemented_for_this_subject_project`. Subject projects with type-field-structure discipline overlay the stub with a real parser (TypeScript interfaces, Rust traits, OWL constraints, etc.).
- **`verification-ritual` system agent** (CP1). Loads category specs at dispatch; runs deterministic categories; defers LLM categories via `overall_status: needs_llm_judgment`. Required outputs: `per_category_result`, `overall_status`, `new_candidacies`, `summary`.
- **`verification-ritual-llm` worker agent** (CP3). Second instance of the **read-only-by-contract agent pattern** (after `reconnaissance` v2.7.0). Two modes: `cat-9-judge` + `cat-8-semantic-equivalence`. Multi-mode `required_outputs`. Tools: Read/Grep/Glob.
- **`adversarial-critic` cat-9-second-pass mode** (CP3). Third instance of the read-only-by-contract pattern. Fires on Cat 9 **vetoes only** (verdicts that change downstream state); Cat 9 passes don't need second-pass. Verdict shape: `confirm_veto | dispute_veto | extend_veto`. Multi-mode `required_outputs` with `default_mode: review-second-pass` for back-compat with v2.5.0+ dispatches.

### Added — substrate primitives
- **`PredicateMetadata` dataclass** (CP2; Gap H). Typed substrate-supplied context (`self_path`, `task_id`, `cycle_id`, `phase_context`, `cadence`) threaded to every category predicate. Cat 7's `self_path` migrated out of canonical_sources namespace abuse into metadata.
- **Subject-project hook loader** (CP2; Gap F). Sibling `cat-NN-*.py` files alongside specs are auto-imported into per-surface sandbox namespace at `subject.<surface>.<module-name>`. Defensive: ImportError surfaces as `unresolved_predicate` miss with `details.import_error`. `_resolve_predicate` supports three qualified-name shapes.
- **`default_mode` frontmatter mechanism** (CP3). Multi-mode agents declare a default mode; daemon uses it when `task.inputs.mode` is absent. Preserves back-compat for single→multi-mode agent migrations.
- **`FNSR_SURFACES_DIR` env var** (CP1; default `./surfaces`). Operator can override surfaces directory location.
- **`FNSR_FORWARD_TRACK_AGING_THRESHOLD_PHASES` env var** (CP4; default 3). Tunable per subject-project phase cadence.

### Added — four-class miss taxonomy (v2.8.0-alpha.2 + alpha.3)

`per_category_result` miss entries carry `evidence.miss_class` discriminating four operator-fix paths:

| Miss class | Operator fix path |
|---|---|
| `malformed_spec` | edit / repair the cat-NN-*.md spec file |
| `unresolved_predicate` | fix the predicate code |
| `missing_canonical_source` | provide the canonical source(s) — `details.missing_canonical_source_keys` lists them |
| `categorical_coverage_miss` | phase-exit-retro deliberable territory (Cat 9 / Cat 10 candidacy surfacing class) |

Each class is independently filterable; downstream tooling selects the operator action type cleanly.

### Added — forward-track operating surface (CP4)
- **`state_admin forward-track transition`** — lifecycle A→B→C per Spec 07. State C requires `--resolution-path` (one of `ratified-into-spec`, `merged-into-roadmap-release`, `withdrawn`). Emits `forward_track_state_transition` audit event.
- **`state_admin forward-track list`** — query by `--sub-surface`, `--state`, `--phase` filters.
- **`state_admin forward-track aging`** — flag forward-tracks inherited through ≥ threshold phases without resolution. Aging warnings are themselves `forward_track_aging_warning` audit events (per Aaron's CP4 observation: warnings are audit-chain entries, not just CLI output; future operators can review aging history at phase boundaries).
- **`state_admin forward-track create --surfacing-task-id`** (CP3 refinement). Records the originating task — preserves audit-trail evidence for phase-exit-retro deliberation without manual chain-walking.

### Added — Pass 2a/2b chain canonical (CP4)
- **`commit-finalize` task type documented** as canonical Pass 2b consumer per FNSR Spec 03 + Aaron's Gap C adjudication. The substrate's `depends_on` graph carries the wiring; CPS enforces dispatch ordering. The architect's ratification ruling references the verification-ritual task @id in its `referenced_evidence` field.
- **Read-compat with v2.7.0 operator-applier chains preserved**. The audit chain's append-only invariant means v2.7.0 entries remain valid in v2.8.0 state files; new chains use the v2.8.0 shape; old chains continue to verify under `state_admin.py verify`.

### Changed
- CLAUDE.md gains §7.11 (Verification Ritual Surface). §3 Agent Roster lists `verification-ritual`, `verification-ritual-llm`; `adversarial-critic` row documents two-mode contract. §5 Validation and §10 Key Files updated.
- PLAYBOOK.md gains §4.9 (Verification ritual operator patterns), §4.7/4.8 (Pass 2a sequencing + phase-boundary workflows from v2.7.0). Four-miss-class operator-fix table documented; v2.7.0/v2.8.0 audit-chain-shape read-compat called out.
- Orchestrator's category-loop ordering: `missing_canonical_source` check moved BEFORE the LLM-deferral check. Cat 9 only defers when canonical sources are present; otherwise it misses with the appropriate class. Substrate principle going forward: an LLM category should defer only when it has the inputs to make a judgment.

### Tests
**90 new unit tests added across v2.8.0 (was 156 at v2.6.0; now 294)**:
- CP1: 48 (Cat 1–7 predicates + verification-ritual orchestration)
- CP2: 24 (Cat 8 + Cat 10 framework + miss taxonomy + subject hooks + PredicateMetadata)
- CP3: 15 (Cat 9 spec + verification-ritual-llm contract + adversarial-critic cat-9-second-pass + 4th miss class + --surfacing-task-id)
- CP4: 16 (forward-track transition + list + aging + env var + chain integrity)

Every daemon change kept the suite green at the per-checkpoint level. The v2.8.0 final suite is the union of all four checkpoint test sets.

### Gap surfacing cadence — pattern stable across four checkpoints
Each checkpoint surfaced gaps that the next checkpoint folded in:
- CP1 → Gap F (per-category .py hook loader), Gap G (three-class miss taxonomy), Gap H (PredicateMetadata)
- CP2 → Gap I (4th miss class: missing_canonical_source)
- CP3 → orchestrator-ordering catch (LLM categories shouldn't defer without inputs)
- CP4 → ready to ship

The build-incrementally pattern — surface gaps as substrate observations; triage blocking vs clarifying vs mechanical; fold adjudicated refinements additively — is now stable substrate process, not just per-release procedure.

### FNSR milestone — verification-as-substrate

v2.8.0 is the verification-as-substrate move. The substrate now operates the full Pass 2a/Pass 2b discipline at machine speed with auditable LLM-judgment fallback. The `adversarial-critic` cat-9-second-pass pattern is the architecture's precedent for non-deterministic-but-auditable normative judgment — the same shape that the synthetic moral person project's reasoning apparatus will need at every level where moral judgments fall outside rule-checking territory.

The build-order from v2.9.0+ extends the substrate (test-runner + git-committer + template-sync, then generalized synthesist + phase-exit-retro + phase-complete-declaration, then surface_audience) but doesn't change its fundamental nature. v2.8.0 is the change.

### Provenance
- FNSR Protocol Specifications v1.1 bundle (`project/Routing/00-README.md` and `01–07-*.md`); Logic-Team-reviewed.
- Aaron's CP1/CP2/CP3/CP4 adjudications (Gaps A–I); the gap-surfacing cadence is itself substrate process.

## v2.8.0-alpha.3 — Verification ritual Checkpoint 3: Cat 9 LLM judge + adversarial-critic second-pass + 4th miss class

Third checkpoint of v2.8.0. Adds the LLM side of the verification ritual per FNSR Spec 02 + Aaron's CP1 architectural call (two-agent split). Cat 9 (cited-content consistency) is the substrate's first non-deterministic verification category; the paired-verdict adversarial-critic second-pass mitigation makes its LLM judgment auditable rather than oracular. Plus Gap I — the fourth miss class — confirmed and split.

### Added
- **`MISS_MISSING_CANONICAL_SOURCE` 4th miss class** (Gap I post-CP2 adjudication). Each of the four miss classes has a distinct operator-fix path:
  - `malformed_spec` — operator fixes the spec file
  - `unresolved_predicate` — operator fixes the predicate code
  - `missing_canonical_source` — operator provides the canonical source (NEW)
  - `categorical_coverage_miss` — phase-exit retro deliberable territory
  Backward-compatible additive change; CP2 consumers using `unresolved_predicate.details.reason="missing_canonical_source"` keep working but the new constant is the canonical surface going forward.
- **`cat-09-cited-content-consistency.md` spec file**. Cat 9 candidacy per FNSR Spec 02 §"Cat 9 Candidacy". `implementation_mode: llm`; `llm_dispatcher_agent: verification-ritual-llm`; `llm_mode: cat-9-judge`; `canonical_source_keys: [spec, decisions]`. The deterministic `verification-ritual` system agent emits `status: deferred_llm` for Cat 9 entries when canonical sources are present (sets `overall_status: needs_llm_judgment`); operator queues `verification-ritual-llm` next.
- **`verification-ritual-llm` worker agent** at [.claude/agents/verification-ritual-llm.md](.claude/agents/verification-ritual-llm.md). **Second instance of the read-only-by-contract agent pattern** (after `reconnaissance` v2.7.0). Tools: Read/Grep/Glob. Two modes via multi-mode `required_outputs`:
  - `cat-9-judge` — judges cited-content consistency. Category-agnostic prompt template (per Aaron's CP3 observation 1): receives `citation_reference`, `citing_framing`, `canonical_content`; verdicts `consistent | inconsistent | requires_operator_decision`. Examples in the prompt include the ADR-012 ghost (ADR-registry flavor, Spec 06) AND Q-4-Step5-A Miss 1 (spec §3.4.1 flavor) as parallel cases.
  - `cat-8-semantic-equivalence` — judges semantic equivalence for Cat 8 activation-time deferrals when the artifact carries the `semantic_equivalence_acceptable: {reason, scope}` structured flag (Gap B refinement from CP2).
- **`adversarial-critic` agent extended with `cat-9-second-pass` mode** per FNSR Spec 02 §"Open questions" + Aaron's CP3 observation 2. **Third instance of the read-only-by-contract agent pattern.** Fires on Cat 9 **vetoes only** (verdicts that change downstream state); Cat 9 passes don't require second-pass since they don't uniquely change state. Output verdict shape: `confirm_veto | dispute_veto | extend_veto` per Cat 9 entry; overall verdict `vetoes_confirmed | vetoes_disputed | vetoes_extended`.
- **`default_mode` frontmatter field** for multi-mode agents. Daemon parses it and uses it when `task.inputs.mode` is absent — back-compat for tasks dispatching `adversarial-critic` without explicit mode (existing CP2-and-earlier dispatches keep working under the `review-second-pass` default). Added to the multi-mode `required_outputs` parser.
- **`state_admin forward-track create --surfacing-task-id`** (Aaron's CP3 observation 3). Optional field recording the task that surfaced a candidacy (e.g., the `verification-ritual-llm` task whose `new_candidacies` prompted the forward-track). Preserves audit-trail evidence for phase-exit-retro deliberation without requiring manual chain-walking. Backward-compatible: existing v2.7.0/v2.8.0-alpha.x forward-tracks without this field continue to work; v2.8.0 transition/list/aging will tolerate its absence.
- **15 new unit tests**. Full suite: 278 tests (was 263 at alpha.2).

### Changed
- Orchestrator's category-loop ordering: missing-canonical-source check now runs BEFORE the LLM-deferral check. Means an LLM-only category without its required sources emits `miss_class: missing_canonical_source`, not the deferral signal. The deferral only fires when there's content to judge — preserves `overall_status: pass` semantics for runs where Cat 9 wasn't applicable to the cases at hand.
- Cat 9 deferred-LLM entries now carry `evidence.llm_dispatcher_agent` and `evidence.llm_mode` fields so the operator's downstream task-queueing knows exactly which worker agent to dispatch with which mode.
- `_agent_required_outputs` gains the `default_mode` semantic for back-compat with single-mode → multi-mode agent migrations.
- CLAUDE.md §3 Agent Roster — `verification-ritual-llm` added; `adversarial-critic` row updated to document the two-mode operating contract.

### Architecture: Cat 9 as FNSR-relevant precedent
Cat 9 is where the substrate first leaves deterministic territory in a way the operator cannot unwind by reading code. Cat 1–7 deterministic predicates either pass or veto with a structural answer the operator can verify by hand. Cat 9 emits an LLM verdict that an operator can disagree with but can't re-derive deterministically.

The paired-verdict adversarial-critic second-pass exists for this reason: to make Cat 9's LLM judgment **auditable against itself** rather than treating it as oracular. The pattern is **FNSR-relevant infrastructure** beyond v2.8.0 — when the synthetic moral person substrate must make normative judgments that aren't deterministic (rule-checking failures, equity assessments, novel-case interpretations), the same pattern applies:
1. Don't pretend the LLM verdict is deterministic.
2. Make the verdict auditable via paired-verdict machinery.
3. Require second-pass for verdicts that change state.

The `adversarial-critic.md` `cat-9-second-pass` mode is the first concrete substrate implementation of this pattern. Future FNSR work draws on its shape.

### Operator workflow (v2.8.0-alpha.3 chain)
Substantive change with Cat 9 candidate references:
```
verification-ritual          (deterministic Cat 1-8, 10; deferred_llm for Cat 9)
    ↓
verification-ritual-llm      (LLM Cat 9 judge; may emit one or more vetoes)
    ↓ (only when ≥1 Cat 9 veto)
adversarial-critic mode:cat-9-second-pass   (confirm/dispute/extend the veto)
    ↓
operator decides: honor veto or override based on adversarial-critic verdict
```
If `verification-ritual-llm` emits `new_candidacies` (patterns no current category covers), operator runs `state_admin forward-track create --surfacing-task-id <verification-ritual-llm task @id> --subject-type candidacy --sub-surface internal-methodology-refinement ...` to track the candidacy through phase-exit retro deliberation.

### What's still pending for v2.8.0 final (CP4)
- Forward-track operating commands: `state_admin forward-track transition`, `list`, `aging` (matched-pair scope with the v2.8.0 verification-ritual agent per Aaron's directive).
- `commit-finalize` task type wired as Pass 2b consumer (CP3 ships only the documented surface; CP3's substrate doesn't dispatch commit-finalize anywhere specially — the v2.7.0 operator-applier interim continues until CP4 lands).
- Final v2.8.0 docs sweep (CLAUDE.md §7.x consolidation; PLAYBOOK.md verification-ritual operator patterns).
- v2.8.0 tag.

## v2.8.0-alpha.2 — Verification ritual Checkpoint 2: Cat 8 hybrid + Cat 10 hook framework + miss taxonomy

Second checkpoint of v2.8.0. Builds on alpha.1 foundation with three substrate changes (Gaps F, G, H adjudicated by Aaron post-CP1) plus Cat 8 / Cat 10 implementation per the spec bundle. Cat 9 LLM judge + new_candidacies operator-decision routing land in CP3.

### Added
- **`PredicateMetadata` dataclass** (Gap H). All Cat 1–7 (+ Cat 8) predicate signatures refactored to `(artifact, canonical_sources, metadata)`. The dataclass carries substrate-supplied context (`self_path`, `task_id`, `cycle_id`, `phase_context`, `cadence`); fields are optional and grow additively. Cat 7's `self_path` lookup migrated from the `canonical_sources["_artifact_self_path"]` namespace abuse into `metadata.self_path`. Backward-compatible fallback in the orchestrator for any predicate still on the legacy 2-arg signature (sunset at v2.8.0 final).
- **Three-class miss taxonomy** (Gap G). `per_category_result` miss entries now carry an `evidence.miss_class` field:
  - `malformed_spec` — category spec file invalid (no frontmatter, missing `category_id`, read failure). Emitted instead of silent-skip per Aaron's audit-trail-honesty adjudication.
  - `unresolved_predicate` — spec valid but predicate doesn't resolve (substrate default missing, subject-project hook missing/failed-to-import, or required canonical source absent — bucketed here in CP2 with details.reason discrimination; Gap I observation for post-CP2 if 4th class warrants splitting).
  - `categorical_coverage_miss` — spec ran and predicate emitted miss because the case falls in known-uncovered territory (Cat 9 / Cat 10 candidacy surfacing class; phase-exit-retro deliberable).
  Constants exposed: `fnsr_daemon.MISS_MALFORMED_SPEC`, `MISS_UNRESOLVED_PREDICATE`, `MISS_CATEGORICAL_COVERAGE`.
- **Subject-project hook loader** (Gap F). Sibling `cat-NN-*.py` files alongside `cat-NN-*.md` specs are auto-imported into a per-surface sandbox namespace at `subject.<surface>.<module-name>`. Defensive: ImportError records the failure; subsequent `_resolve_predicate` calls for that name emit `unresolved_predicate` miss with `details.import_error`. The `_resolve_predicate` extension supports three qualified-name shapes:
  - `fnsr_daemon.<func>` — substrate default
  - `subject.<surface>.<module>` — co-located .py file; function name == module name
  - `subject.<surface>.<module>.<func>` — explicit function name
- **`cat-08-multi-canonical-source.md` + `cat_08_multi_canonical_source` predicate**. Hybrid two-cadence per Spec 02 §"Cat 8". Pre-routing cadence is deterministic (IRI/CURIE existence check against vendored `iri_registries`). Activation-time cadence is deterministic strict-equality OR emits `needs_llm_judgment` when the citing artifact carries a `semantic_equivalence_acceptable: {reason, scope}` flag (Gap B refinement). The CP3 `verification-ritual-llm` worker agent consumes the deferred payload.
- **`cat-10-type-field-structure.md` + `.py` stub**. Substrate scaffolding for the Cat 10 candidacy per Spec 02 §"Cat 10" + Aaron's Gap A adjudication. The shipped `.py` stub returns `status: miss, evidence.miss_class: categorical_coverage_miss, details.reason: not_implemented_for_this_subject_project`. Subject projects with type-field-structure discipline (TypeScript interfaces, Rust traits, OWL constraints) overlay this file with a real parser; the barcode-template ships the stub indefinitely.
- **`_parse_se_acceptable` helper**. Extracts `semantic_equivalence_acceptable: {reason, scope}` from artifact text in either inline-JSON form or YAML-frontmatter-style form. The structured-flag (not bare boolean) is Aaron's Gap B refinement — operators committing to semantic equivalence write their rationale into the audit trail, mirroring `editorial_verdict_reason` from v2.7.0 architect ratification.
- **24 new unit tests**. Full suite: 262 tests (was 238 at alpha.1).

### Changed
- Cat 1–7 predicate signatures refactored to take `metadata` as third arg. Substrate-side; predicates that didn't need self_path are unaffected. Cat 7's self_path read switched from `canonical_sources["_artifact_self_path"]` to `metadata.self_path`.
- Orchestrator threads PredicateMetadata to each predicate; constructs it from task inputs (cycle_id, phase_context, artifact_self_path) and the cadence selector.
- Loader sentinel pattern: malformed category spec files are returned as `{_malformed: True, _malformed_reason: "..."}` entries so the orchestrator can emit explicit malformed_spec misses.
- Overall_status logic extended: `needs_llm_judgment` if any deterministic category emits the deferral OR any LLM-only category is queued. `pass` only when every applicable category passes.

### Architecture per Aaron's CP1 adjudications
- **Gap F (per-surface sandbox namespace)**: `subject.<surface>.<module-name>`, not flat `subject.<module>`. Future surfaces (cycle, commit, bankings) get their own namespace prefix.
- **Gap F (defensive import-failure)**: ImportError doesn't crash the agent; surfaces as `unresolved_predicate` miss with `details.import_error`.
- **Gap G (three classes)**: implemented as named constants. Distinguishing the four-classes-vs-three observation: missing-canonical-source is bucketed under `unresolved_predicate` with `details.reason: missing_canonical_source` in CP2. **Gap I (post-CP2 observation)**: if the missing-canonical-source case warrants its own 4th miss class, it can be split out additively without breaking existing miss-class consumers.
- **Gap H (typed PredicateMetadata)**: dataclass over TypedDict for runtime clarity (matches existing `WorkerResult` pattern).
- **Gap A (Cat 10 subject hook)**: shipped as stub; GraphWrite later overlays with a TS parser.
- **Gap B (semantic_equivalence_acceptable structured)**: `{reason, scope}` not bare boolean; serves the same misclassification-surfacing role as `editorial_verdict_reason`.
- **Gap D (two-cadence narrow scope)**: activation-time runs ONLY two-cadence categories. Cat 1–7 and Cat 10 (cadence: pre-routing) are filtered out at activation-time; only Cat 8 runs.

### Open observation surfacing for v2.8.0 CP3 adjudication
- **Gap I — missing-canonical-source as 4th miss class?** The three-class taxonomy locks cleanly except for "spec valid + predicate code resolvable + required canonical sources absent." CP2 buckets this under `unresolved_predicate` with `details.reason: missing_canonical_source`; semantically, this is "predicate inputs missing" rather than "predicate code missing." Downstream operator behavior: operator-provides-the-source (4th class flavor) vs operator-fixes-the-code (current unresolved_predicate flavor). If the distinction matters for downstream tooling, splitting it out as `MISS_MISSING_CANONICAL_SOURCE` is a small additive change with no breakage. Flagging for adjudication; not blocking CP3.

## v2.8.0-alpha.1 — Verification ritual Checkpoint 1: Cat 1-7 deterministic + surfaces directory

First checkpoint of v2.8.0, implementing FNSR Protocol Spec 02 in stages per the four-checkpoint plan. Ships the foundation: the `surfaces/` directory layout, category-spec loader, seven deterministic category predicates (Cat 1–7), and the `verification-ritual` system agent orchestrator. Cat 8 hybrid + Cat 10 hook framework + two-cadence handling land in CP2 (v2.8.0-alpha.2). LLM-required Cat 9 + adversarial-critic second-pass land in CP3.

### Added
- **`surfaces/verification/` directory** — first explicit use of FNSR Spec 01's surface-registry primitive. Contains `surface-spec.md` (verification surface metadata) and `categories/` (per-category spec files). Future surfaces (cycle, commit, bankings, forward-track) follow the same `surfaces/<surface>/<bucket-or-category>/` layout.
- **Seven category spec files** under `surfaces/verification/categories/`:
  - `cat-01-spec-section-existence.md` — STRUCTURAL spec §N.M citation check
  - `cat-02-adr-cross-reference.md` — STRUCTURAL ADR-NNN registry existence
  - `cat-03-q-ruling-cross-reference.md` — STRUCTURAL Q-ruling identifier resolution
  - `cat-04-reason-code-frozen-enum.md` — STRUCTURAL expectedReason against frozen enum
  - `cat-05-fol-owl-type-discriminator.md` — STRUCTURAL @type membership in FOL∪OWL canonical sets
  - `cat-06-manifest-mirror-consistency.md` — STRUCTURAL manifest-mirror against fixture expectedOutcome fields
  - `cat-07-cross-phase-cross-reference.md` — STRUCTURAL cross-phase/cross-amendment path resolution + reciprocal-reference symmetry
- **Category-spec loader** (`_load_category_specs`, `_parse_category_frontmatter`, `_resolve_predicate`) in `fnsr_daemon.py`. Reads category spec frontmatter (YAML-ish, stdlib-only parsing); resolves named Python predicates from the daemon's globals.
- **Seven Cat 1–7 deterministic predicates** in `fnsr_daemon.py` (`cat_01_spec_section_existence` through `cat_07_cross_phase_cross_reference`). Each takes `(artifact_text, canonical_sources)` and returns `{status: pass|veto|miss, evidence: <category-specific dict>}`.
- **`verification-ritual` system agent** registered in `SYSTEM_AGENTS`. Loads category specs at dispatch time; filters by cadence + canonical-source availability; runs each applicable category's predicate; aggregates into `per_category_result`, `overall_status` (pass | veto | needs_llm_judgment), `new_candidacies`, `summary`. Required outputs declared in `.claude/agents/verification-ritual.md` frontmatter; CPS enforces.
- **`FNSR_SURFACES_DIR` env var** (default `./surfaces`) — operator can override the surfaces directory location.
- **48 new unit tests** in `tests/test_verification_ritual.py`. Full suite: 238 tests (was 190; +48).

### Architecture per Aaron's adjudications
- **Call 1 (two-agent split)**: this release ships only the `verification-ritual` system agent. LLM-required categories (Cat 9 + Cat 8-semantic-equivalence) defer via `overall_status: needs_llm_judgment` for a future `verification-ritual-llm` worker agent (CP3). Operator-composes-chains pattern matches v2.7.0.
- **Call 2 (categories directory)**: `surfaces/verification/categories/cat-NN-*.md`. Adding a new category = drop a new file + implement the predicate; no substrate release.
- **Gap A (Cat 10 subject-project hook)**: framework ships in CP2; CP1 doesn't include Cat 10.
- **Gap C (commit-finalize explicit-chain gating)**: not wired in CP1; documented in the verification-ritual agent contract for CP4 finalization.
- **Gap D (two-cadence handling)**: pre-routing categories filtered correctly in CP1; activation-time-only categories filtered out. Cat 8 two-cadence specifics land in CP2.

### Open gaps surfacing from CP1 implementation
- See "Gaps F–H" notes in the CP1 commit message and the v2.8.0-alpha.1 GitHub release notes for adjudication before CP2 begins.

### Operator workflow
For v2.8.0-alpha.1 (CP1), the verification-ritual is dispatched as a normal task. Example:

```json
{
  "@id": "urn:fnsr:task:verify-Q-4-Step5-A",
  "agent": "verification-ritual",
  "inputs": {
    "artifact_path": "project/reviews/Q-4-Step5-A.md",
    "canonical_sources": {
      "spec": "project/SPEC.md",
      "decisions": "project/DECISIONS.md"
    },
    "cadence": "pre-routing"
  }
}
```

Operator queues this upstream of `architect` (mode: ratification) per Gap C; the architect reads `UPSTREAM[verification-ritual-task-id].outputs.overall_status` and refuses ratification on `veto`.

## v2.7.0 — Pass 2a sequencing (FNSR Spec 03), banking lifecycle (Spec 05), Forward-Track Surface (Spec 07)

Minor release implementing v2.7.0 of the FNSR Protocol Specifications v1.1 bundle (Logic-Team-reviewed; delivered as `project/Routing/`). This is the substrate-level work that enables Pass 2a evidence-gated change, makes the banking lifecycle first-class, and introduces the Forward-Track Surface as structurally distinct from bankings. Five pieces:

### Added
- **`reconnaissance` worker agent** at [.claude/agents/reconnaissance.md](.claude/agents/reconnaissance.md). Read-only by contract (tools: Read, Grep, Glob; no Edit/Write/Bash). Produces `findings`, `summary`, `evidence_paths` — no proposals, no recommendations. First instance of the **read-only-by-contract agent pattern**; future agents that gather evidence without taking action (verification-ritual deterministic categories, adversarial-critic second-pass verdicts, FNSR moral-person evidence-collection) draw on this shape. Includes a `scope_violation` structured-error refusal when asked to do something outside the contract.
- **`architect` worker agent extended to two modes** at [.claude/agents/architect.md](.claude/agents/architect.md):
  - `review` (existing v2.5.0 contract): structural findings + recommendations
  - `ratification` (new in v2.7.0; FNSR Spec 03 Pass 2a): six-field ruling payload with `ruling`, `editorial_verdict`, `editorial_verdict_reason`, `rationale`, `referenced_evidence`, `bankings`. Includes the refusal contract (substantive changes without UPSTREAM reconnaissance → `ruling: denied, rationale: reconnaissance_required`). The `editorial_verdict_reason` field is the audit-surfacing mechanism for the LLM's classification rationale.
- **Daemon: multi-mode `required_outputs` parsing.** Agent frontmatter now supports both flat-list syntax (single-mode agents) AND per-mode dict syntax (multi-mode agents like architect). CPS reads `task.inputs.mode` to pick the right required_outputs list at check time. Backward-compatible: single-mode agents continue to declare `required_outputs: [a, b, c]` as before.
- **`state_admin.py bank` extended (FNSR Spec 05)** with `--category` (Spec 05 taxonomy: methodology-refinement-candidate | pattern-observation | discipline-correction | contingency-operationalization | discipline-state-transition-observation; default pattern-observation) and `--state` (1=verbal-pending, 2=partially-committed, 3=formalized; default 1). Emits `event=banking` events with the full Spec 05 audit event structure (`banking_id`, `category`, `state`, `transition_history`, `forward_tracked_by`, optional `surfacing_cycle`). The v2.6.0 `--candidate-class` flag is still accepted and mapped to Spec 05 categories. Existing v2.6.0 audit events (event=forward_track with candidate_class payload) remain in the chain untouched and are read as legacy bankings; no migration; no phantom transition events backfilled.
- **`state_admin.py transition-banking <banking-id> --to-state N --reason "..."`** (FNSR Spec 05 §"Lifecycle state transitions"). Emits a `banking_state_transition` audit event on the same task that hosts the banking's create event. For operators electing explicit-mode lifecycle operation. Includes `--trigger` (e.g., `pass_2b_commit_landed`, `phase_exit_doc_pass_fold`, `manual_operator_action`).
- **`state_admin.py phase-boundary <from> <to> --anchor-task <id>`**. Emits a `phase_boundary_declared` audit event. Substrate is phase-schema-neutral; operator declares boundaries as first-class events.
- **`state_admin.py forward-track create`** (FNSR Spec 07). Creates a forward-track in State A with the FULL Spec 07 audit event structure, including fields not yet operated on in v2.7.0 (`inherited_through_phases: []`, `transition_history: [{state: A, ...}]`). v2.8.0's `transition`/`list` commands must read these without migration.
- **`state_admin.py forward-track inherit --from-phase <id> --to-phase <id>`** (FNSR Spec 07). Walks all Spec 07 forward-track events; for unresolved forward-tracks (state A or B) whose current phase context matches `--from-phase`, emits a `forward_track_phase_inheritance` event on the same anchor task. Does not double-inherit (a forward-track inherited from phase-3 → phase-4 will not match a subsequent `--from-phase phase-3` call).
- **34 new tests.** Full suite: 190 tests (was 156; +5 from v2.6.1 ADR-012 ghost fixture, +29 from v2.7.0 surface). Coverage: state_admin extensions (bank v2.7.0 shape, legacy back-compat, transition-banking, phase-boundary, forward-track create/inherit), multi-mode required_outputs parsing, reconnaissance contract, architect ratification ruling shape, CPS multi-mode behavior.

### Changed
- CLAUDE.md §3 Agent Roster — `reconnaissance` added to worker agents; `architect` row updated to document the two-mode operating contract.
- CLAUDE.md §3 shared agent contract — `required_outputs:` bullet updated to document multi-mode dict syntax.
- CLAUDE.md §5 Validation — test count updated; coverage expanded for v2.7.0 additions.
- CLAUDE.md §7.7 (Banking Lifecycle, Spec 05) replaces v2.6.0's "Forward-Track Banking" section. Documents three-state lifecycle; implicit vs explicit operating modes; v2.6.0 backward compatibility.
- CLAUDE.md gains §7.8 (Pass 2a Sequencing per Spec 03), §7.9 (Phase Boundaries and the Forward-Track Surface per Spec 07), §7.10 (Forward-Track vs Banking Distinction — substrate naming correction).
- CLAUDE.md §10 Key Files — `state_admin.py` row enumerates the v2.7.0 subcommands and notes the v2.6.0 back-compat.
- PLAYBOOK.md §1 gains three new failure-mode entries: `ruling: denied, rationale: reconnaissance_required`; architect ratification missing `editorial_verdict_reason`; reconnaissance agent returned `error: scope_violation`.
- PLAYBOOK.md §4.6 (Banking insights) updated for v2.7.0 Spec 05 lifecycle; documents implicit-vs-explicit operating modes and v2.6.0 back-compat.
- PLAYBOOK.md gains §4.7 (Pass 2a sequencing: reconnaissance → ratification) and §4.8 (Phase boundaries and forward-track inheritance).

### Why a minor version (v2.7.0) instead of v3.0.0
v2.7.0 adds new daemon-recognized contract shapes (multi-mode required_outputs, architect ratification, reconnaissance agent), four new operator CLI subcommands, and a substrate-level naming correction (banking vs forward-track). All backward compatible — existing v2.6.x agents and v2.6.x state files keep working unchanged. The migration is operator-side: new chains use the v2.7.0 surface; old chains and events remain valid.

### Why Pass 2b commit-finalize is NOT in v2.7.0
v2.7.0 ships Pass 2a (reconnaissance + ratification + architect refusal contract). The verification-ritual agent that gates Pass 2b commit-finalize is v2.8.0 work per FNSR Spec 02. In v2.7.0 interim, the operator manually queues an applier task after ratification succeeds. The audit chain shows `reconnaissance → ratification → operator-applier`; v2.8.0 changes only the third step to `commit-finalize` (verification-ritual-gated). Clean transition; no transitional task type to deprecate.

### Operator workflow shifts
- Substantive changes (defined terms, ADR text, normative shall/must, behavioral spec content) now require a reconnaissance task in UPSTREAM of the architect ratification. Editorial changes (typos, formatting, terminology-tightening, citation format) bypass reconnaissance per the architect's `editorial_verdict: editorial` classification.
- Bankings can be emitted with explicit `--category` (Spec 05) and `--state`. Or stay implicit (default state 1, default category pattern-observation) and let phase-exit doc-pass reconcile. Both modes are first-class.
- Phase boundaries are operator-declared audit events. Forward-track inheritance is a paired separate command. The substrate doesn't know what "phase" means — that's the subject project.

### FNSR-relevance note
The `reconnaissance` agent is the first instance of the read-only-by-contract agent pattern. Its contract is defined by what it CANNOT do (Read/Grep/Glob, no Edit/Write, produces findings not proposals). Future agents that need similar narrow scope can draw on this shape. Worth keeping the frontmatter and prompt structure clean enough to serve as a template for the verification-ritual deterministic categories (v2.8.0), the adversarial-critic second-pass verdicts (Spec 02 Cat 9), and eventually whatever evidence-gathering agents the FNSR moral-person substrate may need.

### Provenance
- FNSR Protocol Specifications v1.1 bundle (`project/Routing/00-README.md` and `01–07-*.md`); Logic Team instance-layer review folded in.
- Spec 03 (Pass 2a/2b sequencing) — reconnaissance/ratification/commit-finalize task types, architect refusal contract.
- Spec 05 (Banking Lifecycle) — three-state lifecycle, taxonomy, audit event structure, implicit-vs-explicit operating-mode neutrality.
- Spec 07 (Forward-Track Surface) — surface separation from bankings, audience sub-surfaces, audit event structure including unused-in-v2.7.0 fields.

## v2.6.1 — ADR-012 ghost test fixture (Spec 06 anchor for v2.7.0+ Cat 9)

Patch release. Adds the canonical ADR-citation mismatch fixture (the "ADR-012 ghost") from FNSR Protocol Spec 06 as a regression-locked test class in `tests/test_adr_and_awaiting.py`. No daemon behavior change.

### Added
- **`TestAdr012GhostFixture`** in `tests/test_adr_and_awaiting.py` — five tests that lock in v2.6.0's correct existence-check-passes-on-ghost behavior:
  - `test_registry_recognizes_adr_012` — precondition: ADR-012 is registered in DECISIONS.md.
  - `test_v260_passes_ghost_citation_in_canonical_doc` — ghost framing in `project/SPEC.md` passes; structural existence is satisfied.
  - `test_v260_passes_ghost_citation_in_decisions_destination` — same passing behavior when the ghost lands in DECISIONS.md itself.
  - `test_v260_passes_ghost_citation_in_arc_prefix` — same passing behavior when the ghost lands under `arc/` (canonical-by-prefix).
  - `test_v260_vetoes_companion_unregistered_adr_in_same_payload` — when the ghost (ADR-012, registered) is mixed with a genuinely missing ADR (ADR-099) in the same `after`, the missing one vetoes; the ghost passes (i.e., ADR-012 does NOT appear in the veto message).
- Full suite: 156 tests (was 151; +5).

### Why a patch
v2.6.0's CPS check (Cat 2 per FNSR Spec 02 — ADR cross-reference existence) is correct as far as it goes. The ghost case structurally passes existence and fails only at cited-content consistency (Cat 9 candidacy per FNSR Spec 02), which is v2.7.0+ work. This fixture documents the v2.6.0 → v2.7.0+ coverage progression in code: the same architect output that passes v2.6.0 will veto under Cat 9 in v2.7.0+. No state-mutation contract changes; the daemon ships unchanged.

### Provenance
- `project/Routing/06-adr-citation-mismatch-fixture.md` (FNSR Protocol Spec 06; Logic Team Input 2; Q-4-Step5-A architect ruling 2026-05-14)
- Spec 06's pseudocode in §"Test Fixture Structure" referenced an aspirational `cps_adr_citation_check` helper; the canonical artifact is the test written against the real v2.6.0 function `_check_adr_citations(proposed_outputs, decisions_path)`.

## v2.6.0 — ADR-citation CPS check, awaiting_operator_decision handoff, forward-track banking

Minor release adding three operator-protocol surfaces driven by lessons from the GraphWrite kickoff session. Where v2.5.0 hardened the operator's *recovery* tools (PLAYBOOK, state_admin reset/abandon, question-resolver), v2.6.0 hardens the operator's *handoff* and *insight-preservation* surfaces. Four pieces:

### Added
- **ADR-citation CPS check.** When a worker agent proposes a `changes[].after` payload destined for a canonical doc (default: `project/DECISIONS.md`, `project/SPEC.md`, `project/ROADMAP.md`, `project/IMPLEMENTATION_PLAN.md`, anything under `arc/`), the daemon parses the proposed content for `ADR-NNN` citations and vetoes the commit if any cited ADR is not a `## ADR-NNN:` header in `project/DECISIONS.md`. Closes the "agent invents ADR-007 in SPEC.md before ADR-007 is registered" failure mode. Scoped — citations in non-canonical paths (e.g., source comments) are NOT checked.
  - Helpers: `_load_adr_registry`, `_is_canonical_doc`, `_check_adr_citations`.
  - Configuration: `FNSR_DECISIONS_PATH`, `FNSR_CANONICAL_DOCS`, `FNSR_CANONICAL_DOC_PREFIXES`.
- **`awaiting_operator_decision` task status.** An agent that hits a question only the operator can answer may return `{"outputs": {"status": "awaiting_operator_decision", "options": [...], "recommendation": "..."}}`. The daemon recognizes this shape, validates it (non-empty `options[]`, non-empty `recommendation`), and commits the task with the new status. Daemon startup emits a WARNING per awaiting task so operators see them on resume.
  - Helper: `_validate_awaiting_decision_shape`.
  - CPS vetoes on malformed shape (empty options, missing/blank recommendation, wrong types).
- **`state_admin.py resolve <task-id> <option-index>`** — closes an awaiting task by selecting an option. Validates the task IS awaiting, validates the index is in range, appends an `operator_resolution` audit entry (chain-hashed), annotates `outputs.operator_resolution`, sets `status=done`. Supports `--note` for the rationale.
- **`state_admin.py bank <anchor-task-id> --class {methodology|pattern|risk|insight} --content "..." [--cycle N]`** — appends a `forward_track` history entry on the anchor task. Captures methodology insights / recurring patterns / latent risks that aren't yet actionable as tasks or ADRs. Entries chain into the audit trail; retrospective sweeps fold the highest-signal ones into PLAYBOOK / template / ADRs.
- **`state_admin.py status` surfaces awaiting tasks** at the top of its output under an `!! AWAITING OPERATOR DECISION` header.
- **32 new unit tests** across `test_adr_and_awaiting.py` (22: ADR registry parser, canonical-doc scoping, ADR-citation check with valid/missing/multi-citation/mixed cases, awaiting-decision shape validation) and `test_state_admin.py` extensions (10: resolve happy-path + validation + audit-chain integrity, bank events, status highlights awaiting). Full suite: 151 tests.

### Changed
- CLAUDE.md §2 (Architectural Commitments) — CPS hook description now enumerates all veto reasons including ADR-citation and awaiting-shape.
- CLAUDE.md §5 (Validation) — test coverage description updated.
- CLAUDE.md §7 (Barcode Flow) — step 7 documents the awaiting-decision commit branch; step 8 documents the startup WARNING scan. Task statuses list gains `awaiting_operator_decision`.
- CLAUDE.md gains §7.5 (canonical docs + ADR-citation CPS), §7.6 (operator-decision handoff path), §7.7 (forward-track banking).
- CLAUDE.md §11 (Key Files) — `state_admin.py` row enumerates resolve and bank subcommands and the status awaiting-surfacing behavior.
- PLAYBOOK.md gains two failure-mode entries (ADR-citation veto, malformed awaiting_operator_decision) in §1 and two new operator-workflow sections (§4.5 resolving an awaiting task, §4.6 banking forward-track insights).

### Why a minor version (v2.6.0) instead of a patch
v2.6.0 introduces new daemon-recognized contract shapes (`awaiting_operator_decision`), a new CPS check, and two new operator CLI subcommands. New observable surface area, but backward compatible — existing agents and existing state files keep working unchanged.

### Operator workflow shifts
- Authoring ADRs is now a daemon-enforced contract: register the ADR header in DECISIONS.md *before* citing the ADR number in any canonical doc. The CPS check makes the ordering explicit.
- When an agent doesn't have enough context to decide, it can punt to the operator via `status=awaiting_operator_decision` instead of producing wrong-shape output or asking for retries. Operator resolves via `state_admin.py resolve`.
- Methodology / pattern / risk observations that arise mid-run no longer need to be jotted in scratch files. Bank them against an anchor task and let retrospective sweeps fold them in.

## v2.5.0 — Operator playbook, state_admin CLI, question-resolver agent, developer task-scope heuristic

Minor release packaging the operational lessons from a full real-world kickoff session. The patches in v2.0–v2.4.2 hardened the daemon against specific failure modes; v2.5.0 hardens the operator experience around them. Four pieces:

### Added
- **`PLAYBOOK.md`** — operator playbook documenting failure-mode recognition (every daemon error message we observed in production runs) and recovery patterns. Sections: failure modes from the daemon log, failure modes from agent outputs, dispatch-time anomalies, operator task-splitting workflow, mojibake cleanup patterns, audit-trail inspection, when to manually edit state.jsonld, cross-platform gotchas. ~600 lines.
- **`state_admin.py`** — operator CLI for state.jsonld manipulation. Replaces the ad-hoc one-off Python scripts operators wrote during the kickoff session. Subcommands:
  - `reset <task_id> --reason "..."` — reset a task to ready, clear attempts and outputs, audit-log the reset
  - `abandon <task_id> --reason "..." [--replaced-by id1,id2]` — mark a task blocked when its scope is being replaced
  - `append-tasks <json-file>` — append new tasks from JSON file (skips duplicates)
  - `verify [--quiet]` — re-derive every audit entry's `chain_hash` and report integrity
  - `status [--filter STATUS]` — print task statuses
- **`question-resolver` system agent** — takes a synthesist's `outstanding_questions` plus operator-provided structured answers and drafts proper ADR-NNN entries (auto-numbered, ADR-001 format) for DECISIONS.md. Closes the manual operator-typing gap exposed by the kickoff: synthesist produces questions, operator must answer them, but actually drafting the ADR text was hand-work every time. Deterministic — no LLM in the path so operator intent is preserved exactly.
- **Developer agent task-scope heuristic** — when an instruction asks for >3 logical decisions, touches >2 files, or requires a section-move, the developer is now advised to return `{outputs: {error: "task_too_broad", suggested_split: [...]}}` rather than producing a partial / wrong-shape output. CPS recognizes the structured error; operator splits via the playbook pattern.
- **21 new unit tests** across `test_state_admin.py` (7) and `test_question_resolver.py` (14). Full suite: 119 tests.

### Changed
- CLAUDE.md §3 (Agent Roster) lists `question-resolver` alongside `applier` and `mojibake-repair`.
- CLAUDE.md §11 (Key Files) adds `state_admin.py` and `PLAYBOOK.md`.
- `developer.md` operating contract gains scope-guidance item 9.

### Why a minor version (v2.5.0) instead of v2.4.3 patch
v2.0–v2.4.2 were all daemon-internal improvements. v2.5.0 adds new operator-facing surface area (a new CLI tool, a new agent, a substantial new doc). The capability set is meaningfully larger. Backward compatible.

### Operator workflow shifts
- Use `python state_admin.py reset/abandon` instead of writing one-off `_split_*.py` scripts.
- When the synthesist surfaces outstanding questions, write structured answers as a YAML/JSON file and queue a `question-resolver` task instead of writing developer-task instructions by hand.
- When something goes sideways, check PLAYBOOK.md first.

## v2.4.2 — Developer envelope auto-coerce + API transient backoff

Patch release. Closes the two recurring failure modes observed during a real-world kickoff session: developer agent dropping the `{changes:[...], summary, self_assessment}` envelope on simple tasks, and Anthropic API 5xx errors burning 3 retry attempts in 15 seconds.

### Added
- **`_coerce_developer_envelope`** — when `_extract_outputs` returns a dict that looks like a single change (has `file`, `before`, `after` keys, no `changes` array), the daemon wraps it in the proper developer envelope, sets `self_assessment: needs_review`, and flags `_auto_coerced: True` in the output. Audit-visible. Closes the "LLM forgot the wrapper" failure mode without requiring a retry.
- **`_is_api_transient_error`** — detects `is_error:true` + `api_error_status: 5XX` in claude's JSON envelope. When found, `invoke_subagent` sleeps `FNSR_API_BACKOFF_S` seconds (default 60) before returning the failure, giving Anthropic time to recover instead of triggering immediate retries that would all hit the same outage. Configurable via env var.
- **12 new unit tests** covering envelope coerce paths (proper envelope preserved, bare change wrapped, non-change dict pass-through, etc.) and API transient detection (5xx detected, 4xx not, whitespace-tolerant JSON parsing).

### Changed
- `invoke_subagent` integrates both improvements transparently. Existing call sites unchanged.
- `WorkerResult` semantics unchanged. CPS check happily accepts auto-coerced outputs (they have all required keys after wrapping).

### Discovery context
v2.4.0/v2.4.1 kickoff session: developer agent emitted a single change object instead of the `{changes:[...], ...}` envelope on three separate complex-scope tasks. Operator manually split each task to ever-smaller scope before the LLM produced the right shape. v2.4.2's coerce makes this self-healing: the daemon recognizes the common LLM mistake and wraps it automatically.

Same session: an Anthropic API 500 incident caused all 3 retry attempts of a developer task to fire and fail within 15 seconds (the API was down for that whole window). v2.4.2's API backoff spreads the retries over ~3 minutes instead, giving the service room to recover.

### Configuration
- `FNSR_API_BACKOFF_S` (default 60) — seconds to sleep after a detected API 5xx before returning failure to the daemon loop. Total wall-clock with 3 retries ≈ 3 × (failure time + 60s). Set to 0 to disable backoff.

## v2.4.1 — Arrow mojibake patterns

Patch release. Adds three arrow-mojibake patterns to `_MOJIBAKE_PATTERNS`. The pattern set in v2.4.0 covered punctuation mojibake (em-dash, smart quotes, ellipsis) and Latin-1 supplement mojibake (`§`, `°`, etc.) but missed arrow characters whose UTF-8 third byte falls in the Unicode General Punctuation block and gets reinterpreted as a different cp1252 character.

### Added
- `â†'` → `→` (U+2192 right arrow — the one we hit in production)
- `â†'` → `↑` (U+2191 up arrow)
- `â†"` → `↓` (U+2193 down arrow)
- One new unit test (`test_right_arrow`) covering the new pattern class

### Discovery context
v2.4.0 kickoff's SPEC-edit task: developer agent emitted `v0.3 â†' v0.4` (where SPEC.md has `v0.3 → v0.4`) in its `before` snippet. The mojibake-repair pass didn't recognize the arrow pattern, so the applier's strict before-match correctly rejected the change with `before_not_found`. Adding the patterns closes that gap.

### Left arrow (`←`)
Not included. Its UTF-8 third byte is 0x90, which is undefined in cp1252 — observed behavior varies by tool. If we see it in production, we'll add it then.

## v2.4.0 — `mojibake-repair` system agent + Windows operator docs

Adds the second system agent (`mojibake-repair`) and inserts it into the standard kickoff ritual. Closes the LLM-side encoding inconsistency gap that v2.3.1's BOM-on-write couldn't reach: even with BOM'd inputs, agents occasionally emit mojibake in their outputs. The repair runs deterministically between content-producing agents and the applier.

### Added
- **`mojibake-repair` system agent** — second deterministic Python agent (after `applier`). Cleans 23 known cp1252-UTF8 mojibake patterns (`Â§` → `§`, `â€"` → `—`, smart quotes, ellipsis, super/subscript, fractions, etc.) from upstream `changes[].before` and `changes[].after` before the applier consumes them.
- **`.claude/agents/mojibake-repair.md`** — descriptive doc for the agent.
- **15 new unit tests** covering the repair patterns, mixed proper/mojibake content preservation, and the system-agent dispatch contract.
- **README "Windows operators" section** documenting the cp1252 Read tool issue and the three-layer mitigation (BOM on write + mojibake-repair agent + manual BOM for legacy files).

### Changed
- **Kickoff ritual: 9 tasks → 12 tasks.** Three `mojibake-repair` tasks inserted between each content-producing agent (planner / developer) and the corresponding applier task. Operators who don't need the repair (ASCII-only subject projects) can remove the three tasks from `state.jsonld`.
- Task IDs renumbered: `002-roadmap-apply` is now `003-roadmap-apply`, etc. Existing customized `state.jsonld` files from earlier versions need no changes — only the template's default ships with the new chain.
- CLAUDE.md §3 (Agent Roster) and §8 (Kickoff Ritual) updated to reflect the new agent + chain.

### Discovery context
v2.2/v2.3 kickoff produced an `IMPLEMENTATION_PLAN.md` with 190 mojibake `Â§` AND 190 proper `§` mixed together — the same planner emitted both correct and corrupted bytes for the same section-reference pattern. BOM-on-write (v2.3.1) prevents this for future file reads, but doesn't help when an agent has ALREADY emitted mojibake into its output JSON. `mojibake-repair` runs after the agent, cleans the output deterministically, and feeds the cleaned changes to the applier.

### False-positive risk
A document legitimately containing `Â§` or `â€"` literally (e.g., a tutorial about mojibake — yes, the irony is not lost on us) will be rewritten by the repair. Operators with such content can skip the repair tasks by removing them from `state.jsonld`.

## v2.3.1 — Applier writes UTF-8 BOM on new files

Patch release. The applier now prepends a UTF-8 BOM (`EF BB BF`) when creating new files unless the content already starts with one. This forces Claude Code's `Read` tool to decode the file as UTF-8 on subsequent agent reads, instead of defaulting to cp1252 on Windows — which silently produced mojibake (e.g., `§` rendered as `Â§`) and broke downstream `before`-match in apply tasks.

### Discovery context
v2.2/v2.3 kickoff produced an `IMPLEMENTATION_PLAN.md` with 190 mojibake `Â§` characters (plus 190 correctly-encoded `§`). The cause: the applier wrote the file BOM-less in task 002 (and again in 009), so Claude's Read tool decoded those files as cp1252 when downstream agents (developer, planner) read them. Even after manually BOM'ing project files, any file the applier CREATED inherited the bug.

### Changed
- `_apply_changes` new-file branch prepends `﻿` (UTF-8 BOM character) unless content already starts with one. Reflected in the applier's `bom_prepended` flag in the applied entry.
- Edit-mode writes preserve whatever BOM state existed (no change in behavior).
- Two new tests: BOM presence on create; no double-BOM if content already has one.

### Migration notes
Operators with existing BOM-less project files should manually add BOM (e.g., `Set-Content -Encoding UTF8BOM file.md` on Windows or `sed -i '1s/^/\xef\xbb\xbf/' file.md` on POSIX). Files the applier creates from this version onward will have BOM automatically. Edit-mode writes don't retroactively add BOM to existing files.

### Known limitation
LLM-side encoding inconsistency can still produce mojibake in agent OUTPUTS (not file reads). Observed in the v2.3.0 kickoff: the planner's IMPLEMENTATION_PLAN.md output contained both `§` and `Â§` for the same section-reference pattern, suggesting stochastic encoding in the model's generation. Mitigation: operators can post-process planner outputs with mojibake regex replacement before applying (see project/IMPLEMENTATION_PLAN.md repair pattern in the GraphWrite kickoff run).

## v2.3.0 — Multi-change atomic apply

The applier now handles multiple edits to the same file correctly. Each change's `before` is located in the ORIGINAL file content (not the in-progress intermediate state), overlapping changes are detected and rejected, and non-overlapping changes are applied end-to-start in a single pass so earlier positions don't shift.

### Why
Pre-v2.3.0 the applier processed changes sequentially, re-reading the file after each apply. When a `developer` agent proposed multi-edit revisions (typical for a synthesist's revise-this-roadmap output), applying change C1 mutated the file and broke C2's `before` match — even when the changes targeted independent regions. Result: most of a revision's changes silently failed with `before_not_found`, even though they were correct against the original.

### Added
- **`overlaps_other_change`** failure reason — when two changes' regions intersect in the original file, the later one (by start position) is rejected. Greedy keep-earliest policy.
- **6 new unit tests** covering: non-overlapping multi-edit success, cascade case (C1's `after` resembles C2's `before`), overlap detection, multi-file independence, mixed create+edit, position preservation under size-changing edits.

### Changed
- `_apply_changes` refactored: classify changes into new-files vs edits, group edits by file, locate each edit's position in the original, detect overlaps, apply non-overlapping kept set end-to-start.
- Per-change error semantics are unchanged for single-change cases — backward compatible.

### Discovery context
Surfaced during the v2.2.x kickoff ritual: task 006 (developer revise) proposed 15 ROADMAP edits; task 007 (applier) reported `apply_partial_failure` with 6 applied and 9 `before_not_found`. The 9 failures weren't drift — they were the cascade. v2.3.0 lets the same task succeed cleanly.

## v2.2.2 — Prompt via stdin (Windows cmd.exe 8191-char arg limit)

Patch release. Pipes the dispatch prompt to claude's stdin instead of passing it as a CLI argument, sidestepping Windows's cmd.exe 8191-character command-line limit. Without this, any task whose UPSTREAM block carried a few KB of prior outputs (i.e. anything past the first 1-2 steps of a chain) instantly failed with `The command line is too long.` on Windows.

### Changed
- `_resolve_claude_command` no longer takes a prompt argument; it only assembles flags (`-p --agent <name> --output-format json`).
- `invoke_subagent` passes the prompt via `subprocess.run(input=prompt, ...)`. Claude Code's `-p` flag reads stdin when no positional prompt is given.

### Discovery context
v2.2.0's kickoff ritual stalled at task 004 (adversarial-critic) on Windows after task 003 produced a 3KB review of a 14KB ROADMAP. The dispatch errored in 79ms with `The command line is too long.` — the cmd.exe `/c claude.cmd -p "<full prompt>"` exceeded 8191 chars once UPSTREAM started carrying real content.

### Cross-platform note
No behavior change on POSIX where command-line limits are 128KB-2MB. Pure Windows fix.

## v2.2.1 — Atomic-write retry for Windows transient locks

Patch release. Survives transient file-system locks (OneDrive sync, antivirus, Windows Search indexer) that intermittently cause `os.replace` to raise `PermissionError` mid-daemon-run. The daemon now retries with exponential backoff (up to ~5 seconds across 6 attempts) before propagating the error.

### Changed
- `_atomic_write` in `fnsr_daemon.py` retries on `PermissionError`. No behavior change on POSIX or when the rename succeeds on the first try.

### Discovery context
The bug surfaced during the v2.2.0 kickoff ritual's first real-world run on a project in OneDrive — the chain stalled at task 002 because the daemon couldn't persist the post-applier state update. The applier itself fired correctly; only the state-write failed. With this patch the chain proceeds past transient sync interference.

### Known related issue (not fixed in v2.2.1)
On Windows, Claude Code's `Read` tool may decode UTF-8 files without BOM as cp1252, producing mojibake for non-ASCII characters (em-dash, smart quotes, etc.). If your project files contain non-ASCII characters and the planner produces garbled output, add a UTF-8 BOM to the affected files. v2.3.0 will add an applier `mode: "replace"` to make the kickoff ritual robust against this regardless of source encoding.

## v2.2.0 — Kickoff ritual: SPEC → ROADMAP → IMPLEMENTATION_PLAN

Adds the standard project startup ritual. Drop a SPEC.md into `./project/`, run the daemon, and the template's pre-loaded 9-task chain produces a reviewed-and-revised ROADMAP and a detailed IMPLEMENTATION_PLAN with falsifiable acceptance criteria and exit gates — all hash-chained in the audit trail.

### Added
- **`planner` worker agent.** Mode-driven document author: `inputs.mode: "roadmap" | "implementation-plan"`. Reads SPEC (and optionally existing ROADMAP), produces structured planning documents as `changes[]` consumed by the applier. Required outputs: `[changes, summary, self_assessment]`.
- **Kickoff ritual** baked into `state.jsonld` as the template's default first-run experience. Nine tasks: roadmap draft → apply → review → critique → synthesize → revise → revise-apply → implementation-plan draft → apply. No manual task queueing needed for the first run.
- **CLAUDE.md §8 "The Kickoff Ritual"** documenting the chain, the prerequisite (SPEC.md must exist), and how to customize it.

### Changed
- README quick-start rewritten around the kickoff. The minimum operator workflow is now: clone template → drop SPEC.md in `./project/` → `python fnsr_daemon.py`. The chain runs end-to-end in ~25-40 minutes depending on SPEC complexity.
- Agent roster table in CLAUDE.md now includes `planner`.
- `state.jsonld` ships with the 9-task ritual instead of an empty queue.

### Migration notes
Drop-in compatible with v2.1.0 daemon. Existing operators who customized their `state.jsonld` should NOT replace it — the kickoff is for new instances. Pre-existing instances continue to work unchanged.

## v2.1.0 — System agents, applier, required-keys CPS, test suite

Additive release. The "hit run, walk away" pipeline now lands: a developer agent's `changes[]` proposals can be executed by a deterministic system agent.

### Added
- **System agent infrastructure.** `SYSTEM_AGENTS` registry + `invoke_agent` dispatcher in the daemon. System agents are deterministic Python functions that run locally (no LLM). Worker agents (LLM) and system agents (Python) share the same task contract.
- **`applier` system agent.** Consumes a developer agent's `changes[]` and writes them to disk with strict before-snippet matching (each `before` must appear exactly once; ambiguous or missing → CPS veto). Documented at `.claude/agents/applier.md`.
- **Required-keys CPS validation.** Each agent's frontmatter declares `required_outputs: [keys]`. The daemon parses it on dispatch; CPS vetoes any successful output missing a required key.
- **`tests/` directory** with stdlib `unittest` coverage (62 tests) across routing, extractor, CPS, audit, upstream, reconciliation, daemon lock, and applier. Run via `python -m unittest discover tests`.

### Changed
- All 7 worker agents now declare `required_outputs:` in frontmatter.
- `cps_check` signature now reads the agent's required-keys list from frontmatter via a new `_agent_required_outputs` helper.
- `developer` agent body updated to reference the `applier` by name (no longer "an apply step not yet built").
- CLAUDE.md restructured agent roster into Worker / System sections; flow step 4 now documents `invoke_agent` dispatcher.
- README documents the apply step pattern with a queueable example task and adds a Testing section.

### Migration notes
Drop-in compatible with v2.0.0 task queues. Existing state.jsonld files continue to work — the new `required_outputs` check only activates if the agent's frontmatter declares one.

## v2.0.0 — Barcode Orchestrator

**Major refactor.** Barcode is now a deterministic Python multi-agent orchestrator for Claude Code subagents, not a TypeScript JSON-LD service scaffold.

### Added
- `fnsr_daemon.py` — single-file Python stdlib orchestrator
- `state.jsonld` — JSON-LD work queue with SHA-256 hash chain audit trail
- `.claude/agents/` — seven worker agents (spec-reviewer, adversarial-critic, synthesist, architect, developer, semantic-sme, ux-sme)
- CPS containment hook, crash recovery, daemon-side upstream injection
- SPL v0.1: priority-based task routing
- `--agent <name>` invocation pattern with tolerant output extractor

### Removed
- TypeScript kernel scaffold (`src/`, `tests/`, `dist/`, `package.json`, etc.)
- Old layer-based architecture docs (`docs/`)
- npm-based CI workflow

### Changed
- `CLAUDE.md` rewritten as orchestrator-centric system directives
- `README.md` rewritten as Barcode template instantiation guide
- `.gitignore` slimmed to language-agnostic

### Migration notes
This is a breaking change. Existing clones based on the TS scaffold should treat this as a new template — there is no migration path from v1.x. The `./project/` convention is preserved; subject project docs (SPEC.md, ROADMAP.md, DECISIONS.md) live there as before.

## [0.1.0] - 2026-02-19

### Added

- Kernel with pure JSON-LD identity transform (`src/kernel/transform.ts`)
- Deterministic canonicalization (`src/kernel/canonicalize.ts`)
- CLI entry point (`src/kernel/index.ts`)
- Spec tests: determinism, no-network, snapshot
- Static kernel purity checker
- Architecture documentation (6 core principles)
- Computation model specification
- Composition guide and adapter boundary documentation
- Contributing guidelines with spec test checklist
- Example input/output JSON-LD documents
- CI/CD pipeline with GitHub Actions
- MIT License
