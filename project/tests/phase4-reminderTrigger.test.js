import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { reminderTrigger } from '../src/flows/reminderTrigger.js';
import { createInMemoryStateAdapter } from '../src/adapters/state/inMemoryStateAdapter.js';
import { createTestOrchestrationAdapter } from '../src/adapters/orchestration/testOrchestrationAdapter.js';
import { createNoopNotificationAdapter } from '../src/adapters/notification/noopNotificationAdapter.js';
import { createTaskDefinition } from '../src/entities/taskDefinition.js';
import { createTaskInstance } from '../src/entities/taskInstance.js';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function setupDueInstance(reminderMode = 'once') {
  const state = createInMemoryStateAdapter();
  const orch = createTestOrchestrationAdapter();
  const notif = createNoopNotificationAdapter();

  const taskDef = createTaskDefinition({
    title: 'Test Reminder Task',
    description: 'Test description',
    assignedTo: 'urn:ftm:user:test-child',
    createdBy: 'urn:ftm:user:test-parent',
    dueAt: new Date(Date.now() - 1000).toISOString(), // 1s in the past
    reminderMode,
    intervalSeconds: reminderMode === 'persistent' ? 300 : null,
    persistUntilSeconds: reminderMode === 'persistent' ? 86400 : null,
  });
  await state.saveTaskDefinition(taskDef);

  const instance = createTaskInstance({
    taskDefinitionId: taskDef['@id'],
    assignedTo: 'urn:ftm:user:test-child',
    dueAt: new Date(Date.now() - 1000).toISOString(), // 1s in the past so reminderEvaluator returns shouldRemind true
  });
  await state.saveTaskInstance(instance);

  return { state, orch, notif, instanceId: instance['@id'], taskDef };
}

async function setupWithSendSpy() {
  const { state, orch, notif, instanceId } = await setupDueInstance();
  const sendCount = []; // captures each send invocation's payload; length == call count
  const origSend = notif.send.bind(notif);
  notif.send = async (payload) => {
    sendCount.push(payload);
    return origSend(payload);
  };
  return { state, orch, notif, instanceId, sendCount };
}

// ---------------------------------------------------------------------------
// 4.2 §8.2 reminderTrigger
// ---------------------------------------------------------------------------

describe('4.2 §8.2 reminderTrigger', () => {
  test('shouldRemind true: notificationAdapter.send called exactly once with requestForegroundDisplay true', async () => {
    const { state, orch, notif, instanceId, sendCount } = await setupWithSendSpy();
    const currentTime = new Date().toISOString();
    await reminderTrigger({
      stateAdapter: state,
      notificationAdapter: notif,
      orchestrationAdapter: orch,
      instanceId,
      currentTime,
    });
    assert.equal(sendCount.length, 1, 'send should be called exactly once');
    assert.equal(
      sendCount[0].requestForegroundDisplay,
      true,
      'notification payload should have requestForegroundDisplay: true',
    );
  });

  test('after send: instance reminderSummary.totalSent equals previous + 1', async () => {
    const { state, orch, notif, instanceId } = await setupDueInstance();
    const before = await state.getTaskInstance(instanceId);
    const prevTotalSent = before['ftm:reminderSummary']['ftm:totalSent'];
    const currentTime = new Date().toISOString();
    await reminderTrigger({
      stateAdapter: state,
      notificationAdapter: notif,
      orchestrationAdapter: orch,
      instanceId,
      currentTime,
    });
    const stored = await state.getTaskInstance(instanceId);
    assert.equal(
      stored['ftm:reminderSummary']['ftm:totalSent'],
      prevTotalSent + 1,
      'totalSent should be incremented by 1',
    );
  });

  test('after send: instance reminderSummary.lastSentAt equals currentTime', async () => {
    const { state, orch, notif, instanceId } = await setupDueInstance();
    const currentTime = new Date().toISOString();
    await reminderTrigger({
      stateAdapter: state,
      notificationAdapter: notif,
      orchestrationAdapter: orch,
      instanceId,
      currentTime,
    });
    const stored = await state.getTaskInstance(instanceId);
    assert.equal(
      stored['ftm:reminderSummary']['ftm:lastSentAt'],
      currentTime,
      'lastSentAt should equal currentTime',
    );
  });

  test('after send: instance reminderSummary.lastDeliveryStatus reflects receipt.status (delivered for noop)', async () => {
    const { state, orch, notif, instanceId } = await setupDueInstance();
    const currentTime = new Date().toISOString();
    await reminderTrigger({
      stateAdapter: state,
      notificationAdapter: notif,
      orchestrationAdapter: orch,
      instanceId,
      currentTime,
    });
    const stored = await state.getTaskInstance(instanceId);
    assert.equal(
      stored['ftm:reminderSummary']['ftm:lastDeliveryStatus'],
      'delivered',
      'lastDeliveryStatus should be delivered (noop adapter returns delivered)',
    );
  });

  test('after send: instance reminderSummary.recentEvents has the new ReminderEvent prepended; length capped at 3', async () => {
    const { state, orch, notif, instanceId } = await setupDueInstance('persistent');
    // Pre-populate with 3 existing events to exercise the slice(0, 3) cap.
    // lastDeliveryStatus: 'failed' triggers the retry-after-failure branch in
    // reminderEvaluator so shouldRemind is true regardless of interval elapsed.
    const base = await state.getTaskInstance(instanceId);
    const prePopulated = {
      ...base,
      'ftm:clientSequence': 2,
      'ftm:reminderSummary': {
        ...base['ftm:reminderSummary'],
        'ftm:totalSent': 3,
        'ftm:lastSentAt': '2026-05-01T10:00:00Z',
        'ftm:lastDeliveryStatus': 'failed',
        'ftm:recentEvents': [
          {
            '@type': 'ftm:ReminderEvent',
            'ftm:sentAt': { '@type': 'xsd:dateTime', '@value': '2026-05-01T10:00:00Z' },
            'ftm:deliveryStatus': 'failed',
          },
          {
            '@type': 'ftm:ReminderEvent',
            'ftm:sentAt': { '@type': 'xsd:dateTime', '@value': '2026-05-01T09:00:00Z' },
            'ftm:deliveryStatus': 'delivered',
          },
          {
            '@type': 'ftm:ReminderEvent',
            'ftm:sentAt': { '@type': 'xsd:dateTime', '@value': '2026-05-01T08:00:00Z' },
            'ftm:deliveryStatus': 'delivered',
          },
        ],
      },
    };
    await state.saveTaskInstance(prePopulated);
    const currentTime = new Date().toISOString();
    await reminderTrigger({
      stateAdapter: state,
      notificationAdapter: notif,
      orchestrationAdapter: orch,
      instanceId,
      currentTime,
    });
    const stored = await state.getTaskInstance(instanceId);
    const events = stored['ftm:reminderSummary']['ftm:recentEvents'];
    assert.equal(events.length, 3, 'recentEvents should be capped at 3');
    assert.equal(
      events[0]['ftm:sentAt']['@value'],
      currentTime,
      'first event should be the new one (prepended)',
    );
    assert.equal(
      events[0]['@type'],
      'ftm:ReminderEvent',
      'new event should be of type ftm:ReminderEvent',
    );
  });

  test('after send: instance ftm:clientSequence equals previous + 1', async () => {
    const { state, orch, notif, instanceId } = await setupDueInstance();
    const before = await state.getTaskInstance(instanceId);
    const prevSeq = before['ftm:clientSequence'];
    const currentTime = new Date().toISOString();
    await reminderTrigger({
      stateAdapter: state,
      notificationAdapter: notif,
      orchestrationAdapter: orch,
      instanceId,
      currentTime,
    });
    const stored = await state.getTaskInstance(instanceId);
    assert.equal(
      stored['ftm:clientSequence'],
      prevSeq + 1,
      'ftm:clientSequence should be incremented by 1',
    );
  });

  test('after send: instance ftm:updatedAt @value equals currentTime', async () => {
    const { state, orch, notif, instanceId } = await setupDueInstance();
    const currentTime = new Date().toISOString();
    await reminderTrigger({
      stateAdapter: state,
      notificationAdapter: notif,
      orchestrationAdapter: orch,
      instanceId,
      currentTime,
    });
    const stored = await state.getTaskInstance(instanceId);
    assert.equal(
      stored['ftm:updatedAt']['@value'],
      currentTime,
      'ftm:updatedAt @value should equal currentTime',
    );
  });

  test('shouldRemind false (already-complete): send NOT called, instance unchanged', async () => {
    const { state, orch, notif, instanceId, sendCount } = await setupWithSendSpy();
    // Mark instance as completed so reminderEvaluator Rule 1 short-circuits
    const base = await state.getTaskInstance(instanceId);
    const completed = {
      ...base,
      'ftm:clientSequence': 2,
      'ftm:completionState': {
        ...base['ftm:completionState'],
        'ftm:status': 'completed',
      },
    };
    await state.saveTaskInstance(completed);
    const currentTime = new Date().toISOString();
    await reminderTrigger({
      stateAdapter: state,
      notificationAdapter: notif,
      orchestrationAdapter: orch,
      instanceId,
      currentTime,
    });
    assert.equal(sendCount.length, 0, 'send should NOT be called when instance is already complete');
    const stored = await state.getTaskInstance(instanceId);
    assert.equal(
      stored['ftm:completionState']['ftm:status'],
      'completed',
      'instance status should remain completed (unchanged)',
    );
    assert.equal(stored['ftm:clientSequence'], 2, 'ftm:clientSequence should be unchanged');
  });

  test('persistent mode + window not expired: a new orchestration callback is scheduled (assert by observing orch state)', async () => {
    const { state, notif, instanceId } = await setupDueInstance('persistent');
    const scheduleAtCalls = [];
    const innerOrch = createTestOrchestrationAdapter();
    const spyOrch = {
      ...innerOrch,
      scheduleAt(isoTimestamp, callback) {
        scheduleAtCalls.push(isoTimestamp);
        return innerOrch.scheduleAt(isoTimestamp, callback);
      },
    };
    const currentTime = new Date().toISOString();
    await reminderTrigger({
      stateAdapter: state,
      notificationAdapter: notif,
      orchestrationAdapter: spyOrch,
      instanceId,
      currentTime,
    });
    assert.equal(
      scheduleAtCalls.length,
      1,
      'scheduleAt should be called once for the next persistent reminder',
    );
  });
});
