/**
 * Identity resolution (Phase 5)
 *
 * Derives the current user identity from (in priority order):
 *   1. URL query string  ?as=role:userId
 *   2. localStorage      'ftm.identity'
 *   3. null
 *
 * All exports guard browser-globals with typeof so the module is safe
 * to import in Node (where window / localStorage are undefined).
 */

/**
 * Resolves the current identity.
 *
 * @returns {{ userId: string, role: string } | null}
 */
export function resolveIdentity() {
  // 1. URL query string: ?as=role:userId  (e.g. ?as=parent:abc)
  if (typeof window !== 'undefined') {
    const params = new URLSearchParams(window.location.search);
    const as = params.get('as');
    if (as) {
      const colonIdx = as.indexOf(':');
      if (colonIdx > 0) {
        const role = as.slice(0, colonIdx);
        const userId = as.slice(colonIdx + 1);
        if (role && userId) {
          return { userId: 'urn:ftm:' + role + ':' + userId, role };
        }
      }
    }
  }

  // 2. localStorage
  if (typeof localStorage !== 'undefined') {
    const raw = localStorage.getItem('ftm.identity');
    if (raw) {
      try {
        const parsed = JSON.parse(raw);
        if (
          parsed !== null &&
          typeof parsed === 'object' &&
          typeof parsed.userId === 'string' &&
          typeof parsed.role === 'string'
        ) {
          return parsed;
        }
      } catch (_e) {
        // malformed JSON — fall through to null
      }
    }
  }

  // 3. No identity found
  return null;
}

/**
 * Persists an identity object to localStorage.
 *
 * @param {{ userId: string, role: string }} identity
 */
export function setIdentity(identity) {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem('ftm.identity', JSON.stringify(identity));
}
