"""Tests for the v2.9.0 git-committer system agent.

Strategy:
- Real tempdir git repos for happy paths + safety-refusal paths (slower
  but exercises actual git semantics).
- Mocked subprocess for hook_failure discrimination (needs a synthesized
  stderr pattern that real git wouldn't produce in a sandbox).

Covers:
- Safety-by-default: dirty tree, protected branch, bypass-without-reason
  all refuse with error: refused_unsafe_commit + reason discriminator
- Explicit opt-in bypass with bypass_reason → commit succeeds + audit
  records the bypass via outputs.bypass_invoked
- Two-class failure discrimination (hook_failure vs git_command_failure)
- Required-outputs satisfy CPS on success
- files_changed + commit_sha + branch surfaced correctly
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fnsr_daemon as d


def _have_git() -> bool:
    try:
        subprocess.run(["git", "--version"], capture_output=True,
                       check=False, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@unittest.skipUnless(_have_git(), "git binary not available")
class TestGitCommitterRealRepo(unittest.TestCase):
    """Tests against real tempdir git repos."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="fnsr-gc-test-"))
        # Init (default branch name varies by git version); rename to
        # feature/test after initial commit for compatibility with older git.
        subprocess.run(["git", "init", str(self.tmpdir)],
                       capture_output=True, check=True)
        subprocess.run(["git", "-C", str(self.tmpdir), "config",
                        "user.email", "test@example.com"],
                       capture_output=True, check=True)
        subprocess.run(["git", "-C", str(self.tmpdir), "config",
                        "user.name", "Test"],
                       capture_output=True, check=True)
        subprocess.run(["git", "-C", str(self.tmpdir), "config",
                        "commit.gpgsign", "false"],
                       capture_output=True, check=True)
        # Initial commit so HEAD exists
        (self.tmpdir / "README.md").write_text("# test\n")
        subprocess.run(["git", "-C", str(self.tmpdir), "add", "README.md"],
                       capture_output=True, check=True)
        subprocess.run(["git", "-C", str(self.tmpdir), "commit",
                        "-m", "initial", "--no-gpg-sign"],
                       capture_output=True, check=True)
        # Rename current branch to feature/test (non-protected)
        subprocess.run(["git", "-C", str(self.tmpdir), "branch",
                        "-M", "feature/test"],
                       capture_output=True, check=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _commit(self, **inputs):
        task = {"@id": "urn:test:commit",
                "agent": "git-committer",
                "inputs": {"cwd": str(self.tmpdir), **inputs}}
        return d._git_committer(task, {})

    def test_happy_path_commit_succeeds(self):
        (self.tmpdir / "new.txt").write_text("hello\n")
        result = self._commit(
            message="add new file", paths=["new.txt"])
        self.assertEqual(result.outputs.get("status"), "committed")
        self.assertIn("new.txt", result.outputs["files_changed"])
        self.assertEqual(len(result.outputs["commit_sha"]), 40)
        self.assertEqual(result.outputs["branch"], "feature/test")
        self.assertIsNone(result.outputs["bypass_invoked"])

    def test_required_outputs_pass_cps(self):
        (self.tmpdir / "x.txt").write_text("x\n")
        result = self._commit(message="x", paths=["x.txt"])
        task = {"agent": "git-committer"}
        # MUST NOT raise.
        d.cps_check(task, result.outputs)

    def test_refuses_dirty_working_tree(self):
        # Create staged path AND a separate dirty file
        (self.tmpdir / "staged.txt").write_text("staged\n")
        (self.tmpdir / "unrelated.txt").write_text("unrelated dirty\n")
        result = self._commit(
            message="x", paths=["staged.txt"])
        self.assertEqual(result.outputs.get("error"),
                         "refused_unsafe_commit")
        self.assertEqual(result.outputs.get("reason"), "dirty_working_tree")
        self.assertIn("unrelated.txt", result.outputs.get("dirty_paths", []))

    def test_allow_dirty_with_bypass_reason_succeeds(self):
        (self.tmpdir / "staged.txt").write_text("staged\n")
        (self.tmpdir / "unrelated.txt").write_text("unrelated dirty\n")
        result = self._commit(
            message="x", paths=["staged.txt"],
            allow_dirty=True,
            bypass_reason="unrelated.txt is operator's WIP from a different "
                          "task; intentional to leave dirty for now")
        self.assertEqual(result.outputs.get("status"), "committed")
        bypass = result.outputs["bypass_invoked"]
        self.assertTrue(bypass["allow_dirty"])
        self.assertIn("WIP", bypass["bypass_reason"])

    def test_refuses_protected_branch(self):
        # Switch to main
        subprocess.run(["git", "-C", str(self.tmpdir), "checkout", "-b", "main"],
                       capture_output=True, check=True)
        (self.tmpdir / "x.txt").write_text("x\n")
        result = self._commit(message="x", paths=["x.txt"])
        self.assertEqual(result.outputs.get("error"),
                         "refused_unsafe_commit")
        self.assertEqual(result.outputs.get("reason"), "protected_branch")
        self.assertEqual(result.outputs.get("current_branch"), "main")

    def test_allow_protected_branch_with_bypass_reason_succeeds(self):
        subprocess.run(["git", "-C", str(self.tmpdir), "checkout", "-b", "main"],
                       capture_output=True, check=True)
        (self.tmpdir / "x.txt").write_text("x\n")
        result = self._commit(
            message="x", paths=["x.txt"],
            allow_protected_branch=True,
            bypass_reason="operator-approved direct commit to main for "
                          "v2.9.0 release tag preparation")
        self.assertEqual(result.outputs.get("status"), "committed")
        self.assertTrue(result.outputs["bypass_invoked"]["allow_protected_branch"])

    def test_refuses_bypass_flag_without_reason(self):
        (self.tmpdir / "x.txt").write_text("x\n")
        result = self._commit(
            message="x", paths=["x.txt"], allow_dirty=True)
        self.assertEqual(result.outputs.get("error"),
                         "refused_unsafe_commit")
        self.assertEqual(result.outputs.get("reason"),
                         "bypass_flag_without_reason")

    def test_refuses_bypass_flag_with_empty_reason(self):
        (self.tmpdir / "x.txt").write_text("x\n")
        result = self._commit(
            message="x", paths=["x.txt"],
            allow_dirty=True, bypass_reason="   ")  # whitespace only
        self.assertEqual(result.outputs.get("error"),
                         "refused_unsafe_commit")
        self.assertEqual(result.outputs.get("reason"),
                         "bypass_flag_without_reason")

    def test_missing_message_returns_error(self):
        result = self._commit(paths=["x.txt"])
        self.assertEqual(result.outputs.get("error"),
                         "missing_commit_message")

    def test_missing_paths_returns_error(self):
        result = self._commit(message="x")
        self.assertEqual(result.outputs.get("error"), "missing_paths")

    def test_paths_must_be_a_list(self):
        result = self._commit(message="x", paths="single_path.txt")
        self.assertEqual(result.outputs.get("error"), "missing_paths")

    def test_multi_line_commit_message_preserved(self):
        (self.tmpdir / "x.txt").write_text("x\n")
        msg = ("v2.9.0: test\n\n"
               "Body line one.\n"
               "Body line two with $literal dollar.\n")
        result = self._commit(message=msg, paths=["x.txt"])
        self.assertEqual(result.outputs.get("status"), "committed")
        # Verify the actual commit message in git log
        proc = subprocess.run(
            ["git", "-C", str(self.tmpdir), "log", "-1", "--format=%B"],
            capture_output=True, text=True, check=True)
        self.assertIn("Body line one.", proc.stdout)
        self.assertIn("$literal dollar", proc.stdout)

    def test_custom_protected_branches_via_inputs(self):
        # Use feature/test as protected
        (self.tmpdir / "x.txt").write_text("x\n")
        result = self._commit(
            message="x", paths=["x.txt"],
            protected_branches=["feature/test", "release/*"])
        self.assertEqual(result.outputs.get("error"),
                         "refused_unsafe_commit")
        self.assertEqual(result.outputs.get("reason"), "protected_branch")

    def test_custom_protected_branches_via_env_var(self):
        (self.tmpdir / "x.txt").write_text("x\n")
        old = os.environ.get("FNSR_PROTECTED_BRANCHES")
        os.environ["FNSR_PROTECTED_BRANCHES"] = "feature/test:release"
        try:
            result = self._commit(message="x", paths=["x.txt"])
            self.assertEqual(result.outputs.get("reason"),
                             "protected_branch")
        finally:
            if old is None:
                os.environ.pop("FNSR_PROTECTED_BRANCHES", None)
            else:
                os.environ["FNSR_PROTECTED_BRANCHES"] = old

    def test_commit_sha_resolved_correctly(self):
        (self.tmpdir / "x.txt").write_text("x\n")
        result = self._commit(message="x", paths=["x.txt"])
        sha = result.outputs["commit_sha"]
        # Verify SHA actually exists in repo
        proc = subprocess.run(
            ["git", "-C", str(self.tmpdir), "cat-file", "-e", sha],
            capture_output=True, check=False)
        self.assertEqual(proc.returncode, 0,
                         f"SHA {sha} does not exist in repo")


class TestGitCommitterFailureDiscrimination(unittest.TestCase):
    """Two-class failure discrimination via mocked subprocess.
    Required because triggering pre-commit hook rejection in a tempdir
    sandbox requires setting up hook scripts; mocking is cleaner for
    unit tests."""

    def test_hook_failure_discriminated_from_git_command_failure(self):
        # Simulate hook-failure stderr pattern
        hook_stderr = (
            "pre-commit hook failed:\n"
            "linter: 3 errors found in fnsr_daemon.py\n"
            "fnsr_daemon.py:123:1: E501 line too long\n"
            "hooks/pre-commit returned non-zero exit code 1\n"
        )

        def fake_run(args, **kwargs):
            sub = args[1] if len(args) > 1 else ""
            if sub == "rev-parse" and "--abbrev-ref" in args:
                return MagicMock(returncode=0, stdout="feature/x\n", stderr="")
            if sub == "status":
                return MagicMock(returncode=0, stdout="", stderr="")
            if sub == "add":
                return MagicMock(returncode=0, stdout="", stderr="")
            if sub == "commit":
                return MagicMock(returncode=1, stdout="", stderr=hook_stderr)
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch.object(subprocess, "run", side_effect=fake_run):
            task = {"agent": "git-committer",
                    "inputs": {"message": "x", "paths": ["x.txt"]}}
            result = d._git_committer(task, {})
        self.assertEqual(result.outputs.get("error"), "hook_failure")
        self.assertIn("raw_stderr_tail", result.outputs)
        self.assertIn("linter", result.outputs["raw_stderr_tail"])

    def test_non_hook_git_failure_classified_as_git_command_failure(self):
        # Simulate non-hook commit failure (e.g., nothing to commit)
        generic_err = "nothing to commit, working tree clean\n"

        def fake_run(args, **kwargs):
            sub = args[1] if len(args) > 1 else ""
            if sub == "rev-parse" and "--abbrev-ref" in args:
                return MagicMock(returncode=0, stdout="feature/x\n", stderr="")
            if sub == "status":
                return MagicMock(returncode=0, stdout="", stderr="")
            if sub == "add":
                return MagicMock(returncode=0, stdout="", stderr="")
            if sub == "commit":
                return MagicMock(returncode=1, stdout="", stderr=generic_err)
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch.object(subprocess, "run", side_effect=fake_run):
            task = {"agent": "git-committer",
                    "inputs": {"message": "x", "paths": ["x.txt"]}}
            result = d._git_committer(task, {})
        self.assertEqual(result.outputs.get("error"), "git_command_failure")
        self.assertIn("nothing to commit", result.outputs["raw_stderr_tail"])

    def test_not_a_git_repo_classified_as_git_command_failure(self):
        def fake_run(args, **kwargs):
            if "rev-parse" in args:
                return MagicMock(returncode=128, stdout="",
                                  stderr="not a git repository")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch.object(subprocess, "run", side_effect=fake_run):
            task = {"agent": "git-committer",
                    "inputs": {"message": "x", "paths": ["x.txt"]}}
            result = d._git_committer(task, {})
        self.assertEqual(result.outputs.get("error"), "git_command_failure")
        self.assertEqual(result.outputs.get("reason"),
                         "not_a_git_repo_or_git_unavailable")

    def test_git_add_failure_classified_as_git_command_failure(self):
        def fake_run(args, **kwargs):
            sub = args[1] if len(args) > 1 else ""
            if sub == "rev-parse" and "--abbrev-ref" in args:
                return MagicMock(returncode=0, stdout="feature/x\n", stderr="")
            if sub == "status":
                return MagicMock(returncode=0, stdout="", stderr="")
            if sub == "add":
                return MagicMock(returncode=128, stdout="",
                                  stderr="pathspec 'nope.txt' did not match any files")
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch.object(subprocess, "run", side_effect=fake_run):
            task = {"agent": "git-committer",
                    "inputs": {"message": "x", "paths": ["nope.txt"]}}
            result = d._git_committer(task, {})
        self.assertEqual(result.outputs.get("error"), "git_command_failure")
        self.assertEqual(result.outputs.get("reason"), "git_add_failed")

    def test_hook_discriminator_recognizes_common_patterns(self):
        # Direct test of the heuristic helper
        self.assertTrue(d._git_diff_was_hook_failure(
            "pre-commit hook script returned non-zero"))
        self.assertTrue(d._git_diff_was_hook_failure(
            "hooks/pre-commit: linter failed"))
        self.assertTrue(d._git_diff_was_hook_failure(
            "commit-msg hook rejected: message too short"))
        self.assertFalse(d._git_diff_was_hook_failure(
            "nothing to commit, working tree clean"))
        self.assertFalse(d._git_diff_was_hook_failure(
            "fatal: not a git repository"))


if __name__ == "__main__":
    unittest.main()
