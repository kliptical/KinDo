import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { scheduleComputer } from '../src/modules/scheduleComputer.js';
import { reminderEvaluator } from '../src/modules/reminderEvaluator.js';
import { recurrenceMaterializer } from '../src/modules/recurrenceMaterializer.js';
import { createInMemoryStateAdapter } from '../src/adapters/state/inMemoryStateAdapter.js';
import { createTaskDefinition } from '../src/entities/taskDefinition.js';
import { createTaskInstance } from '../src/entities/taskInstance.js';
import { createTestOrchestrationAdapter } from '../src/adapters/orchestration/testOrchestrationAdapter.js';
import { bootResume } from '../src/flows/bootResume.js';
import { createNoopNotificationAdapter } from '../src/adapters/notification/noopNotificationAdapter.js';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Fixed 'now' for all tests — prevents wall-clock races. */
const currentTime = '2026-05-22T10:00:00Z';

/**
 * One hour before currentTime — used as the instance dueAt for reminder tests
 * that require the task to already be due at evaluation time.
 */
const dueAtPast = '2026-05-22T09:00:00Z';

/**
 * recurrenceStart 2 calendar days before currentTime.  FREQ=DAILY from this
 * anchor produces 3 past occurrences under current-only policy: May 20, May 21,
 * and May 22 (toISOString emits the .000Z suffix; '2026-05-22T10:00:00.000Z'
 * is lexicographically less than '2026-05-22T10:00:00Z', so the May 22
 * occurrence counts as past too).
 */
const recurrenceStartForCatchUp = '2026-05-20T10:00:00Z';

/**
 * recurrenceStart 1 day after currentTime — safe future anchor; no past
 * occurrences exist within the catch-up window, so skipped = 0.
 */
const recurrenceStartFuture = '2026-05-23T10:00:00Z';

// ---------------------------------------------------------------------------
// Helper factories
// ---------------------------------------------------------------------------

/**
 * Returns a persistent-mode TaskDefinition.
 *
 * @param {{ intervalSeconds?: number, persistUntilSeconds?: number|null }} [opts]
 */
function makePersistentDef({ intervalSeconds = 300, persistUntilSeconds = 7200 } = {}) {
  return createTaskDefinition({
    title:              'Persistent Reminder Task',
    description:        'Offline scenario — persistent reminder',
    assignedTo:         'urn:ftm:user:child-test',
    createdBy:          'urn:ftm:user:parent-test',
    dueAt:              dueAtPast,
    reminderMode:       'persistent',
    intervalSeconds,
    persistUntilSeconds,
  });
}

/**
 * Build a TaskInstance and apply shallow overrides into completionState and
 * reminderSummary sub-objects, plus an optional top-level dueAt override.
 *
 * @param {{ dueAt?: string, completionState?: object, reminderSummary?: object }} [overrides]
 */
function makeInstance(overrides = {}) {
  const base = createTaskInstance({
    taskDefinitionId: 'urn:ftm:task:test',
    assignedTo:       'urn:ftm:user:child-test',
    dueAt:            overrides.dueAt ?? dueAtPast,
  });
  if (overrides.completionState) {
    Object.assign(base['ftm:completionState'], overrides.completionState);
  }
  if (overrides.reminderSummary) {
    Object.assign(base['ftm:reminderSummary'], overrides.reminderSummary);
  }
  return base;
}

/**
 * Returns a recurring FREQ=DAILY TaskDefinition anchored at `recurrenceStart`.
 *
 * @param {string} recurrenceStart - ISO-8601 start timestamp
 */
function makeRecurringDef(recurrenceStart) {
  return createTaskDefinition({
    title:           'Daily Recurring Task',
    description:     'Offline scenario — multi-day catch-up',
    assignedTo:      'urn:ftm:user:child-test',
    createdBy:       'urn:ftm:user:parent-test',
    dueAt:           recurrenceStart,
    scheduleType:    'recurring',
    recurrenceRule:  'FREQ=DAILY',
    recurrenceStart,
  });
}

// ---------------------------------------------------------------------------
// 4.10 §10 Offline Behavior Scenarios
// ---------------------------------------------------------------------------

describe('4.10 §10 Offline Behavior Scenarios', () => {
  // ── Test 1: failed notification retry ───────────────────────────────────
  test('failed notification retry: instance with lastDeliveryStatus failed and totalSent 1 returns shouldRemind true reason retry-after-failure (persistent mode)', () => {
    // persistUntilSeconds=7200 (2 hrs); instance dueAt=09:00Z; window expires at
    // 11:00Z. currentTime=10:00Z → still inside window.
    // totalSent=1 (skips initial-reminder branch), lastDeliveryStatus=failed
    // → retry-after-failure.
    const def = makePersistentDef({ intervalSeconds: 300, persistUntilSeconds: 7200 });
    const instance = makeInstance({
      reminderSummary: {
        'ftm:totalSent':           1,
        'ftm:lastSentAt':          '2026-05-22T09:05:00Z',
        'ftm:lastDeliveryStatus':  'failed',
      },
    });
    const result = reminderEvaluator(instance, def, currentTime);
    assert.equal(result.shouldRemind, true);
    assert.equal(result.reason, 'retry-after-failure');
  });

  // ── Test 2: conflict resolution end-to-end ──────────────────────────────
  test('conflict resolution end-to-end: save TaskInstance seq=1 then seq=2 via stateAdapter; getTaskInstance returns seq=2 entity', async () => {
    // In-order saves: seq=1 arrives first, seq=2 arrives second.
    // LWW: incomingSeq(2) > existingSeq(1) → incoming wins → seq=2 is stored.
    const state = createInMemoryStateAdapter();
    const base  = createTaskInstance({
      taskDefinitionId: 'urn:ftm:task:conflict-test',
      assignedTo:       'urn:ftm:user:child-test',
      dueAt:            currentTime,
    });
    const seq1 = { ...base, 'ftm:clientSequence': 1 };
    const seq2 = { ...base, 'ftm:clientSequence': 2 };

    await state.saveTaskInstance(seq1);
    await state.saveTaskInstance(seq2);

    const retrieved = await state.getTaskInstance(base['@id']);
    assert.ok(retrieved !== null, 'getTaskInstance must return a non-null entity');
    assert.equal(retrieved['ftm:clientSequence'], 2, 'seq=2 must overwrite seq=1 (higher wins)');
  });

  // ── Test 3: invalid RRULE ────────────────────────────────────────────────
  test('invalid RRULE: scheduleComputer with unparseable recurrenceRule returns [] with array[ftm:error] === invalid-rrule', () => {
    // 'BADRRULE' contains no '=' separator; RRule.parseString passes it to the
    // parseRrule switch which hits the default branch and throws
    // "Unknown RRULE property 'BADRRULE'".  scheduleComputer catches this and
    // returns the error array.
    const def = createTaskDefinition({
      title:           'Broken Recurring Task',
      description:     'Unparseable recurrenceRule',
      assignedTo:      'urn:ftm:user:child-test',
      createdBy:       'urn:ftm:user:parent-test',
      dueAt:           currentTime,
      scheduleType:    'recurring',
      recurrenceRule:  'BADRRULE',
      recurrenceStart: currentTime,
    });
    const result = scheduleComputer(def, '2026-05-22T00:00:00Z');
    assert.ok(Array.isArray(result), 'result must be an array');
    assert.equal(result.length, 0, 'result must be empty');
    assert.equal(result['ftm:error'], 'invalid-rrule', "ftm:error must be 'invalid-rrule'");
  });

  // ── Test 4: missing persistUntilSeconds default ──────────────────────────
  test('missing persistUntilSeconds default: persistent mode currentTime = dueAt + 86401s returns shouldRemind false reason persistence-window-expired', () => {
    // persistUntilSeconds=null → reminderEvaluator applies default of 86400s via ??.
    // Instance dueAt = currentTime ('2026-05-22T10:00:00Z'); window expires at
    // '2026-05-23T10:00:00Z'.  evaluationTime = dueAt + 86401s =
    // '2026-05-23T10:00:01Z' — 1 second past the window → expired.
    const def = createTaskDefinition({
      title:              'Default Persistence Window Task',
      description:        'Tests default persistUntilSeconds=86400',
      assignedTo:         'urn:ftm:user:child-test',
      createdBy:          'urn:ftm:user:parent-test',
      dueAt:              currentTime,
      reminderMode:       'persistent',
      intervalSeconds:    300,
      persistUntilSeconds: null,
    });
    const instance = makeInstance({
      dueAt: currentTime,
      reminderSummary: {
        'ftm:totalSent':          1,
        'ftm:lastSentAt':         '2026-05-22T10:05:00Z',
        'ftm:lastDeliveryStatus': 'delivered',
      },
    });
    // evaluationTime = dueAt + 86401s (1 second past the default 86400s window)
    const evaluationTime = new Date(
      new Date(currentTime).getTime() + 86401 * 1000
    ).toISOString();
    const result = reminderEvaluator(instance, def, evaluationTime);
    assert.equal(result.shouldRemind, false);
    assert.equal(result.reason, 'persistence-window-expired');
  });

  // ── Test 5: multi-day offline catch-up ──────────────────────────────────
  test('multi-day offline catch-up: recurrenceMaterializer with 3 missed past occurrences and catchUpPolicy current-only returns skipped 3', () => {
    // recurrenceStartForCatchUp = '2026-05-20T10:00:00Z' (2 calendar days before
    // currentTime). FREQ=DAILY produces May 20, May 21, May 22 at 10:00:00.000Z.
    // String comparison: toISOString emits .000Z; '2026-05-22T10:00:00.000Z'
    // < '2026-05-22T10:00:00Z' ('.' < 'Z'), so all three count as past →
    // skipped=3 under current-only policy.
    const def = makeRecurringDef(recurrenceStartForCatchUp);
    const { skipped } = recurrenceMaterializer([def], [], currentTime);
    assert.equal(skipped, 3, 'expected 3 past occurrences skipped under current-only policy');
  });

  // ── Test 6: background timers ────────────────────────────────────────────
  test('background timers: bootResume using testOrchestrationAdapter materializes instances and registers callbacks without any real setTimeout/setInterval', async () => {
    // testOrchestrationAdapter replaces all real timers with a deterministic
    // logical clock advanced only by tick().  The scheduleAt spy confirms that
    // each materialized instance registers exactly one callback — no wall-clock
    // I/O occurs at any point in this test.
    const state = createInMemoryStateAdapter();
    const orch  = createTestOrchestrationAdapter();
    const notif = createNoopNotificationAdapter();

    const futureDef = createTaskDefinition({
      title:           'Background Timer Task',
      description:     'Future-anchored recurring task for timer registration check',
      assignedTo:      'urn:ftm:user:child-test',
      createdBy:       'urn:ftm:user:parent-test',
      dueAt:           recurrenceStartFuture,
      scheduleType:    'recurring',
      recurrenceRule:  'FREQ=DAILY',
      recurrenceStart: recurrenceStartFuture,
    });
    await state.saveTaskDefinition(futureDef);

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

    assert.ok(result.toCreate > 0, 'expected at least one TaskInstance materialized');
    assert.equal(
      scheduledCount,
      result.toCreate,
      'each materialized instance must register exactly one scheduleAt callback',
    );
  });

  // ── Test 7: concurrent edit ──────────────────────────────────────────────
  test('concurrent edit: save two TaskInstance with same @id, different clientSequence values; higher sequence survives retrievable via getTaskInstance', async () => {
    // Simulates out-of-order network delivery: seq=5 arrives first (stored),
    // then seq=3 arrives late.  LWW: existingSeq(5) > incomingSeq(3) → existing
    // is kept; seq=3 must NOT overwrite seq=5.
    const state = createInMemoryStateAdapter();
    const base  = createTaskInstance({
      taskDefinitionId: 'urn:ftm:task:concurrent-edit-test',
      assignedTo:       'urn:ftm:user:child-test',
      dueAt:            currentTime,
    });

    const highSeq = { ...base, 'ftm:clientSequence': 5 };
    const lowSeq  = { ...base, 'ftm:clientSequence': 3 };

    await state.saveTaskInstance(highSeq);
    await state.saveTaskInstance(lowSeq);  // must NOT overwrite seq=5

    const retrieved = await state.getTaskInstance(base['@id']);
    assert.ok(retrieved !== null, 'entity must be retrievable after concurrent saves');
    assert.equal(
      retrieved['ftm:clientSequence'],
      5,
      'higher clientSequence (5) must survive when lower (3) arrives after',
    );
  });
});
