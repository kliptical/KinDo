export function createUser(params) {
  const { role, displayName, notificationTokens = [] } = params;

  const VALID_ROLES = ['parent', 'child'];
  if (!VALID_ROLES.includes(role)) {
    throw new Error(
      `role must be one of: ${VALID_ROLES.join(', ')}; got: ${role}`,
    );
  }

  if (typeof displayName !== 'string' || displayName === '') {
    throw new Error('displayName must be a non-empty string');
  }

  return {
    '@context': 'https://schema.familytaskmanager.local/v1/',
    '@type': 'ftm:User',
    '@id': 'urn:ftm:user:' + globalThis.crypto.randomUUID(),
    'ftm:role': role,
    'ftm:displayName': displayName,
    'ftm:notificationTokens': notificationTokens,
  };
}
