/**
 * Identity resolution (Phase 5 + post-Phase-5 polish)
 *
 * Resolution order:
 *   1. localStorage 'ftm.identity' (after first switch this wins permanently)
 *   2. URL query string ?as=role:short    (legacy demo bootstrap)
 *   3. URL query string ?as=<full @id>    (new full-id bootstrap; role
 *                                          resolved downstream from
 *                                          stateAdapter.getUser)
 *   4. null
 *
 * The identity switcher writes to localStorage, so once the user picks
 * a real account, they stay on it across reloads.
 *
 * All exports guard browser-globals with typeof so the module is safe
 * to import in Node (where window / localStorage are undefined).
 */

/**
 * Synchronously resolves an identity from localStorage or URL.
 * For URL bootstrap with a bare @id (no role), returns the userId with
 * role: null — App.js looks up the role from stateAdapter.
 *
 * @returns {{ userId: string, role: string | null } | null}
 */
export function resolveIdentity() {
  // 1. localStorage — sticky once set
  if (typeof localStorage !== 'undefined') {
    const raw = localStorage.getItem('ftm.identity');
    if (raw) {
      try {
        const parsed = JSON.parse(raw);
        if (
          parsed !== null &&
          typeof parsed === 'object' &&
          typeof parsed.userId === 'string'
        ) {
          return { userId: parsed.userId, role: parsed.role ?? null };
        }
      } catch {
        // malformed JSON — fall through
      }
    }
  }

  // 2 + 3. URL ?as=...
  if (typeof window !== 'undefined') {
    const params = new URLSearchParams(window.location.search);
    const as = params.get('as');
    if (as) {
      // Full @id form: ?as=urn:ftm:user:<uuid>
      if (as.startsWith('urn:ftm:')) {
        return { userId: as, role: null };
      }
      // Legacy short form: ?as=role:short
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

  return null;
}

/**
 * Persists an identity object to localStorage.
 *
 * @param {{ userId: string, role: string | null }} identity
 */
export function setIdentity(identity) {
  if (typeof localStorage === 'undefined') return;
  localStorage.setItem('ftm.identity', JSON.stringify(identity));
}

/**
 * Clears the persisted identity (logout-style action).
 */
export function clearIdentity() {
  if (typeof localStorage === 'undefined') return;
  localStorage.removeItem('ftm.identity');
}
