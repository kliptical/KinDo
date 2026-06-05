import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { parentDashboard } from '../src/flows/parentDashboard.js';
import { createInMemoryStateAdapter } from '../src/adapters/state/inMemoryStateAdapter.js';
import { createTaskInstance } from '../src/entities/taskInstance.js';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CHILD_ID = 'urn:ftm:user:child-test';
const OTHER_CHILD_ID = 'urn:ftm:user:child-other';
const DEF_ID = 'urn:ftm:task:def-fixture';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Saves 5 TaskInstances (3 pending, 2 completed) to state, all assigned
 * to CHILD_ID. Pending instances are created with out-of-order dueAt values
 * so that the ascending-sort guarantee is observable.
 *
 * @returns {Promise<{ state: import('../src/adapters/state/inMemoryStateAdapter.js').StateAdapter }>}
 */
async function setupMixedInstances() {
  const state = createInMemoryStateAdapter();

  // 3 pending — deliberately not in dueAt order to exercise the sort guarantee
  const pendingDueDates = [
    '2026-06-03T08:00:00Z',
    '2026-06-01T08:00:00Z',
    '2026-06-02T08:00:00Z',
  ];

  for (const dueAt of pendingDueDates) {
    const inst = createTaskInstance({
      taskDefinitionId: DEF_ID,
      assignedTo: CHILD_ID,
      dueAt,
    });
    await state.saveTaskInstance(inst);
  }

  // 2 completed — spread createTaskInstance output and override completionState
  const completedDueDates = [
    '2026-05-29T08:00:00Z',
    '2026-05-30T08:00:00Z',
  ];

  for (const dueAt of completedDueDates) {
    const inst = createTaskInstance({
      taskDefinitionId: DEF_ID,
      assignedTo: CHILD_ID,
      dueAt,
    });
    const completed = {
      ...inst,
      'ftm:completionState': {
        ...inst['ftm:completionState'],
        'ftm:status': 'completed',
        'ftm:completedAt': new Date().toISOString(),
        'ftm:completedBy': CHILD_ID,
        'ftm:completedByRole': 'child',
      },
    };
    await state.saveTaskInstance(completed);
  }

  return { state };
}

// ---------------------------------------------------------------------------
// 4.4 §8.4 parentDashboard
// ---------------------------------------------------------------------------

describe('4.4 §8.4 parentDashboard', () => {
  test('returns { pending, completed } shape', async () => {
    const { state } = await setupMixedInstances();
    const result = await parentDashboard({ stateAdapter: state, childId: CHILD_ID });
    assert.ok('pending' in result, 'result must have pending key');
    assert.ok('completed' in result, 'result must have completed key');
    assert.ok(Array.isArray(result.pending), 'pending must be an array');
    assert.ok(Array.isArray(result.completed), 'completed must be an array');
  });

  test('pending list contains only instances with completionState.status pending', async () => {
    const { state } = await setupMixedInstances();
    const { pending } = await parentDashboard({ stateAdapter: state, childId: CHILD_ID });
    assert.equal(pending.length, 3, 'expected 3 pending instances');
    for (const inst of pending) {
      assert.equal(
        inst['ftm:completionState']['ftm:status'],
        'pending',
        'every item in pending must have ftm:completionState.ftm:status === pending',
      );
    }
  });

  test('completed list contains only instances with completionState.status completed', async () => {
    const { state } = await setupMixedInstances();
    const { completed } = await parentDashboard({ stateAdapter: state, childId: CHILD_ID });
    assert.equal(completed.length, 2, 'expected 2 completed instances');
    for (const inst of completed) {
      assert.equal(
        inst['ftm:completionState']['ftm:status'],
        'completed',
        'every item in completed must have ftm:completionState.ftm:status === completed',
      );
    }
  });

  test('pending list is sorted by dueAt ascending', async () => {
    const { state } = await setupMixedInstances();
    const { pending } = await parentDashboard({ stateAdapter: state, childId: CHILD_ID });
    assert.equal(pending.length, 3, 'expected 3 pending instances to verify sort order');
    const dueDates = pending.map(inst => inst['ftm:dueAt']['@value']);
    for (let i = 1; i < dueDates.length; i++) {
      assert.ok(
        dueDates[i - 1] <= dueDates[i],
        `pending[${i - 1}].dueAt (${dueDates[i - 1]}) must be <= pending[${i}].dueAt (${dueDates[i]})`,
      );
    }
  });

  test('childId filter excludes other children\'s instances', async () => {
    const { state } = await setupMixedInstances();

    // Add one instance assigned to a different child — must not appear in the result
    const otherInst = createTaskInstance({
      taskDefinitionId: DEF_ID,
      assignedTo: OTHER_CHILD_ID,
      dueAt: '2026-06-10T08:00:00Z',
    });
    await state.saveTaskInstance(otherInst);

    const { pending, completed } = await parentDashboard({
      stateAdapter: state,
      childId: CHILD_ID,
    });

    const allReturned = [...pending, ...completed];
    for (const inst of allReturned) {
      assert.equal(
        inst['ftm:assignedTo'],
        CHILD_ID,
        'all returned instances must be assigned to CHILD_ID; other children must be excluded',
      );
    }
  });
});
