# Barcode Template

A deterministic multi-agent orchestrator for Claude Code subagents. Build a project by writing its SPEC, queueing review / design / implementation tasks, and running the daemon. The orchestrator dispatches the right specialist agents in the right order, audit-logs every state transition with a SHA-256 hash chain, and gives you back structured findings.

The vision: clone the template, drop your `SPEC.md` into `./project/`, queue your first task, run the daemon, walk away. Come back to a structured, auditable record of multi-agent analysis and proposals on your specification.

## What's in here

| Path | Purpose |
|---|---|
| `fnsr_daemon.py` | The orchestrator — single-file Python stdlib. |
| `state.jsonld` | JSON-LD work queue. Ships empty. |
| `.claude/agents/` | Seven specialist worker agents. |
| `CLAUDE.md` | Operating directives for the Barcode System. |
| `.gitignore` | Runtime artifact ignores. |

The seven agents:
- **spec-reviewer** — structural / ontological / conformance review of specifications
- **adversarial-critic** — confirm, refute, or extend an upstream reviewer
- **synthesist** — reconcile reviewer + critic into a single decision
- **architect** — system-level structural review; tradeoffs and load-bearing decisions
- **developer** — minimal change proposals (describe-only, no file writes)
- **semantic-sme** — ontology, BFO/CCO grounding, OWL DL conformance
- **ux-sme** — workflows, cognitive load, expert/novice modes

## Prerequisites

- Python 3.9 or later
- Claude Code CLI installed: `npm install -g @anthropic-ai/claude-code`
- An authenticated Claude Code session (run `claude` interactively once to log in)

## Quick start

### 1. Clone or copy this template

```
cp -r barcode-template/ my-project/
cd my-project/
```

### 2. Drop your SPEC into `./project/`

By convention, the subject project lives at `./project/`. Create the directory and drop in your specification:

```
mkdir -p project/
# Place your SPEC.md (required) and any supporting docs under ./project/
```

The minimum you need is `./project/SPEC.md`. Optional supporting docs: `DECISIONS.md`, `README.md`, source fixtures.

### 3. Run the daemon

```
python fnsr_daemon.py
```

The template ships with `state.jsonld` pre-loaded with the **kickoff ritual** — a 12-task chain that automatically turns your SPEC into a reviewed, revised ROADMAP plus a detailed implementation plan with acceptance criteria and exit gates. You don't need to queue tasks manually for the first run.

The kickoff:

```
001-roadmap-draft               (planner, mode=roadmap)         — SPEC -> ROADMAP draft
002-roadmap-repair              (mojibake-repair)                — cleans mojibake from planner output
003-roadmap-apply               (applier)                        — writes ROADMAP.md
004-roadmap-review              (spec-reviewer)                  — analyzes ROADMAP vs SPEC
005-roadmap-critique            (adversarial-critic)             — adversarial pass
006-roadmap-synthesize          (synthesist)                     — reconciles 004 + 005
007-roadmap-revise              (developer)                      — proposes ROADMAP edits
008-roadmap-revise-repair       (mojibake-repair)                — cleans mojibake
009-roadmap-revise-apply        (applier)                        — writes revisions
010-implementation-plan-draft   (planner, mode=implementation-plan)  — SPEC + ROADMAP -> IMPLEMENTATION_PLAN
011-implementation-plan-repair  (mojibake-repair)                — cleans mojibake
012-implementation-plan-apply   (applier)                        — writes IMPLEMENTATION_PLAN.md
```

The first headless `claude` invocation typically takes 3-5 minutes; subsequent dispatches are faster. Appliers and mojibake-repair are deterministic Python (instant). The full 12-task chain typically completes in 30-45 minutes depending on SPEC complexity. The daemon polls every 2 seconds for new ready tasks.

### 4. Inspect the result

After the chain completes you'll have:

- `project/ROADMAP.md` — strategic phases tracing back to the SPEC, adversarially reviewed and revised
- `project/IMPLEMENTATION_PLAN.md` — falsifiable acceptance criteria and exit gates per phase
- `state.jsonld` — full audit trail of every transition (every change hash-chained)

```
python -c "import json; s=json.load(open('state.jsonld')); [print(t['@id'], t['status']) for t in s['tasks']]"
```

Each task's `history` array records every event with `prev_hash` and `chain_hash`.

### 5. Stop the daemon (when it's done or you want a break)

`Ctrl-C` in the daemon's terminal. The current cycle completes, then it exits cleanly. State is safe — atomic writes mean interrupts can't corrupt anything.

### 6. Continue with implementation

After the kickoff, you have a vetted ROADMAP + IMPLEMENTATION_PLAN. The next phase is implementing against them. Queue more tasks in `state.jsonld` — typically a chain of `architect` (structural review of proposed approach) → `developer` (changes proposals) → `applier` (lands the code) per phase.

The synthesist and other reviewers can run on the implementation outputs the same way they ran on the roadmap.

## How it works (short version)

Read [CLAUDE.md](CLAUDE.md) for the full architecture. The essentials:

- **Routing is deterministic.** `next_ready_task` is a pure function of state: pick `status=ready` with all deps `done`, order by `priority` then @id.
- **Two agent kinds.** *Worker agents* run in fresh `claude --agent <name>` processes (LLM reasoning). *System agents* like `applier` are deterministic Python functions in the daemon.
- **Workers are stateless.** Each Claude call is a fresh process; memory lives in `state.jsonld`.
- **Upstream injection.** The daemon resolves predecessor outputs and inlines them into the prompt (the `UPSTREAM` block). Worker agents never read state directly.
- **Audit trail.** Every transition gets a SHA-256 chain-hashed history entry (`prev_hash` → `chain_hash`). Tamper-evident, not yet tamper-proof.
- **CPS containment.** A pre-commit veto rejects null outputs, agent-reported structured errors (`outputs.error` truthy), and missing required keys (declared in agent frontmatter via `required_outputs: [...]`). Vetoed tasks land in `blocked` with the rejected payload preserved.
- **Crash recovery.** On startup, the daemon revives any task left `in_progress` from a prior dead instance.

## Applying changes

The `developer` worker agent produces structured `changes[]` proposals (file, before, after). Queue an `applier` system-agent task downstream to land them on disk:

```json
{
  "@id": "urn:fnsr:task:apply-1",
  "agent": "applier",
  "status": "ready",
  "inputs": {
    "source_task": "urn:fnsr:task:developer-1",
    "apply_root": "."
  },
  "depends_on": ["urn:fnsr:task:developer-1"],
  "attempts": 0,
  "history": []
}
```

The applier verifies each `before` snippet appears EXACTLY ONCE in its target file (no drift, no ambiguity). On any failure — file missing, before not found, before not unique, new-file collision — CPS vetoes the task and lands `status=blocked` with the full applied/failed list preserved in the audit history for operator inspection.

## Testing

```
python -m unittest discover tests
```

The stdlib `unittest` suite covers routing, the output extractor, CPS (null + structured error + required-keys), audit-trail hashing, upstream resolution, in-progress reconciliation + daemon lock, and the applier. Every daemon change should keep it green.

## Conventions to know

- Subject project lives at `./project/`.
- All agents return `{"outputs": {...}}`. No prose outside the JSON.
- Structured failures: `{"outputs": {"error": "<slug>", ...}}` → daemon treats as CPS veto.
- Each agent declares its required output keys in frontmatter (`required_outputs: [...]`). CPS vetoes if any are missing.
- Worker agents have `Read, Grep, Glob` only. No `Edit` or `Write`. File mutations route through the `applier` system agent.

## Extending the template

- **Add agents.** Drop a new `*.md` file into `.claude/agents/` with YAML frontmatter (`name`, `description`, `tools`, `model`) and an operating contract. The contract MUST require the `{"outputs": {...}}` envelope.
- **Customize routing.** Edit `next_ready_task` in `fnsr_daemon.py`. Default is priority-then-lex; add phase grouping, conditional next-step routing, etc.
- **Add CPS predicates.** Edit `cps_check` to enforce per-agent schemas, business rules, or content policies beyond the null/error sentinels.
- **Add subject-specific guidance.** Put it in `./project/CLAUDE.md`. Barcode's own `CLAUDE.md` is the orchestrator contract; the subject's `CLAUDE.md` is your domain.

## Status

**v0.2.** Multi-agent dispatch with audit trail, crash recovery, upstream injection, unified output contracts, structured-error CPS vetoes, required-keys validation, system-agent dispatch with the `applier` deterministic write-path, and a `unittest` coverage suite.

### Roadmap

- **Real cryptographic signing.** `hiri_sign` is currently SHA-256 only — tamper-evident via chain consistency but not tamper-proof. Future: HMAC-SHA256 (stdlib) or Ed25519 (optional dep).
- **SPL v0.2.** Priority field is the v0.1 minimum. Phase grouping, fan-out/fan-in, and conditional next-step routing are future iterations.
- **Synthesist consensus model.** Current vocabulary is reviewer + critic specific. Multi-source panels (architect + semantic-sme + ux-sme running in parallel) need a richer consensus model.
- **More system agents.** The applier is the first. Future candidates: test-runner, linter, git-committer — anything deterministic the daemon could run between LLM steps.

## Windows operators: known encoding caveat

Claude Code's `Read` tool on Windows can decode BOM-less UTF-8 files as cp1252, producing mojibake (`§` → `Â§`, `—` → `â€"`, etc.) in agent outputs. The template handles this in three layers:

1. **Applier writes UTF-8 BOM** on every new file it creates (v2.3.1+). Forces Claude's Read tool to decode subsequent reads as UTF-8 reliably.
2. **`mojibake-repair` system agent** sits between content-producing agents and the applier in the standard kickoff chain (v2.4.0+). Cleans known mojibake patterns from `changes[].before` and `changes[].after` so the applier never writes corrupted bytes.
3. **Operator workaround for legacy files**: if you bring in pre-existing project files (e.g., a SPEC.md you drafted before adopting the template), prepend a UTF-8 BOM manually:

   ```powershell
   # PowerShell
   $content = Get-Content project/SPEC.md -Raw -Encoding UTF8
   [System.IO.File]::WriteAllText("project/SPEC.md", $content, [System.Text.UTF8Encoding]::new($true))
   ```

   ```bash
   # POSIX
   sed -i '1s/^/\xef\xbb\xbf/' project/SPEC.md
   ```

If your subject project uses only ASCII characters, none of this affects you and you can ignore this section.

## Common pitfalls

- **Don't use "Use the X subagent" prompt phrasing.** Always invoke via `--agent <name>`. The other form causes the parent session to summarize the subagent in prose, breaking the JSON output contract.
- **Don't run the daemon from inside `.claude/agents/`.** Run it from the Barcode root so it finds `state.jsonld` and `.claude/agents/` correctly.
- **OneDrive / iCloud sync can silently revert file saves during rapid iteration.** Consider working outside cloud-synced folders, or use `cp -f` / `Copy-Item -Force` if you suspect a save didn't land.
- **First headless `claude` call takes 3–5 minutes.** Subsequent calls are faster. Don't assume the daemon is hung if it's quiet for the first few minutes.

## License

(Operator: replace this section with your project's license once instantiated.)
