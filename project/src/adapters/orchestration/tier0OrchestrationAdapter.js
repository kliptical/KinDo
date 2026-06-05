/**
 * @typedef {Object} OrchestrationAdapter
 * @property {function(string, function(): void): string} scheduleAt
 *   Request that callback be invoked at or after isoTimestamp.
 *   Returns an opaque handle that can be used to cancel.
 *   Implementations MUST document their background behavior (SPEC §6.1).
 * @property {function(number, function(): void): string} scheduleInterval
 *   Request that callback be invoked every intervalMs milliseconds.
 *   Returns an opaque handle that can be used to cancel.
 * @property {function(string): void} cancel
 *   Cancel a previously scheduled timeout or interval by its opaque handle.
 * @property {function(string): void} onResume
 *   Called on every boot or foreground resume. Allows the adapter to
 *   re-register any timers that were lost while backgrounded (SPEC §6.1).
 */

/**
 * Creates a Tier 0 OrchestrationAdapter per SPEC §6.1.
 * Schedules callbacks using native setTimeout / setInterval.
 *
 * Background throttling is a known limitation per SPEC §6.1 Tier 0 —
 * JavaScript timers are unreliable when a browser tab or PWA is backgrounded.
 *
 * @returns {OrchestrationAdapter}
 */
export function createTier0OrchestrationAdapter() {
  /**
   * Internal handle registry.
   * @type {Map<string, {type: 'timeout'|'interval', nodeHandle: any}>}
   */
  const handles = new Map();

  return {
    // ── Scheduling ───────────────────────────────────────────────────────────

    /**
     * Schedules `callback` to fire at or after `isoTimestamp`.
     *
     * If the target time is in the past or present (delayMs <= 0), the callback
     * is queued via queueMicrotask so it fires asynchronously on the current
     * event-loop turn. Otherwise setTimeout(callback, delayMs) is used.
     *
     * Returns an opaque handle string. Implementations MUST document their
     * background behaviour (SPEC §6.1): Tier 0 timers may be throttled or
     * frozen when a browser tab or PWA is backgrounded.
     *
     * @param {string} isoTimestamp - ISO-8601 target fire time
     * @param {function(): void} callback
     * @returns {string} opaque cancellation handle
     */
    scheduleAt(isoTimestamp, callback) {
      const handle = crypto.randomUUID();
      const delayMs = new Date(isoTimestamp).getTime() - Date.now();

      if (delayMs <= 0) {
        // Already past — fire on next microtask; no real timer to cancel.
        queueMicrotask(callback);
        handles.set(handle, { type: 'timeout', nodeHandle: null });
      } else {
        const nodeHandle = setTimeout(callback, delayMs);
        handles.set(handle, { type: 'timeout', nodeHandle });
      }

      return handle;
    },

    /**
     * Schedules `callback` to fire every `intervalMs` milliseconds.
     * Returns an opaque handle string that can be passed to `cancel`.
     *
     * @param {number} intervalMs
     * @param {function(): void} callback
     * @returns {string} opaque cancellation handle
     */
    scheduleInterval(intervalMs, callback) {
      const handle = crypto.randomUUID();
      const nodeHandle = setInterval(callback, intervalMs);
      handles.set(handle, { type: 'interval', nodeHandle });
      return handle;
    },

    // ── Cancellation ─────────────────────────────────────────────────────────

    /**
     * Cancels the timer identified by `handle`. No-ops silently if the handle
     * is unknown or the callback has already fired.
     *
     * @param {string} handle - opaque handle returned by scheduleAt or scheduleInterval
     * @returns {void}
     */
    cancel(handle) {
      const entry = handles.get(handle);
      if (!entry) return;

      if (entry.type === 'timeout') {
        clearTimeout(entry.nodeHandle);
      } else {
        clearInterval(entry.nodeHandle);
      }
      handles.delete(handle);
    },

    // ── Resume ───────────────────────────────────────────────────────────────

    /**
     * Called by the application on every boot or foreground resume (SPEC §6.1).
     *
     * Tier 0 does not perform resume reconciliation internally. The three-step
     * reconciliation sequence (RecurrenceMaterializer → ReminderEvaluator →
     * re-dispatch) is composed externally by the orchestration layer (SPEC §6.1).
     * This method is a no-op placeholder for future Tier 0 resume hooks.
     *
     * @param {string} currentTime - ISO-8601 timestamp of the resume event
     * @returns {void}
     */
    onResume(currentTime) {
      // No-op placeholder. Resume reconciliation is composed externally
      // by the orchestration layer per SPEC §6.1.
      void currentTime;
    },
  };
}
