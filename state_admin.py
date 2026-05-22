"""Operator utilities for state.jsonld manipulation.

Replaces the ad-hoc one-off Python scripts operators wrote to reset failed
tasks, abandon failing chains, append new tasks, or verify audit-chain
integrity. Every modification preserves the SHA-256 hash chain by routing
through fnsr_daemon's `hiri_sign` and `_last_hash` helpers.

v2.6.0 surface:
    python state_admin.py reset <task_id> --reason "..." [--operator NAME]
    python state_admin.py abandon <task_id> --reason "..." \\
        [--replaced-by id1,id2,id3] [--operator NAME]
    python state_admin.py append-tasks <json-file>
    python state_admin.py verify [--quiet]
    python state_admin.py status [--filter STATUS]
    python state_admin.py resolve <task_id> --option N [--notes "..."]
    python state_admin.py bank <task_id> --content "..." \\
        [--category CAT] [--state N] [--cycle N]
                # v2.6.0 also accepted --candidate-class (legacy);
                # see cmd_bank for the v2.6.0 -> Spec 05 category mapping.

v2.7.0 additions (Pass 2a sequencing + banking lifecycle per FNSR Specs 03/05/07):
    python state_admin.py transition-banking <banking_id> --to-state N \\
        --reason "..." [--transitioning-cycle CYCLE]
    python state_admin.py phase-boundary <from_phase> <to_phase> \\
        --anchor-task <task_id> [--declared-by NAME]
    python state_admin.py forward-track create --anchor-task <task_id> \\
        --sub-surface {consumer-closure-path|internal-methodology-refinement} \\
        --subject-type {banking|fixture|capability|candidacy|other} \\
        --subject-id <id> --description "..." \\
        --deliberation-cycle <cycle-id> --phase-origin <phase-id> \\
        [--ft-id <ft-id>]
    python state_admin.py forward-track inherit --from-phase <id> \\
        --to-phase <id> --inherited-at-cycle <cycle-id>

All commands operate on `state.jsonld` in the current directory by default;
pass `--state-path PATH` to override. STOP THE DAEMON before modifying state
to avoid race conditions on the lock file.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

# Import daemon helpers from sibling module
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))
import fnsr_daemon as d


def _load_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        raise SystemExit(f"state file not found: {state_path}")
    with open(state_path, encoding="utf-8") as f:
        return json.load(f)


def _save_state(state_path: Path, state: dict[str, Any]) -> None:
    tmp = state_path.with_suffix(state_path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, state_path)


def _find_task(state: dict[str, Any], task_id: str) -> Optional[dict[str, Any]]:
    for t in state.get("tasks", []):
        if t.get("@id") == task_id:
            return t
    return None


def _append_audit(task: dict[str, Any], event: str,
                  payload: dict[str, Any]) -> None:
    """Append an audit entry chained from the task's last hash. Mutates task
    in place. Uses fnsr_daemon's hiri_sign so the chain is verifiable by
    the existing daemon-side audit-integrity check."""
    prev_hash = d._last_hash(task)
    new_hash = d.hiri_sign(prev_hash, {"event": event, "payload": payload})
    task.setdefault("history", []).append({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": event,
        "payload": payload,
        "prev_hash": prev_hash,
        "chain_hash": new_hash,
    })


# ---------- Commands ----------------------------------------------------

def cmd_reset(args: argparse.Namespace) -> int:
    """Reset a task to status=ready, clearing attempts and outputs. Adds an
    operator_reset audit entry recording the reason."""
    state_path = Path(args.state_path)
    state = _load_state(state_path)
    task = _find_task(state, args.task_id)
    if task is None:
        print(f"task not found: {args.task_id}", file=sys.stderr)
        return 1
    old_status = task.get("status")
    old_attempts = task.get("attempts", 0)
    payload = {
        "reason": args.reason,
        "reset_fields": {
            "status": f"{old_status} -> ready",
            "attempts": f"{old_attempts} -> 0",
            "outputs": "cleared",
        },
        "operator": args.operator,
    }
    _append_audit(task, "operator_reset", payload)
    task["status"] = "ready"
    task["attempts"] = 0
    task["outputs"] = None
    _save_state(state_path, state)
    print(f"reset: {args.task_id}  (was status={old_status}, attempts={old_attempts})")
    return 0


def cmd_abandon(args: argparse.Namespace) -> int:
    """Mark a task as blocked with an operator_reset audit entry. Used when
    a task's scope is wrong and operator is replacing it with new tasks."""
    state_path = Path(args.state_path)
    state = _load_state(state_path)
    task = _find_task(state, args.task_id)
    if task is None:
        print(f"task not found: {args.task_id}", file=sys.stderr)
        return 1
    payload: dict[str, Any] = {
        "reason": args.reason,
        "reset_fields": {"status": f"{task.get('status')} -> blocked (abandoned)"},
        "operator": args.operator,
    }
    if args.replaced_by:
        payload["replaced_by"] = [
            x.strip() for x in args.replaced_by.split(",") if x.strip()
        ]
    _append_audit(task, "operator_reset", payload)
    task["status"] = "blocked"
    _save_state(state_path, state)
    print(f"abandoned: {args.task_id}  (status now blocked)")
    if payload.get("replaced_by"):
        print(f"  replaced by: {', '.join(payload['replaced_by'])}")
    return 0


def cmd_append_tasks(args: argparse.Namespace) -> int:
    """Append new tasks from a JSON file to state.jsonld. The JSON file
    must contain either a list of task objects or an object with a "tasks"
    key. IDs that already exist in state.jsonld are skipped (no overwrite)."""
    state_path = Path(args.state_path)
    state = _load_state(state_path)
    src = Path(args.tasks_file)
    if not src.exists():
        print(f"tasks file not found: {src}", file=sys.stderr)
        return 1
    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    new_tasks = data.get("tasks", data) if isinstance(data, dict) else data
    if not isinstance(new_tasks, list):
        print("tasks file must contain a list or an object with `tasks` key",
              file=sys.stderr)
        return 1
    existing = {t["@id"] for t in state.get("tasks", [])}
    added = 0
    skipped = 0
    for nt in new_tasks:
        if not isinstance(nt, dict) or "@id" not in nt:
            print(f"skipping malformed task: {nt!r}", file=sys.stderr)
            continue
        if nt["@id"] in existing:
            skipped += 1
            continue
        state["tasks"].append(nt)
        added += 1
    _save_state(state_path, state)
    print(f"appended {added} task(s); skipped {skipped} duplicate(s)")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify audit-chain integrity across all tasks' history. Re-derives
    each entry's chain_hash from prev_hash + event + payload via hiri_sign
    and reports any mismatch or chain break."""
    state_path = Path(args.state_path)
    state = _load_state(state_path)
    ok = True
    total_entries = 0
    for t in state.get("tasks", []):
        prev = "0" * 64
        for i, h in enumerate(t.get("history", [])):
            total_entries += 1
            if h.get("prev_hash") != prev:
                ok = False
                print(f"BREAK  {t['@id']}  history[{i}]  prev_hash mismatch "
                      f"(expected {prev[:16]}..., got "
                      f"{(h.get('prev_hash') or 'missing')[:16]}...)",
                      file=sys.stderr)
                break
            recomputed = d.hiri_sign(
                prev, {"event": h["event"], "payload": h["payload"]}
            )
            actual = h.get("chain_hash") or h.get("hash")
            if recomputed != actual:
                ok = False
                print(f"MISMATCH  {t['@id']}  history[{i}]  chain_hash mismatch "
                      f"(recomputed {recomputed[:16]}..., stored "
                      f"{(actual or 'missing')[:16]}...)", file=sys.stderr)
                break
            prev = recomputed
    if not args.quiet:
        print(f"verified {total_entries} audit entries across "
              f"{len(state.get('tasks', []))} tasks: "
              f"{'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def cmd_status(args: argparse.Namespace) -> int:
    """Print task statuses. Optional --filter STATUS to show only one bucket.
    `awaiting_operator_decision` tasks are surfaced at the top regardless of
    filter so operators don't miss them."""
    state_path = Path(args.state_path)
    state = _load_state(state_path)
    by_status: dict[str, list[str]] = {}
    for t in state.get("tasks", []):
        by_status.setdefault(t.get("status", "?"), []).append(t["@id"])
    if args.filter:
        ids = by_status.get(args.filter, [])
        for tid in ids:
            print(tid)
        return 0
    # Surface awaiting_operator_decision at the top — operators must see it
    awaiting = by_status.pop("awaiting_operator_decision", [])
    if awaiting:
        print(f"!! AWAITING OPERATOR DECISION ({len(awaiting)}):")
        for tid in awaiting:
            print(f"  {tid}")
            print(f"    resolve: python state_admin.py resolve {tid} --option N")
        print()
    for status, ids in sorted(by_status.items()):
        print(f"{status} ({len(ids)}):")
        for tid in ids:
            print(f"  {tid}")
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    """Resolve an `awaiting_operator_decision` task by picking one of the
    options the agent surfaced. Records the operator_resolution audit event,
    annotates the task's outputs with the chosen option, and marks the task
    done so downstream chain dependencies advance.

    The chosen ADR (if the operator wants one drafted) is the operator's
    next step — queue a question-resolver task with the resolution as a
    structured answer, or edit DECISIONS.md directly.
    """
    state_path = Path(args.state_path)
    state = _load_state(state_path)
    task = _find_task(state, args.task_id)
    if task is None:
        print(f"task not found: {args.task_id}", file=sys.stderr)
        return 1
    if task.get("status") != "awaiting_operator_decision":
        print(f"task {args.task_id} status is {task.get('status')!r}, "
              f"not awaiting_operator_decision", file=sys.stderr)
        return 1
    outputs = task.get("outputs") or {}
    options = outputs.get("options")
    if not isinstance(options, list) or not options:
        print(f"task {args.task_id} has no options to resolve", file=sys.stderr)
        return 1
    if args.option < 1 or args.option > len(options):
        print(f"option {args.option} out of range; task has {len(options)} "
              f"option(s)", file=sys.stderr)
        return 1
    chosen_option = options[args.option - 1]
    payload = {
        "chosen_option_index": args.option,
        "chosen_option": chosen_option,
        "operator": args.operator,
    }
    if args.notes:
        payload["notes"] = args.notes
    _append_audit(task, "operator_resolution", payload)
    # Annotate outputs with the resolution so downstream agents reading
    # via UPSTREAM see the resolved choice
    if isinstance(task.get("outputs"), dict):
        task["outputs"]["operator_resolution"] = payload
    task["status"] = "done"
    _save_state(state_path, state)
    print(f"resolved: {args.task_id}  (option {args.option} of "
          f"{len(options)})")
    return 0


# v2.7.0 Spec 05 banking category set (closed enumeration; Spec 05 §"Banking taxonomy")
SPEC05_CATEGORIES = (
    "methodology-refinement-candidate",
    "pattern-observation",
    "discipline-correction",
    "contingency-operationalization",
    "discipline-state-transition-observation",
)

# v2.6.0 --candidate-class -> Spec 05 --category back-compat mapping
V260_TO_SPEC05_CATEGORY = {
    "pattern": "pattern-observation",
    "methodology": "methodology-refinement-candidate",
    "decision": "discipline-correction",
    "risk": "methodology-refinement-candidate",
    "other": "pattern-observation",
}


def _resolve_banking_category(args: argparse.Namespace) -> str:
    """Resolve --category (Spec 05) given the caller may have passed
    --candidate-class (v2.6.0 legacy). v2.6.0 values are mapped to their
    Spec 05 equivalents per V260_TO_SPEC05_CATEGORY."""
    if args.category:
        return args.category
    if args.candidate_class:
        return V260_TO_SPEC05_CATEGORY.get(args.candidate_class, args.candidate_class)
    return "pattern-observation"


def _banking_id(task: dict[str, Any]) -> str:
    """Generate a banking_id stable to the anchor task + sequence within
    the task's history. Format: bank-<task-id-tail>-<sequence>."""
    task_id = task.get("@id", "unknown")
    task_tail = task_id.rsplit(":", 1)[-1]
    sequence = sum(
        1 for h in task.get("history", [])
        if h.get("event") in ("banking", "forward_track")
    )
    return f"bank-{task_tail}-{sequence + 1}"


def cmd_bank(args: argparse.Namespace) -> int:
    """Record a banking audit event against a task per Spec 05.

    v2.6.0 emitted event=forward_track with --candidate-class payload.
    v2.7.0+ emits event=banking with the Spec 05 audit event structure
    (banking_id, category, state, surfacing_cycle, content,
    transition_history, forward_tracked_by). Legacy --candidate-class
    is still accepted and mapped to the closest Spec 05 category; the
    v2.6.0 audit events already in the chain remain untouched and are
    read as legacy bankings by downstream consumers.

    Spec 05 §"Important: this spec corrects the original directive":
    bankings have a three-state lifecycle (verbal-pending ->
    partially-committed -> formalized). New bankings default to State 1
    (verbal-pending) unless --state overrides.
    """
    state_path = Path(args.state_path)
    state = _load_state(state_path)
    task = _find_task(state, args.task_id)
    if task is None:
        print(f"task not found: {args.task_id}", file=sys.stderr)
        return 1
    category = _resolve_banking_category(args)
    if category not in SPEC05_CATEGORIES:
        print(f"warning: category {category!r} is not a Spec 05 category; "
              f"accepted but downstream readers may not classify it correctly",
              file=sys.stderr)
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    banking_id = args.banking_id or _banking_id(task)
    transition_entry: dict[str, Any] = {
        "state": args.state,
        "timestamp": timestamp,
    }
    if args.cycle is not None:
        transition_entry["transitioning_cycle"] = args.cycle
    payload: dict[str, Any] = {
        "banking_id": banking_id,
        "category": category,
        "state": args.state,
        "content": args.content,
        "transition_history": [transition_entry],
        "forward_tracked_by": [],
        "operator": args.operator,
    }
    if args.cycle is not None:
        payload["surfacing_cycle"] = args.cycle
    _append_audit(task, "banking", payload)
    _save_state(state_path, state)
    print(f"banked: {args.task_id}  banking_id={banking_id}  "
          f"category={category}  state={args.state}"
          + (f"  cycle={args.cycle}" if args.cycle is not None else ""))
    return 0


def _find_banking(state: dict[str, Any], banking_id: str) \
        -> Optional[tuple[dict[str, Any], dict[str, Any]]]:
    """Locate a banking event by banking_id across all task histories.
    Returns (task, event_entry) on hit, or None.

    Accepts BOTH v2.7.0+ event=banking events AND v2.6.0 legacy
    event=forward_track events (when their payload contains a
    banking_id field). v2.6.0 events without banking_id are not
    findable here; the operator must transition them by hand if needed.
    """
    for t in state.get("tasks", []):
        for h in t.get("history", []):
            payload = h.get("payload") or {}
            if h.get("event") in ("banking", "forward_track") and \
                    payload.get("banking_id") == banking_id:
                return (t, h)
    return None


def _banking_current_state(task: dict[str, Any], banking_id: str) -> Optional[int]:
    """Compute a banking's current lifecycle state by walking the task's
    history. Returns the latest state from a transition event, or the
    initial state from the create event, or None if not found."""
    current = None
    for h in task.get("history", []):
        payload = h.get("payload") or {}
        if payload.get("banking_id") != banking_id:
            continue
        if h.get("event") == "banking" or h.get("event") == "forward_track":
            current = payload.get("state", 1)
        elif h.get("event") == "banking_state_transition":
            current = payload.get("to_state", current)
    return current


def cmd_transition_banking(args: argparse.Namespace) -> int:
    """Transition a banking to a new lifecycle state per Spec 05.

    Emits a banking_state_transition audit event on the SAME task that
    hosts the banking's create event. The substrate is neutral about
    whether the subject project operates the lifecycle implicitly
    (no transition events, reconciliation at phase-exit doc-pass) or
    explicitly (per-transition events); this command is for the
    explicit-mode operators.
    """
    state_path = Path(args.state_path)
    state = _load_state(state_path)
    found = _find_banking(state, args.banking_id)
    if found is None:
        print(f"banking not found: {args.banking_id}", file=sys.stderr)
        return 1
    task, _create_event = found
    current_state = _banking_current_state(task, args.banking_id)
    if current_state is None:
        print(f"banking {args.banking_id} has no resolvable state",
              file=sys.stderr)
        return 1
    if current_state == args.to_state:
        print(f"banking {args.banking_id} already at state {current_state}; "
              f"no-op", file=sys.stderr)
        return 1
    payload: dict[str, Any] = {
        "banking_id": args.banking_id,
        "from_state": current_state,
        "to_state": args.to_state,
        "trigger": args.trigger,
        "reason": args.reason,
        "operator": args.operator,
    }
    if args.transitioning_cycle:
        payload["transitioning_cycle"] = args.transitioning_cycle
    _append_audit(task, "banking_state_transition", payload)
    _save_state(state_path, state)
    print(f"transitioned: {args.banking_id}  "
          f"state {current_state} -> {args.to_state}")
    return 0


def cmd_phase_boundary(args: argparse.Namespace) -> int:
    """Emit a phase_boundary_declared audit event.

    Phases are subject-project concepts, not substrate primitives. This
    command lets the operator declare a phase transition as a first-class
    audit event without coupling the substrate to a phase schema. The
    event anchors to a specific task (operator picks; typically the last
    task of from_phase or the first task of to_phase).

    Pair with `forward-track inherit` to bulk-inherit unresolved
    forward-tracks across the boundary.
    """
    state_path = Path(args.state_path)
    state = _load_state(state_path)
    task = _find_task(state, args.anchor_task)
    if task is None:
        print(f"anchor task not found: {args.anchor_task}", file=sys.stderr)
        return 1
    payload: dict[str, Any] = {
        "from_phase": args.from_phase,
        "to_phase": args.to_phase,
        "declared_by": args.declared_by,
    }
    if args.cycle:
        payload["cycle"] = args.cycle
    if args.notes:
        payload["notes"] = args.notes
    _append_audit(task, "phase_boundary_declared", payload)
    _save_state(state_path, state)
    print(f"phase-boundary: {args.from_phase} -> {args.to_phase}  "
          f"(anchored on {args.anchor_task})")
    return 0


def cmd_phase_complete_declaration(args: argparse.Namespace) -> int:
    """Emit a phase_complete_declared audit event (v3.0-alpha.2).

    Operator-authoritative declaration that a phase has met its
    acceptance criteria. NOT a predicate-derived assertion — the
    operator names the phase and certifies completion; the substrate
    records it. Future automation hook (AC-pass rollup via test-runner
    or similar) remains future work; v3.0-alpha.2 ships only the
    operator-declared event mechanism per Aaron's CP2 observation #4.

    Typical use sequence:
        state_admin phase-complete-declaration phase-3 \\
            --anchor-task <id> \\
            --acceptance-criteria-met AC-3.1,AC-3.2,AC-3.3 \\
            --rationale "Operator-reviewed; all ACs verified; ready for phase-4 entry"
        state_admin phase-boundary phase-3 phase-4 --anchor-task <id>
        state_admin forward-track inherit --from-phase phase-3 --to-phase phase-4

    The three commands are deliberately separate — the operator may
    declare phase-complete without immediately transitioning the
    boundary (e.g., to allow phase-exit retro deliberation first).
    """
    state_path = Path(args.state_path)
    state = _load_state(state_path)
    task = _find_task(state, args.anchor_task)
    if task is None:
        print(f"anchor task not found: {args.anchor_task}", file=sys.stderr)
        return 1
    if not args.rationale or not args.rationale.strip():
        print("--rationale is required (operator's stated justification "
              "for declaring phase complete)", file=sys.stderr)
        return 1
    acs_met = []
    if args.acceptance_criteria_met:
        acs_met = [
            ac.strip() for ac in args.acceptance_criteria_met.split(",")
            if ac.strip()
        ]
    payload: dict[str, Any] = {
        "phase": args.phase,
        "acceptance_criteria_met": acs_met,
        "rationale": args.rationale.strip(),
        "declared_by": args.declared_by,
        "declaration_kind": "operator_authoritative",
    }
    if args.acceptance_criteria_pending:
        payload["acceptance_criteria_pending"] = [
            ac.strip()
            for ac in args.acceptance_criteria_pending.split(",")
            if ac.strip()
        ]
    if args.notes:
        payload["notes"] = args.notes
    _append_audit(task, "phase_complete_declared", payload)
    _save_state(state_path, state)
    print(f"phase-complete-declared: {args.phase}  "
          f"(anchored on {args.anchor_task})  "
          f"{len(acs_met)} AC(s) certified met")
    return 0


def _forward_track_id(task: dict[str, Any]) -> str:
    """Generate a forward_track_id stable to the anchor task + sequence."""
    task_id = task.get("@id", "unknown")
    task_tail = task_id.rsplit(":", 1)[-1]
    sequence = sum(
        1 for h in task.get("history", [])
        if h.get("event") == "forward_track"
        and "forward_track_id" in (h.get("payload") or {})
    )
    return f"ft-{task_tail}-{sequence + 1}"


def cmd_forward_track_create(args: argparse.Namespace) -> int:
    """Create a forward-track audit event per Spec 07.

    Forward-tracks record COMMITMENTS TO FUTURE DELIBERATION on specific
    items. Distinct from bankings (which record observations ABOUT the
    protocol). Lifecycle: candidate (State A) -> deliberated-at-named-cycle
    (State B) -> resolved (State C). v2.7.0 ships State A creation +
    inheritance; State B/C transitions and list/aging queries land in
    v2.8.0.

    Audit event structure matches Spec 07 §"Audit event structure for
    forward-tracks" EXACTLY, including fields that won't be operated on
    in v2.7.0 (inherited_through_phases: [], transition_history: [{...}]).
    Forward-tracks created in v2.7.0 must be readable by v2.8.0 transition
    and list without migration.
    """
    state_path = Path(args.state_path)
    state = _load_state(state_path)
    task = _find_task(state, args.anchor_task)
    if task is None:
        print(f"anchor task not found: {args.anchor_task}", file=sys.stderr)
        return 1
    ft_id = args.ft_id or _forward_track_id(task)
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    payload: dict[str, Any] = {
        "forward_track_id": ft_id,
        "state": "A",
        "sub_surface": args.sub_surface,
        "subject": {
            "type": args.subject_type,
            "id": args.subject_id,
            "description": args.description,
        },
        "named_deliberation_cycle": args.deliberation_cycle,
        "phase_origin": args.phase_origin,
        "inherited_through_phases": [],
        "transition_history": [
            {
                "state": "A",
                "timestamp": timestamp,
                "transitioning_cycle": args.deliberation_cycle,
            }
        ],
        "operator": args.operator,
    }
    # v2.8.0-alpha.3 (Aaron's CP3 observation 3): preserve audit-trail
    # honesty for candidacies by recording the task that surfaced the
    # forward-track. Phase-exit-retro can then trace back to original
    # evidence without manually walking the chain.
    if args.surfacing_task_id:
        payload["surfacing_task_id"] = args.surfacing_task_id
    _append_audit(task, "forward_track", payload)
    _save_state(state_path, state)
    print(f"forward-track created: {ft_id}  "
          f"sub_surface={args.sub_surface}  "
          f"subject={args.subject_type}:{args.subject_id}  "
          f"phase_origin={args.phase_origin}")
    return 0


def _ft_is_spec07(payload: dict[str, Any]) -> bool:
    """Distinguish a Spec 07 forward-track event payload from a v2.6.0
    legacy bank event payload (which also used event=forward_track).
    The Spec 07 payload has a forward_track_id field; the legacy v2.6.0
    payload does not."""
    return "forward_track_id" in payload


def _ft_current_state(task: dict[str, Any], ft_id: str) -> Optional[str]:
    """Compute a forward-track's current lifecycle state by walking the
    task's history."""
    current = None
    for h in task.get("history", []):
        payload = h.get("payload") or {}
        if payload.get("forward_track_id") != ft_id:
            continue
        ev = h.get("event")
        if ev == "forward_track" and _ft_is_spec07(payload):
            current = payload.get("state", "A")
        elif ev == "forward_track_state_transition":
            current = payload.get("to_state", current)
    return current


def _find_forward_track(state: dict[str, Any], ft_id: str) \
        -> Optional[tuple[dict[str, Any], dict[str, Any]]]:
    """Locate a Spec 07 forward-track event by forward_track_id across
    all task histories. Returns (task, create-event) on hit, or None."""
    for t in state.get("tasks", []):
        for h in t.get("history", []):
            payload = h.get("payload") or {}
            if (h.get("event") == "forward_track"
                    and payload.get("forward_track_id") == ft_id):
                return (t, h)
    return None


def _ft_inheritance_count(task: dict[str, Any], ft_id: str) -> int:
    """Count forward_track_phase_inheritance events for a given ft_id
    on its anchor task. Used by the aging command to determine whether
    a forward-track has been inherited through the configured threshold
    of phases without resolution."""
    return sum(
        1 for h in task.get("history", [])
        if h.get("event") == "forward_track_phase_inheritance"
        and (h.get("payload") or {}).get("forward_track_id") == ft_id
    )


def cmd_forward_track_transition(args: argparse.Namespace) -> int:
    """Transition a forward-track's lifecycle state per FNSR Spec 07.

    State A (candidate) -> State B (deliberated-at-named-cycle):
        the named deliberation cycle has run; outcome is pending
        resolution.
    State B -> State C (resolved):
        terminal state reached via one of three resolution paths:
        ratified-into-spec, merged-into-roadmap-release, withdrawn.
    State A -> State C (skip B):
        valid when deliberation resolves directly without an
        intermediate B state (e.g., the surfacing cycle itself
        produces the resolution).

    Emits a forward_track_state_transition audit event on the same
    task that hosts the original forward-track create event.
    """
    state_path = Path(args.state_path)
    state = _load_state(state_path)
    found = _find_forward_track(state, args.ft_id)
    if found is None:
        print(f"forward-track not found: {args.ft_id}", file=sys.stderr)
        return 1
    task, _create_event = found
    current_state = _ft_current_state(task, args.ft_id)
    if current_state is None:
        print(f"forward-track {args.ft_id} has no resolvable state",
              file=sys.stderr)
        return 1
    if current_state == args.to_state:
        print(f"forward-track {args.ft_id} already at state "
              f"{current_state}; no-op", file=sys.stderr)
        return 1
    if args.to_state == "C" and not args.resolution_path:
        print(f"transition to state C requires --resolution-path "
              f"({{ratified-into-spec|merged-into-roadmap-release|withdrawn}})",
              file=sys.stderr)
        return 1
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    payload: dict[str, Any] = {
        "forward_track_id": args.ft_id,
        "from_state": current_state,
        "to_state": args.to_state,
        "trigger": args.trigger,
        "reason": args.reason,
        "transitioning_cycle": args.transitioning_cycle,
        "timestamp": timestamp,
        "operator": args.operator,
    }
    if args.to_state == "C":
        payload["resolution_path"] = args.resolution_path
    _append_audit(task, "forward_track_state_transition", payload)
    _save_state(state_path, state)
    print(f"transitioned: {args.ft_id}  "
          f"state {current_state} -> {args.to_state}"
          + (f"  resolution={args.resolution_path}"
             if args.resolution_path else ""))
    return 0


def cmd_forward_track_list(args: argparse.Namespace) -> int:
    """Query Spec 07 forward-tracks by sub_surface / state / phase.

    Walks all task histories; for each Spec 07 forward-track event
    (event=forward_track with forward_track_id), computes current
    state + current phase context from the inheritance chain; applies
    the filters; prints a summary table.
    """
    state_path = Path(args.state_path)
    state = _load_state(state_path)
    rows = []
    seen: set[str] = set()
    for task in state.get("tasks", []):
        for h in task.get("history", []):
            payload = h.get("payload") or {}
            if h.get("event") != "forward_track":
                continue
            if "forward_track_id" not in payload:
                continue
            ft_id = payload["forward_track_id"]
            if ft_id in seen:
                continue
            seen.add(ft_id)
            current_state = _ft_current_state(task, ft_id) or "A"
            # Compute current phase from inheritance chain
            current_phase = payload.get("phase_origin", "?")
            for h2 in task.get("history", []):
                p2 = h2.get("payload") or {}
                if (h2.get("event") == "forward_track_phase_inheritance"
                        and p2.get("forward_track_id") == ft_id):
                    current_phase = p2.get("to_phase", current_phase)
            # Apply filters
            if args.sub_surface and payload.get("sub_surface") != args.sub_surface:
                continue
            if args.state and current_state != args.state:
                continue
            if args.phase and current_phase != args.phase:
                continue
            rows.append({
                "ft_id": ft_id,
                "sub_surface": payload.get("sub_surface", "?"),
                "subject_type": payload.get("subject", {}).get("type", "?"),
                "subject_id": payload.get("subject", {}).get("id", "?"),
                "state": current_state,
                "phase": current_phase,
                "anchor_task": task.get("@id", "?"),
            })
    if not rows:
        print("(no forward-tracks match the given filters)")
        return 0
    for r in rows:
        print(f"  {r['ft_id']}  state={r['state']}  phase={r['phase']}  "
              f"sub_surface={r['sub_surface']}  "
              f"subject={r['subject_type']}:{r['subject_id']}")
    print(f"total: {len(rows)} forward-track(s)")
    return 0


def cmd_forward_track_aging(args: argparse.Namespace) -> int:
    """Flag forward-tracks that have inherited through the configured
    threshold of phases without resolution.

    Per FNSR Spec 07 §"Aging policy" + Aaron's CP4 observation 1:
    long-lived candidates may indicate substantive blockers or
    candidates that should be withdrawn rather than perpetually
    deferred. The threshold defaults to 3 phases; overridable via
    --threshold flag OR FNSR_FORWARD_TRACK_AGING_THRESHOLD_PHASES env
    var.

    Each aging warning is itself emitted as a forward_track_aging_warning
    audit event on the forward-track's anchor task. The audit chain
    records when the warning was raised, so a future operator reviewing
    aging history can see what was flagged at which cycle.
    """
    state_path = Path(args.state_path)
    state = _load_state(state_path)
    # Resolve threshold: --threshold > env var > Spec 07 default (3)
    threshold = args.threshold
    if threshold is None:
        env_val = os.environ.get(
            "FNSR_FORWARD_TRACK_AGING_THRESHOLD_PHASES")
        try:
            threshold = int(env_val) if env_val else 3
        except ValueError:
            threshold = 3
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    warned = 0
    skipped_resolved = 0
    skipped_under_threshold = 0
    seen: set[str] = set()
    for task in state.get("tasks", []):
        for h in list(task.get("history", [])):
            payload = h.get("payload") or {}
            if h.get("event") != "forward_track":
                continue
            if "forward_track_id" not in payload:
                continue
            ft_id = payload["forward_track_id"]
            if ft_id in seen:
                continue
            seen.add(ft_id)
            current_state = _ft_current_state(task, ft_id) or "A"
            if current_state == "C":
                skipped_resolved += 1
                continue
            inheritance_count = _ft_inheritance_count(task, ft_id)
            if inheritance_count < threshold:
                skipped_under_threshold += 1
                continue
            warning_payload = {
                "forward_track_id": ft_id,
                "current_state": current_state,
                "inheritance_count": inheritance_count,
                "threshold": threshold,
                "subject": payload.get("subject", {}),
                "sub_surface": payload.get("sub_surface", "?"),
                "phase_origin": payload.get("phase_origin", "?"),
                "timestamp": timestamp,
                "operator": args.operator,
            }
            if args.notes:
                warning_payload["notes"] = args.notes
            _append_audit(task, "forward_track_aging_warning",
                          warning_payload)
            warned += 1
            print(f"  AGING  {ft_id}  "
                  f"inherited_through={inheritance_count}  "
                  f"state={current_state}  "
                  f"subject={payload.get('subject', {}).get('id', '?')}")
    if warned:
        _save_state(state_path, state)
    print(f"forward-track aging (threshold={threshold}): "
          f"{warned} warning(s), "
          f"{skipped_resolved} skipped resolved, "
          f"{skipped_under_threshold} skipped under threshold")
    return 0


def cmd_forward_track_inherit(args: argparse.Namespace) -> int:
    """Bulk-inherit unresolved forward-tracks across an operator-declared
    phase boundary per Spec 07.

    Walks every Spec 07 forward-track event in state.jsonld; for each
    forward-track whose current state is A or B (not resolved) and whose
    phase_origin matches --from-phase OR whose inherited_through_phases
    tail matches --from-phase, emits a forward_track_phase_inheritance
    audit event on the SAME task hosting the original forward-track. The
    inheritance event updates the forward-track's effective phase context
    (computed from the chain at read time).
    """
    state_path = Path(args.state_path)
    state = _load_state(state_path)
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    inherited = 0
    skipped_resolved = 0
    seen_ids: set[str] = set()
    for task in state.get("tasks", []):
        for h in list(task.get("history", [])):
            payload = h.get("payload") or {}
            if h.get("event") != "forward_track":
                continue
            if not _ft_is_spec07(payload):
                continue
            ft_id = payload["forward_track_id"]
            if ft_id in seen_ids:
                continue
            seen_ids.add(ft_id)
            # Determine current phase context: latest inheritance event's
            # to_phase, or original phase_origin.
            current_phase = payload.get("phase_origin")
            for h2 in task.get("history", []):
                p2 = h2.get("payload") or {}
                if p2.get("forward_track_id") != ft_id:
                    continue
                if h2.get("event") == "forward_track_phase_inheritance":
                    current_phase = p2.get("to_phase", current_phase)
            if current_phase != args.from_phase:
                continue
            current_state = _ft_current_state(task, ft_id)
            if current_state == "C":
                skipped_resolved += 1
                continue
            inheritance_payload = {
                "forward_track_id": ft_id,
                "from_phase": args.from_phase,
                "to_phase": args.to_phase,
                "inherited_at_cycle": args.inherited_at_cycle,
                "timestamp": timestamp,
                "operator": args.operator,
            }
            _append_audit(task, "forward_track_phase_inheritance",
                          inheritance_payload)
            inherited += 1
    if inherited:
        _save_state(state_path, state)
    print(f"forward-track inherit: {args.from_phase} -> {args.to_phase}  "
          f"inherited={inherited}  skipped_resolved={skipped_resolved}")
    return 0


# ---------- template-sync (v2.9.0) ---------------------------------------
#
# Automates the dual-track-workflow manifest's "files that must stay
# identical across all three repos" sync step. Replaces ad-hoc `cp -f`
# operator commands with a deterministic + verify-able workflow.

# Default manifest: the files the dual-track-workflow memory designates
# as "must stay identical." Override via FNSR_TEMPLATE_SYNC_MANIFEST env
# var or --manifest CLI flag.
_DEFAULT_TEMPLATE_SYNC_MANIFEST = (
    "fnsr_daemon.py",
    "state_admin.py",
    "PLAYBOOK.md",
    ".gitignore",
    ".claude/agents/adversarial-critic.md",
    ".claude/agents/applier.md",
    ".claude/agents/architect.md",
    ".claude/agents/delivery-manager.md",
    ".claude/agents/developer.md",
    ".claude/agents/git-committer.md",
    ".claude/agents/marep-orchestrator.md",
    ".claude/agents/mojibake-repair.md",
    ".claude/agents/planner.md",
    ".claude/agents/qa.md",
    ".claude/agents/question-resolver.md",
    ".claude/agents/reconnaissance.md",
    ".claude/agents/retro-applier.md",
    ".claude/agents/risk-analyst.md",
    ".claude/agents/semantic-sme.md",
    ".claude/agents/spec-reviewer.md",
    ".claude/agents/synthesist.md",
    ".claude/agents/test-runner.md",
    ".claude/agents/ux-sme.md",
    ".claude/agents/verification-ritual.md",
    ".claude/agents/verification-ritual-llm.md",
    "surfaces/verification/surface-spec.md",
    "surfaces/verification/categories/cat-01-spec-section-existence.md",
    "surfaces/verification/categories/cat-02-adr-cross-reference.md",
    "surfaces/verification/categories/cat-03-q-ruling-cross-reference.md",
    "surfaces/verification/categories/cat-04-reason-code-frozen-enum.md",
    "surfaces/verification/categories/cat-05-fol-owl-type-discriminator.md",
    "surfaces/verification/categories/cat-06-manifest-mirror-consistency.md",
    "surfaces/verification/categories/cat-07-cross-phase-cross-reference.md",
    "surfaces/verification/categories/cat-08-multi-canonical-source.md",
    "surfaces/verification/categories/cat-09-cited-content-consistency.md",
    "surfaces/verification/categories/cat-10-type-field-structure.md",
    "surfaces/verification/categories/cat-10-type-field-structure.py",
    "surfaces/_primitives/bounded-authority-orchestrator.md",
    "surfaces/_primitives/episodic-to-semantic-promotion.md",
    "surfaces/retro/surface-spec.md",
    "surfaces/retro/agents/orchestrator.md",
    "surfaces/retro/agents/architect.md",
    "surfaces/retro/agents/developer.md",
    "surfaces/retro/agents/user-advocate.md",
    "surfaces/retro/agents/skeptic.md",
    "surfaces/retro/agents/qa.md",
    "surfaces/retro/agents/delivery-manager.md",
    "surfaces/retro/agents/risk-analyst.md",
    "surfaces/retro/phases/01-gathering.md",
    "surfaces/retro/phases/02-merge.md",
    "surfaces/retro/phases/03-analysis.md",
    "surfaces/retro/phases/04-consensus.md",
    "surfaces/retro/phases/05-actions.md",
    "surfaces/retro/phases/06-compression.md",
    "tests/__init__.py",
    "tests/test_adr_and_awaiting.py",
    "tests/test_apply.py",
    "tests/test_audit.py",
    "tests/test_coerce_and_backoff.py",
    "tests/test_cps.py",
    "tests/test_extractor.py",
    "tests/test_git_committer.py",
    "tests/test_mojibake.py",
    "tests/test_question_resolver.py",
    "tests/test_reconciliation.py",
    "tests/test_retro_surface_foundation.py",
    "tests/test_v3_alpha_2_substrate.py",
    "tests/test_routing.py",
    "tests/test_state_admin.py",
    "tests/test_test_runner.py",
    "tests/test_upstream.py",
    "tests/test_verification_ritual.py",
)


def _load_template_sync_manifest(args: argparse.Namespace) -> list[str]:
    """Resolve manifest: --manifest > FNSR_TEMPLATE_SYNC_MANIFEST > default."""
    manifest_path = (args.manifest
                     or os.environ.get("FNSR_TEMPLATE_SYNC_MANIFEST"))
    if manifest_path:
        with open(manifest_path, encoding="utf-8") as f:
            return [
                line.strip()
                for line in f
                if line.strip() and not line.lstrip().startswith("#")
            ]
    return list(_DEFAULT_TEMPLATE_SYNC_MANIFEST)


def _read_bytes_or_none(path: Path) -> Optional[bytes]:
    if not path.exists() or not path.is_file():
        return None
    try:
        return path.read_bytes()
    except OSError:
        return None


def cmd_template_sync(args: argparse.Namespace) -> int:
    """Sync substrate-shared files from source repo to target repo(s).

    Default mode: verify (drift report only). Use --mode sync to copy
    source -> targets then verify. Files in the manifest that are
    absent from the source repo are flagged but do not cause a non-zero
    exit; this lets manifests evolve across releases.

    Exit codes:
      0  no drift after operation
      1  drift remains after operation (verify mode never auto-fixes)
      2  source file missing for one or more manifest entries
    """
    source = Path(args.source or ".").resolve()
    targets = [Path(t.strip()).resolve()
               for t in args.targets.split(",") if t.strip()]
    if not targets:
        print("no targets specified", file=sys.stderr)
        return 1
    manifest = _load_template_sync_manifest(args)
    missing_source: list[str] = []
    drift: list[tuple[str, str, str]] = []  # (file, target, reason)
    synced: list[tuple[str, str]] = []
    unchanged: list[tuple[str, str]] = []
    for rel in manifest:
        src_path = source / rel
        src_bytes = _read_bytes_or_none(src_path)
        if src_bytes is None:
            missing_source.append(rel)
            continue
        for target in targets:
            tgt_path = target / rel
            tgt_bytes = _read_bytes_or_none(tgt_path)
            target_name = target.name
            if args.mode == "sync":
                # Always overwrite; create parent dirs if needed.
                tgt_path.parent.mkdir(parents=True, exist_ok=True)
                if tgt_bytes != src_bytes:
                    tgt_path.write_bytes(src_bytes)
                    synced.append((rel, target_name))
                else:
                    unchanged.append((rel, target_name))
            else:
                # verify mode
                if tgt_bytes is None:
                    drift.append((rel, target_name, "absent_from_target"))
                elif tgt_bytes != src_bytes:
                    drift.append((rel, target_name, "content_differs"))
                else:
                    unchanged.append((rel, target_name))
    # Reporting
    if missing_source:
        print(f"missing in source ({len(missing_source)} file(s)):", file=sys.stderr)
        for rel in missing_source:
            print(f"  - {rel}", file=sys.stderr)
    if args.mode == "sync":
        if synced:
            print(f"synced {len(synced)} file(s):")
            for rel, target_name in synced:
                print(f"  {rel} -> {target_name}")
        if unchanged:
            print(f"unchanged: {len(unchanged)} file(s)")
        # Post-sync verification
        post_drift: list[tuple[str, str, str]] = []
        for rel in manifest:
            src_path = source / rel
            src_bytes = _read_bytes_or_none(src_path)
            if src_bytes is None:
                continue
            for target in targets:
                tgt_path = target / rel
                if _read_bytes_or_none(tgt_path) != src_bytes:
                    post_drift.append((rel, target.name, "still_differs"))
        if post_drift:
            print(f"WARNING: drift remains after sync ({len(post_drift)}):",
                  file=sys.stderr)
            for rel, target_name, reason in post_drift:
                print(f"  {rel} ({target_name}): {reason}", file=sys.stderr)
            return 1
        print("template-sync: complete; no drift remains.")
        return 0 if not missing_source else 2
    else:
        # verify mode
        if drift:
            print(f"drift detected ({len(drift)} file(s)):")
            for rel, target_name, reason in drift:
                print(f"  {rel} ({target_name}): {reason}")
        if unchanged:
            print(f"identical: {len(unchanged)} file(s)")
        if drift:
            return 1
        if missing_source:
            return 2
        return 0


# ---------- CLI ---------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Operator utilities for state.jsonld manipulation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="STOP THE DAEMON before modifying state (Ctrl-C in its terminal).",
    )
    p.add_argument("--state-path", default="state.jsonld",
                   help="path to state.jsonld (default: ./state.jsonld)")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_reset = sub.add_parser("reset", help="reset task to ready with audit")
    p_reset.add_argument("task_id")
    p_reset.add_argument("--reason", required=True)
    p_reset.add_argument("--operator", default="operator")
    p_reset.set_defaults(func=cmd_reset)

    p_abandon = sub.add_parser("abandon", help="mark task blocked with audit")
    p_abandon.add_argument("task_id")
    p_abandon.add_argument("--reason", required=True)
    p_abandon.add_argument("--replaced-by",
                            help="comma-separated replacement task @ids")
    p_abandon.add_argument("--operator", default="operator")
    p_abandon.set_defaults(func=cmd_abandon)

    p_append = sub.add_parser("append-tasks", help="append tasks from JSON file")
    p_append.add_argument("tasks_file")
    p_append.set_defaults(func=cmd_append_tasks)

    p_verify = sub.add_parser("verify", help="verify audit-chain integrity")
    p_verify.add_argument("--quiet", action="store_true")
    p_verify.set_defaults(func=cmd_verify)

    p_status = sub.add_parser("status", help="print task statuses")
    p_status.add_argument("--filter",
                           help="show only this status (ready|in_progress|"
                                "done|blocked|failed|awaiting_operator_decision)")
    p_status.set_defaults(func=cmd_status)

    p_resolve = sub.add_parser("resolve",
                                help="resolve an awaiting_operator_decision task")
    p_resolve.add_argument("task_id")
    p_resolve.add_argument("--option", type=int, required=True,
                            help="1-based index of the option to pick")
    p_resolve.add_argument("--notes",
                            help="optional operator notes recorded with the "
                                 "resolution")
    p_resolve.add_argument("--operator", default="operator")
    p_resolve.set_defaults(func=cmd_resolve)

    p_bank = sub.add_parser("bank",
                             help="record a banking audit event (Spec 05)")
    p_bank.add_argument("task_id",
                         help="task @id to anchor the audit entry against")
    p_bank.add_argument("--content", required=True,
                         help="the banking content / observation text")
    p_bank.add_argument("--category", default=None,
                         choices=SPEC05_CATEGORIES,
                         help="Spec 05 banking taxonomy category "
                              "(default: pattern-observation)")
    p_bank.add_argument("--candidate-class", default=None,
                         choices=("pattern", "methodology", "decision",
                                  "risk", "other"),
                         help="v2.6.0 legacy synonym; mapped to a Spec 05 "
                              "category. Prefer --category for v2.7.0+.")
    p_bank.add_argument("--state", type=int, default=1, choices=(1, 2, 3),
                         help="banking lifecycle state (Spec 05): "
                              "1=verbal-pending, 2=partially-committed, "
                              "3=formalized (default: 1)")
    p_bank.add_argument("--banking-id", default=None,
                         help="optional explicit banking_id "
                              "(default: auto-generated from task @id)")
    p_bank.add_argument("--cycle", default=None,
                         help="optional surfacing cycle identifier")
    p_bank.add_argument("--operator", default="operator")
    p_bank.set_defaults(func=cmd_bank)

    p_trans = sub.add_parser("transition-banking",
                              help="transition a banking to a new state "
                                   "(Spec 05 lifecycle)")
    p_trans.add_argument("banking_id",
                          help="banking_id to transition")
    p_trans.add_argument("--to-state", type=int, required=True,
                          choices=(1, 2, 3),
                          help="target state (1/2/3)")
    p_trans.add_argument("--reason", required=True,
                          help="rationale for the transition")
    p_trans.add_argument("--trigger", default="manual_operator_action",
                          help="trigger label per Spec 05 §'Lifecycle state "
                               "transitions' (e.g., pass_2b_commit_landed, "
                               "phase_exit_doc_pass_fold, "
                               "manual_operator_action)")
    p_trans.add_argument("--transitioning-cycle", default=None,
                          help="cycle id during which the transition occurred")
    p_trans.add_argument("--operator", default="operator")
    p_trans.set_defaults(func=cmd_transition_banking)

    p_phase = sub.add_parser("phase-boundary",
                              help="emit a phase_boundary_declared audit "
                                   "event (operator-emitted; substrate is "
                                   "phase-schema-neutral)")
    p_phase.add_argument("from_phase",
                          help="phase identifier we are leaving "
                               "(e.g., phase-1)")
    p_phase.add_argument("to_phase",
                          help="phase identifier we are entering "
                               "(e.g., phase-2)")
    p_phase.add_argument("--anchor-task", required=True,
                          help="task @id to anchor the phase-boundary event "
                               "against")
    p_phase.add_argument("--cycle", default=None,
                          help="optional cycle id at which the boundary is "
                               "declared")
    p_phase.add_argument("--notes", default=None,
                          help="optional operator notes")
    p_phase.add_argument("--declared-by", default="operator")
    p_phase.set_defaults(func=cmd_phase_boundary)

    p_pc = sub.add_parser(
        "phase-complete-declaration",
        help=("emit a phase_complete_declared audit event "
              "(v3.0-alpha.2; operator-authoritative)"),
    )
    p_pc.add_argument("phase",
                       help="phase identifier being declared complete "
                            "(e.g., phase-3)")
    p_pc.add_argument("--anchor-task", required=True,
                       help="task @id to anchor the audit event against")
    p_pc.add_argument("--rationale", required=True,
                       help="operator's stated justification for declaring "
                            "the phase complete; recorded in audit chain")
    p_pc.add_argument("--acceptance-criteria-met", default=None,
                       help="comma-separated list of AC identifiers the "
                            "operator certifies as met (e.g., AC-3.1,AC-3.2)")
    p_pc.add_argument("--acceptance-criteria-pending", default=None,
                       help="comma-separated list of AC identifiers known "
                            "incomplete at declaration time (operator "
                            "acknowledges; documented for audit)")
    p_pc.add_argument("--notes", default=None,
                       help="optional operator notes")
    p_pc.add_argument("--declared-by", default="operator")
    p_pc.set_defaults(func=cmd_phase_complete_declaration)

    p_ft = sub.add_parser("forward-track",
                           help="forward-track surface operations (Spec 07)")
    ft_sub = p_ft.add_subparsers(dest="ft_cmd", required=True)

    p_ft_create = ft_sub.add_parser(
        "create",
        help="create a forward-track in State A (candidate)"
    )
    p_ft_create.add_argument("--anchor-task", required=True,
                              help="task @id to anchor the forward-track "
                                   "event against (typically the surfacing "
                                   "task)")
    p_ft_create.add_argument(
        "--sub-surface", required=True,
        choices=("consumer-closure-path", "internal-methodology-refinement"),
        help="audience sub-surface (Spec 07 §'Audience sub-surfaces')"
    )
    p_ft_create.add_argument(
        "--subject-type", required=True,
        choices=("banking", "fixture", "capability", "candidacy", "other"),
        help="what kind of item is being forward-tracked"
    )
    p_ft_create.add_argument("--subject-id", required=True,
                              help="referenced-event id (or descriptor for "
                                   "type=other)")
    p_ft_create.add_argument("--description", required=True,
                              help="human-readable description")
    p_ft_create.add_argument("--deliberation-cycle", required=True,
                              help="named cycle at which deliberation will "
                                   "occur (e.g., phase-exit-retro, "
                                   "v0.2-roadmap)")
    p_ft_create.add_argument("--phase-origin", required=True,
                              help="phase that surfaced the forward-track "
                                   "(e.g., phase-1)")
    p_ft_create.add_argument("--ft-id", default=None,
                              help="optional explicit forward_track_id "
                                   "(default: auto-generated)")
    p_ft_create.add_argument("--surfacing-task-id", default=None,
                              help="task @id that surfaced this candidacy "
                                   "(e.g., the verification-ritual-llm task "
                                   "whose new_candidacies prompted the "
                                   "creation). Preserves audit-trail evidence "
                                   "for phase-exit-retro deliberation.")
    p_ft_create.add_argument("--operator", default="operator")
    p_ft_create.set_defaults(func=cmd_forward_track_create)

    p_ft_inherit = ft_sub.add_parser(
        "inherit",
        help="bulk-inherit unresolved forward-tracks across a phase boundary"
    )
    p_ft_inherit.add_argument("--from-phase", required=True)
    p_ft_inherit.add_argument("--to-phase", required=True)
    p_ft_inherit.add_argument("--inherited-at-cycle", required=True,
                               help="entry cycle id of the destination phase")
    p_ft_inherit.add_argument("--operator", default="operator")
    p_ft_inherit.set_defaults(func=cmd_forward_track_inherit)

    p_ft_trans = ft_sub.add_parser(
        "transition",
        help="transition a forward-track's lifecycle state (Spec 07 A/B/C)",
    )
    p_ft_trans.add_argument("ft_id",
                             help="forward_track_id to transition")
    p_ft_trans.add_argument(
        "--to-state", required=True, choices=("B", "C"),
        help="target state: B=deliberated-at-named-cycle, "
             "C=resolved (requires --resolution-path)"
    )
    p_ft_trans.add_argument("--reason", required=True,
                             help="rationale for the transition")
    p_ft_trans.add_argument(
        "--resolution-path", default=None,
        choices=("ratified-into-spec", "merged-into-roadmap-release",
                 "withdrawn"),
        help="required when --to-state=C; one of the three Spec 07 "
             "resolution paths"
    )
    p_ft_trans.add_argument(
        "--trigger", default="manual_operator_action",
        help="trigger label (e.g., named_deliberation_cycle_ran, "
             "resolution_reached, manual_operator_action)"
    )
    p_ft_trans.add_argument("--transitioning-cycle", default=None,
                             help="cycle id during which the transition "
                                  "occurred")
    p_ft_trans.add_argument("--operator", default="operator")
    p_ft_trans.set_defaults(func=cmd_forward_track_transition)

    p_ft_list = ft_sub.add_parser(
        "list",
        help="query forward-tracks by sub_surface / state / phase",
    )
    p_ft_list.add_argument(
        "--sub-surface", default=None,
        choices=("consumer-closure-path", "internal-methodology-refinement"),
        help="filter by audience sub-surface"
    )
    p_ft_list.add_argument("--state", default=None,
                            choices=("A", "B", "C"),
                            help="filter by current lifecycle state")
    p_ft_list.add_argument("--phase", default=None,
                            help="filter by current phase context "
                                 "(phase_origin or tail of inheritance "
                                 "chain)")
    p_ft_list.set_defaults(func=cmd_forward_track_list)

    p_ft_age = ft_sub.add_parser(
        "aging",
        help="flag forward-tracks inherited through >= threshold phases "
             "without resolution; emits forward_track_aging_warning audit "
             "events",
    )
    p_ft_age.add_argument("--threshold", type=int, default=None,
                           help="minimum inheritance count to warn on "
                                "(default: 3 or FNSR_FORWARD_TRACK_"
                                "AGING_THRESHOLD_PHASES env var)")
    p_ft_age.add_argument("--notes", default=None,
                           help="optional operator notes recorded with "
                                "each aging warning")
    p_ft_age.add_argument("--operator", default="operator")
    p_ft_age.set_defaults(func=cmd_forward_track_aging)

    p_sync = sub.add_parser(
        "template-sync",
        help="Sync template-shared files from source repo to target "
             "repo(s) per the dual-track-workflow manifest. Default "
             "manifest is the substrate-shared file list; override via "
             "FNSR_TEMPLATE_SYNC_MANIFEST env var.",
    )
    p_sync.add_argument("--source", default=None,
                         help="source repo root (default: cwd)")
    p_sync.add_argument("--targets", required=True,
                         help="comma-separated target repo roots")
    p_sync.add_argument("--mode", default="verify",
                         choices=("verify", "sync"),
                         help="verify: report drift only; sync: copy "
                              "source -> targets then verify "
                              "(default: verify)")
    p_sync.add_argument("--manifest", default=None,
                         help="path to a manifest file (one path per "
                              "line, # comments). Defaults to the "
                              "substrate's hardcoded shared-files list.")
    p_sync.set_defaults(func=cmd_template_sync)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
