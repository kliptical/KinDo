import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { bootResume } from '../src/flows/bootResume.js';
import { createInMemoryStateAdapter } from '../src/adapters/state/inMemoryStateAdapter.js';
import { createTestOrchestrationAdapter } from '../src/adapters/orchestration/testOrchestrationAdapter.js';
import { createNoopNotificationAdapter } from '../src/adapters/notification/noopNotificationAdapter.js';
import { createTaskDefinition } from '../src/entities/taskDefinition.js';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Fixed 'now' for all tests — prevents wall-clock races. */
const currentTime = '2026-05-31T10:00:00Z';

/**
 * recurrenceStart 1 day in the future from currentTime.
 * FREQ=DAILY from June 1 within the 14-day combined window (May 24 – June 7)
 * yields 7 future occurrences per definition; skipped = 0.
 */
const recurrenceStartFuture = '2026-06-01T10:00:00Z';

/**
 * recurrenceStart 8 days before currentTime.
 * FREQ=DAILY from May 23; the 7-day catch-up window covers May 24 – May 30
 * (7 occurrences). All fall before currentTime, so current-only policy
 * increments skipped for each; skipped >= 7 > 0.
 */
const recurrenceStartPast = '2026-05-23T10:00:00Z';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Saves 2 recurring TaskDefinitions (FREQ=DAILY, recurrenceStart 1 day in
 * the future) to a fresh in-memory state. Returns fresh adapters.
 *
 * @returns {Promise<{ state, orch, notif }>}
 */
async function setupRecurringDefs() {
  const state = createInMemoryStateAdapter();
  const orch  = createTestOrchestrationAdapter();
  const notif = createNoopNotificationAdapter();

  const def1 = createTaskDefinition({
    title:           'Recurring Task A',
    description:     'First daily recurring task',
    assignedTo:      'urn:ftm:user:child-a',
    createdBy:       'urn:ftm:user:parent-a',
    dueAt:           recurrenceStartFuture,
    scheduleType:    'recurring',
    recurrenceRule:  'FREQ=DAILY',
    recurrenceStart: recurrenceStartFuture,
  });

  const def2 = createTaskDefinition({
    title:           'Recurring Task B',
    description:     'Second daily recurring task',
    assignedTo:      'urn:ftm:user:child-a',
    createdBy:       'urn:ftm:user:parent-a',
    dueAt:           recurrenceStartFuture,
    scheduleType:    'recurring',
    recurrenceRule:  'FREQ=DAILY',
    recurrenceStart: recurrenceStartFuture,
  });

  await state.saveTaskDefinition(def1);
  await state.saveTaskDefinition(def2);

  return { state, orch, notif };
}

// ---------------------------------------------------------------------------
// 4.5 §8.5 bootResume
// ---------------------------------------------------------------------------

describe('4.5 §8.5 bootResume', () => {
  test('returns { toCreate, skipped } shape', async () => {
    const { state, orch, notif } = await setupRecurringDefs();

    const result = await bootResume({
      stateAdapter:         state,
      orchestrationAdapter: orch,
      notificationAdapter:  notif,
      currentTime,
    });

    assert.ok('toCreate' in result, 'result must have toCreate key');
    assert.ok('skipped'  in result, 'result must have skipped key');
    assert.equal(typeof result.toCreate, 'number', 'toCreate must be a number');
    assert.equal(typeof result.skipped,  'number', 'skipped must be a number');
  });

  test('2 recurring task definitions + empty instances: stateAdapter.listTaskInstances returns >0 entries after bootResume', async () => {
    const { state, orch, notif } = await setupRecurringDefs();

    const result = await bootResume({
      stateAdapter:         state,
      orchestrationAdapter: orch,
      notificationAdapter:  notif,
      currentTime,
    });

    const instances = await state.listTaskInstances();
    assert.ok(
      instances.length > 0,
      'expected at least one TaskInstance in state after bootResume',
    );
    assert.equal(
      instances.length,
      result.toCreate,
      'listTaskInstances count must equal result.toCreate (state starts empty)',
    );
  });

  test('skipped count reported when catchUpPolicy default current-only and past occurrences exist', async () => {
    // Inline past-anchored definition: recurrenceStart 8 days before currentTime.
    // The 7-day catch-up window (May 24 – May 30) contains 7 past occurrences;
    // current-only policy skips each one, so result.skipped >= 7 > 0.
    const state = createInMemoryStateAdapter();
    const orch  = createTestOrchestrationAdapter();
    const notif = createNoopNotificationAdapter();

    const pastDef = createTaskDefinition({
      title:           'Past Recurring Task',
      description:     'Daily task anchored 8 days before currentTime',
      assignedTo:      'urn:ftm:user:child-b',
      createdBy:       'urn:ftm:user:parent-b',
      dueAt:           recurrenceStartPast,
      scheduleType:    'recurring',
      recurrenceRule:  'FREQ=DAILY',
      recurrenceStart: recurrenceStartPast,
    });

    await state.saveTaskDefinition(pastDef);

    const result = await bootResume({
      stateAdapter:         state,
      orchestrationAdapter: orch,
      notificationAdapter:  notif,
      currentTime,
    });

    assert.equal(typeof result.skipped, 'number', 'skipped must be a number');
    assert.ok(
      result.skipped > 0,
      'expected skipped > 0: past occurrences exist within the catch-up window and current-only policy is in effect',
    );
  });

  test('orchestration callbacks registered for each new instance (verify by orch state having entries)', async () => {
    const { state, orch, notif } = await setupRecurringDefs();

    // Spy on scheduleAt to count registrations without exposing adapter internals.
    let scheduledCount = 0;
    const originalScheduleAt = orch.scheduleAt.bind(orch);
    orch.scheduleAt = (isoTimestamp, cb) => {
      scheduledCount++;
      return originalScheduleAt(isoTimestamp, cb);
    };

    const result = await bootResume({
      stateAdapter:         state,
      orchestrationAdapter: orch,
      notificationAdapter:  notif,
      currentTime,
    });

    assert.ok(
      scheduledCount > 0,
      'expected orchestrationAdapter.scheduleAt to be called at least once',
    );
    assert.equal(
      scheduledCount,
      result.toCreate,
      'expected one scheduleAt registration per created TaskInstance',
    );
  });
});
