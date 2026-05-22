---
role: "@QA"
agent_file: .claude/agents/qa.md
bao_pattern: false
contract_class: read-only
permitted_sections:
  - issues
  - issues[*]/qa_evidence
status: stub (v3.0-alpha.2 foundation)
---

# `@QA` — retro-surface role binding

Maps the v3.0-alpha.2 `qa.md` analytical agent to the retro `@QA` role per MAREP v2.2 §4.2. Read-only-by-contract pattern; focus on test coverage, regression patterns, defect distribution, verification-scope drift, test-infrastructure friction.

Not a BAO instance.
