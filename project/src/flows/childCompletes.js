import { completionProcessor } from '../modules/completionProcessor.js';
import { emitTaskCompleted } from '../events/completionEmitter.js';

/**
 * Flow: Child Marks Task Complete (SPEC §8.3)
 *
 * Orchestrates the full child-completion sequence:
 *  1. Load the TaskInstance from state.
 *  2. Guard: instance must exist.
 *  3. Apply completion via completionProcessor (pure transform).
 *  4. Persist the updated TaskInstance via stateAdapter.
 *  5. Cancel any outstanding reminder handles via orchestrationAdapter.
 *  6. Emit the ftm:taskCompleted event for reactive UI updates.
 *
 * No I/O outside the injected adapters. Pure composition — this flow
 * does not own state or timers itself.
 *
 * @param {Object} args
 * @param {Object} args.stateAdapter          - StateAdapter (SPEC §5.1)
 * @param {Object} args.orchestrationAdapter  - OrchestrationAdapter (SPEC §6.1)
 * @param {string} args.instanceId            - @id of the ftm:TaskInstance to complete
 * @param {string} args.childId               - userId of the child completing the task
 * @param {string} args.currentTime           - ISO-8601 completion timestamp
 * @param {Array}  args.reminderHandles       - Handles of pending reminders to cancel (default [])
 * @returns {Promise<{completed: boolean, reason?: string, updated?: Object}>}
 */
export async function childCompletes({
  stateAdapter,
  orchestrationAdapter,
  instanceId,
  childId,
  currentTime,
  reminderHandles = [],
}) {
  // Step 1 — load instance
  const instance = await stateAdapter.getTaskInstance(instanceId);

  // Step 2 — guard: instance must exist
  if (!instance) return { completed: false, reason: 'instance-not-found' };

  // Step 3 — apply completion transform (pure; no mutation of original)
  const updated = completionProcessor(instance, childId, 'child', currentTime);

  // Step 4 — persist updated instance
  await stateAdapter.saveTaskInstance(updated);

  // Step 5 — cancel outstanding reminder handles
  for (const handle of reminderHandles) {
    orchestrationAdapter.cancel(handle);
  }

  // Step 6 — emit completion event
  emitTaskCompleted(updated);

  // Step 7 — return result
  return { completed: true, updated };
}
