/**
 * Accept a completion signal and return an updated TaskInstance.
 * Pure function — no I/O, no side effects. Original instance is never mutated.
 *
 * TODO: SPEC §11 completedBy userId check and role-to-assignedTo cross-check
 * deferred to Phase 4 application flow. CompletionProcessor is a pure function
 * with no User store access. Operator decision I4.
 *
 * @param {Object} instance        - ftm:TaskInstance JSON-LD object
 * @param {string} completedBy     - userId of the person completing the task
 * @param {string} completedByRole - 'child' | 'parent'
 * @param {string} completedAt     - ISO-8601 completion timestamp
 * @returns {Object} TaskInstance (new copy; original is not mutated)
 */
export function completionProcessor(instance, completedBy, completedByRole, completedAt) {
  // Idempotency — return a spread-copy with a warning; do not re-set fields
  if (instance['ftm:completionState']['ftm:status'] === 'completed') {
    return { ...instance, 'ftm:warning': 'already-complete' };
  }

  return {
    ...instance,
    'ftm:completionState': {
      ...instance['ftm:completionState'],
      'ftm:status': 'completed',
      'ftm:completedAt': completedAt,
      'ftm:completedBy': completedBy,
      'ftm:completedByRole': completedByRole,
    },
    'ftm:clientSequence': instance['ftm:clientSequence'] + 1,
    'ftm:updatedAt': { '@type': 'xsd:dateTime', '@value': completedAt },
  };
}
