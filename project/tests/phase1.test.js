import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { FTM_CONTEXT } from '../src/context.js';
import { createTaskDefinition } from '../src/entities/taskDefinition.js';
import { createTaskInstance } from '../src/entities/taskInstance.js';
import { createReminderEvent } from '../src/entities/reminderEvent.js';
import { createUser } from '../src/entities/user.js';
import { validateTaskDefinition } from '../src/validation/validateTaskDefinition.js';
import { validateTaskInstance } from '../src/validation/validateTaskInstance.js';
import { stripFtmPrefix, expandFtmPrefix } from '../src/utils/roundTrip.js';

// ---------------------------------------------------------------------------
// Shared fixture params
// ---------------------------------------------------------------------------

const BASE_TD_PARAMS = {
  title: 'Test Task',
  description: 'A test task description',
  assignedTo: 'urn:ftm:user:abc',
  createdBy: 'urn:ftm:user:def',
  dueAt: '2026-05-22T18:00:00Z',
};

const BASE_TI_PARAMS = {
  taskDefinitionId: 'urn:ftm:task:abc',
  assignedTo: 'urn:ftm:user:def',
  dueAt: '2026-05-22T18:00:00Z',
};

// ---------------------------------------------------------------------------
// 1.1 context
// ---------------------------------------------------------------------------

describe('1.1 context', () => {
  test('FTM_CONTEXT.ftm is the correct namespace URI', () => {
    assert.equal(FTM_CONTEXT.ftm, 'https://schema.familytaskmanager.local/v1/');
  });

  test('FTM_CONTEXT.xsd is the correct XSD namespace URI', () => {
    assert.equal(FTM_CONTEXT.xsd, 'http://www.w3.org/2001/XMLSchema#');
  });

  test('FTM_CONTEXT.schema is the correct schema.org URI', () => {
    assert.equal(FTM_CONTEXT.schema, 'https://schema.org/');
  });
});

// ---------------------------------------------------------------------------
// 1.2 TaskDefinition factory
// ---------------------------------------------------------------------------

describe('1.2 TaskDefinition factory', () => {
  test('@type is ftm:TaskDefinition', () => {
    const td = createTaskDefinition(BASE_TD_PARAMS);
    assert.equal(td['@type'], 'ftm:TaskDefinition');
  });

  test('@id matches urn:ftm:task: prefix', () => {
    const td = createTaskDefinition(BASE_TD_PARAMS);
    assert.match(td['@id'], /^urn:ftm:task:/);
  });

  test('ftm:version is 1', () => {
    const td = createTaskDefinition(BASE_TD_PARAMS);
    assert.equal(td['ftm:version'], 1);
  });

  test('ftm:clientSequence is 1', () => {
    const td = createTaskDefinition(BASE_TD_PARAMS);
    assert.equal(td['ftm:clientSequence'], 1);
  });

  test('ftm:status is active', () => {
    const td = createTaskDefinition(BASE_TD_PARAMS);
    assert.equal(td['ftm:status'], 'active');
  });

  test('one-time schedule: scheduleType one-time, recurrenceRule null, recurrenceStart null', () => {
    const td = createTaskDefinition(BASE_TD_PARAMS);
    assert.equal(td['ftm:schedule']['ftm:scheduleType'], 'one-time');
    assert.equal(td['ftm:schedule']['ftm:recurrenceRule'], null);
    assert.equal(td['ftm:schedule']['ftm:recurrenceStart'], null);
  });

  test('recurring schedule: scheduleType recurring, recurrenceRule and recurrenceStart non-null', () => {
    const td = createTaskDefinition({
      ...BASE_TD_PARAMS,
      scheduleType: 'recurring',
      recurrenceRule: 'FREQ=WEEKLY',
      recurrenceStart: '2026-05-22T00:00:00Z',
    });
    assert.equal(td['ftm:schedule']['ftm:scheduleType'], 'recurring');
    assert.ok(td['ftm:schedule']['ftm:recurrenceRule'] !== null);
    assert.ok(td['ftm:schedule']['ftm:recurrenceStart'] !== null);
  });

  test('once reminderPolicy: mode is once, intervalSeconds is null', () => {
    const td = createTaskDefinition(BASE_TD_PARAMS);
    assert.equal(td['ftm:reminderPolicy']['ftm:mode'], 'once');
    assert.equal(td['ftm:reminderPolicy']['ftm:intervalSeconds'], null);
  });

  test('two calls produce distinct @id values (no I/O caching)', () => {
    const td1 = createTaskDefinition(BASE_TD_PARAMS);
    const td2 = createTaskDefinition(BASE_TD_PARAMS);
    assert.notEqual(td1['@id'], td2['@id']);
  });
});

// ---------------------------------------------------------------------------
// 1.3 TaskInstance factory
// ---------------------------------------------------------------------------

describe('1.3 TaskInstance factory', () => {
  test('@type is ftm:TaskInstance', () => {
    const ti = createTaskInstance(BASE_TI_PARAMS);
    assert.equal(ti['@type'], 'ftm:TaskInstance');
  });

  test('@id matches urn:ftm:instance: prefix', () => {
    const ti = createTaskInstance(BASE_TI_PARAMS);
    assert.match(ti['@id'], /^urn:ftm:instance:/);
  });

  test('completionState ftm:status is pending', () => {
    const ti = createTaskInstance(BASE_TI_PARAMS);
    assert.equal(ti['ftm:completionState']['ftm:status'], 'pending');
  });

  test('completionState completedAt, completedBy, completedByRole are null', () => {
    const ti = createTaskInstance(BASE_TI_PARAMS);
    assert.equal(ti['ftm:completionState']['ftm:completedAt'], null);
    assert.equal(ti['ftm:completionState']['ftm:completedBy'], null);
    assert.equal(ti['ftm:completionState']['ftm:completedByRole'], null);
  });

  test('reminderSummary ftm:totalSent is 0', () => {
    const ti = createTaskInstance(BASE_TI_PARAMS);
    assert.equal(ti['ftm:reminderSummary']['ftm:totalSent'], 0);
  });

  test('reminderSummary ftm:recentEvents is an empty array', () => {
    const ti = createTaskInstance(BASE_TI_PARAMS);
    assert.deepEqual(ti['ftm:reminderSummary']['ftm:recentEvents'], []);
  });

  test('ftm:clientSequence is 1', () => {
    const ti = createTaskInstance(BASE_TI_PARAMS);
    assert.equal(ti['ftm:clientSequence'], 1);
  });
});

// ---------------------------------------------------------------------------
// 1.4 ReminderEvent
// ---------------------------------------------------------------------------

describe('1.4 ReminderEvent', () => {
  const SENT_AT = '2026-05-22T18:00:00Z';

  test('delivered status is accepted without throwing', () => {
    assert.doesNotThrow(() => createReminderEvent(SENT_AT, 'delivered'));
  });

  test('failed status is accepted without throwing', () => {
    assert.doesNotThrow(() => createReminderEvent(SENT_AT, 'failed'));
  });

  test('deferred status is accepted without throwing', () => {
    assert.doesNotThrow(() => createReminderEvent(SENT_AT, 'deferred'));
  });

  test('unknown status throws an error', () => {
    assert.throws(() => createReminderEvent(SENT_AT, 'unknown'));
  });
});

// ---------------------------------------------------------------------------
// 1.5 User factory
// ---------------------------------------------------------------------------

describe('1.5 User factory', () => {
  test('@type is ftm:User', () => {
    const u = createUser({ role: 'parent', displayName: 'Alice' });
    assert.equal(u['@type'], 'ftm:User');
  });

  test('parent role is accepted without throwing', () => {
    assert.doesNotThrow(() => createUser({ role: 'parent', displayName: 'Alice' }));
  });

  test('child role is accepted without throwing', () => {
    assert.doesNotThrow(() => createUser({ role: 'child', displayName: 'Bob' }));
  });

  test('ftm:displayName is stored as a non-empty string', () => {
    const u = createUser({ role: 'parent', displayName: 'Alice' });
    assert.equal(typeof u['ftm:displayName'], 'string');
    assert.ok(u['ftm:displayName'].length > 0);
  });

  test('ftm:notificationTokens defaults to an empty array', () => {
    const u = createUser({ role: 'parent', displayName: 'Alice' });
    assert.deepEqual(u['ftm:notificationTokens'], []);
  });
});

// ---------------------------------------------------------------------------
// 1.6 round-trip
// ---------------------------------------------------------------------------

describe('1.6 round-trip', () => {
  test('JSON serialize/deserialize deep-equals original TaskDefinition', () => {
    const td = createTaskDefinition(BASE_TD_PARAMS);
    assert.deepEqual(JSON.parse(JSON.stringify(td)), td);
  });

  test('stripFtmPrefix then expandFtmPrefix round-trips to original', () => {
    const td = createTaskDefinition(BASE_TD_PARAMS);
    const stripped = stripFtmPrefix(td);
    const restored = expandFtmPrefix(stripped);
    assert.deepEqual(restored, td);
  });

  test('@context survives strip and expand unchanged', () => {
    const td = createTaskDefinition(BASE_TD_PARAMS);
    const restored = expandFtmPrefix(stripFtmPrefix(td));
    assert.equal(restored['@context'], td['@context']);
  });

  test('@type survives strip and expand unchanged', () => {
    const td = createTaskDefinition(BASE_TD_PARAMS);
    const restored = expandFtmPrefix(stripFtmPrefix(td));
    assert.equal(restored['@type'], td['@type']);
  });

  test('@id survives strip and expand unchanged', () => {
    const td = createTaskDefinition(BASE_TD_PARAMS);
    const restored = expandFtmPrefix(stripFtmPrefix(td));
    assert.equal(restored['@id'], td['@id']);
  });
});

// ---------------------------------------------------------------------------
// 1.7 validateTaskDefinition
// ---------------------------------------------------------------------------

describe('1.7 validateTaskDefinition', () => {
  test('empty title produces errors', () => {
    const td = createTaskDefinition({ ...BASE_TD_PARAMS, title: '' });
    const { errors } = validateTaskDefinition(td);
    assert.ok(errors.length > 0);
  });

  test('title of 201 chars produces errors', () => {
    const td = createTaskDefinition({ ...BASE_TD_PARAMS, title: 'a'.repeat(201) });
    const { errors } = validateTaskDefinition(td);
    assert.ok(errors.length > 0);
  });

  test('title of 200 chars produces no title error', () => {
    const td = createTaskDefinition({ ...BASE_TD_PARAMS, title: 'a'.repeat(200) });
    const { errors } = validateTaskDefinition(td);
    const titleErrors = errors.filter((e) => e.includes('title'));
    assert.equal(titleErrors.length, 0);
  });

  test('recurring scheduleType with null recurrenceRule produces recurring rule error', () => {
    const td = createTaskDefinition({
      ...BASE_TD_PARAMS,
      scheduleType: 'recurring',
      recurrenceRule: null,
      recurrenceStart: '2026-05-22T00:00:00Z',
    });
    const { errors } = validateTaskDefinition(td);
    assert.ok(errors.some((e) => e.includes('recurrenceRule')));
  });

  test('recurring scheduleType with null recurrenceStart produces recurrenceStart error', () => {
    const td = createTaskDefinition({
      ...BASE_TD_PARAMS,
      scheduleType: 'recurring',
      recurrenceRule: 'FREQ=WEEKLY',
      recurrenceStart: null,
    });
    const { errors } = validateTaskDefinition(td);
    assert.ok(errors.some((e) => e.includes('recurrenceStart')));
  });

  test('recurring scheduleType with non-date recurrenceStart produces datetime error', () => {
    const td = createTaskDefinition({
      ...BASE_TD_PARAMS,
      scheduleType: 'recurring',
      recurrenceRule: 'FREQ=WEEKLY',
      recurrenceStart: 'not-a-date',
    });
    const { errors } = validateTaskDefinition(td);
    assert.ok(errors.some((e) => e.includes('datetime')));
  });

  test('persistent reminderMode with intervalSeconds 59 produces errors', () => {
    const td = createTaskDefinition({
      ...BASE_TD_PARAMS,
      reminderMode: 'persistent',
      intervalSeconds: 59,
    });
    const { errors } = validateTaskDefinition(td);
    assert.ok(errors.length > 0);
  });

  test('persistent reminderMode with intervalSeconds 60 produces no intervalSeconds error', () => {
    const td = createTaskDefinition({
      ...BASE_TD_PARAMS,
      reminderMode: 'persistent',
      intervalSeconds: 60,
    });
    const { errors } = validateTaskDefinition(td);
    const intervalErrors = errors.filter((e) => e.includes('intervalSeconds'));
    assert.equal(intervalErrors.length, 0);
  });

  test('persistUntilSeconds 100 with intervalSeconds 200 produces errors', () => {
    const td = createTaskDefinition({
      ...BASE_TD_PARAMS,
      reminderMode: 'persistent',
      intervalSeconds: 200,
      persistUntilSeconds: 100,
    });
    const { errors } = validateTaskDefinition(td);
    assert.ok(errors.length > 0);
  });

  test('persistUntilSeconds 200 with intervalSeconds 200 produces no persistUntilSeconds error', () => {
    const td = createTaskDefinition({
      ...BASE_TD_PARAMS,
      reminderMode: 'persistent',
      intervalSeconds: 200,
      persistUntilSeconds: 200,
    });
    const { errors } = validateTaskDefinition(td);
    const persistErrors = errors.filter((e) => e.includes('persistUntilSeconds'));
    assert.equal(persistErrors.length, 0);
  });

  test('fully valid one-time TaskDefinition is valid with no errors', () => {
    const td = createTaskDefinition(BASE_TD_PARAMS);
    const { valid, errors } = validateTaskDefinition(td);
    assert.equal(valid, true);
    assert.equal(errors.length, 0);
  });
});

// ---------------------------------------------------------------------------
// 1.8 validateTaskInstance
// ---------------------------------------------------------------------------

describe('1.8 validateTaskInstance', () => {
  test('dueAt @value not-a-datetime produces errors', () => {
    const ti = createTaskInstance({ ...BASE_TI_PARAMS, dueAt: 'not-a-datetime' });
    const { errors } = validateTaskInstance(ti);
    assert.ok(errors.length > 0);
  });

  test('clientSequence 0 produces errors', () => {
    const ti = createTaskInstance(BASE_TI_PARAMS);
    ti['ftm:clientSequence'] = 0;
    const { errors } = validateTaskInstance(ti);
    assert.ok(errors.length > 0);
  });

  test('clientSequence -1 produces errors', () => {
    const ti = createTaskInstance(BASE_TI_PARAMS);
    ti['ftm:clientSequence'] = -1;
    const { errors } = validateTaskInstance(ti);
    assert.ok(errors.length > 0);
  });

  test('clientSequence 1.5 produces errors', () => {
    const ti = createTaskInstance(BASE_TI_PARAMS);
    ti['ftm:clientSequence'] = 1.5;
    const { errors } = validateTaskInstance(ti);
    assert.ok(errors.length > 0);
  });

  test('valid dueAt and clientSequence 1 is valid with no errors', () => {
    const ti = createTaskInstance(BASE_TI_PARAMS);
    const { valid, errors } = validateTaskInstance(ti);
    assert.equal(valid, true);
    assert.equal(errors.length, 0);
  });
});
