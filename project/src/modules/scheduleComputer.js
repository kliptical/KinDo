import rrulePkg from 'rrule';
const { RRule } = rrulePkg;
import { createTaskInstance } from '../entities/taskInstance.js';

/**
 * Derive zero or more TaskInstance skeletons from a TaskDefinition.
 * Pure function — no I/O, no side effects.
 *
 * @param {Object} taskDef                           - ftm:TaskDefinition JSON-LD object
 * @param {string} referenceTime                     - ISO-8601 reference timestamp
 * @param {Object} [options={}]
 * @param {number} [options.lookAheadSeconds=604800]  - window length in seconds (default 7 days)
 * @returns {Array} TaskInstance[]
 */
export function scheduleComputer(taskDef, referenceTime, options = {}) {
  const lookAheadSeconds =
    options.lookAheadSeconds !== undefined ? options.lookAheadSeconds : 604800;

  const schedule = taskDef['ftm:schedule'];
  const scheduleType = schedule['ftm:scheduleType'];

  // --- one-time ---
  if (scheduleType === 'one-time') {
    const dueAtValue = schedule['ftm:dueAt']['@value'];
    if (dueAtValue <= referenceTime) {
      return [];
    }
    return [
      createTaskInstance({
        taskDefinitionId: taskDef['@id'],
        assignedTo: taskDef['ftm:assignedTo'],
        dueAt: dueAtValue,
      }),
    ];
  }

  // --- recurring ---
  if (scheduleType === 'recurring') {
    const recurrenceRule = schedule['ftm:recurrenceRule'];

    // null or empty string → treat as invalid
    if (!recurrenceRule) {
      const result = [];
      result['ftm:error'] = 'invalid-rrule';
      return result;
    }

    let rule;
    try {
      rule = new RRule({
        ...RRule.parseString(recurrenceRule),
        dtstart: new Date(schedule['ftm:recurrenceStart']),
      });
    } catch (_err) {
      const result = [];
      result['ftm:error'] = 'invalid-rrule';
      return result;
    }

    const start = new Date(referenceTime);
    const end = new Date(new Date(referenceTime).getTime() + lookAheadSeconds * 1000);
    const rawDates = rule.between(start, end, true);

    // Enforce open-start: exclude any occurrence exactly equal to referenceTime
    const dates = rawDates.filter(d => d.getTime() !== start.getTime());

    return dates.map(d =>
      createTaskInstance({
        taskDefinitionId: taskDef['@id'],
        assignedTo: taskDef['ftm:assignedTo'],
        dueAt: d.toISOString(),
      })
    );
  }

  // Unknown scheduleType — return empty array
  return [];
}
