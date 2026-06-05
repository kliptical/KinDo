/**
 * Deep-link resolver (SPEC §9)
 *
 * Resolves deep-link URIs to a TaskInstance (or null) via stateAdapter.
 * Supported URI schemes:
 *   ftm://instance/<id>          — native deep-link format
 *   #/instance/<id>              — hash-router equivalent
 *   /#/instance/<id>             — hash-router with leading slash
 *
 * Note: UI rendering for this route is deferred to Phase 5. This module
 * returns the TaskInstance (or null) for the caller to render.
 *
 * @param {string} uri
 * @param {{ stateAdapter: Object }} options
 * @returns {Promise<Object|null>}
 */
export async function resolveDeepLink(uri, { stateAdapter }) {
  let id = null;

  // Scheme 1: ftm://instance/<id>
  const nativeMatch = uri.match(/^ftm:\/\/instance\/([^/?#]+)/);
  if (nativeMatch) {
    id = nativeMatch[1];
  }

  // Scheme 2: #/instance/<id> or /#/instance/<id>
  if (!id) {
    const hashMatch = uri.match(/^\/?#\/instance\/([^/?#]+)/);
    if (hashMatch) {
      id = hashMatch[1];
    }
  }

  if (!id) return null;

  const fullId = 'urn:ftm:instance:' + id;
  return await stateAdapter.getTaskInstance(fullId);
}
