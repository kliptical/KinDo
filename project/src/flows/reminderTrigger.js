import { reminderEvaluator } from '../modules/reminderEvaluator.js';

/**
 * Flow: Reminder Trigger (SPEC §8.2)
 *
 * Fired by the OrchestrationAdapter when a TaskInstance reaches its dueAt time.
 * Evaluates whether a reminder should be dispatched, sends it via the
 * NotificationAdapter, updates the instance's reminderSummary, and — for
 * persistent-mode tasks that are still within the persistence window — schedules
 * the next reminder interval.
 *
 * No I/O outside the injected adapters. Pure composition — this flow
 * does not own state or timers itself.
 *
 * @param {Object} args
 * @param {Object} args.stateAdapter          - StateAdapter (SPEC §5.1)
 * @param {Object} args.notificationAdapter   - NotificationAdapter (SPEC §7)
 * @param {Object} args.orchestrationAdapter  - OrchestrationAdapter (SPEC §6.1)
 * @param {string} args.instanceId            - @id of the ftm:TaskInstance to evaluate
 * @param {string} args.currentTime           - ISO-8601 current timestamp
 * @returns {Promise<{dispatched: boolean, reason?: string, receipt?: Object, updated?: Object}>}
 */
export async function reminderTrigger({
  stateAdapter,
  notificationAdapter,
  orchestrationAdapter,
  instanceId,
  currentTime,
}) {
  // Step 1 — load instance
  const instance = await stateAdapter.getTaskInstance(instanceId);

  // Step 2 — guard: instance must exist
  if (!instance) return { dispatched: false, reason: 'instance-not-found' };

  // Step 3 — load task definition
  const taskDef = await stateAdapter.getTaskDefinition(instance['ftm:taskDefinition']);

  // Step 4 — evaluate reminder eligibility
  const verdict = reminderEvaluator(instance, taskDef, currentTime);

  // Step 5 — bail if no reminder needed
  if (!verdict.shouldRemind) return { dispatched: false, reason: verdict.reason };

  // Step 6 — dispatch notification
  const receipt = await notificationAdapter.send({
    recipientUserId: instance['ftm:assignedTo'],
    title: taskDef['ftm:title'],
    body: taskDef['ftm:description'] ?? '',
    deepLinkUri: 'ftm://instance/' + instance['@id'].split(':').pop(),
    requestForegroundDisplay: true,
  });

  // Step 7 — build updated instance with incremented reminderSummary
  const updated = { ...instance };
  updated['ftm:reminderSummary'] = {
    ...instance['ftm:reminderSummary'],
    'ftm:totalSent': instance['ftm:reminderSummary']['ftm:totalSent'] + 1,
    'ftm:lastSentAt': currentTime,
    'ftm:lastDeliveryStatus': receipt.status,
    'ftm:recentEvents': [
      {
        '@type': 'ftm:ReminderEvent',
        'ftm:sentAt': { '@type': 'xsd:dateTime', '@value': currentTime },
        'ftm:deliveryStatus': receipt.status,
      },
      ...instance['ftm:reminderSummary']['ftm:recentEvents'],
    ].slice(0, 3),
  };
  updated['ftm:clientSequence'] = instance['ftm:clientSequence'] + 1;
  updated['ftm:updatedAt'] = { '@type': 'xsd:dateTime', '@value': currentTime };

  // Step 8 — persist updated instance
  await stateAdapter.saveTaskInstance(updated);

  // Step 9 — schedule next reminder for persistent-mode tasks within persistence window
  if (taskDef['ftm:reminderPolicy']['ftm:mode'] === 'persistent') {
    const persistUntil = taskDef['ftm:reminderPolicy']['ftm:persistUntilSeconds'] ?? 86400;
    const dueAtMs = new Date(instance['ftm:dueAt']['@value']).getTime();
    const currentMs = new Date(currentTime).getTime();

    if (currentMs <= dueAtMs + persistUntil * 1000) {
      const intervalMs = taskDef['ftm:reminderPolicy']['ftm:intervalSeconds'] * 1000;
      orchestrationAdapter.scheduleAt(
        new Date(currentMs + intervalMs).toISOString(),
        () => { /* next reminder */ }
      );
    }
  }

  // Step 10 — return dispatch result
  return { dispatched: true, receipt, updated };
}
