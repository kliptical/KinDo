import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { parentCreatesTask } from '../src/flows/parentCreatesTask.js';
import { createInMemoryStateAdapter } from '../src/adapters/state/inMemoryStateAdapter.js';
import { createTestOrchestrationAdapter } from '../src/adapters/orchestration/testOrchestrationAdapter.js';
import { createUser } from '../src/entities/user.js';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function setup() {
  const state = createInMemoryStateAdapter();
  const orch = createTestOrchestrationAdapter();
  const parent = createUser({ role: 'parent', displayName: 'Test Parent' });
  const child = createUser({ role: 'child', displayName: 'Test Child' });
  await state.saveUser(parent);
  await state.saveUser(child);
  return { state, orch, parent, child };
}

function oneTimeParams(child, parent, dueAt) {
  return {
    title: 'One-Time Task',
    description: 'A one-time test task',
    assignedTo: child['@id'],
    createdBy: parent['@id'],
    dueAt,
    scheduleType: 'one-time',
  };
}

function recurringParams(child, parent, recurrenceStart) {
  return {
    title: 'Daily Recurring Task',
    description: 'A daily recurring test task',
    assignedTo: child['@id'],
    createdBy: parent['@id'],
    scheduleType: 'recurring',
    recurrenceRule: 'FREQ=DAILY',
    recurrenceStart,
  };
}

// ---------------------------------------------------------------------------
// 4.1 §8.1 parentCreatesTask
// ---------------------------------------------------------------------------

describe('4.1 §8.1 parentCreatesTask', () => {
  test('one-time task: TaskDefinition is stored (getTaskDefinition returns it)', async () => {
    const { state, orch, parent, child } = await setup();
    const dueAt = new Date(Date.now() + 86_400_000).toISOString(); // 1 day from now
    const { taskDef } = await parentCreatesTask({
      stateAdapter: state,
      orchestrationAdapter: orch,
      params: oneTimeParams(child, parent, dueAt),
    });
    const stored = await state.getTaskDefinition(taskDef['@id']);
    assert.ok(stored !== null, 'TaskDefinition should be stored');
    assert.equal(stored['@id'], taskDef['@id']);
  });

  test('one-time task produces exactly 1 stored instance (getTaskInstance + listTaskInstances confirms count)', async () => {
    const { state, orch, parent, child } = await setup();
    const dueAt = new Date(Date.now() + 86_400_000).toISOString();
    const { taskDef, instances } = await parentCreatesTask({
      stateAdapter: state,
      orchestrationAdapter: orch,
      params: oneTimeParams(child, parent, dueAt),
    });
    assert.equal(instances.length, 1, 'flow should return 1 instance');
    const retrieved = await state.getTaskInstance(instances[0]['@id']);
    assert.ok(retrieved !== null, 'instance should be retrievable by @id');
    const all = await state.listTaskInstances({ taskDefinitionId: taskDef['@id'] });
    assert.equal(all.length, 1, 'listTaskInstances should return exactly 1');
  });

  test('one-time task registers exactly 1 orchestration callback at the instance dueAt (assert via orch internals OR a fixture spy)', async () => {
    const { state, parent, child } = await setup();
    const scheduleAtCalls = [];
    const innerOrch = createTestOrchestrationAdapter();
    const spyOrch = {
      ...innerOrch,
      scheduleAt(isoTimestamp, callback) {
        scheduleAtCalls.push(isoTimestamp);
        return innerOrch.scheduleAt(isoTimestamp, callback);
      },
    };
    const dueAt = new Date(Date.now() + 86_400_000).toISOString();
    const { instances } = await parentCreatesTask({
      stateAdapter: state,
      orchestrationAdapter: spyOrch,
      params: oneTimeParams(child, parent, dueAt),
    });
    assert.equal(scheduleAtCalls.length, 1, 'scheduleAt should be called exactly once');
    assert.equal(
      scheduleAtCalls[0],
      instances[0]['ftm:dueAt']['@value'],
      'scheduleAt timestamp should match the instance ftm:dueAt @value',
    );
  });

  test('recurring task (FREQ=DAILY recurrenceStart 1 day from now, lookAheadSeconds 604800) produces 7 stored instances and 7 registered callbacks', async () => {
    const { state, parent, child } = await setup();
    const scheduleAtCalls = [];
    const innerOrch = createTestOrchestrationAdapter();
    const spyOrch = {
      ...innerOrch,
      scheduleAt(isoTimestamp, callback) {
        scheduleAtCalls.push(isoTimestamp);
        return innerOrch.scheduleAt(isoTimestamp, callback);
      },
    };
    // recurrenceStart 1 day out: 7 daily occurrences fit in the default 604800 s window
    const recurrenceStart = new Date(Date.now() + 86_400_000).toISOString();
    const { taskDef, instances } = await parentCreatesTask({
      stateAdapter: state,
      orchestrationAdapter: spyOrch,
      params: recurringParams(child, parent, recurrenceStart),
    });
    assert.equal(instances.length, 7, 'flow should return 7 instances');
    const all = await state.listTaskInstances({ taskDefinitionId: taskDef['@id'] });
    assert.equal(all.length, 7, 'listTaskInstances should return 7 stored instances');
    assert.equal(scheduleAtCalls.length, 7, 'scheduleAt should be called 7 times');
  });

  test('TaskDefinition stored includes ftm:clientSequence === 1 and ftm:updatedAt with @value set', async () => {
    const { state, orch, parent, child } = await setup();
    const dueAt = new Date(Date.now() + 86_400_000).toISOString();
    const { taskDef } = await parentCreatesTask({
      stateAdapter: state,
      orchestrationAdapter: orch,
      params: oneTimeParams(child, parent, dueAt),
    });
    const stored = await state.getTaskDefinition(taskDef['@id']);
    assert.equal(stored['ftm:clientSequence'], 1, 'ftm:clientSequence should be 1');
    assert.ok(
      stored['ftm:updatedAt'] != null &&
        typeof stored['ftm:updatedAt']['@value'] === 'string' &&
        stored['ftm:updatedAt']['@value'] !== '',
      'ftm:updatedAt should be an object with a non-empty @value string',
    );
  });
});
