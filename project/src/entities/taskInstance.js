export function createTaskInstance(params) {
  const { taskDefinitionId, assignedTo, dueAt } = params;

  const now = new Date().toISOString();

  return {
    '@context': 'https://schema.familytaskmanager.local/v1/',
    '@type': 'ftm:TaskInstance',
    '@id': 'urn:ftm:instance:' + globalThis.crypto.randomUUID(),
    'ftm:taskDefinition': taskDefinitionId,
    'ftm:assignedTo': assignedTo,
    'ftm:dueAt': { '@type': 'xsd:dateTime', '@value': dueAt },
    'ftm:createdAt': { '@type': 'xsd:dateTime', '@value': now },
    'ftm:updatedAt': { '@type': 'xsd:dateTime', '@value': now },
    'ftm:clientSequence': 1,
    'ftm:completionState': {
      '@type': 'ftm:CompletionState',
      'ftm:status': 'pending',
      'ftm:completedAt': null,
      'ftm:completedBy': null,
      'ftm:completedByRole': null,
    },
    'ftm:reminderSummary': {
      '@type': 'ftm:ReminderSummary',
      'ftm:totalSent': 0,
      'ftm:lastSentAt': null,
      'ftm:lastDeliveryStatus': null,
      'ftm:recentEvents': [],
    },
  };
}
