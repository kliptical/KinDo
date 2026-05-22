---
name: question-resolver
description: Deterministic system agent. Takes a synthesist's `outstanding_questions` list and operator-provided structured answers, drafts proper ADR entries (matching ADR-001 format) for DECISIONS.md. Runs as Python in the orchestrator, NOT as a Claude subagent.
required_outputs: [changes, summary, self_assessment]
---

# question-resolver — system agent

The third system agent (after `applier` and `mojibake-repair`). Closes the manual-operator-typing gap that surfaced during real-world kickoff sessions: synthesist produces `outstanding_questions`, operator must answer them, but actually drafting the ADR text was hand-work every time.

Now the operator provides structured answers; question-resolver deterministically formats them into ADR-NNN entries that the applier consumes.

## Operating contract

1. The orchestrator passes TASK_ID and INPUTS plus UPSTREAM resolved from `depends_on`. The upstream task MUST be a synthesist (or any agent emitting `outstanding_questions: [...]`).

2. INPUTS schema:

   ```
   source_task     : str    <- @id of synthesist task whose outputs
                                contain `outstanding_questions: [...]`
   answers         : list   <- one entry per outstanding_question, in
                                the same order:
                                  None  -> defer this question (skipped)
                                  dict  -> {title, decision, context,
                                           consequences: [...]}
   decisions_path  : str?   <- default "project/DECISIONS.md"
   ```

3. Each `answers[i]` dict (when not None) MUST have:
   - `title`     — short ADR title
   - `decision`  — one sentence stating the choice
   - `context`   — paragraph explaining why
   - `consequences` — optional list of bullet strings (defaults to "(none specified)")

4. Output on success — standard developer envelope so the applier consumes it:

   ```json
   {
     "outputs": {
       "changes": [
         {
           "id": "C1",
           "file": "project/DECISIONS.md",
           "rationale": "Append N ADR(s) for operator-answered ...",
           "before": "<entire current DECISIONS.md content>",
           "after": "<same content + new ADR-NNN blocks>",
           "scope": "broad"
         }
       ],
       "summary": "drafted N ADR(s) (ADR-NNN through ADR-MMM); K deferred",
       "self_assessment": "confident" | "uncertain"
     }
   }
   ```

5. ADR numbering auto-discovers from existing `## ADR-NNN:` headers in DECISIONS.md. The next ADR is `max + 1`, formatted as `ADR-NNN` with 3-digit zero-padding.

6. ADR template:

   ```markdown
   ## ADR-NNN: {title}

   **Date:** YYYY-MM-DD

   **Decision:** {decision}

   **Context:** {context}

   **Consequences:**
   - {consequence 1}
   - {consequence 2}
   - ...

   ---
   ```

   Date is today's UTC date in ISO format.

7. Output on failure (CPS veto → `status=blocked`):

   ```json
   {
     "error": "missing_source_task" | "answers_must_be_list"
            | "source_not_in_upstream"
            | "source_has_no_outstanding_questions"
            | "decisions_file_not_found"
            | "malformed_answer" | "answer_missing_fields"
            | "consequences_must_be_list" | "no_answers_provided",
     "index"?: <integer for per-answer errors>,
     "missing"?: [<list of missing fields>],
     "hint"?: "..."
   }
   ```

8. `self_assessment` is `confident` if every question received an answer, `uncertain` if any were deferred (None entries).

## Why deterministic

The synthesist's outstanding_questions are real engineering decisions; the operator is the authority. Letting an LLM "interpret" the operator's answer into ADR prose risks drift between what the operator decided and what gets written. Deterministic template fill preserves exact operator intent.

## When to queue this

Typically right after a synthesist task whose output has `outstanding_questions`:

```
synthesist           → question-resolver  → mojibake-repair (optional) → applier  → DECISIONS.md updated
                     (answers in inputs)                                              with new ADRs
```

The operator authoring task inputs is the only LLM-adjacent step; the rest is deterministic.

## Constraints

System agent — runs as Python in `fnsr_daemon.py`, not via Claude. `tools` and `model` fields are N/A. Does not invoke other agents. Does not modify any file except via the applier downstream.
