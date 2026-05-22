"""Tests for the v2.9.0 test-runner system agent.

Covers:
- Happy path (all_pass / failures / errors)
- Subprocess failure modes (timeout, unresolvable command, file not found)
- Output parser auto-detection (python_unittest, npm, raw fallback)
- Output parser correctness against representative unittest/npm stdout
- Required-outputs satisfy CPS
- first_n_failures limit
- Custom cwd
- raw_stdout_tail capture
"""
import os
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fnsr_daemon as d


_UNITTEST_PASS_STDERR = """\
test_one (tests.x.TestX.test_one) ... ok
test_two (tests.x.TestX.test_two) ... ok
test_three (tests.x.TestX.test_three) ... ok

----------------------------------------------------------------------
Ran 3 tests in 0.012s

OK
"""

_UNITTEST_FAIL_STDERR = """\
test_one (tests.x.TestX.test_one) ... ok
test_two (tests.x.TestX.test_two) ... FAIL
test_three (tests.x.TestX.test_three) ... ok

======================================================================
FAIL: test_two (tests.x.TestX.test_two)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "tests/test_x.py", line 10, in test_two
    self.assertEqual(1, 2)
AssertionError: 1 != 2

----------------------------------------------------------------------
Ran 3 tests in 0.012s

FAILED (failures=1)
"""

_UNITTEST_MIXED_STDERR = """\
test_a ... ok
test_b ... ERROR
test_c ... skipped 'reason'
test_d ... FAIL

======================================================================
ERROR: test_b (tests.x.TestX.test_b)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "x.py", line 1, in test_b
    raise RuntimeError("boom")
RuntimeError: boom

======================================================================
FAIL: test_d (tests.x.TestX.test_d)
----------------------------------------------------------------------
AssertionError: x != y

----------------------------------------------------------------------
Ran 4 tests in 0.020s

FAILED (failures=1, errors=1, skipped=1)
"""

_NPM_PASS_STDOUT = """\
PASS  src/feature.test.js
PASS  src/other.test.js

Tests:       5 passed, 5 total
Snapshots:   0 total
Time:        1.234 s
"""

_NPM_FAIL_STDOUT = """\
FAIL  src/feature.test.js
PASS  src/other.test.js

Tests:       2 failed, 1 skipped, 4 passed, 7 total
Snapshots:   0 total
Time:        2.345 s
"""


def _mock_proc(returncode=0, stdout="", stderr=""):
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


class TestTestRunnerHappyPaths(unittest.TestCase):
    def test_all_pass_python_unittest(self):
        with patch.object(subprocess, "run",
                           return_value=_mock_proc(0, "", _UNITTEST_PASS_STDERR)):
            task = {"@id": "urn:test:t1", "agent": "test-runner",
                    "inputs": {"cmd": "python -m unittest discover tests"}}
            result = d._test_runner(task, {})
        self.assertEqual(result.outputs["status"], "all_pass")
        self.assertEqual(result.outputs["passed"], 3)
        self.assertEqual(result.outputs["failed"], 0)
        self.assertEqual(result.outputs["total"], 3)
        self.assertEqual(result.outputs["parser_used"], "python_unittest")

    def test_failures_python_unittest(self):
        with patch.object(subprocess, "run",
                           return_value=_mock_proc(1, "", _UNITTEST_FAIL_STDERR)):
            task = {"@id": "urn:test:t1", "agent": "test-runner",
                    "inputs": {"cmd": "python -m unittest discover tests"}}
            result = d._test_runner(task, {})
        self.assertEqual(result.outputs["status"], "failures")
        self.assertEqual(result.outputs["passed"], 2)
        self.assertEqual(result.outputs["failed"], 1)
        self.assertEqual(result.outputs["total"], 3)
        self.assertEqual(len(result.outputs["first_n_failures"]), 1)
        self.assertIn("test_two", result.outputs["first_n_failures"][0]["test_name"])

    def test_mixed_errors_failures_skipped(self):
        with patch.object(subprocess, "run",
                           return_value=_mock_proc(1, "", _UNITTEST_MIXED_STDERR)):
            task = {"agent": "test-runner",
                    "inputs": {"cmd": "python -m unittest discover tests"}}
            result = d._test_runner(task, {})
        self.assertEqual(result.outputs["status"], "failures")
        # 1 failure + 1 error = 2 failed total
        self.assertEqual(result.outputs["failed"], 2)
        self.assertEqual(result.outputs["skipped"], 1)
        self.assertEqual(result.outputs["total"], 4)
        self.assertEqual(result.outputs["passed"], 1)  # 4 total - 2 failed - 1 skipped

    def test_npm_all_pass(self):
        with patch.object(subprocess, "run",
                           return_value=_mock_proc(0, _NPM_PASS_STDOUT, "")):
            task = {"agent": "test-runner",
                    "inputs": {"cmd": "npm test"}}
            result = d._test_runner(task, {})
        self.assertEqual(result.outputs["status"], "all_pass")
        self.assertEqual(result.outputs["passed"], 5)
        self.assertEqual(result.outputs["total"], 5)
        self.assertEqual(result.outputs["parser_used"], "npm")

    def test_npm_failures(self):
        with patch.object(subprocess, "run",
                           return_value=_mock_proc(1, _NPM_FAIL_STDOUT, "")):
            task = {"agent": "test-runner",
                    "inputs": {"cmd": "npm test"}}
            result = d._test_runner(task, {})
        self.assertEqual(result.outputs["status"], "failures")
        self.assertEqual(result.outputs["failed"], 2)
        self.assertEqual(result.outputs["skipped"], 1)
        self.assertEqual(result.outputs["passed"], 4)
        self.assertEqual(result.outputs["total"], 7)


class TestTestRunnerErrorPaths(unittest.TestCase):
    def test_command_unresolvable_when_no_cmd_no_env(self):
        # Clear env var if set
        old = os.environ.pop("FNSR_TEST_RUNNER_CMD", None)
        try:
            task = {"agent": "test-runner", "inputs": {}}
            result = d._test_runner(task, {})
            self.assertEqual(result.outputs.get("error"),
                              "test_command_unresolvable")
        finally:
            if old is not None:
                os.environ["FNSR_TEST_RUNNER_CMD"] = old

    def test_env_var_fallback(self):
        old = os.environ.get("FNSR_TEST_RUNNER_CMD")
        os.environ["FNSR_TEST_RUNNER_CMD"] = "python -m unittest discover tests"
        try:
            with patch.object(subprocess, "run",
                               return_value=_mock_proc(0, "",
                                                        _UNITTEST_PASS_STDERR)):
                task = {"agent": "test-runner", "inputs": {}}
                result = d._test_runner(task, {})
            self.assertEqual(result.outputs["status"], "all_pass")
        finally:
            if old is None:
                os.environ.pop("FNSR_TEST_RUNNER_CMD", None)
            else:
                os.environ["FNSR_TEST_RUNNER_CMD"] = old

    def test_timeout(self):
        timeout_exc = subprocess.TimeoutExpired(
            cmd=["x"], timeout=1, output="partial output")
        with patch.object(subprocess, "run", side_effect=timeout_exc):
            task = {"agent": "test-runner",
                    "inputs": {"cmd": "python -m unittest", "timeout_s": 1}}
            result = d._test_runner(task, {})
        self.assertEqual(result.outputs.get("error"), "timeout")
        self.assertIn("raw_stdout_tail", result.outputs)

    def test_subprocess_file_not_found(self):
        with patch.object(subprocess, "run",
                           side_effect=FileNotFoundError("no such command")):
            task = {"agent": "test-runner",
                    "inputs": {"cmd": "nonexistent-cmd"}}
            result = d._test_runner(task, {})
        self.assertEqual(result.outputs.get("error"), "subprocess_failed")


class TestTestRunnerParserDetection(unittest.TestCase):
    def test_detect_python_unittest(self):
        self.assertEqual(
            d._detect_parser("python -m unittest discover tests"),
            "python_unittest")
        self.assertEqual(
            d._detect_parser("python3 -m unittest tests.foo"),
            "python_unittest")

    def test_detect_npm(self):
        self.assertEqual(d._detect_parser("npm test"), "npm")
        self.assertEqual(d._detect_parser("npm run test"), "npm")
        self.assertEqual(d._detect_parser("yarn test"), "npm")
        self.assertEqual(d._detect_parser("jest --ci"), "npm")

    def test_detect_raw_fallback(self):
        self.assertEqual(d._detect_parser("cargo test"), "raw")
        self.assertEqual(d._detect_parser("./run-tests.sh"), "raw")

    def test_explicit_parser_overrides_detection(self):
        with patch.object(subprocess, "run",
                           return_value=_mock_proc(0, "", _UNITTEST_PASS_STDERR)):
            task = {"agent": "test-runner",
                    "inputs": {"cmd": "weird-cmd", "parser": "python_unittest"}}
            result = d._test_runner(task, {})
        self.assertEqual(result.outputs["parser_used"], "python_unittest")


class TestTestRunnerStructure(unittest.TestCase):
    def test_required_outputs_present_on_success(self):
        # CPS contract: required_outputs must be in the agent's output
        # when run succeeds.
        with patch.object(subprocess, "run",
                           return_value=_mock_proc(0, "", _UNITTEST_PASS_STDERR)):
            task = {"agent": "test-runner",
                    "inputs": {"cmd": "python -m unittest"}}
            result = d._test_runner(task, {})
        for key in ("status", "passed", "failed", "skipped", "total", "summary"):
            self.assertIn(key, result.outputs)
        # CPS check should pass.
        d.cps_check(task, result.outputs)

    def test_first_n_failures_respected(self):
        # Generate stdout with 10 failures; capture only 3.
        many_failures_text = (
            "Ran 10 tests in 0.1s\n\nFAILED (failures=10)\n\n"
            + "\n\n".join(
                f"FAIL: test_{i} (m.T.test_{i})\n"
                "----------------------------------------------------------------------\n"
                f"AssertionError: failure body {i}\n"
                for i in range(10)
            )
        )
        with patch.object(subprocess, "run",
                           return_value=_mock_proc(1, "", many_failures_text)):
            task = {"agent": "test-runner",
                    "inputs": {"cmd": "python -m unittest",
                                "first_n_failures": 3}}
            result = d._test_runner(task, {})
        self.assertLessEqual(len(result.outputs["first_n_failures"]), 3)

    def test_raw_stdout_tail_truncated(self):
        very_long = "x" * 5000
        with patch.object(subprocess, "run",
                           return_value=_mock_proc(0, very_long, "")):
            task = {"agent": "test-runner",
                    "inputs": {"cmd": "python -m unittest"}}
            result = d._test_runner(task, {})
        # raw_stdout_tail is last 2000 chars
        self.assertLessEqual(len(result.outputs["raw_stdout_tail"]), 2001)

    def test_exit_code_recorded(self):
        with patch.object(subprocess, "run",
                           return_value=_mock_proc(42, "", "")):
            task = {"agent": "test-runner",
                    "inputs": {"cmd": "python -m unittest"}}
            result = d._test_runner(task, {})
        self.assertEqual(result.outputs["exit_code"], 42)


class TestTestRunnerCustomCwd(unittest.TestCase):
    def test_cwd_passed_to_subprocess(self):
        call_kwargs = {}
        def capture_run(*args, **kwargs):
            call_kwargs.update(kwargs)
            return _mock_proc(0, "", _UNITTEST_PASS_STDERR)
        with patch.object(subprocess, "run", side_effect=capture_run):
            task = {"agent": "test-runner",
                    "inputs": {"cmd": "python -m unittest",
                                "cwd": "/some/path"}}
            d._test_runner(task, {})
        self.assertEqual(call_kwargs.get("cwd"), "/some/path")


class TestTestRunnerEndToEnd(unittest.TestCase):
    """Real subprocess invocation against the actual test suite — no
    mocks. Validates that the test-runner can actually run something
    end-to-end. Skipped if Python isn't on PATH for some reason."""

    def test_real_substrate_self_validation(self):
        # The test-runner can run the substrate's own test suite.
        # Note: this test runs the test suite recursively; the recursion
        # is one-deep (this single test invokes a one-shot run of the
        # full suite, which does NOT include this test).
        # Use a fast-completing single test module to keep runtime low.
        task = {"@id": "urn:test:self-validation",
                "agent": "test-runner",
                "inputs": {
                    "cmd": "python -m unittest tests.test_routing",
                    "cwd": ".",
                    "timeout_s": 30,
                }}
        result = d._test_runner(task, {})
        # Test framework was able to run; status reflects the outcome.
        self.assertIn(result.outputs.get("status"),
                       ("all_pass", "failures", "errors"))
        # If everything passed, this assertion holds; otherwise
        # the substrate has a real failure surfaced.
        if result.outputs.get("status") == "all_pass":
            self.assertGreater(result.outputs["total"], 0)


if __name__ == "__main__":
    unittest.main()
