import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fnsr_daemon as d


class TestReconcileInProgress(unittest.TestCase):
    def test_revives_in_progress_tasks(self):
        state = {"tasks": [
            {"@id": "urn:t:done", "status": "done", "attempts": 1,
             "history": [{"event": "completed", "payload": {},
                          "prev_hash": "0" * 64, "chain_hash": "a" * 64}]},
            {"@id": "urn:t:stuck1", "status": "in_progress", "attempts": 2,
             "history": [{"event": "attempt_failed", "payload": {},
                          "prev_hash": "0" * 64, "chain_hash": "b" * 64}]},
            {"@id": "urn:t:stuck2", "status": "in_progress", "attempts": 1,
             "history": []},
            {"@id": "urn:t:ready", "status": "ready", "attempts": 0,
             "history": []},
        ]}
        n = d._reconcile_in_progress(state)
        self.assertEqual(n, 2)
        statuses = {t["@id"]: t["status"] for t in state["tasks"]}
        self.assertEqual(statuses["urn:t:stuck1"], "ready")
        self.assertEqual(statuses["urn:t:stuck2"], "ready")
        self.assertEqual(statuses["urn:t:done"], "done")
        self.assertEqual(statuses["urn:t:ready"], "ready")

    def test_preserves_attempts(self):
        state = {"tasks": [
            {"@id": "urn:t:s", "status": "in_progress", "attempts": 2,
             "history": []},
        ]}
        d._reconcile_in_progress(state)
        self.assertEqual(state["tasks"][0]["attempts"], 2)

    def test_appends_audit_entry_chained(self):
        state = {"tasks": [
            {"@id": "urn:t:s", "status": "in_progress", "attempts": 1,
             "history": [{"event": "attempt_failed", "payload": {},
                          "prev_hash": "0" * 64, "chain_hash": "b" * 64}]},
        ]}
        d._reconcile_in_progress(state)
        task = state["tasks"][0]
        self.assertEqual(len(task["history"]), 2)
        self.assertEqual(task["history"][-1]["event"],
                         "recovered_from_in_progress")
        self.assertEqual(task["history"][-1]["prev_hash"], "b" * 64)


class TestDaemonLock(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="fnsr-lock-test-")
        self._orig_path = d.DAEMON_PID_PATH
        d.DAEMON_PID_PATH = Path(self.tmpdir) / "test.pid"

    def tearDown(self):
        d.DAEMON_PID_PATH = self._orig_path
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_first_lock_succeeds(self):
        f = d._acquire_daemon_lock()
        self.assertIsNotNone(f)
        f.close()

    def test_second_lock_blocked_while_first_held(self):
        f1 = d._acquire_daemon_lock()
        self.assertIsNotNone(f1)
        f2 = d._acquire_daemon_lock()
        self.assertIsNone(f2)
        f1.close()

    def test_relock_after_release(self):
        f1 = d._acquire_daemon_lock()
        f1.close()
        f2 = d._acquire_daemon_lock()
        self.assertIsNotNone(f2)
        f2.close()

    def test_pid_written_to_lock_file(self):
        f = d._acquire_daemon_lock()
        # Release the OS lock before reading (msvcrt on Windows blocks
        # reads from a separate handle while the byte-range lock is held).
        f.close()
        pid_path = Path(self.tmpdir) / "test.pid"
        self.assertEqual(pid_path.read_text().strip(), str(os.getpid()))


if __name__ == "__main__":
    unittest.main()
