import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { taskListComputer } from '../src/modules/taskListComputer.js';
import { createTaskInstance } from '../src/entities/taskInstance.js';

// ---------------------------------------------------------------------------
// Helper factory (module-level, not inside describe blocks)
// ---------------------------------------------------------------------------

/**
 * Returns a TaskInstance assigned to `assignedTo` with `dueAt`.
 * If `status` is 'completed', sets ftm:completionState.ftm:status accordingly.
 *
 * @param {string} assignedTo
 * @param {string} dueAt       - ISO-8601 string
 * @param {'pending'|'completed'} [status='pending']
 * @returns {Object} ftm:TaskInstance JSON-LD object
 */
function makeInstance(assignedTo, dueAt, status = 'pending') {
  const base = createTaskInstance({
    taskDefinitionId: 'urn:ftm:taskdef:test',
    assignedTo,
    dueAt,
  });
  if (status === 'completed') {
    return {
      ...base,
      'ftm:completionState': {
        ...base['ftm:completionState'],
        'ftm:status': 'completed',
      },
    };
  }
  return base;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('2.4 TaskListComputer', () => {
  test('filter by assignedTo excludes other children', () => {
    const child1 = makeInstance('urn:ftm:child:child-1', '2026-06-01T09:00:00Z');
    const child2 = makeInstance('urn:ftm:child:child-2', '2026-06-01T09:00:00Z');
    const result = taskListComputer([child1, child2], { assignedTo: 'urn:ftm:child:child-1' });
    assert.equal(result.length, 1);
    assert.equal(result[0]['ftm:assignedTo'], 'urn:ftm:child:child-1');
  });

  test('filter by status pending excludes completed', () => {
    const pending = makeInstance('urn:ftm:child:child-1', '2026-06-01T09:00:00Z', 'pending');
    const completed = makeInstance('urn:ftm:child:child-1', '2026-06-02T09:00:00Z', 'completed');
    const result = taskListComputer([pending, completed], { status: 'pending' });
    assert.equal(result.length, 1);
    assert.equal(result[0]['ftm:completionState']['ftm:status'], 'pending');
  });

  test('filter by status completed excludes pending', () => {
    const pending = makeInstance('urn:ftm:child:child-1', '2026-06-01T09:00:00Z', 'pending');
    const completed = makeInstance('urn:ftm:child:child-1', '2026-06-02T09:00:00Z', 'completed');
    const result = taskListComputer([pending, completed], { status: 'completed' });
    assert.equal(result.length, 1);
    assert.equal(result[0]['ftm:completionState']['ftm:status'], 'completed');
  });

  test('filter by fromDate excludes earlier instances', () => {
    // early is before fromDate threshold; later meets it exactly (>=)
    const early = makeInstance('urn:ftm:child:child-1', '2026-05-01T09:00:00Z');
    const later = makeInstance('urn:ftm:child:child-1', '2026-06-01T09:00:00Z');
    const result = taskListComputer([early, later], { fromDate: '2026-06-01T09:00:00Z' });
    assert.equal(result.length, 1);
    assert.equal(result[0]['ftm:dueAt']['@value'], '2026-06-01T09:00:00Z');
  });

  test('filter by toDate excludes later instances', () => {
    // later is after toDate threshold; early meets it exactly (<=)
    const early = makeInstance('urn:ftm:child:child-1', '2026-05-01T09:00:00Z');
    const later = makeInstance('urn:ftm:child:child-1', '2026-06-01T09:00:00Z');
    const result = taskListComputer([early, later], { toDate: '2026-05-01T09:00:00Z' });
    assert.equal(result.length, 1);
    assert.equal(result[0]['ftm:dueAt']['@value'], '2026-05-01T09:00:00Z');
  });

  test('empty filter returns all instances', () => {
    const a = makeInstance('urn:ftm:child:child-1', '2026-06-01T09:00:00Z');
    const b = makeInstance('urn:ftm:child:child-2', '2026-06-02T09:00:00Z', 'completed');
    const c = makeInstance('urn:ftm:child:child-3', '2026-06-03T09:00:00Z');
    const result = taskListComputer([a, b, c]);
    assert.equal(result.length, 3);
  });

  test('default sort is dueAt ascending', () => {
    // Supply instances in non-ascending order; result must be ascending
    const third = makeInstance('urn:ftm:child:child-1', '2026-06-03T09:00:00Z');
    const first = makeInstance('urn:ftm:child:child-1', '2026-06-01T09:00:00Z');
    const second = makeInstance('urn:ftm:child:child-1', '2026-06-02T09:00:00Z');
    const result = taskListComputer([third, first, second]);
    assert.equal(result[0]['ftm:dueAt']['@value'], '2026-06-01T09:00:00Z');
    assert.equal(result[1]['ftm:dueAt']['@value'], '2026-06-02T09:00:00Z');
    assert.equal(result[2]['ftm:dueAt']['@value'], '2026-06-03T09:00:00Z');
  });

  test('equal dueAt: pending before completed', () => {
    // Both instances share the same dueAt; completed is supplied first
    const sameDue = '2026-06-01T09:00:00Z';
    const completedInst = makeInstance('urn:ftm:child:child-1', sameDue, 'completed');
    const pendingInst = makeInstance('urn:ftm:child:child-1', sameDue, 'pending');
    const result = taskListComputer([completedInst, pendingInst]);
    assert.equal(result[0]['ftm:completionState']['ftm:status'], 'pending');
    assert.equal(result[1]['ftm:completionState']['ftm:status'], 'completed');
  });

  test('does not mutate input array (original ordering preserved)', () => {
    // Supply in reverse-chronological order; taskListComputer must not reorder the original
    const late = makeInstance('urn:ftm:child:child-1', '2026-06-03T09:00:00Z');
    const early = makeInstance('urn:ftm:child:child-1', '2026-06-01T09:00:00Z');
    const input = [late, early];
    taskListComputer(input);
    // Reference equality confirms elements were not shifted within the original array
    assert.strictEqual(input[0], late);
    assert.strictEqual(input[1], early);
    assert.equal(input.length, 2);
  });

  // SPEC §13 item 7
  test('§13.7 parent dashboard derives pending and completed lists from taskListComputer output only — no adapter call in test', () => {
    // Simulate two children; parent queries child-1's pending and completed lists
    // via taskListComputer filters alone — no persistence adapter involved.
    const child1Pending = makeInstance('urn:ftm:child:child-1', '2026-06-01T09:00:00Z', 'pending');
    const child1Completed = makeInstance('urn:ftm:child:child-1', '2026-06-02T09:00:00Z', 'completed');
    const child2Pending = makeInstance('urn:ftm:child:child-2', '2026-06-01T09:00:00Z', 'pending');
    const all = [child1Pending, child1Completed, child2Pending];
    const pendingList = taskListComputer(all, {
      assignedTo: 'urn:ftm:child:child-1',
      status: 'pending',
    });
    const completedList = taskListComputer(all, {
      assignedTo: 'urn:ftm:child:child-1',
      status: 'completed',
    });
    assert.equal(pendingList.length, 1);
    assert.equal(pendingList[0]['ftm:completionState']['ftm:status'], 'pending');
    assert.equal(pendingList[0]['ftm:assignedTo'], 'urn:ftm:child:child-1');
    assert.equal(completedList.length, 1);
    assert.equal(completedList[0]['ftm:completionState']['ftm:status'], 'completed');
    assert.equal(completedList[0]['ftm:assignedTo'], 'urn:ftm:child:child-1');
  });
});
