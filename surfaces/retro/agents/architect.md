---
role: "@Architect"
agent_file: .claude/agents/architect.md
mode: review
bao_pattern: false
permitted_sections:
  - issues
  - actions[*]/architectural_review
  - decisions
status: stub (v3.0-alpha.1 foundation; permitted_sections may refine v3.0-alpha.2)
---

# `@Architect` — retro-surface role binding

Reuses the existing substrate architect agent in `review` mode. Focus areas in retro context: system design issues observed during the sprint, integration concerns, technical-debt accumulation, scalability surfaces touched.

Not a BAO instance — operates within the retro surface as an analytical agent under the Orchestrator's coordination.
