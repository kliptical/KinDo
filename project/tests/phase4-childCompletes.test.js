import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { childCompletes } from '../src/flows/childCompletes.js';
import { createInMemoryStateAdapter } from '../src/adapters/state/inMemoryStateAdapter.js';
import { createTestOrchestrationAdapter } from '../src/adapters/orchestration/testOrchestrationAdapter.js';
import { ftmCompletionEmitter } from '../src/events/completionEmitter.js';
import { createTaskInstance } from '../src/entities/taskInstance.js';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function setupPendingInstance() {
  const state = createInMemoryStateAdapter();
  const orch = createTestOrchestrationAdapter();
  const instance = createTaskInstance({
    taskDefinitionId: 'urn:ftm:task:test-def',
    assignedTo: 'urn:ftm:user:test-child',
    dueAt: new Date(Date.now() + 86_400_000).toISOString(), // 1 day from now
  });
  await state.saveTaskInstance(instance);
  const instanceId = instance['@id'];
  const childId = 'urn:ftm:user:test-child';
  return { state, orch, instanceId, childId };
}

// ---------------------------------------------------------------------------
// 4.3 §8.3 childCompletes
// ---------------------------------------------------------------------------

describe('4.3 §8.3 childCompletes', () => {
  test('saved instance status becomes completed and completedByRole === child', async () => {
    const { state, orch, instanceId, childId } = await setupPendingInstance();
    const currentTime = new Date().toISOString();
    const result = await childCompletes({
      stateAdapter: state,
      orchestrationAdapter: orch,
      instanceId,
      childId,
      currentTime,
      reminderHandles: [],
    });
    assert.equal(result.completed, true, 'result.completed should be true');
    const stored = await state.getTaskInstance(instanceId);
    assert.equal(
      stored['ftm:completionState']['ftm:status'],
      'completed',
      'stored instance ftm:completionState.ftm:status should be completed',
    );
    assert.equal(
      stored['ftm:completionState']['ftm:completedByRole'],
      'child',
      'stored instance ftm:completionState.ftm:completedByRole should be child',
    );
  });

  test('orchestrationAdapter.cancel called for each handle in reminderHandles array (use a tracking handles array)', async () => {
    const { state, instanceId, childId } = await setupPendingInstance();
    const cancelledHandles = [];
    const innerOrch = createTestOrchestrationAdapter();
    const spyOrch = {
      ...innerOrch,
      cancel(handle) {
        cancelledHandles.push(handle);
        return innerOrch.cancel(handle);
      },
    };
    const fakeHandles = ['handle-aaa', 'handle-bbb', 'handle-ccc'];
    await childCompletes({
      stateAdapter: state,
      orchestrationAdapter: spyOrch,
      instanceId,
      childId,
      currentTime: new Date().toISOString(),
      reminderHandles: fakeHandles,
    });
    assert.deepEqual(
      cancelledHandles,
      fakeHandles,
      'cancel should be called once per handle, in order',
    );
  });

  test('ftmCompletionEmitter emits ftm:taskCompleted with the updated instance (register a listener; call flow; assert listener received)', async () => {
    const { state, orch, instanceId, childId } = await setupPendingInstance();
    let received = null;
    ftmCompletionEmitter.once('ftm:taskCompleted', (updatedInstance) => {
      received = updatedInstance;
    });
    const result = await childCompletes({
      stateAdapter: state,
      orchestrationAdapter: orch,
      instanceId,
      childId,
      currentTime: new Date().toISOString(),
      reminderHandles: [],
    });
    assert.ok(received !== null, 'ftmCompletionEmitter should have emitted ftm:taskCompleted');
    assert.equal(
      received['@id'],
      result.updated['@id'],
      'emitted instance @id should match result.updated @id',
    );
    assert.equal(
      received['ftm:completionState']['ftm:status'],
      'completed',
      'emitted instance should have completed status',
    );
  });

  test('updated instance is retrievable via getTaskInstance (saved correctly)', async () => {
    const { state, orch, instanceId, childId } = await setupPendingInstance();
    const result = await childCompletes({
      stateAdapter: state,
      orchestrationAdapter: orch,
      instanceId,
      childId,
      currentTime: new Date().toISOString(),
      reminderHandles: [],
    });
    assert.equal(result.completed, true, 'result.completed should be true');
    const stored = await state.getTaskInstance(instanceId);
    assert.ok(stored !== null, 'instance should be retrievable after completion');
    assert.equal(
      stored['ftm:completionState']['ftm:status'],
      'completed',
      'retrieved instance should have completed status',
    );
    assert.equal(
      stored['@id'],
      result.updated['@id'],
      'retrieved instance @id should match result.updated @id',
    );
  });

  test('non-existent instanceId returns { completed: false, reason: instance-not-found }', async () => {
    const state = createInMemoryStateAdapter();
    const orch = createTestOrchestrationAdapter();
    const result = await childCompletes({
      stateAdapter: state,
      orchestrationAdapter: orch,
      instanceId: 'urn:ftm:instance:does-not-exist',
      childId: 'urn:ftm:user:test-child',
      currentTime: new Date().toISOString(),
    });
    assert.equal(result.completed, false, 'result.completed should be false');
    assert.equal(result.reason, 'instance-not-found', 'result.reason should be instance-not-found');
  });
});
