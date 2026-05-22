---
name: git-committer
description: Deterministic system agent (v2.9.0). Creates a git commit via subprocess with strict safety defaults — refuses dirty working tree, protected-branch commits, and bypass-hooks unless the operator explicitly opts in with a bypass_reason recorded in the audit chain. First substrate agent with externally-visible side effects; see PLAYBOOK §4.10 for the operator-review-before-queuing pattern that applies to this class of agent.
required_outputs: [status, commit_sha, branch, files_changed, summary]
---

# git-committer — system agent (v2.9.0)

Stages and commits files via subprocess invocation of `git`. First substrate agent with **externally-visible side effects**: a commit lands in a repository that other systems (remotes, CI, collaborators) can see and reason about. Safety-by-default with explicit-opt-in bypass; every bypass becomes a citable audit event.

## Inputs

```json
{
  "@id": "urn:fnsr:task:commit-X",
  "agent": "git-committer",
  "inputs": {
    "message": "v2.9.0: test-runner + template-sync + git-committer",
    "paths": ["fnsr_daemon.py", "tests/test_test_runner.py"],
    "cwd": ".",
    "allow_bypass_hooks": false,
    "allow_dirty": false,
    "allow_protected_branch": false,
    "bypass_reason": null,
    "protected_branches": ["main", "master"]
  }
}
```

Required:
- `message` — commit message. Multi-line OK; passed via stdin to avoid shell escaping issues.
- `paths` — list of repo-relative paths to stage with `git add`. Use this rather than `-A` per CLAUDE.md §6 best practice (avoid accidentally staging .env or large binaries).

Optional:
- `cwd` — working directory of the repo. Default: cwd.
- `allow_bypass_hooks` — opt-in to skip pre-commit hooks (passes `--no-verify` to git). MUST be paired with `bypass_reason`.
- `allow_dirty` — opt-in to allow commit when working tree has uncommitted changes outside `paths`. MUST be paired with `bypass_reason`.
- `allow_protected_branch` — opt-in to commit to a branch in `protected_branches`. MUST be paired with `bypass_reason`.
- `bypass_reason` — required (and recorded in audit) when ANY `allow_*` flag is true. Operator's stated reason for the override.
- `protected_branches` — list of branch names treated as protected. Default: `["main", "master"]`. Override env var: `FNSR_PROTECTED_BRANCHES` (colon-separated).

## Outputs

On success:

```json
{
  "status": "committed",
  "commit_sha": "<full sha>",
  "branch": "<branch-name>",
  "files_changed": ["fnsr_daemon.py", "tests/test_test_runner.py"],
  "summary": "Committed 2 files to <branch> at <short-sha>",
  "bypass_invoked": null
}
```

When a bypass was invoked, the audit-event-bearing field is populated:

```json
{
  "status": "committed",
  "commit_sha": "...",
  "branch": "feature/x",
  "files_changed": [...],
  "summary": "...",
  "bypass_invoked": {
    "allow_bypass_hooks": true,
    "bypass_reason": "Hook is a long-running integration test we'll run separately after this commit lands; verified manually."
  }
}
```

On safety refusal (default-refuse path; no commit attempted):

```json
{
  "error": "refused_unsafe_commit",
  "reason": "dirty_working_tree" | "protected_branch" | "bypass_hooks_without_reason" | "dirty_without_reason" | "protected_without_reason",
  "details": "<diagnostic + remediation hint>",
  "current_branch": "main",
  "dirty_paths": [...]    // when reason: dirty_working_tree
}
```

On command failure (commit attempted but git rejected it):

```json
{
  "error": "git_command_failure" | "hook_failure",
  "reason": "<diagnostic>",
  "raw_stderr_tail": "<last 2000 chars>",
  "exit_code": <int>
}
```

## Two-class failure discrimination

Per Aaron's CP4 adjudication, git-related failures map to the v2.8.0-alpha.3 four-class miss taxonomy under `unresolved_predicate` with `evidence.reason` discriminating:

- **`hook_failure`** — pre-commit hooks ran and rejected the commit. The substrate is doing its job correctly; the underlying code or content is the operator-fix path. Inspect the hook's stderr in `raw_stderr_tail`; fix the underlying issue (linter complaint, test failure, lint config); re-queue.
- **`git_command_failure`** — git itself returned non-zero exit for a reason other than hook rejection. Possible causes: dirty working tree (when not allowed), protected branch (when not allowed), nothing-to-commit (paths already up-to-date), branch divergence, etc. The substrate or environment is the operator-fix path.

Downstream tooling filtering on `evidence.reason` gets clean separation between "fix the code" (`hook_failure`) and "fix the substrate/environment" (`git_command_failure`).

## Safety defaults (DEFAULT REFUSE)

All three default to refusing the commit. Each can be overridden with an explicit opt-in flag + a `bypass_reason` recorded in the audit chain:

| Default refusal | Override flag | Required pair |
|---|---|---|
| Working tree dirty (changes outside `paths`) | `allow_dirty: true` | `bypass_reason: "..."` |
| Branch in `protected_branches` (default: main/master) | `allow_protected_branch: true` | `bypass_reason: "..."` |
| Pre-commit hooks reject the commit | `allow_bypass_hooks: true` | `bypass_reason: "..."` |

The substrate refuses with `error: refused_unsafe_commit` if a bypass flag is set without `bypass_reason`. The audit invariant: every bypass is a citable record of operator intent at the moment of override.

## Externally-visible side-effect profile

A successful commit lands in the local repository. If `git push` is later invoked (NOT by this agent), the commit becomes externally visible. Per PLAYBOOK §4.10, git-committer dispatches SHOULD be operator-reviewed for content before queuing — not because the substrate enforcement is insufficient, but because the externally-visible nature changes the cost-of-error profile.

The git-committer does NOT push. Pushing is a separate operator action (`git push` or a future `git-pusher` agent). This intentionally keeps the externally-visible step under explicit operator control.

## Sequencing in the Pass 2a/2b chain

Typical operator chain for substantive changes:

```
reconnaissance → ratification → applier (writes files) → test-runner (verifies)
                                                                ↓ (only on all_pass)
                                                          git-committer
```

The test-runner's `status: all_pass` is the gating condition the operator (or a future BAO orchestrator agent) checks before queuing git-committer. The substrate doesn't auto-chain; the operator composes.
