export function createTaskDefinition(params) {
  const {
    title,
    description,
    assignedTo,
    createdBy,
    dueAt,
    scheduleType = 'one-time',
    recurrenceRule = null,
    recurrenceStart = null,
    reminderMode = 'once',
    intervalSeconds = null,
    persistUntilSeconds = null,
  } = params;

  const now = new Date().toISOString();

  return {
    '@context': 'https://schema.familytaskmanager.local/v1/',
    '@type': 'ftm:TaskDefinition',
    '@id': 'urn:ftm:task:' + globalThis.crypto.randomUUID(),
    'ftm:title': title,
    'ftm:description': description,
    'ftm:assignedTo': assignedTo,
    'ftm:createdBy': createdBy,
    'ftm:createdAt': { '@type': 'xsd:dateTime', '@value': now },
    'ftm:version': 1,
    'ftm:updatedAt': { '@type': 'xsd:dateTime', '@value': now },
    'ftm:clientSequence': 1,
    'ftm:schedule': {
      '@type': 'ftm:Schedule',
      'ftm:scheduleType': scheduleType,
      'ftm:dueAt': { '@type': 'xsd:dateTime', '@value': dueAt },
      'ftm:recurrenceRule': recurrenceRule,
      'ftm:recurrenceStart': recurrenceStart,
    },
    'ftm:reminderPolicy': {
      '@type': 'ftm:ReminderPolicy',
      'ftm:mode': reminderMode,
      'ftm:intervalSeconds': intervalSeconds,
      'ftm:persistUntilSeconds': persistUntilSeconds,
    },
    'ftm:status': 'active',
  };
}
