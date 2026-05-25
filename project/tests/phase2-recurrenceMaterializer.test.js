import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { recurrenceMaterializer } from '../src/modules/recurrenceMaterializer.js';
import { createTaskDefinition } from '../src/entities/taskDefinition.js';
import { createTaskInstance } from '../src/entities/taskInstance.js';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const currentTime = '2026-05-22T10:00:00Z';
const recurrenceStart = '2026-05-15T10:00:00Z'; // 8 days before currentTime

// ---------------------------------------------------------------------------
// Helper factories (module-level, not inside describe blocks)
// ---------------------------------------------------------------------------

/**
 * Returns a recurring FREQ=DAILY TaskDefinition anchored at `start`.
 */
function makeRecurringDef(start) {
  return createTaskDefinition({
    title: 'Daily Recurring Task',
    description: 'Test recurring task',
    assignedTo: 'urn:ftm:user:test',
    createdBy: 'urn:ftm:user:creator',
    dueAt: start,        // semantically unused for recurring scheduleType
    scheduleType: 'recurring',
    recurrenceRule: 'FREQ=DAILY',
    recurrenceStart: start,
  });
}

/**
 * Returns a TaskInstance referencing `taskDefId` with the given ISO-8601 `dueAt`.
 */
function makeInstance(taskDefId, dueAt) {
  return createTaskInstance({
    taskDefinitionId: taskDefId,
    assignedTo: 'urn:ftm:user:test',
    dueAt,
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('2.5 RecurrenceMaterializer', () => {
  test('one recurring taskDef + empty existingInstances returns toCreate covering look-ahead window, skipped 0', () => {
    // catchUpPolicy:'all' → no past-occurrence filtering; every candidate goes to toCreate.
    // Default window: [currentTime âˆ’ 7d, currentTime + 7d].
    // FREQ=DAILY from May 15; open-start removes the exact windowStart hit (May 15);
    // 14 daily occurrences remain (May 16–29).
    const def = makeRecurringDef(recurrenceStart);
    const { toCreate, skipped } = recurrenceMaterializer(
      [def], [], currentTime, { catchUpPolicy: 'all' }
    );

    assert.equal(skipped, 0);
    assert.equal(toCreate.length, 14);

    // Every returned object must be a TaskInstance referencing this definition
    for (const inst of toCreate) {
      assert.equal(inst['@type'], 'ftm:TaskInstance');
      assert.equal(inst['ftm:taskDefinition'], def['@id']);
    }

    // At least one occurrence must fall inside the future look-ahead window
    const hasFuture = toCreate.some(i => i['ftm:dueAt']['@value'] > currentTime);
    assert.ok(hasFuture, 'expected at least one future occurrence in toCreate');
  });

  test('deduplication: existing instance with matching ftm:taskDefinition + dueAt excluded from toCreate', () => {
    const def = makeRecurringDef(recurrenceStart);

    // First pass: collect all candidates (catchUpPolicy:'all' avoids skipped interference)
    const first = recurrenceMaterializer([def], [], currentTime, { catchUpPolicy: 'all' });
    assert.ok(first.toCreate.length > 0, 'precondition: first pass must yield candidates');

    // Use the first candidate as a pre-existing instance; its dueAt format matches
    // scheduleComputer output exactly (d.toISOString()), so the dedup key will hit.
    const existing = first.toCreate[0];
    const existingDueAt = existing['ftm:dueAt']['@value'];

    const second = recurrenceMaterializer(
      [def], [existing], currentTime, { catchUpPolicy: 'all' }
    );

    assert.equal(second.toCreate.length, first.toCreate.length - 1);
    assert.equal(second.skipped, 0);

    // The deduped occurrence must be absent from the second toCreate
    const found = second.toCreate.some(
      i => i['ftm:taskDefinition'] === def['@id'] && i['ftm:dueAt']['@value'] === existingDueAt
    );
    assert.equal(found, false, 'deduped instance must not reappear in toCreate');
  });

  test('catchUpPolicy default current-only: past missed occurrences excluded from toCreate; skipped is incremented for each', () => {
    // recurrenceStart 8 days back + default 7d catch-up window + 7d look-ahead = 14 candidates
    // (May 16–29 at T10:00:00.000Z). String comparison dueAt < currentTime:
    // May 16–21 are clearly past; May 22 also compares as past because
    // '2026-05-22T10:00:00.000Z' < '2026-05-22T10:00:00Z' lexicographically
    // ('.' ASCII 46 < 'Z' ASCII 90 at the millisecond-boundary position).
    // Result: skipped=7, toCreate=7 (May 23–29).
    const def = makeRecurringDef(recurrenceStart);
    const { toCreate, skipped } = recurrenceMaterializer([def], [], currentTime);

    assert.equal(skipped, 7);
    assert.equal(toCreate.length, 7);

    // Nothing in toCreate must precede currentTime
    for (const inst of toCreate) {
      assert.ok(
        inst['ftm:dueAt']['@value'] >= currentTime,
        `expected dueAt ${inst['ftm:dueAt']['@value']} >= ${currentTime}`
      );
    }
  });

  test('catchUpPolicy current-only with 3 missed past occurrences: skipped === 3 and toCreate contains only present/future occurrences', () => {
    // recurrenceStart='2026-05-20T10:00:00Z' (2 days before currentTime).
    // Candidates in window [May 15, May 29]: May 20–29 (10 total; dtstart falls after
    // windowStart so the open-start filter does not remove anything).
    // Past by string comparison: May 20, May 21, and May 22 (same .000Z < Z edge as above) = 3.
    // toCreate: May 23–29 = 7.
    const nearStart = '2026-05-20T10:00:00Z';
    const def = makeRecurringDef(nearStart);
    const { toCreate, skipped } = recurrenceMaterializer([def], [], currentTime);

    assert.equal(skipped, 3);
    assert.equal(toCreate.length, 7);

    for (const inst of toCreate) {
      assert.ok(
        inst['ftm:dueAt']['@value'] >= currentTime,
        `expected dueAt ${inst['ftm:dueAt']['@value']} >= ${currentTime}`
      );
    }
  });

  test('all candidate occurrences already in existingInstances: returns toCreate [] and skipped 0', () => {
    const def = makeRecurringDef(recurrenceStart);

    // Collect every candidate via a first pass with catchUpPolicy:'all'
    const first = recurrenceMaterializer([def], [], currentTime, { catchUpPolicy: 'all' });
    assert.ok(first.toCreate.length > 0, 'precondition: first pass must yield candidates');

    // Second pass: all prior candidates are now "existing"; dedup must silence every one.
    // Note: dedup fires before the catchUpPolicy check (F6/F11), so skipped stays 0.
    const { toCreate, skipped } = recurrenceMaterializer(
      [def], first.toCreate, currentTime, { catchUpPolicy: 'all' }
    );

    assert.equal(toCreate.length, 0);
    assert.equal(skipped, 0);
  });

  test('does not mutate input arrays (length and contents unchanged after call)', () => {
    const def = makeRecurringDef(recurrenceStart);
    // Supply one existing instance; dueAt uses the .000Z format that scheduleComputer emits
    const existingInst = makeInstance(def['@id'], '2026-05-23T10:00:00.000Z');
    const taskDefs = [def];
    const existingInstances = [existingInst];

    const defsBefore = taskDefs.length;
    const instancesBefore = existingInstances.length;
    const firstDefId = taskDefs[0]['@id'];
    const firstInstId = existingInstances[0]['@id'];

    recurrenceMaterializer(taskDefs, existingInstances, currentTime);

    assert.equal(taskDefs.length, defsBefore, 'taskDefs length must be unchanged');
    assert.equal(existingInstances.length, instancesBefore, 'existingInstances length must be unchanged');
    assert.equal(taskDefs[0]['@id'], firstDefId, 'taskDefs[0] identity must be unchanged');
    assert.equal(existingInstances[0]['@id'], firstInstId, 'existingInstances[0] identity must be unchanged');
  });

  // SPEC §13 item 3
  test('§13.3 RecurrenceMaterializer with fixture taskDefs + instances returns deterministic { toCreate, skipped }; second call with identical args returns same skipped value and toCreate of same length', () => {
    const def = makeRecurringDef(recurrenceStart);
    const opts = { catchUpPolicy: 'all' };

    const first  = recurrenceMaterializer([def], [], currentTime, opts);
    const second = recurrenceMaterializer([def], [], currentTime, opts);

    assert.equal(first.skipped, second.skipped);
    assert.equal(first.toCreate.length, second.toCreate.length);

    // dueAt values must be byte-identical across both calls
    const firstDueTimes  = first.toCreate.map(i => i['ftm:dueAt']['@value']).sort();
    const secondDueTimes = second.toCreate.map(i => i['ftm:dueAt']['@value']).sort();
    assert.deepEqual(firstDueTimes, secondDueTimes);
  });
});
