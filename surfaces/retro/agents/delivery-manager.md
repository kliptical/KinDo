---
role: "@DeliveryManager"
agent_file: .claude/agents/delivery-manager.md
bao_pattern: false
contract_class: read-only
permitted_sections:
  - issues
  - issues[*]/delivery_observations
status: stub (v3.0-alpha.2 foundation)
---

# `@DeliveryManager` — retro-surface role binding

Maps the v3.0-alpha.2 `delivery-manager.md` analytical agent to the retro `@DeliveryManager` role per MAREP v2.2 §4.2. Read-only-by-contract pattern; focus on sprint predictability, throughput, blockers, coordination overhead, dependency thrash.

Not a BAO instance.
