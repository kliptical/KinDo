import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { scheduleComputer } from '../src/modules/scheduleComputer.js';
import { createTaskDefinition } from '../src/entities/taskDefinition.js';

// ---------------------------------------------------------------------------
// Helper factories (module-level, not inside describe blocks)
// ---------------------------------------------------------------------------

function makeOneTimeDef(dueAt) {
  return createTaskDefinition({
    title: 'One-time Task',
    description: 'Test one-time task',
    assignedTo: 'urn:ftm:user:test',
    createdBy: 'urn:ftm:user:creator',
    dueAt,
    scheduleType: 'one-time',
  });
}

function makeDailyRecurringDef(recurrenceStart) {
  return createTaskDefinition({
    title: 'Daily Recurring Task',
    description: 'Test recurring task',
    assignedTo: 'urn:ftm:user:test',
    createdBy: 'urn:ftm:user:creator',
    // dueAt required by factory; semantically unused for recurring scheduleType
    dueAt: recurrenceStart,
    scheduleType: 'recurring',
    recurrenceRule: 'FREQ=DAILY',
    recurrenceStart,
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('2.1 ScheduleComputer', () => {
  test('one-time task with dueAt strictly after referenceTime returns 1 instance', () => {
    const def = makeOneTimeDef('2026-01-02T12:00:00Z');
    const result = scheduleComputer(def, '2026-01-01T12:00:00Z');
    assert.equal(result.length, 1);
  });

  test('one-time task with dueAt equal to referenceTime returns []', () => {
    const def = makeOneTimeDef('2026-01-01T12:00:00Z');
    const result = scheduleComputer(def, '2026-01-01T12:00:00Z');
    assert.equal(result.length, 0);
  });

  test('one-time task with dueAt before referenceTime returns []', () => {
    const def = makeOneTimeDef('2025-12-31T12:00:00Z');
    const result = scheduleComputer(def, '2026-01-01T12:00:00Z');
    assert.equal(result.length, 0);
  });

  test('recurring FREQ=DAILY with lookAheadSeconds 604800 returns 7 instances', () => {
    // dtstart=Jan 1 06:00Z; window [Jan 1 00:00Z, Jan 8 00:00Z]
    // rrule yields Jan 1-7 at 06:00Z (7 dates); none equal referenceTime (midnight)
    const def = makeDailyRecurringDef('2026-01-01T06:00:00Z');
    const result = scheduleComputer(def, '2026-01-01T00:00:00Z', { lookAheadSeconds: 604800 });
    assert.equal(result.length, 7);
  });

  test('all recurring instances have dueAt > referenceTime and <= referenceTime + lookAheadSeconds', () => {
    const referenceTime = '2026-01-01T00:00:00Z';
    const lookAheadSeconds = 604800;
    const def = makeDailyRecurringDef('2026-01-01T06:00:00Z');
    const result = scheduleComputer(def, referenceTime, { lookAheadSeconds });
    const refMs = new Date(referenceTime).getTime();
    const endMs = refMs + lookAheadSeconds * 1000;
    for (const instance of result) {
      const instanceMs = new Date(instance['ftm:dueAt']['@value']).getTime();
      assert.ok(instanceMs > refMs, 'dueAt must be strictly after referenceTime');
      assert.ok(instanceMs <= endMs, 'dueAt must be at or before referenceTime + lookAheadSeconds');
    }
  });

  test('default lookAheadSeconds is 604800 when options omitted', () => {
    // Same dtstart and referenceTime as the explicit-604800 test; result must be identical count
    const def = makeDailyRecurringDef('2026-01-01T06:00:00Z');
    const result = scheduleComputer(def, '2026-01-01T00:00:00Z');
    assert.equal(result.length, 7);
  });

  test('invalid recurrenceRule returns [] with ftm:error invalid-rrule attached to array', () => {
    const def = createTaskDefinition({
      title: 'Broken Recurring',
      description: 'No rule',
      assignedTo: 'urn:ftm:user:test',
      createdBy: 'urn:ftm:user:creator',
      dueAt: '2026-01-01T06:00:00Z',
      scheduleType: 'recurring',
      recurrenceRule: null,
      recurrenceStart: '2026-01-01T06:00:00Z',
    });
    const result = scheduleComputer(def, '2026-01-01T00:00:00Z');
    assert.ok(Array.isArray(result));
    assert.equal(result.length, 0);
    assert.equal(result['ftm:error'], 'invalid-rrule');
  });

  test('all returned instances have completionState.status pending and totalSent 0', () => {
    const def = makeDailyRecurringDef('2026-01-01T06:00:00Z');
    const result = scheduleComputer(def, '2026-01-01T00:00:00Z', { lookAheadSeconds: 604800 });
    for (const instance of result) {
      assert.equal(instance['ftm:completionState']['ftm:status'], 'pending');
      assert.equal(instance['ftm:reminderSummary']['ftm:totalSent'], 0);
    }
  });

  test('two calls with same args produce same logical output (deterministic count and dueAt values; UUIDs may differ)', () => {
    const def = makeDailyRecurringDef('2026-01-01T06:00:00Z');
    const referenceTime = '2026-01-01T00:00:00Z';
    const options = { lookAheadSeconds: 604800 };
    const first = scheduleComputer(def, referenceTime, options);
    const second = scheduleComputer(def, referenceTime, options);
    assert.equal(first.length, second.length);
    const firstDueTimes = first.map(i => i['ftm:dueAt']['@value']).sort();
    const secondDueTimes = second.map(i => i['ftm:dueAt']['@value']).sort();
    assert.deepEqual(firstDueTimes, secondDueTimes);
  });

  // SPEC §13 item 1
  test('§13.1 instantiate TaskDefinition and pass to ScheduleComputer with no network call', () => {
    // Pure-function contract: if any I/O occurred the test would fail or hang
    const def = makeOneTimeDef('2026-06-01T09:00:00Z');
    const result = scheduleComputer(def, '2026-01-01T00:00:00Z');
    assert.ok(Array.isArray(result));
    assert.equal(result.length, 1);
    assert.equal(typeof result[0]['@id'], 'string');
    assert.ok(result[0]['@id'].startsWith('urn:ftm:instance:'));
  });

  // SPEC §13 item 2
  test('§13.2 ScheduleComputer with recurring def + referenceTime 4 days in past returns array covering catch-up window; second call with identical args returns array of same length and dueAt values', () => {
    // recurrenceStart is 4 days before referenceTime (Jan 1 noon → Jan 5 noon)
    const recurrenceStart = '2026-01-01T12:00:00Z';
    const referenceTime  = '2026-01-05T12:00:00Z';
    const def = makeDailyRecurringDef(recurrenceStart);
    const options = { lookAheadSeconds: 604800 };
    const first = scheduleComputer(def, referenceTime, options);
    // referenceTime itself (Jan 5 noon) is filtered by open-start;
    // remaining in window Jan 6–12 noon = 7 instances
    assert.equal(first.length, 7);
    const second = scheduleComputer(def, referenceTime, options);
    assert.equal(first.length, second.length);
    const firstDueTimes  = first.map(i => i['ftm:dueAt']['@value']).sort();
    const secondDueTimes = second.map(i => i['ftm:dueAt']['@value']).sort();
    assert.deepEqual(firstDueTimes, secondDueTimes);
  });
});
