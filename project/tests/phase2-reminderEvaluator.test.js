import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { reminderEvaluator } from '../src/modules/reminderEvaluator.js';
import { createTaskDefinition } from '../src/entities/taskDefinition.js';
import { createTaskInstance } from '../src/entities/taskInstance.js';

// ---------------------------------------------------------------------------
// Helper factories (module-level, not inside describe blocks)
// ---------------------------------------------------------------------------

function makeOnceDef() {
  return createTaskDefinition({
    title: 'Once Reminder Task',
    description: 'Task with once reminder mode',
    assignedTo: 'urn:ftm:user:test',
    createdBy: 'urn:ftm:user:creator',
    dueAt: '2026-01-01T12:00:00Z',
    reminderMode: 'once',
  });
}

function makePersistentDef(intervalSeconds, persistUntilSeconds) {
  return createTaskDefinition({
    title: 'Persistent Reminder Task',
    description: 'Task with persistent reminder mode',
    assignedTo: 'urn:ftm:user:test',
    createdBy: 'urn:ftm:user:creator',
    dueAt: '2026-01-01T12:00:00Z',
    reminderMode: 'persistent',
    intervalSeconds,
    persistUntilSeconds,
  });
}

/**
 * Build a TaskInstance and apply shallow overrides into the
 * completionState and reminderSummary sub-objects, plus an optional
 * top-level dueAt override.
 *
 * @param {{ dueAt?: string, completionState?: object, reminderSummary?: object }} overrides
 */
function makeInstance(overrides = {}) {
  const base = createTaskInstance({
    taskDefinitionId: 'urn:ftm:task:test',
    assignedTo: 'urn:ftm:user:test',
    dueAt: overrides.dueAt ?? '2026-01-01T12:00:00Z',
  });
  if (overrides.completionState) {
    Object.assign(base['ftm:completionState'], overrides.completionState);
  }
  if (overrides.reminderSummary) {
    Object.assign(base['ftm:reminderSummary'], overrides.reminderSummary);
  }
  return base;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('2.2 ReminderEvaluator', () => {
  test('completed instance returns shouldRemind false reason already-complete', () => {
    const def = makeOnceDef();
    const instance = makeInstance({
      dueAt: '2026-01-01T12:00:00Z',
      completionState: { 'ftm:status': 'completed' },
    });
    const result = reminderEvaluator(instance, def, '2026-01-01T13:00:00Z');
    assert.equal(result.shouldRemind, false);
    assert.equal(result.reason, 'already-complete');
  });

  test('dueAt after currentTime returns shouldRemind false reason not-yet-due', () => {
    const def = makeOnceDef();
    // dueAt is tomorrow; currentTime is today
    const instance = makeInstance({ dueAt: '2026-01-02T12:00:00Z' });
    const result = reminderEvaluator(instance, def, '2026-01-01T12:00:00Z');
    assert.equal(result.shouldRemind, false);
    assert.equal(result.reason, 'not-yet-due');
  });

  test('once mode totalSent 0 returns shouldRemind true reason first-and-only', () => {
    const def = makeOnceDef();
    const instance = makeInstance({
      dueAt: '2026-01-01T12:00:00Z',
      reminderSummary: { 'ftm:totalSent': 0 },
    });
    const result = reminderEvaluator(instance, def, '2026-01-01T13:00:00Z');
    assert.equal(result.shouldRemind, true);
    assert.equal(result.reason, 'first-and-only');
  });

  test('once mode totalSent 1 returns shouldRemind false reason once-sent', () => {
    const def = makeOnceDef();
    const instance = makeInstance({
      dueAt: '2026-01-01T12:00:00Z',
      reminderSummary: { 'ftm:totalSent': 1 },
    });
    const result = reminderEvaluator(instance, def, '2026-01-01T13:00:00Z');
    assert.equal(result.shouldRemind, false);
    assert.equal(result.reason, 'once-sent');
  });

  test('persistent mode currentTime past persistUntilSeconds window returns false reason persistence-window-expired', () => {
    // persistUntilSeconds=3600 (1 hr); dueAt=noon; window expires at 13:00Z
    const def = makePersistentDef(300, 3600);
    const instance = makeInstance({
      dueAt: '2026-01-01T12:00:00Z',
      reminderSummary: {
        'ftm:totalSent': 1,
        'ftm:lastSentAt': '2026-01-01T12:05:00Z',
        'ftm:lastDeliveryStatus': 'delivered',
      },
    });
    // currentTime = 13:01Z → 1 second past the 1-hour window
    const result = reminderEvaluator(instance, def, '2026-01-01T13:01:00Z');
    assert.equal(result.shouldRemind, false);
    assert.equal(result.reason, 'persistence-window-expired');
  });

  test('persistent mode persistUntilSeconds absent currentTime = dueAt + 86401s returns persistence-window-expired (default 86400s)', () => {
    // persistUntilSeconds=null → default 86400; dueAt + 86401s = 2026-01-02T12:00:01Z
    const def = makePersistentDef(300, null);
    const instance = makeInstance({
      dueAt: '2026-01-01T12:00:00Z',
      reminderSummary: {
        'ftm:totalSent': 1,
        'ftm:lastSentAt': '2026-01-01T12:05:00Z',
        'ftm:lastDeliveryStatus': 'delivered',
      },
    });
    const result = reminderEvaluator(instance, def, '2026-01-02T12:00:01Z');
    assert.equal(result.shouldRemind, false);
    assert.equal(result.reason, 'persistence-window-expired');
  });

  test('persistent mode persistUntilSeconds absent currentTime = dueAt + 86399s returns NOT persistence-window-expired', () => {
    // persistUntilSeconds=null → default 86400; dueAt + 86399s = 2026-01-02T11:59:59Z → still inside window
    const def = makePersistentDef(300, null);
    const instance = makeInstance({
      dueAt: '2026-01-01T12:00:00Z',
      reminderSummary: {
        'ftm:totalSent': 1,
        'ftm:lastSentAt': '2026-01-01T12:05:00Z',
        'ftm:lastDeliveryStatus': 'delivered',
      },
    });
    const result = reminderEvaluator(instance, def, '2026-01-02T11:59:59Z');
    assert.notEqual(result.reason, 'persistence-window-expired');
  });

  test('persistent mode lastDeliveryStatus failed returns shouldRemind true reason retry-after-failure', () => {
    // interval=5min (300s), persist=1hr; currentTime at dueAt+5min → inside window
    const def = makePersistentDef(300, 3600);
    const instance = makeInstance({
      dueAt: '2026-01-01T12:00:00Z',
      reminderSummary: {
        'ftm:totalSent': 1,
        'ftm:lastSentAt': '2026-01-01T12:04:00Z',
        'ftm:lastDeliveryStatus': 'failed',
      },
    });
    const result = reminderEvaluator(instance, def, '2026-01-01T12:05:00Z');
    assert.equal(result.shouldRemind, true);
    assert.equal(result.reason, 'retry-after-failure');
  });

  test('persistent mode totalSent 0 returns shouldRemind true reason initial-reminder', () => {
    // interval=5min, persist=1hr; currentTime at dueAt+1min → inside window, no prior sends
    const def = makePersistentDef(300, 3600);
    const instance = makeInstance({
      dueAt: '2026-01-01T12:00:00Z',
      reminderSummary: { 'ftm:totalSent': 0 },
    });
    const result = reminderEvaluator(instance, def, '2026-01-01T12:01:00Z');
    assert.equal(result.shouldRemind, true);
    assert.equal(result.reason, 'initial-reminder');
  });

  test('persistent mode interval elapsed returns shouldRemind true reason interval-elapsed', () => {
    // interval=5min (300s); lastSentAt=dueAt; currentTime=dueAt+10min → 10min elapsed â‰¥ 5min
    const def = makePersistentDef(300, 3600);
    const instance = makeInstance({
      dueAt: '2026-01-01T12:00:00Z',
      reminderSummary: {
        'ftm:totalSent': 1,
        'ftm:lastSentAt': '2026-01-01T12:00:00Z',
        'ftm:lastDeliveryStatus': 'delivered',
      },
    });
    const result = reminderEvaluator(instance, def, '2026-01-01T12:10:00Z');
    assert.equal(result.shouldRemind, true);
    assert.equal(result.reason, 'interval-elapsed');
  });

  test('persistent mode interval not elapsed returns shouldRemind false reason interval-not-elapsed', () => {
    // interval=5min (300s); lastSentAt=dueAt; currentTime=dueAt+2min → 2min elapsed < 5min
    const def = makePersistentDef(300, 3600);
    const instance = makeInstance({
      dueAt: '2026-01-01T12:00:00Z',
      reminderSummary: {
        'ftm:totalSent': 1,
        'ftm:lastSentAt': '2026-01-01T12:00:00Z',
        'ftm:lastDeliveryStatus': 'delivered',
      },
    });
    const result = reminderEvaluator(instance, def, '2026-01-01T12:02:00Z');
    assert.equal(result.shouldRemind, false);
    assert.equal(result.reason, 'interval-not-elapsed');
  });

  // SPEC §13 item 4
  test('§13.4 ReminderEvaluator with lastDeliveryStatus failed asserts shouldRemind true and reason retry-after-failure', () => {
    const def = makePersistentDef(300, 3600);
    const instance = makeInstance({
      dueAt: '2026-01-01T12:00:00Z',
      reminderSummary: {
        'ftm:totalSent': 2,
        'ftm:lastSentAt': '2026-01-01T12:10:00Z',
        'ftm:lastDeliveryStatus': 'failed',
      },
    });
    // currentTime within persistence window (15min after dueAt; persist=1hr)
    const result = reminderEvaluator(instance, def, '2026-01-01T12:15:00Z');
    assert.equal(result.shouldRemind, true);
    assert.equal(result.reason, 'retry-after-failure');
  });
});
