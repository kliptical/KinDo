---
name: test-runner
description: Deterministic system agent (v2.9.0). Runs the configured test suite via subprocess and returns structured pass/fail/skip counts plus the first N failures. No LLM in the path. Subject-project-agnostic — the test command is configurable via `FNSR_TEST_RUNNER_CMD` env var or `inputs.cmd` task input. Built-in result parsers for python-unittest and npm; raw-stdout-tail fallback for unrecognized formats.
required_outputs: [status, passed, failed, skipped, total, summary]
---

# test-runner — system agent

Runs a test suite as a subprocess and returns structured outcome counts. First substrate agent with **shell-execution side effects** (subprocess invocation of an external test runner); all output is captured deterministically.

## Inputs

```json
{
  "@id": "urn:fnsr:task:test-run-X",
  "agent": "test-runner",
  "inputs": {
    "cmd": "python -m unittest discover tests",
    "cwd": ".",
    "parser": "python_unittest",
    "first_n_failures": 5,
    "timeout_s": 300
  }
}
```

All fields optional:
- `cmd`: command to run. Defaults to `FNSR_TEST_RUNNER_CMD` env var; if neither is set, returns structured error.
- `cwd`: working directory. Defaults to repo root.
- `parser`: result-format parser. Values: `python_unittest`, `npm`, `raw`. Default: auto-detected from `cmd`.
- `first_n_failures`: number of failures to capture in output. Default: 5.
- `timeout_s`: subprocess timeout. Default: 300.

## Outputs

On success:

```json
{
  "status": "all_pass" | "failures" | "errors",
  "passed": 156,
  "failed": 2,
  "skipped": 0,
  "total": 158,
  "summary": "Ran 158 tests in 1.234s; 2 failures, 0 skipped",
  "first_n_failures": [
    {"test_name": "...", "failure_text": "..."}
  ],
  "raw_stdout_tail": "<last 2000 chars of stdout>",
  "exit_code": 1,
  "duration_s": 1.234
}
```

On structured error:

```json
{
  "error": "test_command_unresolvable | timeout | subprocess_failed",
  "details": "<diagnostic>"
}
```

## Failure classes

- `test_command_unresolvable` — no `cmd` in inputs AND no `FNSR_TEST_RUNNER_CMD` env var.
- `timeout` — subprocess exceeded `timeout_s`.
- `subprocess_failed` — the test process couldn't start (FileNotFoundError, permissions, etc.).

The structured-error path produces CPS veto + `status=blocked`. Operator-fix path: provide the missing command, fix the environment, or extend the timeout.

## Side-effect profile

Read-only side effects: subprocess invocation, stdout/stderr capture, file reads (whatever the test command does). No state.jsonld writes from the test-runner itself; the dispatching task's history records the outcome.

The test-runner does NOT modify subject-project state. Tests that mutate filesystem state (e.g., a test that writes to `/tmp`) are the test-author's responsibility; the substrate doesn't isolate.
