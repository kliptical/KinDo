---
phase_id: 06-compression
name: Final Compression
entry_criteria: Phase 5 exit conditions satisfied
exit_criteria: All deliverables (per MAREP §19) produced and validated; retro state promoted to episodic memory per MAREP §16.4
status: stub (v3.0-alpha.1 foundation)
canonical_reference: ariadne/archive/specs/MAREP-v2.2/MAREP_v2.2.md §12.6 + §13 + §16.4
---

# Phase 6 — Final Compression

Per MAREP v2.2 §12.6 + §13 + §16.4: Orchestrator archives discussion history (logical relocation preserving append-only invariant), preserves canonical findings, generates final summary and action manifest. Retro state promotes to episodic memory at FNSR archive (`<fnsr-archive>/archive/retrospectives/`).

The promotion is **deliberate, not automatic** per Aaron's CP3 adjudication on the Episodic → Semantic boundary. Episodic memory is automatically populated at retro close; Semantic memory promotion (CLAUDE.md / PLAYBOOK.md / ADR updates) requires architect ratification + commit-finalize per FNSR Spec 03.

Per-role `permitted_sections_per_role` to be specified in v3.0-alpha.2. Only the Orchestrator typically operates in this phase.
