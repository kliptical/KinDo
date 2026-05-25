/**
 * Filter and sort a collection of TaskInstance objects.
 * Pure function — no I/O, no side effects.
 *
 * @param {Object[]} instances  - ftm:TaskInstance JSON-LD objects
 * @param {Object}  [filter={}]
 * @param {string}  [filter.assignedTo]           - keep instances assigned to this user
 * @param {'pending'|'completed'} [filter.status] - keep instances with this status
 * @param {string}  [filter.fromDate]             - keep instances where dueAt >= fromDate (ISO-8601)
 * @param {string}  [filter.toDate]               - keep instances where dueAt <= toDate (ISO-8601)
 * @returns {Object[]} TaskInstance[] — filtered and sorted; input array is not mutated
 */
export function taskListComputer(instances, filter = {}) {
  let result = instances.slice(); // shallow copy — do not mutate input

  if (filter.assignedTo !== undefined) {
    result = result.filter(i => i['ftm:assignedTo'] === filter.assignedTo);
  }

  if (filter.status !== undefined) {
    result = result.filter(
      i => i['ftm:completionState']['ftm:status'] === filter.status
    );
  }

  if (filter.fromDate !== undefined) {
    result = result.filter(i => i['ftm:dueAt']['@value'] >= filter.fromDate);
  }

  if (filter.toDate !== undefined) {
    result = result.filter(i => i['ftm:dueAt']['@value'] <= filter.toDate);
  }

  // Sort by dueAt ascending; tiebreak: pending before completed
  result.sort((a, b) => {
    const aDue = a['ftm:dueAt']['@value'];
    const bDue = b['ftm:dueAt']['@value'];
    if (aDue < bDue) return -1;
    if (aDue > bDue) return 1;
    // Equal dueAt: pending before completed
    const aStatus = a['ftm:completionState']['ftm:status'];
    const bStatus = b['ftm:completionState']['ftm:status'];
    if (aStatus === bStatus) return 0;
    return aStatus === 'pending' ? -1 : 1;
  });

  return result;
}
