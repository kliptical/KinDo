import { EventEmitter } from 'node:events';

/**
 * Module-level EventEmitter used in Node environments for task-completion events.
 * Subscribe to the 'ftm:taskCompleted' event to receive updated TaskInstance objects:
 *   ftmCompletionEmitter.on('ftm:taskCompleted', (updatedInstance) => { ... })
 *
 * @type {EventEmitter}
 */
export const ftmCompletionEmitter = new EventEmitter();

/**
 * Emit a task-completed event in the current environment.
 *
 * Environment detection:
 * - **Browser**: fires `CustomEvent("ftm:taskCompleted", { detail: updatedInstance })` on
 *   `window` so the parent UI can react to completion updates reactively (SPEC §8.3 step 6).
 * - **Node**: emits `"ftm:taskCompleted"` on the module-level `ftmCompletionEmitter`.
 *
 * @param {Object} updatedInstance - ftm:TaskInstance JSON-LD object after completion
 */
export function emitTaskCompleted(updatedInstance) {
  const isBrowser = typeof window !== 'undefined' && typeof CustomEvent === 'function';

  if (isBrowser) {
    window.dispatchEvent(new CustomEvent('ftm:taskCompleted', { detail: updatedInstance }));
  } else {
    ftmCompletionEmitter.emit('ftm:taskCompleted', updatedInstance);
  }
}
