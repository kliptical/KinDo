/**
 * Round-trip utilities for FTM JSON-LD entity objects.
 * Strips or expands the 'ftm:' prefix on top-level keys without mutating the input.
 */

/**
 * Returns a new shallow-copy of entity where every key starting with 'ftm:'
 * has the prefix removed (e.g. 'ftm:title' -> 'title').
 * Keys starting with '@' ('@context', '@type', '@id') are preserved unchanged.
 * All other keys are preserved unchanged. Does NOT mutate the input.
 *
 * @param {Object} entity
 * @returns {Object}
 */
export function stripFtmPrefix(entity) {
  const result = {};
  for (const [key, value] of Object.entries(entity)) {
    if (key.startsWith('@')) {
      result[key] = value;
    } else if (key.startsWith('ftm:')) {
      result[key.slice(4)] = value;
    } else {
      result[key] = value;
    }
  }
  return result;
}

/**
 * Returns a new shallow-copy of stripped where every key NOT starting with '@'
 * has 'ftm:' prepended (e.g. 'title' -> 'ftm:title').
 * Keys starting with '@' are preserved unchanged. Does NOT mutate the input.
 *
 * @param {Object} stripped
 * @returns {Object}
 */
export function expandFtmPrefix(stripped) {
  const result = {};
  for (const [key, value] of Object.entries(stripped)) {
    if (key.startsWith('@')) {
      result[key] = value;
    } else {
      result['ftm:' + key] = value;
    }
  }
  return result;
}
