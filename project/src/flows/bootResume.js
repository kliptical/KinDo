import { resumeReconciliation } from '../modules/resumeReconciliation.js';

/**
 * Flow: App Boot / Foreground Resume (SPEC §8.5)
 *
 * Wraps the Phase 3 resumeReconciliation composition for the §8
 * application-flow surface. Runs every time the application starts or
 * returns to the foreground; closes the Ghost Materialization gap and
 * recovers missed reminders.
 *
 * The returned `skipped` count is exposed for optional parent-UI display
 * ("X tasks were skipped while you were away") per SPEC §8.5 step 6.
 *
 * No I/O outside the injected adapters. Pure composition — this flow
 * does not own state or timers itself.
 *
 * @param {Object} args
 * @param {Object} args.stateAdapter           - StateAdapter (SPEC §5.1)
 * @param {Object} args.orchestrationAdapter   - OrchestrationAdapter (SPEC §6.1)
 * @param {Object} args.notificationAdapter    - NotificationAdapter (SPEC §7)
 * @param {string} args.currentTime            - ISO-8601 timestamp representing "now"
 * @returns {Promise<{ toCreate: number, skipped: number }>}
 *   toCreate — count of new TaskInstances materialized and saved.
 *   skipped  — count of past occurrences skipped by catchUpPolicy;
 *               caller MAY display "X tasks were skipped" in parent UI.
 */
export async function bootResume({
  stateAdapter,
  orchestrationAdapter,
  notificationAdapter,
  currentTime,
}) {
  // Step 1 — delegate to resumeReconciliation (SPEC §8.5 steps 1–8)
  const result = await resumeReconciliation({
    stateAdapter,
    orchestrationAdapter,
    notificationAdapter,
    currentTime,
  });

  // Step 2 — return { toCreate, skipped } for caller awareness
  return result; // { toCreate, skipped }
}
