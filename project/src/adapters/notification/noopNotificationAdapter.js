/**
 * Creates a no-op NotificationAdapter.
 *
 * Used by tests that do not verify notification delivery; satisfies
 * SPEC §13 item 9 (NotificationAdapter swap test).
 *
 * `send` resolves immediately with `{ status: "delivered", adapterTier: 0 }`
 * without dispatching any CustomEvent or EventEmitter event.
 *
 * @returns {{ send: function(import('./tier0NotificationAdapter.js').NotificationPayload): Promise<import('./tier0NotificationAdapter.js').NotificationReceipt> }}
 */
export function createNoopNotificationAdapter() {
  return {
    /**
     * Accepts the payload and immediately resolves with a delivered receipt.
     * Does NOT dispatch any CustomEvent or EventEmitter event.
     *
     * Used by tests that do not verify notification delivery; satisfies
     * SPEC §13 item 9 (NotificationAdapter swap test).
     *
     * @param {import('./tier0NotificationAdapter.js').NotificationPayload} payload
     * @returns {Promise<import('./tier0NotificationAdapter.js').NotificationReceipt>}
     */
    async send(payload) {
      void payload;
      return { status: 'delivered', adapterTier: 0 };
    },
  };
}
