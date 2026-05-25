export function validateTaskDefinition(td) {
  const errors = [];

  // Rule: ftm:title must be a non-empty string with length <= 200
  const title = td['ftm:title'];
  if (typeof title !== 'string' || title.length === 0 || title.length > 200) {
    errors.push('title must be non-empty string <= 200 chars');
  }

  const schedule = td['ftm:schedule'] ?? {};
  const scheduleType = schedule['ftm:scheduleType'];
  const recurrenceRule = schedule['ftm:recurrenceRule'];
  const recurrenceStart = schedule['ftm:recurrenceStart'];

  // Rule: recurring task requires recurrenceRule
  if (scheduleType === 'recurring' &&
      (recurrenceRule === null || recurrenceRule === undefined || recurrenceRule === '')) {
    errors.push('recurring task requires recurrenceRule');
  }

  // Rule: recurring task requires recurrenceStart
  if (scheduleType === 'recurring' &&
      (recurrenceStart === null || recurrenceStart === undefined || recurrenceStart === '')) {
    errors.push('recurring task requires recurrenceStart');
  }

  // Rule: if recurrenceStart is non-null, must be parseable as a valid date
  if (recurrenceStart !== null && recurrenceStart !== undefined &&
      new Date(recurrenceStart).toString() === 'Invalid Date') {
    errors.push('recurrenceStart must be valid ISO-8601 datetime');
  }

  const reminderPolicy = td['ftm:reminderPolicy'] ?? {};
  const mode = reminderPolicy['ftm:mode'];
  const intervalSeconds = reminderPolicy['ftm:intervalSeconds'];
  const persistUntilSeconds = reminderPolicy['ftm:persistUntilSeconds'];

  // Rule: persistent mode requires intervalSeconds >= 60
  if (mode === 'persistent' &&
      (!Number.isInteger(intervalSeconds) || intervalSeconds < 60)) {
    errors.push('persistent mode requires intervalSeconds >= 60');
  }

  // Rule: persistUntilSeconds (if non-null) must be >= intervalSeconds (if non-null)
  if (persistUntilSeconds !== null && persistUntilSeconds !== undefined &&
      intervalSeconds !== null && intervalSeconds !== undefined &&
      persistUntilSeconds < intervalSeconds) {
    errors.push('persistUntilSeconds must be >= intervalSeconds');
  }

  // TODO: assignedTo role check (SPEC §11) deferred to Phase 4 — requires StateAdapter.getUser()
  // not available until Phase 3. Operator decision I10.

  return { valid: errors.length === 0, errors };
}
