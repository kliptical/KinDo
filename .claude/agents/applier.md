---
name: applier
description: Deterministic system agent. Applies a developer agent's proposed changes to the filesystem with strict before-snippet matching. Runs as Python in the orchestrator, NOT as a Claude subagent.
required_outputs: [applied, failed, summary]
---

# applier — system agent

The applier is the FIRST system agent: a deterministic Python function dispatched by the daemon instead of via `claude --agent`. It applies a `developer` agent's proposed `changes[]` to the filesystem and records the result in the audit trail.

System agents differ from worker agents:

| | Worker agents | System agents |
|---|---|---|
| Implementation | Markdown contract + Claude LLM dispatch | Python function in `fnsr_daemon.py` |
| Invocation | `claude --agent <name> --output-format json` | Direct function call inside `invoke_agent` |
| Tools | Per frontmatter (`Read, Grep, Glob`) | Whatever Python stdlib allows |
| Determinism | Non-deterministic (LLM) | Deterministic |

The daemon's [SYSTEM_AGENTS](../../fnsr_daemon.py) registry routes named agents to Python functions.

## Operating contract

1. The orchestrator passes TASK_ID and INPUTS plus the UPSTREAM block resolved from `depends_on`.

2. INPUTS schema:

   ```
   source_task : str   <- @id of an upstream task whose outputs contain
                          a `changes[]` list (developer agent contract).
                          MUST also be present in this task's `depends_on`.
   apply_root  : str?  <- root directory for relative file paths
                          (default: ".").
   ```

3. Output shape on success:

   ```json
   {
     "applied": [
       { "id": "C1", "path": "...", "mode": "create" | "edit",
         "bytes_written": 123, "delta_bytes": 5 }
     ],
     "failed": [],
     "summary": "N changes applied"
   }
   ```

4. Output shape on partial failure (triggers CPS veto → `status=blocked`):

   ```json
   {
     "error": "apply_partial_failure",
     "applied": [...],
     "failed": [
       { "id": "C3", "reason": "before_not_found" | "before_not_unique" |
                              "file_not_found" | "new_file_exists" |
                              "missing_required_field" | "io_error",
         "path": "...", "count": 2 }
     ],
     "summary": "N applied, M failed"
   }
   ```

5. Strict semantics: each change's `before` snippet MUST appear EXACTLY ONCE in its target file. Zero matches → drift; >1 matches → ambiguous; both reject. For new files (when `before` is null or empty), the target file MUST NOT already exist.

6. Partial application is preserved on failure: successful changes remain on disk; the audit record carries the full `applied` and `failed` lists. Operators inspect, decide how to proceed.

7. CPS vetoes any task with `error` truthy — so any failed change blocks the task. This is intentional: the operator is the trust root, and silent partial writes are an anti-pattern.

8. The applier has no LLM in its path. Its determinism is the daemon's: same inputs + same filesystem state = same result.
