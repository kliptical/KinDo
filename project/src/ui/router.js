/**
 * Hash-based router (Phase 5)
 *
 * Supported routes:
 *   #/parent/dashboard        -> { view: 'parent-dashboard', params: {} }
 *   #/parent/create           -> { view: 'parent-create',    params: {} }
 *   #/parent/instance/<id>    -> { view: 'parent-instance',  params: { id } }
 *   #/child/tasks             -> { view: 'child-tasks',      params: {} }
 *   #/child/instance/<id>     -> { view: 'child-instance',   params: { id } }
 *   #/instance/<id>           -> { view: 'instance',         params: { id } }
 *   '' | '#/' | null          -> { view: 'home',             params: {} }
 *   anything else             -> { view: 'not-found',        params: {} }
 */

/**
 * Parses a hash-path string into a route descriptor.
 *
 * Normalises by stripping a leading '/' before the '#' character
 * (e.g. '/#/parent/dashboard' -> '#/parent/dashboard').
 *
 * @param {string|null} hashPath
 * @returns {{ view: string, params: object }}
 */
export function parseRoute(hashPath) {
  // Normalise: strip leading '/' before '#' if present
  const raw = (hashPath ?? '').replace(/^\/+(?=#)/, '');

  // Extract fragment (everything after '#')
  const fragment = raw.startsWith('#') ? raw.slice(1) : raw;

  // Home: empty fragment or bare '/'
  if (fragment === '' || fragment === '/') {
    return { view: 'home', params: {} };
  }

  // Split into path segments, discarding the leading empty string from '/'
  const segs = fragment.replace(/^\//, '').split('/');

  if (segs[0] === 'parent') {
    if (segs.length === 2 && segs[1] === 'dashboard') {
      return { view: 'parent-dashboard', params: {} };
    }
    if (segs.length === 2 && segs[1] === 'create') {
      return { view: 'parent-create', params: {} };
    }
    if (segs.length === 3 && segs[1] === 'instance' && segs[2]) {
      return { view: 'parent-instance', params: { id: segs[2] } };
    }
  }

  if (segs[0] === 'child') {
    if (segs.length === 2 && segs[1] === 'tasks') {
      return { view: 'child-tasks', params: {} };
    }
    if (segs.length === 3 && segs[1] === 'instance' && segs[2]) {
      return { view: 'child-instance', params: { id: segs[2] } };
    }
  }

  if (segs[0] === 'instance' && segs.length === 2 && segs[1]) {
    return { view: 'instance', params: { id: segs[1] } };
  }

  return { view: 'not-found', params: {} };
}

/**
 * Navigates to a hash path by setting window.location.hash.
 *
 * @param {string} hashPath
 */
export function navigate(hashPath) {
  if (typeof window === 'undefined') return;
  window.location.hash = hashPath.startsWith('#') ? hashPath : '#' + hashPath;
}

/**
 * Subscribes to hash-route changes.
 *
 * Calls handler(parseRoute(window.location.hash)) on every 'hashchange' event.
 *
 * @param {function({ view: string, params: object }): void} handler
 * @returns {function(): void}  Unsubscribe function.
 */
export function subscribeRoute(handler) {
  if (typeof window === 'undefined') return () => {};
  const listener = () => handler(parseRoute(window.location.hash));
  window.addEventListener('hashchange', listener);
  return () => window.removeEventListener('hashchange', listener);
}
