/**
 * @typedef {Object} NotificationPayload
 * @property {string} recipientUserId
 * @property {string} title
 * @property {string} body
 * @property {string} deepLinkUri - Deep-link URI that opens the specific TaskInstance in the child UI.
 * @property {boolean} requestForegroundDisplay
 *   Hint to the delivery layer: attempt foreground display if device is active.
 *   Adapters that cannot honor this MUST silently ignore it (not error).
 *   Tier 0 behavior: the CustomEvent / EventEmitter dispatch is unconditional —
 *   no additional action is taken for this flag per SPEC §7.2.
 */

/**
 * @typedef {Object} NotificationReceipt
 * @property {'delivered'|'failed'|'deferred'} status
 * @property {0|1|2|3} adapterTier
 * @property {string} [externalId] - Opaque; for use by Tier 3 adapters to track external delivery IDs.
 */

/**
 * @typedef {Object} NotificationAdapter
 * @property {function(NotificationPayload): Promise<NotificationReceipt>} send
 *   Send a notification to the device(s) associated with recipientUserId.
 *   MUST NOT throw on delivery failure; return status "failed" instead.
 */

import { EventEmitter } from 'node:events';

/**
 * Module-level EventEmitter used in Node environments.
 * Subscribe to the 'ftm:alert' event to receive notification payloads:
 *   ftmEmitter.on('ftm:alert', (payload) => { ... })
 *
 * @type {EventEmitter}
 */
export const ftmEmitter = new EventEmitter();

/**
 * Creates a Tier 0 NotificationAdapter per SPEC §7 and §7.1.
 *
 * Tier 0 (In-Process) dispatches a browser CustomEvent or a Node EventEmitter
 * event; it performs no external I/O and ships with core.
 *
 * Background throttling is a known limitation (SPEC §6.1): in-process event
 * delivery is unreliable when a browser tab or PWA is backgrounded, the screen
 * is locked, or the device enters low-power mode.
 *
 * @returns {NotificationAdapter}
 */
export function createTier0NotificationAdapter() {
  return {
    // ── Delivery ─────────────────────────────────────────────────────────────

    /**
     * Dispatches a notification via the in-process channel.
     *
     * Environment detection:
     * - **Browser**: fires `CustomEvent("ftm:alert", { detail: payload })` on
     *   `window`. The child UI subscribes to this event and renders an in-app
     *   modal alert unconditionally, regardless of which view is active (SPEC §7.2).
     * - **Node**: emits `"ftm:alert"` on the module-level `ftmEmitter`.
     *
     * `requestForegroundDisplay` flag: Tier 0 dispatches the event
     * unconditionally regardless of the flag's value — no additional action is
     * taken per SPEC §7.2. Adapters that cannot honor this flag MUST silently
     * ignore it (SPEC §7).
     *
     * MUST NOT throw on internal error; any exception is caught and the
     * receipt reports `status: "failed"` (SPEC §7).
     *
     * @param {NotificationPayload} payload
     * @returns {Promise<NotificationReceipt>}
     */
    async send(payload) {
      try {
        const isBrowser = typeof window !== 'undefined' && typeof CustomEvent === 'function';

        if (isBrowser) {
          window.dispatchEvent(new CustomEvent('ftm:alert', { detail: payload }));
        } else {
          ftmEmitter.emit('ftm:alert', payload);
        }

        return { status: 'delivered', adapterTier: 0 };
      } catch (_err) {
        return { status: 'failed', adapterTier: 0 };
      }
    },
  };
}
