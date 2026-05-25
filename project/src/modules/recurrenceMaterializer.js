import { scheduleComputer } from './scheduleComputer.js';

/**
 * Close the "Ghost Materialization" gap by computing TaskInstances that should
 * exist but are absent from existingInstances.
 * Pure function — no I/O, no side effects. Inputs are not mutated.
 *
 * @param {Object[]} taskDefs           - ftm:TaskDefinition JSON-LD objects (active recurring defs)
 * @param {Object[]} existingInstances  - ftm:TaskInstance JSON-LD objects currently in state
 * @param {string}   currentTime        - ISO-8601 current timestamp
 * @param {Object}  [options={}]
 * @param {number}  [options.lookAheadSeconds=604800]          - look-ahead window in seconds (default 7 days)
 * @param {'all'|'current-only'} [options.catchUpPolicy='current-only']
 * @returns {{ toCreate: Object[], skipped: number }}
 */
export function recurrenceMaterializer(taskDefs, existingInstances, currentTime, options = {}) {
  // FIXME: catchUpWindowSeconds not defined in SPEC §4.5 rule 1a — using 604800s (7 days) as operator-confirmed default (I9).
  const catchUpWindowSeconds = options.catchUpWindowSeconds ?? 604800;
  const lookAheadSeconds = options.lookAheadSeconds ?? 604800;
  const catchUpPolicy = options.catchUpPolicy ?? 'current-only';

  // Build a deduplication key set: "taskDefId|dueAt"
  const existingKeys = new Set(
    existingInstances.map(
      inst => inst['ftm:taskDefinition'] + '|' + inst['ftm:dueAt']['@value']
    )
  );

  const toCreate = [];
  let skipped = 0;

  for (const taskDef of taskDefs) {
    if (taskDef['ftm:schedule']['ftm:scheduleType'] !== 'recurring') {
      continue;
    }

    const windowStart = new Date(
      new Date(currentTime).getTime() - catchUpWindowSeconds * 1000
    ).toISOString();

    const candidates = scheduleComputer(taskDef, windowStart, {
      lookAheadSeconds: catchUpWindowSeconds + lookAheadSeconds,
    });

    // Handle invalid-rrule: if candidates['ftm:error'], skip this definition.
    if (candidates['ftm:error']) {
      continue;
    }

    for (const candidate of candidates) {
      const dueAt = candidate['ftm:dueAt']['@value'];

      // Deduplicate: skip if a matching instance already exists
      if (existingKeys.has(taskDef['@id'] + '|' + dueAt)) {
        continue;
      }

      // catchUpPolicy 'current-only': skip past occurrences; count them
      if (catchUpPolicy === 'current-only' && dueAt < currentTime) {
        skipped++;
        continue;
      }

      toCreate.push(candidate);
    }
  }

  return { toCreate, skipped };
}
