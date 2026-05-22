import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import fnsr_daemon as d
import state_admin


def _seed_state(state_path, tasks):
    state_path.write_text(json.dumps({
        "@context": "https://fnsr.example/context.jsonld",
        "@id": "urn:fnsr:run:test",
        "tasks": tasks,
    }, indent=2), encoding="utf-8")


class TestStateAdmin(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="fnsr-state-admin-"))
        self.state_path = self.tmpdir / "state.jsonld"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _run(self, argv):
        return state_admin.main(argv)

    def test_reset_existing_task(self):
        _seed_state(self.state_path, [
            {"@id": "urn:fnsr:task:001", "agent": "developer",
             "status": "failed", "attempts": 3,
             "outputs": {"changes": [{"id": "C1"}], "summary": "x",
                          "self_assessment": "confident"},
             "depends_on": [], "history": [
                 {"event": "completed", "payload": {},
                  "prev_hash": "0" * 64, "chain_hash": "a" * 64},
             ]},
        ])
        rc = self._run([
            "--state-path", str(self.state_path),
            "reset", "urn:fnsr:task:001", "--reason", "test reset"
        ])
        self.assertEqual(rc, 0)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        t = state["tasks"][0]
        self.assertEqual(t["status"], "ready")
        self.assertEqual(t["attempts"], 0)
        self.assertIsNone(t["outputs"])
        self.assertEqual(len(t["history"]), 2)
        self.assertEqual(t["history"][-1]["event"], "operator_reset")
        self.assertEqual(t["history"][-1]["payload"]["reason"], "test reset")
        # Hash chain integrity
        last_hash = t["history"][-1]["chain_hash"]
        self.assertEqual(t["history"][-1]["prev_hash"], "a" * 64)
        recomputed = d.hiri_sign("a" * 64, {
            "event": "operator_reset",
            "payload": t["history"][-1]["payload"],
        })
        self.assertEqual(last_hash, recomputed)

    def test_reset_missing_task_returns_error(self):
        _seed_state(self.state_path, [])
        rc = self._run([
            "--state-path", str(self.state_path),
            "reset", "urn:fnsr:task:does-not-exist", "--reason", "x"
        ])
        self.assertEqual(rc, 1)

    def test_abandon_with_replaced_by(self):
        _seed_state(self.state_path, [
            {"@id": "urn:fnsr:task:old", "agent": "developer",
             "status": "in_progress", "attempts": 1,
             "outputs": None, "depends_on": [], "history": []},
        ])
        rc = self._run([
            "--state-path", str(self.state_path),
            "abandon", "urn:fnsr:task:old",
            "--reason", "scope too broad",
            "--replaced-by", "urn:fnsr:task:new-a,urn:fnsr:task:new-b",
        ])
        self.assertEqual(rc, 0)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        t = state["tasks"][0]
        self.assertEqual(t["status"], "blocked")
        self.assertEqual(t["history"][-1]["payload"]["replaced_by"],
                         ["urn:fnsr:task:new-a", "urn:fnsr:task:new-b"])

    def test_append_tasks_skips_duplicates(self):
        _seed_state(self.state_path, [
            {"@id": "urn:fnsr:task:existing", "agent": "x",
             "status": "ready", "depends_on": [], "history": []},
        ])
        new_tasks_file = self.tmpdir / "new.json"
        new_tasks_file.write_text(json.dumps([
            {"@id": "urn:fnsr:task:existing", "agent": "x",
             "status": "ready", "depends_on": [], "history": []},
            {"@id": "urn:fnsr:task:fresh", "agent": "y",
             "status": "ready", "depends_on": [], "history": []},
        ]), encoding="utf-8")
        rc = self._run([
            "--state-path", str(self.state_path),
            "append-tasks", str(new_tasks_file),
        ])
        self.assertEqual(rc, 0)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        ids = [t["@id"] for t in state["tasks"]]
        self.assertEqual(len(ids), 2)
        self.assertIn("urn:fnsr:task:fresh", ids)

    def test_verify_pass_on_clean_chain(self):
        # Build a task with a proper hash chain
        task = {"@id": "urn:fnsr:task:t", "agent": "x", "status": "done",
                "depends_on": [], "history": []}
        prev = "0" * 64
        for evt in ("started", "completed"):
            payload = {"info": evt}
            new_hash = d.hiri_sign(prev, {"event": evt, "payload": payload})
            task["history"].append({
                "event": evt, "payload": payload,
                "prev_hash": prev, "chain_hash": new_hash,
            })
            prev = new_hash
        _seed_state(self.state_path, [task])
        rc = self._run([
            "--state-path", str(self.state_path), "verify", "--quiet",
        ])
        self.assertEqual(rc, 0)

    def test_verify_fail_on_broken_chain(self):
        # Same as above but tamper with the second entry's prev_hash
        task = {"@id": "urn:fnsr:task:t", "agent": "x", "status": "done",
                "depends_on": [], "history": [
                    {"event": "started", "payload": {},
                     "prev_hash": "0" * 64, "chain_hash": "a" * 64},
                    {"event": "completed", "payload": {},
                     "prev_hash": "b" * 64,  # WRONG — should be a*64
                     "chain_hash": "c" * 64},
                ]}
        _seed_state(self.state_path, [task])
        rc = self._run([
            "--state-path", str(self.state_path), "verify", "--quiet",
        ])
        self.assertEqual(rc, 1)

    def test_status_filter(self):
        _seed_state(self.state_path, [
            {"@id": "urn:t:1", "status": "done", "depends_on": []},
            {"@id": "urn:t:2", "status": "ready", "depends_on": []},
            {"@id": "urn:t:3", "status": "blocked", "depends_on": []},
            {"@id": "urn:t:4", "status": "ready", "depends_on": []},
        ])
        # Capture stdout
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            rc = self._run([
                "--state-path", str(self.state_path),
                "status", "--filter", "ready",
            ])
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        self.assertEqual(rc, 0)
        self.assertIn("urn:t:2", output)
        self.assertIn("urn:t:4", output)
        self.assertNotIn("urn:t:1", output)
        self.assertNotIn("urn:t:3", output)


class TestResolveCommand(unittest.TestCase):
    """v2.6.0: resolve an `awaiting_operator_decision` task by picking
    one of the agent's surfaced options."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="fnsr-resolve-test-"))
        self.state_path = self.tmpdir / "state.jsonld"

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _seed_awaiting_task(self, options=None, recommendation="prefer A"):
        if options is None:
            options = ["A", "B", "C"]
        _seed_state(self.state_path, [{
            "@id": "urn:fnsr:task:Q1",
            "agent": "architect",
            "status": "awaiting_operator_decision",
            "outputs": {
                "status": "awaiting_operator_decision",
                "options": options,
                "recommendation": recommendation,
            },
            "depends_on": [],
            "attempts": 1,
            "history": [{
                "event": "awaiting_operator_decision",
                "payload": {"options_count": len(options),
                            "recommendation": recommendation},
                "prev_hash": "0" * 64,
                "chain_hash": "a" * 64,
            }],
        }])

    def test_resolve_picks_option_records_audit(self):
        self._seed_awaiting_task()
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "resolve", "urn:fnsr:task:Q1", "--option", "2",
            "--notes", "B has the simpler dependency graph",
        ])
        self.assertEqual(rc, 0)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        t = state["tasks"][0]
        self.assertEqual(t["status"], "done")
        last = t["history"][-1]
        self.assertEqual(last["event"], "operator_resolution")
        self.assertEqual(last["payload"]["chosen_option_index"], 2)
        self.assertEqual(last["payload"]["chosen_option"], "B")
        self.assertEqual(last["payload"]["notes"],
                         "B has the simpler dependency graph")
        # Outputs also annotated for downstream agents
        self.assertEqual(
            t["outputs"]["operator_resolution"]["chosen_option_index"], 2
        )

    def test_resolve_rejects_task_not_awaiting(self):
        _seed_state(self.state_path, [{
            "@id": "urn:fnsr:task:done", "status": "done",
            "depends_on": [], "history": []}])
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "resolve", "urn:fnsr:task:done", "--option", "1",
        ])
        self.assertEqual(rc, 1)

    def test_resolve_rejects_out_of_range_option(self):
        self._seed_awaiting_task(options=["A", "B"])
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "resolve", "urn:fnsr:task:Q1", "--option", "5",
        ])
        self.assertEqual(rc, 1)

    def test_resolve_rejects_zero_option(self):
        self._seed_awaiting_task()
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "resolve", "urn:fnsr:task:Q1", "--option", "0",
        ])
        self.assertEqual(rc, 1)

    def test_resolve_audit_chains_correctly(self):
        # Seed with a properly-chained initial history entry so verify can
        # walk the chain end-to-end after resolve appends its event.
        initial_payload = {"options_count": 3, "recommendation": "A"}
        initial_hash = d.hiri_sign("0" * 64, {
            "event": "awaiting_operator_decision",
            "payload": initial_payload,
        })
        _seed_state(self.state_path, [{
            "@id": "urn:fnsr:task:Q1",
            "agent": "architect",
            "status": "awaiting_operator_decision",
            "outputs": {"status": "awaiting_operator_decision",
                        "options": ["A", "B", "C"],
                        "recommendation": "A"},
            "depends_on": [],
            "attempts": 1,
            "history": [{
                "event": "awaiting_operator_decision",
                "payload": initial_payload,
                "prev_hash": "0" * 64,
                "chain_hash": initial_hash,
            }],
        }])
        state_admin.main([
            "--state-path", str(self.state_path),
            "resolve", "urn:fnsr:task:Q1", "--option", "1",
        ])
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "verify", "--quiet",
        ])
        self.assertEqual(rc, 0)


class TestBankCommand(unittest.TestCase):
    """v2.7.0 `bank` emits event=banking with Spec 05 audit event structure:
    banking_id, category, state, content, transition_history,
    forward_tracked_by, optional surfacing_cycle. v2.6.0's
    --candidate-class flag is still accepted and mapped to Spec 05
    categories per V260_TO_SPEC05_CATEGORY."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="fnsr-bank-test-"))
        self.state_path = self.tmpdir / "state.jsonld"
        _seed_state(self.state_path, [{
            "@id": "urn:fnsr:task:anchor", "agent": "x",
            "status": "done", "depends_on": [], "history": [],
        }])

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_bank_emits_spec05_banking_event(self):
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "bank", "urn:fnsr:task:anchor",
            "--category", "pattern-observation",
            "--content", "observed cascade failure pattern in multi-edit tasks",
            "--cycle", "Q-4-Step5-A",
        ])
        self.assertEqual(rc, 0)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        t = state["tasks"][0]
        self.assertEqual(t["status"], "done")  # unchanged
        self.assertEqual(len(t["history"]), 1)
        evt = t["history"][0]
        self.assertEqual(evt["event"], "banking")
        payload = evt["payload"]
        self.assertEqual(payload["category"], "pattern-observation")
        self.assertEqual(payload["state"], 1)  # default
        self.assertEqual(payload["surfacing_cycle"], "Q-4-Step5-A")
        self.assertIn("cascade", payload["content"])
        # Spec 05 audit event structure: banking_id, transition_history,
        # forward_tracked_by are required.
        self.assertTrue(payload["banking_id"].startswith("bank-"))
        self.assertEqual(payload["forward_tracked_by"], [])
        self.assertEqual(len(payload["transition_history"]), 1)
        self.assertEqual(payload["transition_history"][0]["state"], 1)

    def test_bank_default_category_is_pattern_observation(self):
        # No --category and no --candidate-class -> default
        # pattern-observation per Spec 05.
        state_admin.main([
            "--state-path", str(self.state_path),
            "bank", "urn:fnsr:task:anchor",
            "--content", "<observation>",
        ])
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        evt = state["tasks"][0]["history"][-1]
        self.assertEqual(evt["payload"]["category"], "pattern-observation")

    def test_bank_state_2_partially_committed(self):
        state_admin.main([
            "--state-path", str(self.state_path),
            "bank", "urn:fnsr:task:anchor",
            "--category", "methodology-refinement-candidate",
            "--content", "<observation>",
            "--state", "2",
        ])
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        evt = state["tasks"][0]["history"][-1]
        self.assertEqual(evt["payload"]["state"], 2)
        self.assertEqual(evt["payload"]["transition_history"][0]["state"], 2)

    def test_bank_legacy_candidate_class_maps_to_spec05(self):
        # v2.6.0 back-compat: --candidate-class accepts old taxonomy and
        # maps to Spec 05 category names.
        cases = [
            ("pattern", "pattern-observation"),
            ("methodology", "methodology-refinement-candidate"),
            ("decision", "discipline-correction"),
            ("risk", "methodology-refinement-candidate"),
            ("other", "pattern-observation"),
        ]
        for legacy, expected_spec05 in cases:
            state_admin.main([
                "--state-path", str(self.state_path),
                "bank", "urn:fnsr:task:anchor",
                "--candidate-class", legacy,
                "--content", f"<observation via legacy {legacy}>",
            ])
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        events = state["tasks"][0]["history"]
        self.assertEqual(len(events), len(cases))
        for evt, (legacy, expected_spec05) in zip(events, cases):
            self.assertEqual(evt["payload"]["category"], expected_spec05,
                             f"legacy {legacy!r} should map to {expected_spec05!r}")

    def test_bank_without_cycle_omits_field(self):
        state_admin.main([
            "--state-path", str(self.state_path),
            "bank", "urn:fnsr:task:anchor",
            "--category", "methodology-refinement-candidate",
            "--content", "watch for the X corner case",
        ])
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        evt = state["tasks"][0]["history"][-1]
        self.assertNotIn("surfacing_cycle", evt["payload"])

    def test_bank_chain_integrity_preserved(self):
        state_admin.main([
            "--state-path", str(self.state_path),
            "bank", "urn:fnsr:task:anchor",
            "--category", "methodology-refinement-candidate",
            "--content", "operator-task-splitting pattern worth documenting",
        ])
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "verify", "--quiet",
        ])
        self.assertEqual(rc, 0)

    def test_bank_missing_task_returns_error(self):
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "bank", "urn:fnsr:task:nonexistent",
            "--category", "pattern-observation", "--content", "x",
        ])
        self.assertEqual(rc, 1)

    def test_bank_banking_id_is_unique_per_task(self):
        # Two bankings against the same task should get distinct ids.
        state_admin.main([
            "--state-path", str(self.state_path),
            "bank", "urn:fnsr:task:anchor",
            "--category", "pattern-observation",
            "--content", "first",
        ])
        state_admin.main([
            "--state-path", str(self.state_path),
            "bank", "urn:fnsr:task:anchor",
            "--category", "pattern-observation",
            "--content", "second",
        ])
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        events = state["tasks"][0]["history"]
        self.assertNotEqual(events[0]["payload"]["banking_id"],
                            events[1]["payload"]["banking_id"])


class TestStatusHighlightsAwaiting(unittest.TestCase):
    """v2.6.0: `state_admin status` surfaces awaiting_operator_decision
    tasks at the top, regardless of filter."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="fnsr-status-test-"))
        self.state_path = self.tmpdir / "state.jsonld"
        _seed_state(self.state_path, [
            {"@id": "urn:t:1", "status": "done", "depends_on": []},
            {"@id": "urn:t:2", "status": "awaiting_operator_decision",
             "depends_on": []},
            {"@id": "urn:t:3", "status": "ready", "depends_on": []},
        ])

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_status_surfaces_awaiting_first(self):
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            state_admin.main([
                "--state-path", str(self.state_path), "status",
            ])
            out = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        self.assertIn("!! AWAITING OPERATOR DECISION", out)
        # Awaiting should appear above the other status sections
        awaiting_pos = out.index("AWAITING")
        done_pos = out.index("done")
        ready_pos = out.index("ready")
        self.assertLess(awaiting_pos, done_pos)
        self.assertLess(awaiting_pos, ready_pos)


class TestTransitionBankingCommand(unittest.TestCase):
    """v2.7.0 transition-banking emits a banking_state_transition audit event
    on the same task that hosts the banking. Per Spec 05, this lets the
    substrate operate the banking lifecycle explicitly when the subject
    project elects to (Logic Team operates it implicitly)."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="fnsr-trans-test-"))
        self.state_path = self.tmpdir / "state.jsonld"
        _seed_state(self.state_path, [{
            "@id": "urn:fnsr:task:anchor", "agent": "x",
            "status": "done", "depends_on": [], "history": [],
        }])
        # Create a banking so we can transition it.
        state_admin.main([
            "--state-path", str(self.state_path),
            "bank", "urn:fnsr:task:anchor",
            "--category", "pattern-observation",
            "--content", "test banking for transition",
        ])
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.banking_id = state["tasks"][0]["history"][0]["payload"]["banking_id"]

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_transition_emits_state_transition_event(self):
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "transition-banking", self.banking_id,
            "--to-state", "2",
            "--reason", "pass-2b commit landed",
            "--trigger", "pass_2b_commit_landed",
        ])
        self.assertEqual(rc, 0)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        events = state["tasks"][0]["history"]
        self.assertEqual(events[-1]["event"], "banking_state_transition")
        p = events[-1]["payload"]
        self.assertEqual(p["banking_id"], self.banking_id)
        self.assertEqual(p["from_state"], 1)
        self.assertEqual(p["to_state"], 2)
        self.assertEqual(p["trigger"], "pass_2b_commit_landed")

    def test_transition_chain_integrity_preserved(self):
        state_admin.main([
            "--state-path", str(self.state_path),
            "transition-banking", self.banking_id,
            "--to-state", "3",
            "--reason", "phase-exit doc-pass fold",
            "--trigger", "phase_exit_doc_pass_fold",
        ])
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "verify", "--quiet",
        ])
        self.assertEqual(rc, 0)

    def test_transition_to_same_state_is_noop(self):
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "transition-banking", self.banking_id,
            "--to-state", "1",  # already in state 1
            "--reason", "test", "--trigger", "manual_operator_action",
        ])
        self.assertEqual(rc, 1)

    def test_transition_unknown_banking_returns_error(self):
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "transition-banking", "bank-nope-99",
            "--to-state", "2", "--reason", "test",
            "--trigger", "manual_operator_action",
        ])
        self.assertEqual(rc, 1)

    def test_transition_multi_step_walks_correctly(self):
        # 1 -> 2 -> 3 chain; each transition reads the previous as
        # its "from_state".
        state_admin.main([
            "--state-path", str(self.state_path),
            "transition-banking", self.banking_id,
            "--to-state", "2", "--reason", "step",
            "--trigger", "pass_2b_commit_landed",
        ])
        state_admin.main([
            "--state-path", str(self.state_path),
            "transition-banking", self.banking_id,
            "--to-state", "3", "--reason", "step",
            "--trigger", "phase_exit_doc_pass_fold",
        ])
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        events = state["tasks"][0]["history"]
        # banking + 2 transitions = 3 events
        self.assertEqual(len(events), 3)
        self.assertEqual(events[1]["payload"]["from_state"], 1)
        self.assertEqual(events[1]["payload"]["to_state"], 2)
        self.assertEqual(events[2]["payload"]["from_state"], 2)
        self.assertEqual(events[2]["payload"]["to_state"], 3)


class TestPhaseBoundaryCommand(unittest.TestCase):
    """v2.7.0 phase-boundary emits a phase_boundary_declared audit event
    anchored on a specific task. Substrate is phase-schema-neutral; the
    operator declares the boundary."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="fnsr-phase-test-"))
        self.state_path = self.tmpdir / "state.jsonld"
        _seed_state(self.state_path, [{
            "@id": "urn:fnsr:task:anchor", "agent": "x",
            "status": "done", "depends_on": [], "history": [],
        }])

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_phase_boundary_emits_audit_event(self):
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "phase-boundary", "phase-1", "phase-2",
            "--anchor-task", "urn:fnsr:task:anchor",
            "--notes", "phase-1 exit; phase-2 entry",
        ])
        self.assertEqual(rc, 0)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        evt = state["tasks"][0]["history"][-1]
        self.assertEqual(evt["event"], "phase_boundary_declared")
        self.assertEqual(evt["payload"]["from_phase"], "phase-1")
        self.assertEqual(evt["payload"]["to_phase"], "phase-2")
        self.assertEqual(evt["payload"]["notes"],
                         "phase-1 exit; phase-2 entry")

    def test_phase_boundary_missing_anchor_returns_error(self):
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "phase-boundary", "phase-1", "phase-2",
            "--anchor-task", "urn:fnsr:task:nope",
        ])
        self.assertEqual(rc, 1)

    def test_phase_boundary_chain_integrity_preserved(self):
        state_admin.main([
            "--state-path", str(self.state_path),
            "phase-boundary", "phase-1", "phase-2",
            "--anchor-task", "urn:fnsr:task:anchor",
        ])
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "verify", "--quiet",
        ])
        self.assertEqual(rc, 0)


class TestForwardTrackCreateCommand(unittest.TestCase):
    """v2.7.0 forward-track create emits a Spec 07 audit event with the FULL
    structure (state: A, sub_surface, subject, named_deliberation_cycle,
    phase_origin, inherited_through_phases: [], transition_history:
    [{state: A, ...}]). v2.8.0 transition/list/aging must be able to read
    these without migration."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="fnsr-ft-create-test-"))
        self.state_path = self.tmpdir / "state.jsonld"
        _seed_state(self.state_path, [{
            "@id": "urn:fnsr:task:anchor", "agent": "x",
            "status": "done", "depends_on": [], "history": [],
        }])

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_create_emits_spec07_structured_event(self):
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "create",
            "--anchor-task", "urn:fnsr:task:anchor",
            "--sub-surface", "internal-methodology-refinement",
            "--subject-type", "candidacy",
            "--subject-id", "cat-9-cited-content-consistency",
            "--description", "Cat 9 candidacy from Q-4-Step5-A",
            "--deliberation-cycle", "phase-exit-retro",
            "--phase-origin", "phase-4",
        ])
        self.assertEqual(rc, 0)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        evt = state["tasks"][0]["history"][-1]
        self.assertEqual(evt["event"], "forward_track")
        p = evt["payload"]
        # Spec 07 structure must match EXACTLY, including unused fields.
        self.assertTrue(p["forward_track_id"].startswith("ft-"))
        self.assertEqual(p["state"], "A")
        self.assertEqual(p["sub_surface"], "internal-methodology-refinement")
        self.assertEqual(p["subject"]["type"], "candidacy")
        self.assertEqual(p["subject"]["id"],
                         "cat-9-cited-content-consistency")
        self.assertIn("Cat 9", p["subject"]["description"])
        self.assertEqual(p["named_deliberation_cycle"], "phase-exit-retro")
        self.assertEqual(p["phase_origin"], "phase-4")
        # Empty list, not omitted — Spec 07 requires the field.
        self.assertEqual(p["inherited_through_phases"], [])
        # transition_history seeded with the create.
        self.assertEqual(len(p["transition_history"]), 1)
        self.assertEqual(p["transition_history"][0]["state"], "A")

    def test_create_explicit_ft_id_preserved(self):
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "create",
            "--anchor-task", "urn:fnsr:task:anchor",
            "--sub-surface", "consumer-closure-path",
            "--subject-type", "capability",
            "--subject-id", "feature-v02-x",
            "--description", "v0.2 X capability",
            "--deliberation-cycle", "v0.2-roadmap",
            "--phase-origin", "phase-3",
            "--ft-id", "ft-x-custom-99",
        ])
        self.assertEqual(rc, 0)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        evt = state["tasks"][0]["history"][-1]
        self.assertEqual(evt["payload"]["forward_track_id"],
                         "ft-x-custom-99")

    def test_create_disambiguates_from_v260_legacy_forward_track_events(self):
        # First, seed a v2.6.0-style legacy event (no forward_track_id key).
        # Then create a v2.7.0 Spec 07 forward-track. The two must be
        # distinguishable.
        state_admin.main([
            "--state-path", str(self.state_path),
            "bank", "urn:fnsr:task:anchor",
            "--candidate-class", "pattern",
            "--content", "v2.6.0 legacy banking via --candidate-class",
        ])
        # v2.7.0 bank emits event=banking, NOT event=forward_track.
        # Now create a real forward-track.
        state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "create",
            "--anchor-task", "urn:fnsr:task:anchor",
            "--sub-surface", "internal-methodology-refinement",
            "--subject-type", "banking",
            "--subject-id", "bank-anchor-1",
            "--description", "tracks the bank-anchor-1 banking",
            "--deliberation-cycle", "phase-exit-retro",
            "--phase-origin", "phase-4",
        ])
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        events = state["tasks"][0]["history"]
        # First is the banking; second is the forward-track.
        self.assertEqual(events[0]["event"], "banking")
        self.assertEqual(events[1]["event"], "forward_track")
        self.assertIn("forward_track_id", events[1]["payload"])
        self.assertNotIn("forward_track_id", events[0]["payload"])

    def test_create_with_surfacing_task_id_records_provenance(self):
        # v2.8.0-alpha.3 (Aaron's CP3 observation 3): forward-track
        # create accepts --surfacing-task-id so phase-exit-retro can
        # trace back to the original evidence (e.g., the verification-
        # ritual-llm task whose new_candidacies prompted the creation).
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "create",
            "--anchor-task", "urn:fnsr:task:anchor",
            "--sub-surface", "internal-methodology-refinement",
            "--subject-type", "candidacy",
            "--subject-id", "cat-11-candidacy",
            "--description", "candidacy surfaced by verification-ritual-llm",
            "--deliberation-cycle", "phase-exit-retro",
            "--phase-origin", "phase-4",
            "--surfacing-task-id", "urn:fnsr:task:verify-llm-x",
        ])
        self.assertEqual(rc, 0)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        evt = state["tasks"][0]["history"][-1]
        self.assertEqual(evt["payload"]["surfacing_task_id"],
                         "urn:fnsr:task:verify-llm-x")

    def test_create_without_surfacing_task_id_omits_field(self):
        # --surfacing-task-id is optional; omitting it leaves the
        # field absent from the payload (back-compat with v2.7.0 forward-
        # tracks that didn't have this field).
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "create",
            "--anchor-task", "urn:fnsr:task:anchor",
            "--sub-surface", "consumer-closure-path",
            "--subject-type", "capability",
            "--subject-id", "feat-x",
            "--description", "x",
            "--deliberation-cycle", "v0.2-roadmap",
            "--phase-origin", "phase-3",
        ])
        self.assertEqual(rc, 0)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        evt = state["tasks"][0]["history"][-1]
        self.assertNotIn("surfacing_task_id", evt["payload"])

    def test_create_chain_integrity_preserved(self):
        state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "create",
            "--anchor-task", "urn:fnsr:task:anchor",
            "--sub-surface", "consumer-closure-path",
            "--subject-type", "fixture",
            "--subject-id", "fixture-x",
            "--description", "x fixture commitment",
            "--deliberation-cycle", "v0.2-roadmap",
            "--phase-origin", "phase-3",
        ])
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "verify", "--quiet",
        ])
        self.assertEqual(rc, 0)


class TestForwardTrackInheritCommand(unittest.TestCase):
    """v2.7.0 forward-track inherit walks all Spec 07 forward-track events,
    finds the ones in State A/B whose current phase context matches
    --from-phase, and emits forward_track_phase_inheritance events on
    the same anchor tasks."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="fnsr-ft-inherit-test-"))
        self.state_path = self.tmpdir / "state.jsonld"
        _seed_state(self.state_path, [
            {"@id": "urn:fnsr:task:t1", "agent": "x", "status": "done",
             "depends_on": [], "history": []},
            {"@id": "urn:fnsr:task:t2", "agent": "x", "status": "done",
             "depends_on": [], "history": []},
        ])
        # Create three forward-tracks across the two anchor tasks, all
        # phase_origin=phase-3.
        for anchor, ft_id, sub_surface in [
            ("urn:fnsr:task:t1", "ft-a", "consumer-closure-path"),
            ("urn:fnsr:task:t1", "ft-b", "internal-methodology-refinement"),
            ("urn:fnsr:task:t2", "ft-c", "internal-methodology-refinement"),
        ]:
            state_admin.main([
                "--state-path", str(self.state_path),
                "forward-track", "create",
                "--anchor-task", anchor,
                "--sub-surface", sub_surface,
                "--subject-type", "candidacy",
                "--subject-id", ft_id + "-subj",
                "--description", ft_id + " description",
                "--deliberation-cycle", "phase-exit-retro",
                "--phase-origin", "phase-3",
                "--ft-id", ft_id,
            ])

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_inherit_emits_event_per_unresolved_forward_track(self):
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "inherit",
            "--from-phase", "phase-3",
            "--to-phase", "phase-4",
            "--inherited-at-cycle", "phase-4-entry",
        ])
        self.assertEqual(rc, 0)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        inheritance_events = []
        for t in state["tasks"]:
            for h in t.get("history", []):
                if h["event"] == "forward_track_phase_inheritance":
                    inheritance_events.append(h)
        # 3 forward-tracks, all unresolved, all in phase-3 -> 3 events.
        self.assertEqual(len(inheritance_events), 3)
        for evt in inheritance_events:
            self.assertEqual(evt["payload"]["from_phase"], "phase-3")
            self.assertEqual(evt["payload"]["to_phase"], "phase-4")
            self.assertEqual(evt["payload"]["inherited_at_cycle"],
                             "phase-4-entry")

    def test_inherit_chain_integrity_preserved(self):
        state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "inherit",
            "--from-phase", "phase-3",
            "--to-phase", "phase-4",
            "--inherited-at-cycle", "phase-4-entry",
        ])
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "verify", "--quiet",
        ])
        self.assertEqual(rc, 0)

    def test_inherit_no_matching_forward_tracks_emits_zero_events(self):
        # phase-2 has no forward-tracks
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "inherit",
            "--from-phase", "phase-2",
            "--to-phase", "phase-3",
            "--inherited-at-cycle", "phase-3-entry",
        ])
        self.assertEqual(rc, 0)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        for t in state["tasks"]:
            for h in t.get("history", []):
                self.assertNotEqual(h["event"],
                                    "forward_track_phase_inheritance")

    def test_inherit_does_not_double_inherit(self):
        # First inherit moves phase-3 -> phase-4. A second inherit with
        # the SAME --from-phase should now find zero forward-tracks
        # (because their current phase context is phase-4).
        state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "inherit",
            "--from-phase", "phase-3",
            "--to-phase", "phase-4",
            "--inherited-at-cycle", "phase-4-entry",
        ])
        state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "inherit",
            "--from-phase", "phase-3",
            "--to-phase", "phase-5",
            "--inherited-at-cycle", "phase-5-entry",
        ])
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        # Should still have only 3 inheritance events (the first call),
        # not 6 (which would happen if --from-phase phase-3 matched
        # forward-tracks already inherited).
        count = sum(
            1 for t in state["tasks"]
            for h in t.get("history", [])
            if h["event"] == "forward_track_phase_inheritance"
        )
        self.assertEqual(count, 3)


class TestForwardTrackTransitionCommand(unittest.TestCase):
    """v2.8.0 Checkpoint 4: forward-track transition (Spec 07 lifecycle
    A→B→C with resolution_path on terminal). Pairs with create/inherit
    (CP1/CP2/CP3) to give the operator the full operating surface for
    Spec 07 forward-tracks."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="fnsr-ft-trans-test-"))
        self.state_path = self.tmpdir / "state.jsonld"
        _seed_state(self.state_path, [{
            "@id": "urn:fnsr:task:anchor", "agent": "x",
            "status": "done", "depends_on": [], "history": [],
        }])
        state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "create",
            "--anchor-task", "urn:fnsr:task:anchor",
            "--sub-surface", "internal-methodology-refinement",
            "--subject-type", "candidacy",
            "--subject-id", "cat-9-candidacy",
            "--description", "Cat 9 candidacy from Q-4-Step5-A",
            "--deliberation-cycle", "phase-exit-retro",
            "--phase-origin", "phase-4",
            "--ft-id", "ft-x",
        ])

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_transition_a_to_b(self):
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "transition", "ft-x",
            "--to-state", "B",
            "--reason", "phase-exit retro ran",
            "--trigger", "named_deliberation_cycle_ran",
        ])
        self.assertEqual(rc, 0)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        evt = state["tasks"][0]["history"][-1]
        self.assertEqual(evt["event"], "forward_track_state_transition")
        self.assertEqual(evt["payload"]["from_state"], "A")
        self.assertEqual(evt["payload"]["to_state"], "B")
        self.assertNotIn("resolution_path", evt["payload"])

    def test_transition_b_to_c_with_resolution_path(self):
        state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "transition", "ft-x",
            "--to-state", "B",
            "--reason", "deliberated",
            "--trigger", "named_deliberation_cycle_ran",
        ])
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "transition", "ft-x",
            "--to-state", "C",
            "--reason", "ratified into authoring-discipline doc",
            "--resolution-path", "ratified-into-spec",
        ])
        self.assertEqual(rc, 0)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        evt = state["tasks"][0]["history"][-1]
        self.assertEqual(evt["payload"]["from_state"], "B")
        self.assertEqual(evt["payload"]["to_state"], "C")
        self.assertEqual(evt["payload"]["resolution_path"],
                         "ratified-into-spec")

    def test_transition_to_c_without_resolution_path_returns_error(self):
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "transition", "ft-x",
            "--to-state", "C",
            "--reason", "test",
        ])
        self.assertEqual(rc, 1)

    def test_transition_no_op_when_already_in_state(self):
        # Forward-track was created in State A; transitioning to A again
        # is a no-op.
        # We can't use --to-state A (choices exclude it); so transition
        # to B once, then to B again.
        state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "transition", "ft-x",
            "--to-state", "B", "--reason", "step",
        ])
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "transition", "ft-x",
            "--to-state", "B", "--reason", "no-op repeat",
        ])
        self.assertEqual(rc, 1)

    def test_transition_unknown_ft_id_returns_error(self):
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "transition", "ft-nope",
            "--to-state", "B", "--reason", "x",
        ])
        self.assertEqual(rc, 1)

    def test_transition_chain_integrity_preserved(self):
        state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "transition", "ft-x",
            "--to-state", "B", "--reason", "step",
        ])
        state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "transition", "ft-x",
            "--to-state", "C", "--reason", "resolved",
            "--resolution-path", "withdrawn",
        ])
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "verify", "--quiet",
        ])
        self.assertEqual(rc, 0)


class TestForwardTrackListCommand(unittest.TestCase):
    """v2.8.0 CP4: forward-track list with filters by sub_surface / state
    / phase."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="fnsr-ft-list-test-"))
        self.state_path = self.tmpdir / "state.jsonld"
        _seed_state(self.state_path, [{
            "@id": "urn:fnsr:task:anchor", "agent": "x",
            "status": "done", "depends_on": [], "history": [],
        }])
        for ft_id, sub_surface, phase in [
            ("ft-a", "consumer-closure-path", "phase-3"),
            ("ft-b", "internal-methodology-refinement", "phase-3"),
            ("ft-c", "internal-methodology-refinement", "phase-4"),
        ]:
            state_admin.main([
                "--state-path", str(self.state_path),
                "forward-track", "create",
                "--anchor-task", "urn:fnsr:task:anchor",
                "--sub-surface", sub_surface,
                "--subject-type", "candidacy",
                "--subject-id", ft_id + "-subj",
                "--description", ft_id + " description",
                "--deliberation-cycle", "phase-exit-retro",
                "--phase-origin", phase,
                "--ft-id", ft_id,
            ])

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_list_all_no_filters(self):
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            state_admin.main([
                "--state-path", str(self.state_path),
                "forward-track", "list",
            ])
            out = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        self.assertIn("ft-a", out)
        self.assertIn("ft-b", out)
        self.assertIn("ft-c", out)
        self.assertIn("total: 3", out)

    def test_list_filter_by_sub_surface(self):
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            state_admin.main([
                "--state-path", str(self.state_path),
                "forward-track", "list",
                "--sub-surface", "consumer-closure-path",
            ])
            out = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        self.assertIn("ft-a", out)
        self.assertNotIn("ft-b", out)
        self.assertNotIn("ft-c", out)

    def test_list_filter_by_phase(self):
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            state_admin.main([
                "--state-path", str(self.state_path),
                "forward-track", "list",
                "--phase", "phase-3",
            ])
            out = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        self.assertIn("ft-a", out)
        self.assertIn("ft-b", out)
        self.assertNotIn("ft-c", out)

    def test_list_filter_by_state(self):
        # Transition ft-a to B; filter by state=B should yield only ft-a.
        state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "transition", "ft-a",
            "--to-state", "B", "--reason", "x",
        ])
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            state_admin.main([
                "--state-path", str(self.state_path),
                "forward-track", "list", "--state", "B",
            ])
            out = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        self.assertIn("ft-a", out)
        self.assertNotIn("ft-b", out)
        self.assertNotIn("ft-c", out)

    def test_list_no_matches_returns_message(self):
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            state_admin.main([
                "--state-path", str(self.state_path),
                "forward-track", "list",
                "--state", "C",  # no resolved forward-tracks
            ])
            out = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        self.assertIn("no forward-tracks", out.lower())


class TestForwardTrackAgingCommand(unittest.TestCase):
    """v2.8.0 CP4: forward-track aging emits forward_track_aging_warning
    audit events for forward-tracks inherited through >= threshold
    phases without resolution. Per Aaron's CP4 observation 1: warnings
    are audit-chain events (not just CLI output) so future operators
    can review aging history at phase boundaries."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="fnsr-ft-aging-test-"))
        self.state_path = self.tmpdir / "state.jsonld"
        _seed_state(self.state_path, [{
            "@id": "urn:fnsr:task:anchor", "agent": "x",
            "status": "done", "depends_on": [], "history": [],
        }])
        # Forward-tracks at varying inheritance depths
        for ft_id in ("ft-young", "ft-aged", "ft-resolved"):
            state_admin.main([
                "--state-path", str(self.state_path),
                "forward-track", "create",
                "--anchor-task", "urn:fnsr:task:anchor",
                "--sub-surface", "internal-methodology-refinement",
                "--subject-type", "candidacy",
                "--subject-id", ft_id + "-subj",
                "--description", ft_id,
                "--deliberation-cycle", "phase-exit-retro",
                "--phase-origin", "phase-1",
                "--ft-id", ft_id,
            ])
        # Inherit ft-young once (under threshold of 3)
        state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "inherit",
            "--from-phase", "phase-1", "--to-phase", "phase-2",
            "--inherited-at-cycle", "phase-2-entry",
        ])
        # Inherit ft-aged + ft-resolved through three phases (>= threshold)
        # by walking each individually since the inherit command operates
        # on phase boundaries.
        # ft-young is now in phase-2; ft-aged + ft-resolved also in phase-2.
        # Continue inheritance: phase-2 -> phase-3 -> phase-4
        state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "inherit",
            "--from-phase", "phase-2", "--to-phase", "phase-3",
            "--inherited-at-cycle", "phase-3-entry",
        ])
        state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "inherit",
            "--from-phase", "phase-3", "--to-phase", "phase-4",
            "--inherited-at-cycle", "phase-4-entry",
        ])
        # ft-resolved transitions to state C - should be skipped by aging
        state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "transition", "ft-resolved",
            "--to-state", "C", "--reason", "resolved",
            "--resolution-path", "withdrawn",
        ])

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_aging_warns_above_threshold_skips_resolved(self):
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "aging",
        ])
        self.assertEqual(rc, 0)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        warnings = [
            h for h in state["tasks"][0]["history"]
            if h["event"] == "forward_track_aging_warning"
        ]
        # ft-young inherited only once (3 inheritances total: 1 each
        # for phase-1->2, 2->3, 3->4 — wait, ft-young was created with
        # phase-1 then inherited from phase-1->2 only since the next two
        # inheritances filter on from-phase=2 then from-phase=3 etc.)
        # Actually: all three inherit calls walk from the current phase.
        # ft-young was created in phase-1. After inherit phase-1->2: phase=2.
        # After inherit phase-2->3: phase=3. After inherit phase-3->4: phase=4.
        # So ft-young inheritance_count = 3.
        # ft-aged created phase-1, same inheritance path = 3 inheritances.
        # ft-resolved same = 3 inheritances, then state C — skipped.
        # threshold default = 3; ft-young and ft-aged both warned.
        warned_ids = {w["payload"]["forward_track_id"] for w in warnings}
        self.assertIn("ft-young", warned_ids)
        self.assertIn("ft-aged", warned_ids)
        self.assertNotIn("ft-resolved", warned_ids)

    def test_aging_threshold_flag_overrides_default(self):
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "aging",
            "--threshold", "99",  # nothing meets this threshold
        ])
        self.assertEqual(rc, 0)
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        warnings = [
            h for h in state["tasks"][0]["history"]
            if h["event"] == "forward_track_aging_warning"
        ]
        self.assertEqual(len(warnings), 0)

    def test_aging_env_var_threshold(self):
        # FNSR_FORWARD_TRACK_AGING_THRESHOLD_PHASES env var
        old_env = os.environ.get("FNSR_FORWARD_TRACK_AGING_THRESHOLD_PHASES")
        os.environ["FNSR_FORWARD_TRACK_AGING_THRESHOLD_PHASES"] = "99"
        try:
            rc = state_admin.main([
                "--state-path", str(self.state_path),
                "forward-track", "aging",
            ])
            self.assertEqual(rc, 0)
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            warnings = [
                h for h in state["tasks"][0]["history"]
                if h["event"] == "forward_track_aging_warning"
            ]
            self.assertEqual(len(warnings), 0)
        finally:
            if old_env is None:
                del os.environ["FNSR_FORWARD_TRACK_AGING_THRESHOLD_PHASES"]
            else:
                os.environ["FNSR_FORWARD_TRACK_AGING_THRESHOLD_PHASES"] = old_env

    def test_aging_warning_payload_has_required_fields(self):
        state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "aging",
        ])
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        warnings = [
            h for h in state["tasks"][0]["history"]
            if h["event"] == "forward_track_aging_warning"
        ]
        self.assertTrue(len(warnings) > 0)
        for w in warnings:
            p = w["payload"]
            self.assertIn("forward_track_id", p)
            self.assertIn("inheritance_count", p)
            self.assertIn("threshold", p)
            self.assertIn("current_state", p)
            self.assertIn("timestamp", p)

    def test_aging_chain_integrity_preserved(self):
        state_admin.main([
            "--state-path", str(self.state_path),
            "forward-track", "aging",
        ])
        rc = state_admin.main([
            "--state-path", str(self.state_path),
            "verify", "--quiet",
        ])
        self.assertEqual(rc, 0)


class TestTemplateSyncCommand(unittest.TestCase):
    """v2.9.0 template-sync command: deterministic substrate-shared file
    sync from source repo to target repo(s), with verify and sync modes,
    custom manifest support, and idempotency."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="fnsr-tsync-test-"))
        self.source = self.tmpdir / "source"
        self.target_a = self.tmpdir / "target_a"
        self.target_b = self.tmpdir / "target_b"
        for p in (self.source, self.target_a, self.target_b):
            p.mkdir(parents=True)
        (self.source / "fnsr_daemon.py").write_text(
            "# source content\n", encoding="utf-8")
        (self.source / "PLAYBOOK.md").write_text(
            "# source playbook\n", encoding="utf-8")
        (self.source / "tests").mkdir()
        (self.source / "tests" / "test_x.py").write_text(
            "# source test\n", encoding="utf-8")
        # Manifest file pointing at these three
        self.manifest_path = self.tmpdir / "manifest.txt"
        self.manifest_path.write_text(
            "# test manifest\n"
            "fnsr_daemon.py\n"
            "PLAYBOOK.md\n"
            "tests/test_x.py\n",
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_verify_mode_clean_when_targets_match(self):
        # Pre-populate targets with matching content
        for t in (self.target_a, self.target_b):
            (t / "fnsr_daemon.py").write_text("# source content\n",
                                                encoding="utf-8")
            (t / "PLAYBOOK.md").write_text("# source playbook\n",
                                             encoding="utf-8")
            (t / "tests").mkdir()
            (t / "tests" / "test_x.py").write_text("# source test\n",
                                                     encoding="utf-8")
        rc = state_admin.main([
            "template-sync",
            "--source", str(self.source),
            "--targets", f"{self.target_a},{self.target_b}",
            "--manifest", str(self.manifest_path),
            "--mode", "verify",
        ])
        self.assertEqual(rc, 0)

    def test_verify_mode_reports_drift_when_target_differs(self):
        (self.target_a / "fnsr_daemon.py").write_text("# DIFFERENT\n",
                                                       encoding="utf-8")
        rc = state_admin.main([
            "template-sync",
            "--source", str(self.source),
            "--targets", str(self.target_a),
            "--manifest", str(self.manifest_path),
            "--mode", "verify",
        ])
        self.assertEqual(rc, 1)  # drift detected

    def test_verify_mode_reports_drift_when_target_missing(self):
        # target_a lacks the source files entirely
        rc = state_admin.main([
            "template-sync",
            "--source", str(self.source),
            "--targets", str(self.target_a),
            "--manifest", str(self.manifest_path),
            "--mode", "verify",
        ])
        self.assertEqual(rc, 1)

    def test_sync_mode_copies_source_to_target(self):
        rc = state_admin.main([
            "template-sync",
            "--source", str(self.source),
            "--targets", str(self.target_a),
            "--manifest", str(self.manifest_path),
            "--mode", "sync",
        ])
        self.assertEqual(rc, 0)
        for rel in ("fnsr_daemon.py", "PLAYBOOK.md", "tests/test_x.py"):
            src_text = (self.source / rel).read_text(encoding="utf-8")
            tgt_text = (self.target_a / rel).read_text(encoding="utf-8")
            self.assertEqual(src_text, tgt_text)

    def test_sync_mode_creates_parent_dirs(self):
        # target_b lacks the tests/ subdirectory; sync should create it
        rc = state_admin.main([
            "template-sync",
            "--source", str(self.source),
            "--targets", str(self.target_b),
            "--manifest", str(self.manifest_path),
            "--mode", "sync",
        ])
        self.assertEqual(rc, 0)
        self.assertTrue((self.target_b / "tests" / "test_x.py").exists())

    def test_sync_mode_idempotent_second_run_unchanged(self):
        state_admin.main([
            "template-sync",
            "--source", str(self.source),
            "--targets", str(self.target_a),
            "--manifest", str(self.manifest_path),
            "--mode", "sync",
        ])
        # Second run should report unchanged + clean exit
        rc = state_admin.main([
            "template-sync",
            "--source", str(self.source),
            "--targets", str(self.target_a),
            "--manifest", str(self.manifest_path),
            "--mode", "verify",
        ])
        self.assertEqual(rc, 0)

    def test_missing_source_file_returns_exit_code_2(self):
        # Manifest references a file that doesn't exist in source
        manifest_with_missing = self.tmpdir / "manifest_missing.txt"
        manifest_with_missing.write_text(
            "fnsr_daemon.py\nnonexistent_in_source.md\n", encoding="utf-8")
        rc = state_admin.main([
            "template-sync",
            "--source", str(self.source),
            "--targets", str(self.target_a),
            "--manifest", str(manifest_with_missing),
            "--mode", "sync",
        ])
        self.assertEqual(rc, 2)

    def test_manifest_comments_and_blanks_ignored(self):
        manifest = self.tmpdir / "manifest_comments.txt"
        manifest.write_text(
            "# top-level comment\n"
            "\n"
            "fnsr_daemon.py\n"
            "  # indented comment\n"
            "PLAYBOOK.md\n"
            "\n",
            encoding="utf-8",
        )
        rc = state_admin.main([
            "template-sync",
            "--source", str(self.source),
            "--targets", str(self.target_a),
            "--manifest", str(manifest),
            "--mode", "sync",
        ])
        # Should sync 2 files (fnsr_daemon.py + PLAYBOOK.md) without
        # treating "# top-level comment" or "  # indented comment" as paths
        self.assertEqual(rc, 0)
        self.assertTrue((self.target_a / "fnsr_daemon.py").exists())
        self.assertTrue((self.target_a / "PLAYBOOK.md").exists())

    def test_env_var_manifest_override(self):
        old = os.environ.get("FNSR_TEMPLATE_SYNC_MANIFEST")
        os.environ["FNSR_TEMPLATE_SYNC_MANIFEST"] = str(self.manifest_path)
        try:
            rc = state_admin.main([
                "template-sync",
                "--source", str(self.source),
                "--targets", str(self.target_a),
                "--mode", "sync",
            ])
            self.assertEqual(rc, 0)
        finally:
            if old is None:
                os.environ.pop("FNSR_TEMPLATE_SYNC_MANIFEST", None)
            else:
                os.environ["FNSR_TEMPLATE_SYNC_MANIFEST"] = old

    def test_multiple_targets_synced_in_one_invocation(self):
        rc = state_admin.main([
            "template-sync",
            "--source", str(self.source),
            "--targets", f"{self.target_a},{self.target_b}",
            "--manifest", str(self.manifest_path),
            "--mode", "sync",
        ])
        self.assertEqual(rc, 0)
        # Both targets should have all three source files
        for t in (self.target_a, self.target_b):
            for rel in ("fnsr_daemon.py", "PLAYBOOK.md", "tests/test_x.py"):
                self.assertTrue((t / rel).exists(),
                                 f"{rel} missing from {t.name}")

    def test_no_targets_returns_error(self):
        rc = state_admin.main([
            "template-sync",
            "--source", str(self.source),
            "--targets", "",
            "--manifest", str(self.manifest_path),
        ])
        self.assertEqual(rc, 1)

    def test_default_manifest_is_substrate_shared_files(self):
        # Confirm the default manifest constant exists + contains the
        # substrate-shared files per the dual-track-workflow memory.
        default = state_admin._DEFAULT_TEMPLATE_SYNC_MANIFEST
        self.assertIn("fnsr_daemon.py", default)
        self.assertIn("state_admin.py", default)
        self.assertIn("PLAYBOOK.md", default)
        # Should include test-runner.md (v2.9.0)
        self.assertIn(".claude/agents/test-runner.md", default)


if __name__ == "__main__":
    unittest.main()
