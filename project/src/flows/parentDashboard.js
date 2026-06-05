import { taskListComputer } from '../modules/taskListComputer.js';

/**
 * Flow: Parent Views Task Dashboard (SPEC §8.4)
 *
 * Loads all TaskInstances (optionally scoped to a single child) and
 * partitions them into pending and completed lists via taskListComputer.
 *
 * No I/O outside the injected stateAdapter. Pure composition — this
 * flow does not own state itself.
 *
 * @param {Object}  args
 * @param {Object}  args.stateAdapter  - StateAdapter (SPEC §5.1)
 * @param {string}  [args.childId]     - If provided, filters instances to this child's @id
 * @returns {Promise<{ pending: Object[], completed: Object[] }>}
 */
export async function parentDashboard({ stateAdapter, childId }) {
  // Step 1 — build adapter filter (undefined → no assignedTo constraint; returns all)
  const filter = childId ? { assignedTo: childId } : undefined;

  // Step 2 — load instances, optionally scoped to one child
  const allInstances = await stateAdapter.listTaskInstances(filter);

  // Step 3 — partition into pending and completed lists
  const pending = taskListComputer(allInstances, { status: 'pending' });
  const completed = taskListComputer(allInstances, { status: 'completed' });

  // Step 4 — return dashboard payload
  return { pending, completed };
}
