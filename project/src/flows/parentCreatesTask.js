import { createTaskDefinition } from '../entities/taskDefinition.js';
import { scheduleComputer } from '../modules/scheduleComputer.js';

/**
 * Flow: Parent Creates a Task (SPEC §8.1)
 *
 * Orchestrates the full task-creation sequence:
 *  1. Construct a TaskDefinition from caller-supplied params.
 *  2. Persist the TaskDefinition via stateAdapter.
 *  3. Derive TaskInstances for the default look-ahead window.
 *  4. Persist each TaskInstance via stateAdapter.
 *  5. Schedule a reminder trigger for each instance's due time
 *     via orchestrationAdapter.
 *
 * No I/O outside the injected adapters. Pure composition — this flow
 * does not own state or timers itself.
 *
 * @param {Object} args
 * @param {Object} args.stateAdapter       - StateAdapter (SPEC §5.1)
 * @param {Object} args.orchestrationAdapter - OrchestrationAdapter (SPEC §6.1)
 * @param {Object} args.params             - Parameters forwarded to createTaskDefinition
 * @returns {Promise<{taskDef: Object, instances: Array}>}
 */
export async function parentCreatesTask({ stateAdapter, orchestrationAdapter, params }) {
  const taskDef = createTaskDefinition(params);

  await stateAdapter.saveTaskDefinition(taskDef);

  const instances = scheduleComputer(taskDef, new Date().toISOString());

  for (const instance of instances) {
    await stateAdapter.saveTaskInstance(instance);
  }

  for (const instance of instances) {
    orchestrationAdapter.scheduleAt(
      instance['ftm:dueAt']['@value'],
      () => {
        // Reminder trigger placeholder; actual wiring composes with reminderTrigger flow.
      }
    );
  }

  return { taskDef, instances };
}
