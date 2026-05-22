---
name: mojibake-repair
description: Deterministic system agent. Cleans known cp1252-UTF8 mojibake patterns (e.g., `Â§` → `§`, `â€"` → `—`) from an upstream content-producing agent's `changes[]` outputs before they reach the applier. Runs as Python in the orchestrator, NOT as a Claude subagent.
required_outputs: [changes, summary, self_assessment]
---

# mojibake-repair — system agent

The second system agent (after `applier`). Sits between content-producing LLM agents (planner, developer) and the applier, cleaning known mojibake patterns from `changes[].before` and `changes[].after` so the applier never writes corrupted bytes to disk.

## Why this exists

Claude Code's `Read` tool on Windows defaults to cp1252 decoding for BOM-less UTF-8 files, producing mojibake like `§` → `Â§` and `—` → `â€"`. v2.3.1 fixed the file-write side (applier prepends BOM to new files). But the LLM-emission side is harder: even with BOM'd inputs, planners and developers occasionally emit mojibake in their JSON output — observed in real kickoff runs where the planner produced an `IMPLEMENTATION_PLAN.md` with 190 proper `§` AND 190 mojibake `Â§` mixed together.

mojibake-repair closes that gap deterministically.

## Operating contract

1. The orchestrator passes TASK_ID and INPUTS plus UPSTREAM resolved from `depends_on`.

2. INPUTS schema:

   ```
   source_task : str   <- @id of an upstream task whose outputs contain
                          a `changes[]` list. MUST also be present in
                          this task's `depends_on`.
   ```

3. Output shape on success — identical to `developer` / `planner` output, so the applier consumes it transparently:

   ```json
   {
     "outputs": {
       "changes": [ <repaired changes, same shape as upstream> ],
       "summary": "repaired N mojibake instance(s) across M field(s) in K change(s)",
       "self_assessment": "confident"
     }
   }
   ```

4. Output shape on failure (triggers CPS veto → `status=blocked`):

   ```json
   {
     "error": "missing_source_task" | "source_not_in_upstream" | "source_has_no_changes",
     "source_task": "<id>",
     "needed": ["..."]
   }
   ```

5. Mojibake patterns recognized (extended over time as new ones surface):
    - `Â§` → `§`, `Â¶` → `¶`, `Â°` → `°`, `Â©` → `©`, `Â®` → `®`, `Â±` → `±`, `Â´` → `´`, `Â·` → `·`, `Â¹` → `¹`, `Â²` → `²`, `Â³` → `³`, `Â½` → `½`, `Â¼` → `¼`, `Â¾` → `¾`, `Â«` → `«`, `Â»` → `»`
    - `â€"` → `—` (em-dash), `â€"` → `–` (en-dash), `â€¦` → `…`
    - `â€œ` → `"`, `â€` → `"`, `â€™` → `'`, `â€˜` → `'`

6. The repair is deterministic and stateless: same input always produces same output. No I/O beyond reading upstream from the prompt's UPSTREAM block.

7. The repair is text-substitution only. It does NOT attempt the UTF-8/cp1252 round-trip approach (encode-cp1252 then decode-utf8) because that fails when text mixes proper and mojibake chars — a common case in LLM output.

## When to queue this

In the standard kickoff ritual, mojibake-repair runs after every planner and developer task whose output is destined for an applier:

```
planner(roadmap)         → mojibake-repair → applier  →  ROADMAP.md
spec-reviewer → adversarial-critic → synthesist
developer(revise)        → mojibake-repair → applier  →  ROADMAP.md (revised)
planner(impl-plan)       → mojibake-repair → applier  →  IMPLEMENTATION_PLAN.md
```

If your subject project's SPEC contains no non-ASCII characters (no `§`, `—`, smart quotes, etc.), you can skip the repair tasks — the planner/developer have nothing to mojibake.

## False-positive risk

Theoretical: if a document legitimately contains the substring `Â§` (e.g., a tutorial about mojibake itself), repair will rewrite it to `§`. This is a known trade-off. For ordinary project content the risk is negligible. To opt out, simply don't queue a mojibake-repair task — the applier remains drop-in compatible.

## Constraints

System agent — runs as Python in `fnsr_daemon.py`, not via Claude. `tools` and `model` fields are N/A. Does not invoke other agents.
