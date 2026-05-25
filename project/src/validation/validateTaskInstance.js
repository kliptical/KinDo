export function validateTaskInstance(ti) {
  const errors = [];

  // Rule: ftm:dueAt['@value'] must be a valid ISO-8601 datetime
  const dueAtNode = ti['ftm:dueAt'];
  const dueAtValue = dueAtNode != null ? dueAtNode['@value'] : null;
  if (dueAtValue == null || new Date(dueAtValue).toString() === 'Invalid Date') {
    errors.push('dueAt must be a valid ISO-8601 datetime');
  }

  // Rule: ftm:clientSequence must be a positive integer
  const clientSequence = ti['ftm:clientSequence'];
  if (!Number.isInteger(clientSequence) || clientSequence <= 0) {
    errors.push('clientSequence must be a positive integer');
  }

  return { valid: errors.length === 0, errors };
}
