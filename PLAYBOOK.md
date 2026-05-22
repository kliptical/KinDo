# Barcode Operator Playbook

Failure-mode recognition and recovery patterns for the Barcode orchestrator. Written from real-world experience running the kickoff ritual against a 95KB SPEC on Windows. Each section follows the same shape: **what you see**, **what it means**, **how to recover**.

This document complements [CLAUDE.md](CLAUDE.md) (the formal contract) and [README.md](README.md) (the quick-start). It exists because most failures aren't bugs in the orchestrator — they're patterns at the boundary between the deterministic daemon and the non-deterministic LLM workers. Recognizing them quickly saves hours.

---

## 1. Recognizing failure modes from the daemon log

### `before_not_found`

**Example log:**
```
WARNING fnsr-daemon task urn:fnsr:task:NNN-apply blocked by CPS: agent reported structured error: 'apply_partial_failure'
```
And inspecting state.jsonld history shows `reason: before_not_found` for one or more changes.

**What it means:** The applier searched the target file for the developer/planner agent's `before` snippet and found zero matches. The agent's view of the file diverges from the file's actual content.

**Common causes:**

| Cause | Diagnostic |
|---|---|
| **Mojibake in agent output OR on disk** | Compare the change's `before` bytes against the file's bytes at the expected location. Look for `Â§` vs `§`, `â€"` vs `—`, `â†'` vs `→` — see § 6. |
| **Line endings (CRLF vs LF)** | File has `\r\n`, agent emitted `\n`. Run `sed -i 's/\r$//' file.md` to normalize, or BOM the file. |
| **Earlier change in same chain shifted the content** | The cascade pattern that v2.3.0 fixed. Should not occur post-v2.3.0; if it does, file a bug. |
| **Whitespace differences** | Tabs vs spaces, trailing space, or BOM presence. Compare bytes directly. |

**Recovery:**
1. Inspect the on-disk content and the agent's `before` byte-by-byte. The `_repair_mojibake` helper in `fnsr_daemon` can repair both directions.
2. If the issue is on-disk mojibake (created by a pre-v2.3.1 applier write), run `_repair_mojibake` over the whole file via a one-off operator script (see [§ 6](#6-mojibake-cleanup-patterns)).
3. Reset the apply task: `python state_admin.py reset urn:fnsr:task:NNN-apply --reason "..."`.
4. Re-run the daemon; the existing developer outputs are reused with the now-clean file.

---

### `before_not_unique`

**Example log:** same as above; history shows `reason: before_not_unique, count: N`.

**What it means:** The `before` snippet appears more than once in the file. The applier refuses to guess which one to replace.

**Recovery:** The agent's `before` is too short. Operator options:
- **Reject as agent error.** Re-run with a tighter instruction asking for a more specific `before` (include more surrounding context).
- **Pick the intended occurrence manually.** Edit the file in place, mark the task as done with operator audit.

---

### `overlaps_other_change`

**What it means:** Two changes in the same task target overlapping regions of the same file. The applier (v2.3.0+) detects this and keeps only the earliest-position one; the rest are rejected.

**Recovery:** The agent proposed conflicting edits. Usually means the task scope was too broad. Split the task into smaller chunks; see [§ 4](#4-operator-task-splitting).

---

### `missing required output keys`

**Example log:**
```
WARNING fnsr-daemon task urn:fnsr:task:NNN-edit blocked by CPS: agent 'developer' missing required output keys: ['changes', 'summary', 'self_assessment']
```

**What it means:** The agent's output didn't include keys declared in its `required_outputs:` frontmatter. Almost always the LLM dropped the envelope wrapper.

**Pre-v2.4.2:** Operator had to retry or split.

**Post-v2.4.2:** The daemon auto-coerces bare change-shape dicts via `_coerce_developer_envelope`. If you still see this error AFTER v2.4.2, the agent's output is not even recognizable as a change-shape dict — something more fundamental is wrong.

**Recovery if still failing post-v2.4.2:**
1. Inspect the rejected_outputs in audit history — what shape did the agent return?
2. If it returned prose or an unknown structure: tighten the agent's contract docs and retry, OR split task to reduce scope.
3. Hit by 3 attempts: abandon + split per [§ 4](#4-operator-task-splitting).

---

### `agent reported structured error`

**Example log:** `agent reported structured error: 'insufficient_inputs'` or similar slug.

**What it means:** The agent returned `{"outputs": {"error": "<slug>", ...}}` — a structured failure per its contract. The agent is telling you it can't do the task with the inputs given.

**Recovery:**
- Read the full rejected_outputs in audit history. The agent's `needed` / `hint` fields usually say what's missing.
- Provide the missing inputs, reset the task, retry.
- If `error: task_too_broad` (post-v2.5.0): the agent suggests splitting; see [§ 4](#4-operator-task-splitting).

---

### `cited ADR(s) not found in registry` (v2.6.0)

**Example log:**
```
WARNING fnsr-daemon task urn:fnsr:task:NNN blocked by CPS: change C1 → project/SPEC.md cites ADR(s) not present in DECISIONS.md: ADR-012, ADR-099
```

**What it means:** A worker agent proposed a `change.after` payload destined for a **canonical doc** (default: `project/DECISIONS.md`, `project/SPEC.md`, `project/ROADMAP.md`, `project/IMPLEMENTATION_PLAN.md`, anything under `arc/`) that cites one or more `ADR-NNN` references which are NOT registered as `## ADR-NNN:` headers in [project/DECISIONS.md](project/DECISIONS.md). The daemon parses the proposed text and the registry on every commit; missing ADRs trigger a veto so agents cannot invent ADR numbers in authoritative docs.

**Recovery options:**
1. **The ADR genuinely should exist first.** Queue a `question-resolver` task to draft the missing ADR-NNN entry into DECISIONS.md, then re-run the original task. This is the normal ordering: register ADR → cite ADR.
2. **The agent invented the number.** Reject the agent's proposal entirely. Either reset with a tightened prompt naming the actual ADR to cite, or split into smaller scope so the LLM has less room to confabulate.
3. **The citation belongs in a non-canonical doc** (code comment, etc.). Move the proposed edit to a non-canonical path — the CPS check is scoped to canonical-doc destinations only.

**Configuration knobs** (env vars, set before starting the daemon):
- `FNSR_DECISIONS_PATH` — override the registry-file location.
- `FNSR_CANONICAL_DOCS` — colon-separated exact-path list (overrides defaults).
- `FNSR_CANONICAL_DOC_PREFIXES` — colon-separated prefix list (overrides defaults).

---

### `malformed awaiting_operator_decision` (v2.6.0)

**Example log:**
```
WARNING fnsr-daemon task urn:fnsr:task:NNN blocked by CPS: awaiting_operator_decision shape invalid: options must be a non-empty list
```

**What it means:** The agent returned `outputs.status == "awaiting_operator_decision"` (the v2.6.0 operator-handoff sentinel) but the accompanying shape is malformed. Required shape:
- `options` — non-empty list of strings or `{label, tradeoff}` dicts
- `recommendation` — non-empty string

If both keys are well-formed, the daemon commits the task with `status=awaiting_operator_decision`. If either is missing/empty/wrong type, CPS vetoes.

**Recovery:**
- Read the rejected_outputs in audit history — usually the agent omitted `recommendation` or returned `options: []` as a placeholder.
- Tighten the agent prompt: "If you cannot resolve, return `status: awaiting_operator_decision` with at least two `options[]` AND a non-empty `recommendation` naming your preferred option and why." Reset, retry.
- If the agent CAN actually decide, remove the awaiting-decision branch from its prompt entirely.

---

### `ruling: denied, rationale: reconnaissance_required` (v2.7.0)

**Example outputs in audit history:**
```json
{
  "ruling": "denied",
  "editorial_verdict": "substantive",
  "editorial_verdict_reason": "modifies normative shall language in spec §3.2.1",
  "rationale": "reconnaissance_required",
  ...
}
```

**What it means:** Architect's Pass 2a ratification refused because UPSTREAM lacks a `reconnaissance` task entry, AND the architect classified the proposed change as substantive (not editorial). Per FNSR Protocol Spec 03 §"Reconnaissance requirement", substantive changes require reconnaissance evidence; the refusal is the architect's contract working as designed.

**Recovery options:**
1. **Queue a reconnaissance task first**, then re-queue the ratification with the reconnaissance entry as a `depends_on`. Standard substantive-change chain: `reconnaissance → ratification → operator-applier` (v2.7.0) or `→ commit-finalize` (v2.8.0+).
2. **The change is actually editorial.** Read the `editorial_verdict_reason` field — does the rationale stand up? If the architect mis-classified, re-queue ratification with a clearer prompt asking the architect to re-evaluate the editorial-vs-substantive boundary against the structural heuristic in [.claude/agents/architect.md](.claude/agents/architect.md). The boundary is LLM-judged; misclassifications are expected and the `editorial_verdict_reason` field is the audit-surfacing mechanism.
3. **The change scope is wrong.** If the proposed change touches both editorial AND substantive surfaces, split into two ratification tasks (one for the editorial portion, one for the substantive portion with reconnaissance).

---

### Architect ratification missing `editorial_verdict_reason` (v2.7.0)

**Example log:**
```
WARNING fnsr-daemon task urn:fnsr:task:NNN-ratify blocked by CPS: agent 'architect' missing required output keys: ['editorial_verdict_reason']
```

**What it means:** Architect emitted a ratification ruling but omitted the `editorial_verdict_reason` field. Per FNSR Protocol Spec 03 and the v2.7.0 architect contract, this field is required even when the verdict itself is provided — it's the audit-surfacing mechanism for the LLM's classification rationale.

**Recovery:** Tighten the architect's prompt to explicitly require `editorial_verdict_reason`. Reset the task; retry. If the LLM keeps dropping the field, split the task to reduce cognitive load on the LLM.

---

### Reconnaissance agent returned `error: scope_violation` (v2.7.0)

**Example outputs in audit history:**
```json
{
  "error": "scope_violation",
  "what_was_asked": "propose a fix for the cardinality bug",
  "why_it_violates_contract": "requires proposal, not observation",
  "what_i_can_do_instead": "observe current cardinality behavior in src/kernel/cardinality.ts"
}
```

**What it means:** The reconnaissance agent's task INSTRUCTION asked for something a read-only-by-contract agent cannot do — propose a fix, recommend a change, or decide a tradeoff. The agent correctly refused via the structured-error path. CPS vetoes; task goes `blocked`.

**Recovery:** Re-queue with a properly-scoped task. Read the `what_i_can_do_instead` field — the agent has suggested the observation-shaped subset of the request. Either:
1. Queue a NEW reconnaissance task with the narrowed scope from `what_i_can_do_instead`.
2. Queue a developer task with the original (proposal-shaped) request — the developer agent is allowed to propose.

The reconnaissance agent is the first instance of the read-only-by-contract pattern; this refusal is the pattern working as designed.

---

### `test-runner: subprocess_failed` / `test_command_unresolvable` (v2.9.0)

**Example outputs in audit history:**
```json
{"error": "test_command_unresolvable", "details": "no `cmd` in inputs and no FNSR_TEST_RUNNER_CMD env var set"}
```

**What it means:** The `test-runner` system agent couldn't resolve the test command. Either no `cmd` was passed in task inputs AND no `FNSR_TEST_RUNNER_CMD` env var was set, OR the resolved command couldn't be spawned.

**Recovery:**
1. Pass `cmd` in task inputs explicitly: `{"agent": "test-runner", "inputs": {"cmd": "python -m unittest discover tests"}}`.
2. Set `FNSR_TEST_RUNNER_CMD` env var before starting the daemon: `export FNSR_TEST_RUNNER_CMD="npm test"`.
3. Verify the test command is on PATH and executable in the working directory.

---

### `git-committer: refused_unsafe_commit` (v2.9.0)

**Example outputs in audit history:**
```json
{"error": "refused_unsafe_commit", "reason": "dirty_working_tree" | "protected_branch" | "bypass_flag_without_reason", "details": "..."}
```

**What it means:** The git-committer's safety defaults refused the commit. Three sub-reasons:

- **`dirty_working_tree`** — the working tree has uncommitted changes outside the operator-specified `paths`. Default refusal because mixing unrelated changes into a commit is rarely intentional. Override: pass `allow_dirty: true` AND `bypass_reason: "<rationale>"`.
- **`protected_branch`** — the current branch is in `protected_branches` (default: `main`, `master`). Default refusal because direct commits to main are operator-rare. Override: pass `allow_protected_branch: true` AND `bypass_reason: "<rationale>"`.
- **`bypass_flag_without_reason`** — operator set one or more `allow_*` bypass flags but didn't supply `bypass_reason`. The bypass-with-reason invariant: every bypass becomes a citable audit event. Add the reason and retry.

**Recovery:** Read the `reason` field. For genuine bypass needs, set the appropriate flag PLUS a `bypass_reason` that explains the operator intent at the moment of override. For everything else, fix the underlying issue (clean the working tree; switch off the protected branch; restructure the commit chain).

---

### `git-committer: hook_failure` vs `git-committer: git_command_failure` (v2.9.0)

**Discrimination:** these two error classes look similar but have different operator-fix paths.

`hook_failure`: pre-commit (or commit-msg) hook ran and rejected the commit. The substrate is doing its job correctly; the underlying code or content is the operator-fix path.

```json
{"error": "hook_failure", "reason": "pre_commit_hook_rejected", "raw_stderr_tail": "..."}
```

`git_command_failure`: git itself returned non-zero for a reason other than hook rejection (working tree state, repo unavailable, git add failed, nothing to commit, branch divergence, etc.).

```json
{"error": "git_command_failure", "reason": "git_commit_failed" | "git_add_failed" | "not_a_git_repo_or_git_unavailable", "raw_stderr_tail": "..."}
```

**Recovery — `hook_failure`:** read `raw_stderr_tail`; the hook will name what it rejected (linter error, test failure, message format, etc.). Fix the underlying issue and re-queue. If the hook itself is broken or the bypass is genuinely safe, override with `allow_bypass_hooks: true` + `bypass_reason: "<rationale>"` — the bypass lands in the audit chain.

**Recovery — `git_command_failure`:** read `raw_stderr_tail` for the git error message. Common causes and fixes:
- "not a git repository" → check `cwd` input; ensure `.git/` is initialized
- "pathspec '...' did not match" → check that the `paths` exist in the working tree
- "nothing to commit" → the staged paths are already up-to-date; no commit needed
- "fatal: refusing to merge" / branch divergence → resolve upstream

Both errors land under `unresolved_predicate` in the four-class miss taxonomy (`evidence.miss_class: unresolved_predicate`) with `evidence.reason` discriminating the operator-fix path.

---

### API 5xx errors (post-v2.4.2 backoff)

**Example log:**
```
WARNING fnsr-daemon api transient error for task=urn:fnsr:task:NNN; sleeping 60s before returning failure
```

**What it means:** Anthropic's API returned a 5xx error. The daemon detects it and sleeps 60s before letting the next retry fire, giving the service room to recover instead of burning all attempts in a 15-second window.

**Recovery:** Usually self-heals. If 3 attempts all fail with API 5xx, the task hard-fails. Wait ~10 min, reset, retry. Check [status.claude.com](https://status.claude.com) if persistent.

---

### `task vanished during dispatch`

**Example log:** `ERROR fnsr-daemon task vanished during dispatch: urn:fnsr:task:NNN`

**What it means:** Between the daemon's two state-locks (one to claim the task, one to commit the result), the task disappeared from `state.jsonld`. Almost always an operator action — manually deleting a task while the daemon is running.

**Recovery:** Don't manually edit state.jsonld while the daemon is running. If you need to surgically modify state, stop the daemon first (`Ctrl-C`), edit, then restart.

---

### `PermissionError` on `state.jsonld` (Windows)

**Example log:**
```
ERROR fnsr-daemon uncaught error in cycle; backing off
Traceback (most recent call last):
  ...
PermissionError: [WinError 5] Access is denied: 'state.jsonld.tmp' -> 'state.jsonld'
```

**What it means:** `os.replace` couldn't atomically rename the temp file. Usually OneDrive sync, antivirus, or Windows Search indexer holding a transient lock.

**Recovery:** v2.2.1's atomic_write retry handles transient cases (up to 6 retries over ~4 seconds). If you still see this regularly:
- Move the project out of OneDrive / iCloud / Dropbox synced folders.
- Add `state.jsonld` to your antivirus exclusion list.
- Pause Windows Search indexing for the project directory.

---

### Daemon refuses to start: `could not acquire daemon lock`

**Example log:**
```
ERROR fnsr-daemon could not acquire daemon lock at fnsr.pid; another fnsr-daemon appears to be running. Refusing to start.
```

**What it means:** v2.2.x's startup PID lock detected another live daemon on the same `state.jsonld`. Single-worker by design.

**Recovery:**
- Find the existing daemon: `Get-Process python` on Windows, `ps aux | grep fnsr` on POSIX.
- If it's intentional: leave it alone, your second launch attempt was redundant.
- If it's stale (orphan from a crashed terminal): kill the process. The OS releases the lock on process death; the new daemon will start clean.

---

## 2. Recognizing failure modes from agent outputs

### `_auto_coerced: True` in outputs

**What it means:** The daemon's v2.4.2 envelope-coerce detected that the LLM returned a single change-shape dict instead of the full envelope and auto-wrapped it.

**What you should do:** Treat `self_assessment: needs_review` literally — the agent didn't follow contract, the auto-wrap got you a usable result, but the agent's intent may not match operator intent. Inspect before letting downstream tasks consume.

---

### `summary` says "repaired N mojibake instances"

**What it means:** mojibake-repair found and cleaned mojibake patterns in upstream output. Working as designed.

**No action needed** unless N is surprisingly large (e.g., >50 in a file you'd expect to be clean), in which case check for upstream encoding issues that need a system-level fix.

---

### Developer's `self_assessment: needs_review`

**What it means:** The developer agent thinks its proposal is uncertain. Operator should inspect before letting it land.

**Recovery:** Stop the chain at the upcoming applier task. Inspect the developer's `changes[]` manually. Decide whether to:
- Mark the apply task done with synthetic outputs (skip)
- Let it proceed (accept the dev's uncertainty)
- Reset developer task with a more specific instruction

---

## 3. Recognizing failure modes during dispatch

### Dispatch takes 30+ minutes then times out

**Example log:**
```
WARNING fnsr-daemon task urn:fnsr:task:NNN requeued (attempt 1/3)
...
ERROR fnsr-daemon task urn:fnsr:task:NNN failed after 3 attempts
```

**What it means:** Each attempt hit `TASK_TIMEOUT_S` (default 1800s = 30 min). The LLM took too long to produce output.

**Common causes:**
- Task scope too large (model generating very long output)
- Model stuck in a reasoning loop
- API degraded performance

**Recovery:**
- Bump `FNSR_TASK_TIMEOUT_S=3600` (or higher) for the next run if the scope is genuinely large
- Split the task into smaller chunks per [§ 4](#4-operator-task-splitting)

---

### Multiple fast failures in 15-second window (pre-v2.4.2)

**What it means:** API was returning instant 500s. The daemon's retry loop fires immediately, burning all 3 attempts.

**Post-v2.4.2:** The `_is_api_transient_error` check inserts a 60s sleep. Pre-v2.4.2, you'd hit this.

---

## 4. Operator task-splitting

When a task fails repeatedly due to scope-too-broad (timeout, shape contract violation, mojibake from large output), the operator splits it into smaller sub-tasks. This is the most common recovery action.

### Pattern

1. **Abandon the failing chain** (so the daemon doesn't keep retrying):
   ```
   python state_admin.py abandon urn:fnsr:task:NNN --reason "split: scope too broad" \
       --replaced-by urn:fnsr:task:AAA,urn:fnsr:task:BBB,urn:fnsr:task:CCC
   ```
   This sets status=blocked and adds an `operator_reset` audit entry naming the replacement tasks.

2. **Queue the smaller sub-tasks**. Each sub-task should be:
   - One decision per developer task
   - One file per developer task
   - Each task: `developer` → `mojibake-repair` → `applier` chain
   - Independent (no `depends_on` between sub-groups so failures don't block successes)

3. **Run the daemon.** Sub-groups proceed in lex order; partial success is possible.

### When to split

| Signal | Suggested split |
|---|---|
| Task instruction has >3 logical decisions | One sub-task per decision |
| Task touches >2 distinct files | One sub-task per file |
| Task involves a "move section" operation | One sub-task to delete, one to add |
| Task involves >5 logically independent before/after edits | One sub-task per edit, OR one sub-task per coherent region |
| LLM consistently returns wrong-shape output | Scope is too broad; split until shape comes out right |

---

## 4.5 Resolving an `awaiting_operator_decision` task (v2.6.0)

Some agents — typically the **synthesist** when reconciling contested findings, or the **question-resolver** when the operator's directive is ambiguous — can return:

```json
{
  "outputs": {
    "status": "awaiting_operator_decision",
    "options": ["A: keep current behavior", "B: excise entirely", "C: defer to ADR"],
    "recommendation": "B — context is no longer load-bearing."
  }
}
```

The daemon commits the task with `status=awaiting_operator_decision`. On the **next** daemon startup, you'll see a WARNING line per awaiting task:

```
WARNING fnsr-daemon AWAITING OPERATOR DECISION: urn:fnsr:task:NNN (3 options)
```

`python state_admin.py status` surfaces awaiting tasks at the top of its output with an `!! AWAITING OPERATOR DECISION` header.

### Resolving

```powershell
python state_admin.py resolve urn:fnsr:task:NNN <option-index> [--note "rationale"]
```

`<option-index>` is **0-based**. This:
1. Validates the task IS `awaiting_operator_decision` (refuses otherwise).
2. Validates the option index is in range.
3. Appends an `operator_resolution` history entry (chain-hashed) carrying `{option_index, option_text, note}`.
4. Annotates `outputs.operator_resolution = {option_index, option_text, note}`.
5. Sets `status=done`, making downstream `depends_on` tasks routable.

### When the agent shouldn't have asked

If you read the options and conclude the agent COULD have decided itself, don't resolve — abandon and retry with a tightened prompt. Operator decisions are scarce; agents that punt unnecessarily train the pattern in the wrong direction.

---

## 4.6 Banking insights (v2.6.0 + v2.7.0 Spec 05 lifecycle)

During a run, the operator notices a methodology insight, a recurring pattern, a discipline correction, or a latent risk worth preserving. Banking captures these against an anchor task without polluting the task graph.

### v2.7.0+ canonical form

```powershell
python state_admin.py bank <anchor-task-id> \
    --content "After the v2.6.0 split, the synthesist needed a recommendation field, not options-only." \
    [--category {methodology-refinement-candidate|pattern-observation|discipline-correction|contingency-operationalization|discipline-state-transition-observation}] \
    [--state {1|2|3}] \
    [--cycle <cycle-id>]
```

This appends a `banking` history entry per FNSR Protocol Spec 05 §"Audit event structure for bankings". Default `--category pattern-observation`; default `--state 1` (verbal-pending). The event carries `banking_id`, `category`, `state`, `content`, `transition_history`, `forward_tracked_by`, and optional `surfacing_cycle`.

### v2.6.0 legacy form (still accepted)

```powershell
python state_admin.py bank <anchor-task-id> \
    --candidate-class {pattern|risk|methodology|decision|other} \
    --content "..." [--cycle <cycle-id>]
```

`--candidate-class` values are mapped to Spec 05 categories at command time (pattern → pattern-observation, methodology → methodology-refinement-candidate, decision → discipline-correction, risk → methodology-refinement-candidate, other → pattern-observation). The emitted event is still `event=banking` with the full Spec 05 structure.

### Implicit vs explicit lifecycle operation

Per FNSR Spec 05's v1.1 review note, the substrate is neutral about which mode the subject project operates:

- **Implicit mode** (Logic Team practice): bank with default `--state 1`; never emit transition events; reconcile at phase-exit doc-pass. Counting views may diverge (architect-strict-count vs SME-inclusive-count); the divergence carries information.
- **Explicit mode**: bank, then run `transition-banking` whenever the banking moves between states:

```powershell
python state_admin.py transition-banking <banking-id> \
    --to-state {1|2|3} \
    --reason "..." \
    [--trigger {pass_2b_commit_landed|phase_exit_doc_pass_fold|manual_operator_action}] \
    [--transitioning-cycle <cycle-id>]
```

The transition emits a `banking_state_transition` audit event chain-hashed against the same anchor task that hosts the banking's create event.

### When to bank vs. ADR vs. task

| Signal | Use |
|---|---|
| Operator decision with downstream binding force | **ADR** in DECISIONS.md (queue a question-resolver task) |
| Concrete work that must happen | **Task** (`state_admin.py append-tasks`) |
| Observation worth preserving but not yet actionable | **Bank** (event=banking) |
| Recurring failure mode worth documenting | **Bank** AND eventually fold into this PLAYBOOK |
| **Commitment to FUTURE deliberation on a specific item** | **Forward-track create** (§ 4.8); distinct from banking per Spec 07 |

### Retrieval

Banking entries don't surface in `status` listings (they're not task state). They show up when you walk an anchor task's history:

```powershell
python -c "
import json
s = json.load(open('state.jsonld', encoding='utf-8'))
for t in s['tasks']:
    for h in t['history']:
        if h['event'] == 'banking':
            p = h['payload']
            print(t['@id'], p['banking_id'], p['category'], 'state', p['state'], '-', p['content'])
        # v2.6.0 legacy events used event=forward_track for bankings
        elif h['event'] == 'forward_track' and 'candidate_class' in h.get('payload', {}):
            p = h['payload']
            print(t['@id'], '[v2.6.0 legacy]', p['candidate_class'], '-', p['content'])
"
```

Periodic retrospective sweeps should fold the highest-signal banked entries into the template (PLAYBOOK, agent contracts, ADRs).

---

## 4.7 Pass 2a sequencing: reconnaissance → ratification (v2.7.0)

Per FNSR Protocol Spec 03, changes that mutate canonical state pass through a two-pass discipline. v2.7.0 ships Pass 2a (reconnaissance + ratification); Pass 2b's verification-gated commit-finalize lands in v2.8.0. In v2.7.0 the operator manually queues the apply step after ratification succeeds.

### Substantive-change chain

For changes to defined terms, ADR text, constraint clauses, normative `shall`/`must` language, behavioral spec content — queue:

```
reconnaissance task (read-only investigation)
    ↓
ratification task (architect Pass 2a, mode: ratification)
    ↓
operator manually queues an applier task to land the ratified change
```

The architect's refusal contract refuses ratification when reconnaissance is absent and the change is substantive. The refusal lands as `ruling: denied, rationale: reconnaissance_required` (see § 1 failure modes). Queue a reconnaissance task and re-ratify.

### Editorial-correction chain

For typo fixes, formatting consistency, terminology tightening that preserves semantics, citation format updates:

```
ratification task (architect Pass 2a — editorial_verdict: editorial)
    ↓
operator manually queues an applier task
```

Reconnaissance is bypassed. The architect's `editorial_verdict: editorial` classification permits this.

### Brief-confirmation chain

For follow-up commits to amendments whose substance was ratified at a prior cycle:

```
operator manually queues an applier task with brief_confirmation: true
    in inputs, and depends_on referencing the prior ratification
```

No new ratification — substance was ratified previously. The `brief_confirmation: true` flag is captured for v2.8.0+ cycle-counter suppression.

### Reconnaissance task contract

The `reconnaissance` agent is read-only by contract (tools: Read, Grep, Glob; no Edit/Write/Bash). Its output is `findings`, `summary`, `evidence_paths` — observations grounded in file paths and line ranges. If you queue a reconnaissance task whose INSTRUCTION asks for a proposal or recommendation, the agent will refuse via `error: scope_violation` (see § 1 failure modes). This is the first instance of the read-only-by-contract agent pattern; the refusal is the contract working as designed.

---

## 4.8 Phase boundaries and forward-track inheritance (v2.7.0 Spec 07)

Forward-tracks record commitments to FUTURE deliberation on specific items — structurally distinct from bankings (observations ABOUT the protocol). Spec 07 separates the two surfaces because conflating them would have caused the bankings-lifecycle model to collide with itself at every cross-phase forward-track inheritance event.

### Creating a forward-track

```powershell
python state_admin.py forward-track create \
    --anchor-task <task-id> \
    --sub-surface {consumer-closure-path|internal-methodology-refinement} \
    --subject-type {banking|fixture|capability|candidacy|other} \
    --subject-id <id> --description "..." \
    --deliberation-cycle <cycle-id> --phase-origin <phase-id>
```

Examples:

- A v0.2 feature commitment: `--sub-surface consumer-closure-path --subject-type capability --subject-id feature-x --deliberation-cycle v0.2-roadmap`
- A Cat 9 verification-ritual candidacy: `--sub-surface internal-methodology-refinement --subject-type candidacy --subject-id cat-9-cited-content-consistency --deliberation-cycle phase-exit-retro`

### Declaring a phase boundary

```powershell
python state_admin.py phase-boundary <from-phase> <to-phase> \
    --anchor-task <task-id> [--cycle <cycle-id>] [--notes "..."]
```

This emits a `phase_boundary_declared` event anchored on the specified task. Substrate is phase-schema-neutral; the operator declares.

### Inheriting unresolved forward-tracks across a boundary

```powershell
python state_admin.py forward-track inherit \
    --from-phase <id> --to-phase <id> \
    --inherited-at-cycle <entry-cycle-id>
```

Walks every Spec 07 forward-track event in `state.jsonld`. For each unresolved forward-track (state A or B) whose current phase context matches `--from-phase`, emits a `forward_track_phase_inheritance` event on the same anchor task. The forward-track's effective phase context is then `--to-phase` going forward.

### Phase boundary + inheritance workflow

The two commands are deliberately separate (paired manually or wrapped in a script):

```powershell
# Operator at phase-3 close
python state_admin.py phase-boundary phase-3 phase-4 \
    --anchor-task <last-task-of-phase-3> \
    --cycle phase-3-close \
    --notes "phase-3 exited cleanly; 3 forward-tracks still in state A"

python state_admin.py forward-track inherit \
    --from-phase phase-3 --to-phase phase-4 \
    --inherited-at-cycle phase-4-entry
```

### v2.7.0 forward-track scope

`create` + `inherit` are enabling primitives. `transition` (advance lifecycle state), `list` (query by sub-surface/state), `aging` (flag long-lived candidates) are operating primitives that land in v2.8.0 alongside the verification-ritual agent's new-candidacy emissions.

---

## 4.9 Verification ritual operator patterns (v2.8.0)

The verification ritual (FNSR Spec 02) runs on path-fence-authored content before routing, catching reference drift from canonical sources at machine speed. v2.8.0 ships eight ratified categories (Cat 1–8) plus two candidacies (Cat 9, Cat 10) with a deterministic-where-possible / LLM-where-necessary split.

### Canonical Pass 2a/2b chain

The full v2.8.0 chain for a substantive change:

```
reconnaissance               (read-only investigation; v2.7.0)
    ↓
verification-ritual          (deterministic Cat 1-8, 10; defers Cat 9 to LLM)
    ↓ (if overall_status: needs_llm_judgment)
verification-ritual-llm      (LLM Cat 9 judge; mode: cat-9-judge)
    ↓ (only when ≥1 Cat 9 veto)
adversarial-critic           (mode: cat-9-second-pass; veto mitigation)
    ↓
ratification                 (architect Pass 2a; six-field ruling payload)
    ↓
commit-finalize              (Pass 2b; applier with verification-ritual gating)
```

For **editorial-correction-scope** changes (typo / formatting / terminology-tightening / citation-format-update), reconnaissance is bypassed:

```
verification-ritual → [LLM chain if Cat 9 deferral] → ratification → commit-finalize
```

For **brief-confirmation cycles** (follow-up commits to amendments whose substance was ratified at a prior cycle):

```
commit-finalize (brief_confirmation: true, depends_on: prior ratification)
```

### v2.7.0 / v2.8.0 audit-chain shape — both read-compatible

The substrate's append-only invariant means v2.7.0 audit chains remain valid in v2.8.0 state files. The shape evolution:

| Element | v2.7.0 shape | v2.8.0 shape |
|---|---|---|
| Pass 2b step | operator-applier (manual applier task post-ratification) | `commit-finalize` task type (depends_on includes verification-ritual + ratification) |
| Verification gating | none (interim) | verification-ritual `overall_status: pass` referenced in architect's `referenced_evidence` |
| Cat 9 judgment | unavailable | `verification-ritual-llm` mode `cat-9-judge` with adversarial-critic second-pass on vetoes |

No migration is required; v2.7.0 entries in `state.jsonld` remain readable. New chains use the v2.8.0 shape; old chains continue to verify under `state_admin.py verify`.

### Four miss classes (v2.8.0-alpha.3+) — operator-fix path per class

`per_category_result` miss entries carry `evidence.miss_class` discriminating the operator-fix path:

| Miss class | Meaning | Operator fix path |
|---|---|---|
| `malformed_spec` | category spec file invalid (no frontmatter, missing `category_id`) | edit / repair the `cat-NN-*.md` spec file |
| `unresolved_predicate` | predicate code unavailable (substrate default missing or subject-project hook failed to import) | fix the predicate code (`fnsr_daemon.cat_NN_xxx` or `subject.verification.cat_NN_xxx.py`); inspect `evidence.import_error` when present |
| `missing_canonical_source` | required canonical sources absent from `inputs.canonical_sources` | provide the canonical source(s); `evidence.missing_canonical_source_keys` lists them |
| `categorical_coverage_miss` | spec ran and emitted miss because case falls in known-uncovered territory (Cat 9/10 candidacy surfacing class) | phase-exit-retro deliberable; consider forward-track via `state_admin forward-track create --surfacing-task-id <task @id>` if the case warrants candidacy |

Different filter; different action. Downstream tooling filtering on `miss_class` selects "things the operator should fix in code" (`unresolved_predicate`) vs "things the operator should provide" (`missing_canonical_source`) vs "things the operator should deliberate on" (`categorical_coverage_miss`).

### Forward-track operating commands (v2.8.0 CP4)

`state_admin forward-track` subcommands:

| Subcommand | Purpose |
|---|---|
| `create` | Create a forward-track in State A (candidate). Optional `--surfacing-task-id` records the originating task. |
| `inherit` | Bulk-inherit unresolved forward-tracks across an operator-declared phase boundary. |
| `transition` | Advance a forward-track's lifecycle state (A→B, B→C, A→C). `--to-state C` requires `--resolution-path` (one of `ratified-into-spec`, `merged-into-roadmap-release`, `withdrawn`). |
| `list` | Query by `--sub-surface`, `--state`, `--phase`. |
| `aging` | Flag forward-tracks inherited through ≥ threshold phases without resolution. Threshold defaults to 3, overridable via `--threshold` flag or `FNSR_FORWARD_TRACK_AGING_THRESHOLD_PHASES` env var. Each warning is itself an audit event (`forward_track_aging_warning`) — the audit chain records when warnings surfaced. |

### When verification-ritual emits `needs_llm_judgment`

The deterministic `verification-ritual` returns `overall_status: needs_llm_judgment` when at least one LLM-only category (Cat 9 today; future LLM cats too) was applicable AND its canonical sources were present. Operator action:

1. Queue a `verification-ritual-llm` task with `depends_on: [<verification-ritual task @id>]` and `inputs.mode: cat-9-judge`.
2. If the verification-ritual-llm emits a Cat 9 veto, queue an `adversarial-critic` task with `inputs.mode: cat-9-second-pass` and `depends_on: [<verification-ritual-llm task @id>]`. Cat 9 passes do NOT need second-pass.
3. If the adversarial-critic disputes the veto, decide whether to override the Cat 9 veto or honor it.
4. If verification-ritual-llm emits `new_candidacies`, run `state_admin forward-track create --surfacing-task-id <verification-ritual-llm task @id> --sub-surface internal-methodology-refinement --subject-type candidacy ...` for each candidacy the operator wants to track to phase-exit retro.

---

## 4.10 Operator-review-before-queuing for external-side-effect agents (v2.9.0)

The `git-committer` agent (v2.9.0) is the substrate's **first agent with externally-visible side effects**: a commit lands in a repository that other systems (remotes, CI, collaborators) can see and reason about. Every prior agent produced state changes confined to the substrate's own files (state.jsonld; surface state files; agent outputs).

This changes the cost-of-error profile. Internal substrate operations are recoverable via the audit chain (operator can re-run; previous state is preserved in history). Externally-visible operations are only as recoverable as the external system permits (git commits can be amended or reverted but never made un-seen by collaborators; pushed commits more so; emails sent are sent).

### The pattern

For agents that produce externally-visible side effects:

1. **Operator reviews the dispatch contents before queuing**, not after dispatch returns. The substrate's CPS gating provides a safety boundary, but the externally-visible cost-of-error is higher than the substrate's enforcement alone can warrant.
2. **Agents in this class default to refusing** under conditions where operator judgment is required (`git-committer`'s dirty-tree / protected-branch / bypass-hooks defaults are this pattern).
3. **Bypass requires explicit operator opt-in plus a stated reason** recorded in the audit chain. The reason becomes citable evidence of operator intent at the moment of override.
4. **The agent does NOT chain to subsequent external operations.** `git-committer` does not push. If a future external-side-effect agent emits an email, it does not also call an API. Each externally-visible step is its own dispatched agent under separate operator review.

### Agents in this class (current and future)

| Agent | External side effect | Status |
|---|---|---|
| `git-committer` | Local commit (potentially pushable) | v2.9.0 |
| `git-pusher` (hypothetical) | Push to remote | not implemented |
| `email-sender` (hypothetical) | Email transmission | not implemented |
| `api-caller` (hypothetical) | External HTTP / API call | not implemented |
| `webhook-emitter` (hypothetical) | Webhook to external system | not implemented |

The pattern documented here applies to all of them. When such agents are added in future releases, they MUST follow this pattern: default-refuse-under-judgment-conditions; opt-in-bypass-with-reason; no auto-chaining to further external operations.

### Why this matters (FNSR-relevance)

The synthetic moral person project will eventually require normative apparatus that produces external side effects (decisions communicated to stakeholders; commitments made on the agent's behalf; resources allocated). The operator-review-before-queuing discipline established here for `git-committer` is the substrate's precedent: external-side-effect agents are bounded by operator review, not just by substrate validation.

This is the architecture's answer to: *what stops a substrate from acting unrecoverably in the world?* The answer is not "stronger substrate validation"; the answer is "operator judgment as a gating step, with the substrate's defaults pushing toward conservative refusals when the operator hasn't explicitly opted in."

The pattern is the substrate-vs-procedure distinction (from v2.8.0's four-property pattern) applied to authority over external action: deterministic where possible (the safety defaults are mechanical refusals); operator judgment where necessary (bypass-with-reason); audit-chain visibility for both decisions (refusals and bypasses alike land in history).

### When the operator should review before queuing

For `git-committer`:
- Read the proposed `message` and `paths` before queuing. Confirm the message accurately summarizes the changes and the paths are exactly the operator intends.
- For commits on protected branches: explicitly approve via `allow_protected_branch: true` only when the operator has reviewed the diff AND determined direct-to-main is the right cadence (release-tag preparation; emergency fix; etc.).
- For bypass-hooks: only when the operator has reviewed what the hook would reject AND determined the bypass is genuinely safe in this case.

For future external-side-effect agents: same discipline. Read the proposed action; approve explicitly via opt-in flag + bypass_reason when overriding defaults.

The substrate's role is to make the review tractable (clear `inputs` schemas; explicit bypass surfaces) and to record the operator's decisions (audit-chain entries for both the action and any bypasses invoked). The operator's role is to actually look before dispatching.

---

## 5. Mojibake cleanup patterns

The Barcode template handles mojibake at three layers (v2.3.1 + v2.4.0 + v2.4.1 + v2.4.2). But sometimes mojibake gets baked into project files BEFORE those defenses were in place — particularly if the file was created by an old daemon or by hand.

### Symptom

Agent output contains `Â§`, `â€"`, `â†'`, or similar visual mojibake. Or the applier reports `before_not_found` even though the snippet "looks right."

### One-off operator sweep across project files

```powershell
python -c "
import sys, codecs
from pathlib import Path
sys.path.insert(0, '.')
import fnsr_daemon as d

for fn in Path('project').glob('*.md'):
    raw = fn.read_bytes()
    had_bom = raw.startswith(codecs.BOM_UTF8)
    text = raw[3:].decode('utf-8') if had_bom else raw.decode('utf-8')
    repaired = d._repair_mojibake(text)
    if repaired != text:
        fn.write_bytes(codecs.BOM_UTF8 + repaired.encode('utf-8'))
        print(f'{fn}: repaired')
    else:
        print(f'{fn}: clean')
"
```

This cleans every `.md` under `project/` using the v2.4+ pattern set. Add a UTF-8 BOM on write so future Claude Code Read tool invocations decode correctly.

### Long-term

Once a file has been BOM'd and cleaned, v2.3.1's applier preserves the BOM on subsequent edits and v2.4.0's mojibake-repair catches agent-output mojibake before it lands.

---

## 6. Inspecting the audit trail

### Find a task's history

```powershell
python -c "
import json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
s = json.load(open('state.jsonld', encoding='utf-8'))
for t in s['tasks']:
    if t['@id'] == 'urn:fnsr:task:NNN-name':
        for h in t['history']:
            print(h['ts'], h['event'])
            if 'reason' in h.get('payload', {}):
                print('  ', h['payload']['reason'])
"
```

### Verify chain integrity

```powershell
python state_admin.py verify
```

Walks every task's history, re-derives `chain_hash` from `prev_hash + event + payload`, reports any mismatch. Should print `PASS` for a healthy state.jsonld.

### Find all blocked tasks

```powershell
python -c "
import json
s = json.load(open('state.jsonld', encoding='utf-8'))
for t in s['tasks']:
    if t['status'] == 'blocked':
        last = t['history'][-1] if t['history'] else {}
        print(t['@id'], '-', last.get('payload', {}).get('reason', 'no reason'))
"
```

---

## 7. When to manually edit state.jsonld

The state.jsonld is operator-mutable. Sometimes the right move is to surgically modify it directly. Conventions:

- **Always stop the daemon first** (`Ctrl-C`) to avoid race conditions. The daemon's lock is on `state.jsonld.lock`, not the data file.
- **Use `state_admin.py` for routine operations** (reset, abandon). It preserves the audit chain.
- **For exotic changes, write a one-off Python script** that uses `fnsr_daemon._record` and `fnsr_daemon.hiri_sign` so audit entries chain correctly.
- **Never delete history entries.** The chain is append-only by contract. To "undo" a state change, append an `operator_reset` event documenting the intent.
- **After any manual edit, run `state_admin.py verify`** to confirm chain integrity.

---

## 8. Cross-platform gotchas

### Windows + OneDrive

- Move project out of OneDrive-synced folders if you can. atomic_write retries (v2.2.1) handle transient cases but persistent sync conflicts will still cause failures.
- Add `state.jsonld`, `fnsr.pid`, project files to OneDrive's "Always keep on this device" if you must stay in OneDrive.

### Claude Code Read tool encoding

- Project files without UTF-8 BOM may be decoded as cp1252 on Windows, producing mojibake in agent outputs.
- v2.3.1 makes applier write BOM by default. Manually BOM pre-existing files (see [§ 5](#5-mojibake-cleanup-patterns)).

### Windows `cmd.exe` 8191-char arg limit

- v2.2.2 routes prompts via stdin instead of CLI args, sidestepping the limit. No operator action needed.

---

## 9. When in doubt

- **Inspect first, mutate second.** state.jsonld is the truth; everything in the agents' history is auditable.
- **Stop the daemon before manual edits** to avoid races.
- **The 4-eyes principle is built in:** every state transition is hash-chained. If something looks wrong in the current state, walk the history backward to see when it diverged.
- **Don't fight the contracts.** If CPS is vetoing, it's vetoing for a reason. Splitting / providing more inputs is almost always the right answer.
- **File a bug** if a daemon error message isn't covered by this playbook. Future operators benefit.
