---
role: "@RiskAnalyst"
agent_file: .claude/agents/risk-analyst.md
bao_pattern: false
contract_class: read-only
permitted_sections:
  - issues
  - issues[*]/risk_assessment
  - issues[*]/trigger_conditions
status: stub (v3.0-alpha.2 foundation)
---

# `@RiskAnalyst` — retro-surface role binding

Maps the v3.0-alpha.2 `risk-analyst.md` analytical agent to the retro `@RiskAnalyst` role per MAREP v2.2 §4.2. Read-only-by-contract pattern; focus on hidden failure modes, systemic fragility, operational exposure, coupling brittleness, single-point-of-failure observations.

Distinct from `@Skeptic` (which challenges existing findings); `@RiskAnalyst` surfaces latent risks that didn't fire this sprint but plausibly will under named trigger conditions.

Not a BAO instance.
