export function createReminderEvent(sentAt, deliveryStatus) {
  const VALID_STATUSES = ['delivered', 'failed', 'deferred'];
  if (!VALID_STATUSES.includes(deliveryStatus)) {
    throw new Error(
      `deliveryStatus must be one of: ${VALID_STATUSES.join(', ')}; got: ${deliveryStatus}`,
    );
  }

  return {
    '@type': 'ftm:ReminderEvent',
    'ftm:sentAt': { '@type': 'xsd:dateTime', '@value': sentAt },
    'ftm:deliveryStatus': deliveryStatus,
  };
}
