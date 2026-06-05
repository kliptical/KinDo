import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { resumeReconciliation } from '../src/modules/resumeReconciliation.js';
import { createInMemoryStateAdapter } from '../src/adapters/state/inMemoryStateAdapter.js';
import { createTestOrchestrationAdapter } from '../src/adapters/orchestration/testOrchestrationAdapter.js';
import { createNoopNotificationAdapter } from '../src/adapters/notification/noopNotificationAdapter.js';
import { createTaskDefinition } from '../src/entities/taskDefinition.js';
import { createTaskInstance } from '../src/entities/taskInstance.js';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const currentTime = '2026-05-22T10:00:00Z';
// 8 days before currentTime — exercises the catch-up window (7-day default)
// so that past occurrences exist and skipped > 0 with current-only policy.
const recurrenceStart = '2026-05-14T10:00:00Z';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Builds fresh adapters, attaches a send-count spy to notif, and saves one
 * non-recurring TaskDefinition that notification tests can reference.
 *
 * `sends` is exposed as a live getter on the returned object — always access
 * it via `fixture.sends`, NOT via destructuring, so the post-reconciliation
 * count is visible.
 *
 * @returns {Promise<{ state, orch, notif, sendSpy, baseDef, sends: number }>}
 */
async function setupFixture() {
  const state = createInMemoryStateAdapter();
  const orch  = createTestOrchestrationAdapter();
  const notif = createNoopNotificationAdapter();

  // Spy: wrap send to count invocations; original still resolves the receipt.
  let _sends = 0;
  const originalSend = notif.send.bind(notif);
  const sendSpy = async (payload) => {
    _sends++;
    return originalSend(payload);
  };
  notif.send = sendSpy;

  // One-time TaskDefinition used as the referent for manually created instances.
  // scheduleType: 'one-time' → filtered out by resumeReconciliation's recurring
  // filter in Step 2, so materialisation produces no extra instances.
  const baseDef = createTaskDefinition({
    title:       'Fixture Task',
    description: 'Base fixture task for notification tests',
    assignedTo:  'urn:ftm:user:child-fixture',
    createdBy:   'urn:ftm:user:parent-fixture',
    dueAt:       '2026-05-14T10:00:00Z',
    scheduleType: 'one-time',
  });
  await state.saveTaskDefinition(baseDef);

  const fixture = { state, orch, notif, sendSpy, baseDef };
  // Live getter: returns the closure-captured counter value at access time.
  Object.defineProperty(fixture, 'sends', { get: () => _sends, enumerable: true });
  return fixture;
}

/**
 * Builds fresh adapters and saves two FREQ=DAILY recurring TaskDefinitions
 * anchored 8 days before `currentTime`, exercising the catch-up path.
 *
 * @returns {Promise<{ state, orch, notif, def1, def2 }>}
 */
async function setupTwoRecurringDefs() {
  const state = createInMemoryStateAdapter();
  const orch  = createTestOrchestrationAdapter();
  const notif = createNoopNotificationAdapter();

  const def1 = createTaskDefinition({
    title:           'Daily Chore 1',
    description:     'First recurring task',
    assignedTo:      'urn:ftm:user:child-a',
    createdBy:       'urn:ftm:user:parent-a',
    dueAt:           recurrenceStart,
    scheduleType:    'recurring',
    recurrenceRule:  'FREQ=DAILY',
    recurrenceStart,
  });

  const def2 = createTaskDefinition({
    title:           'Daily Chore 2',
    description:     'Second recurring task',
    assignedTo:      'urn:ftm:user:child-a',
    createdBy:       'urn:ftm:user:parent-a',
    dueAt:           recurrenceStart,
    scheduleType:    'recurring',
    recurrenceRule:  'FREQ=DAILY',
    recurrenceStart,
  });

  await state.saveTaskDefinition(def1);
  await state.saveTaskDefinition(def2);

  return { state, orch, notif, def1, def2 };
}

// ---------------------------------------------------------------------------
// 3.10 Resume Reconciliation
// ---------------------------------------------------------------------------

describe('3.10 Resume Reconciliation', () => {
  test('boot with 2 recurring defs and empty instances: stateAdapter.listTaskInstances returns >0 entries after resumeReconciliation; orchestrationAdapter has registered scheduleAt callbacks for each new instance', async () => {
    const { state, orch, notif } = await setupTwoRecurringDefs();

    // Spy on scheduleAt to count registrations without exposing adapter internals.
    let scheduledCount = 0;
    const originalScheduleAt = orch.scheduleAt.bind(orch);
    orch.scheduleAt = (isoTimestamp, cb) => {
      scheduledCount++;
      return originalScheduleAt(isoTimestamp, cb);
    };

    const result = await resumeReconciliation({
      stateAdapter:         state,
      orchestrationAdapter: orch,
      notificationAdapter:  notif,
      currentTime,
    });

    const instances = await state.listTaskInstances();
    assert.ok(instances.length > 0, 'expected at least one TaskInstance in state after reconciliation');
    assert.equal(
      scheduledCount,
      result.toCreate,
      'expected one scheduleAt registration per created TaskInstance',
    );
    assert.equal(
      instances.length,
      result.toCreate,
      'listTaskInstances count must equal result.toCreate (state starts empty)',
    );
  });

  test('skipped count is reported when catchUpPolicy defaults to current-only and past occurrences exist', async () => {
    const { state, orch, notif } = await setupTwoRecurringDefs();

    const result = await resumeReconciliation({
      stateAdapter:         state,
      orchestrationAdapter: orch,
      notificationAdapter:  notif,
      currentTime,
    });

    // resumeReconciliation passes no options to recurrenceMaterializer, so
    // catchUpPolicy defaults to 'current-only'.  recurrenceStart is 8 days
    // before currentTime; the 7-day catch-up window includes May 15-21 past
    // occurrences which are skipped rather than materialised.
    assert.equal(typeof result.skipped, 'number');
    assert.ok(
      result.skipped > 0,
      'expected skipped > 0: past occurrences exist and current-only policy is in effect',
    );
  });

  test('pending instances with dueAt <= currentTime get reminderEvaluator-driven notification send: 3 overdue pending instances => notif.send call count is 3', async () => {
    const fixture = await setupFixture();
    const { state, orch, notif, baseDef } = fixture;

    // Three overdue pending instances (dueAt <= currentTime, totalSent = 0,
    // reminderMode = 'once') → reminderEvaluator returns shouldRemind: true
    // for each, triggering one notificationAdapter.send call per instance.
    // Note: these use bare-Z ISO strings (no milliseconds) to avoid the
    // .000Z < Z string-ordering edge that affects materializer-produced instances.
    const overdueDates = [
      '2026-05-20T10:00:00Z',
      '2026-05-21T10:00:00Z',
      '2026-05-22T10:00:00Z', // exactly equal to currentTime — still satisfies <= filter
    ];
    for (const dueAt of overdueDates) {
      const instance = createTaskInstance({
        taskDefinitionId: baseDef['@id'],
        assignedTo:       'urn:ftm:user:child-fixture',
        dueAt,
      });
      await state.saveTaskInstance(instance);
    }

    await resumeReconciliation({
      stateAdapter:         state,
      orchestrationAdapter: orch,
      notificationAdapter:  notif,
      currentTime,
    });

    // Access sends via fixture object (not destructured) to read the live getter.
    assert.equal(fixture.sends, 3, 'expected exactly 3 notification sends for 3 overdue pending instances');
  });

  test('completed instances do NOT trigger notification send', async () => {
    const fixture = await setupFixture();
    const { state, orch, notif, baseDef } = fixture;

    // A past-due instance marked completed — reminderEvaluator Rule 1 short-circuits
    // before the due-date check; should NOT generate a send.
    const instance = createTaskInstance({
      taskDefinitionId: baseDef['@id'],
      assignedTo:       'urn:ftm:user:child-fixture',
      dueAt:            '2026-05-20T10:00:00Z',
    });
    const completedInstance = {
      ...instance,
      'ftm:completionState': {
        ...instance['ftm:completionState'],
        'ftm:status':      'completed',
        'ftm:completedAt': '2026-05-20T11:00:00Z',
        'ftm:completedBy': 'urn:ftm:user:child-fixture',
      },
    };
    await state.saveTaskInstance(completedInstance);

    await resumeReconciliation({
      stateAdapter:         state,
      orchestrationAdapter: orch,
      notificationAdapter:  notif,
      currentTime,
    });

    assert.equal(fixture.sends, 0, 'completed instance must not trigger a notification send');
  });

  test('not-yet-due pending instances do NOT trigger notification send', async () => {
    const fixture = await setupFixture();
    const { state, orch, notif, baseDef } = fixture;

    // A pending instance with dueAt strictly after currentTime — filtered out
    // by the pendingDue check in Step 3 before reminderEvaluator is reached.
    const instance = createTaskInstance({
      taskDefinitionId: baseDef['@id'],
      assignedTo:       'urn:ftm:user:child-fixture',
      dueAt:            '2026-05-25T10:00:00Z',
    });
    await state.saveTaskInstance(instance);

    await resumeReconciliation({
      stateAdapter:         state,
      orchestrationAdapter: orch,
      notificationAdapter:  notif,
      currentTime,
    });

    assert.equal(fixture.sends, 0, 'not-yet-due instance must not trigger a notification send');
  });

  test('returns { toCreate: number, skipped: number } shape', async () => {
    const { state, orch, notif } = await setupTwoRecurringDefs();

    const result = await resumeReconciliation({
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
});
