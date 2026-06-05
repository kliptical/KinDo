import { recurrenceMaterializer } from './recurrenceMaterializer.js';
import { reminderEvaluator } from './reminderEvaluator.js';

/**
 * Resume reconciliation orchestrator per SPEC §6.1 and §8.5.
 *
 * Composed externally to the tier adapters, this function is the
 * "orchestration layer" referenced in tier0OrchestrationAdapter's
 * onResume JSDoc. It executes the three-step resume reconciliation
 * sequence on every boot / foreground resume:
 *
 *   1. Notify the orchestration adapter that a resume has occurred.
 *   2. Materialize any recurring TaskInstances absent from state
 *      (bridging the Ghost Materialization gap via recurrenceMaterializer).
 *   3. Re-evaluate all pending instances now due and dispatch reminder
 *      notifications where reminderEvaluator returns shouldRemind: true.
 *
 * **Phase 4 scope boundary**: this function does NOT update
 * `ftm:reminderSummary` on dispatched instances. That mutation belongs
 * to the Phase 4 reminder-trigger flow (SPEC §8.2). Updating summary
 * state here would create a write-ordering conflict with the Phase 4
 * trigger path and is deliberately out of scope for this phase.
 *
 * @param {Object} params
 * @param {Object} params.stateAdapter
 *   Adapter providing listTaskDefinitions, listTaskInstances,
 *   saveTaskInstance, and getTaskDefinition.
 * @param {Object} params.orchestrationAdapter
 *   Adapter providing onResume(currentTime) and
 *   scheduleAt(isoTimestamp, callback).
 * @param {Object} params.notificationAdapter
 *   Adapter providing async send(NotificationPayload).
 * @param {string} params.currentTime
 *   ISO-8601 timestamp representing "now" for this resume event.
 * @returns {Promise<{ toCreate: number, skipped: number }>}
 *   toCreate — count of new TaskInstances saved to state.
 *   skipped  — count of past occurrences skipped by recurrenceMaterializer's
 *               catchUpPolicy (mirrors recurrenceMaterializer's skipped value).
 */
export async function resumeReconciliation({
  stateAdapter,
  orchestrationAdapter,
  notificationAdapter,
  currentTime,
}) {
  // ── Step 1: Inform the orchestration adapter of the resume event ─────────
  // onResume is a documented no-op on Tier 0; called here for adapter
  // contract completeness and future higher-tier adapter compatibility.
  orchestrationAdapter.onResume(currentTime);

  // ── Step 2: Materialize missing recurring TaskInstances ──────────────────

  const allDefs = await stateAdapter.listTaskDefinitions({ status: 'active' });
  const recurringDefs = allDefs.filter(
    d => d['ftm:schedule']['ftm:scheduleType'] === 'recurring'
  );

  const allInstances = await stateAdapter.listTaskInstances();

  const { toCreate, skipped } = recurrenceMaterializer(
    recurringDefs,
    allInstances,
    currentTime
  );

  for (const instance of toCreate) {
    await stateAdapter.saveTaskInstance(instance);
    // Register a timer for the new instance's due time. The callback is an
    // intentional placeholder in this phase — wiring to the Phase 4
    // reminder-trigger flow (SPEC §8.2) is deferred to Phase 4.
    orchestrationAdapter.scheduleAt(instance['ftm:dueAt']['@value'], () => {
      /* placeholder reminder trigger; wired in Phase 4 */
    });
  }

  // ── Step 3: Re-evaluate pending instances that are now due ───────────────
  // Re-load instances so newly saved ones are included in this evaluation pass.
  const updatedInstances = await stateAdapter.listTaskInstances();
  const pendingDue = updatedInstances.filter(
    i =>
      i['ftm:completionState']['ftm:status'] === 'pending' &&
      i['ftm:dueAt']['@value'] <= currentTime
  );

  for (const instance of pendingDue) {
    const def = await stateAdapter.getTaskDefinition(instance['ftm:taskDefinition']);
    const verdict = reminderEvaluator(instance, def, currentTime);

    if (verdict.shouldRemind) {
      await notificationAdapter.send({
        recipientUserId: instance['ftm:assignedTo'],
        title: def['ftm:title'],
        body: def['ftm:description'] ?? '',
        deepLinkUri: 'ftm://instance/' + instance['@id'].split(':').pop(),
        requestForegroundDisplay: true,
      });
    }
  }

  // ── Return summary counts ────────────────────────────────────────────────
  return { toCreate: toCreate.length, skipped };
}
