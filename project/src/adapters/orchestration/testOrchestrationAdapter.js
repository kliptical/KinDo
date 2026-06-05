/**
 * @typedef {import('./tier0OrchestrationAdapter.js').OrchestrationAdapter & {
 *   tick: function(string): void
 * }} TestOrchestrationAdapter
 */

/**
 * @typedef {{
 *   handle: string,
 *   fireAt: number,
 *   cb: function(): void,
 *   fired: boolean
 * }} TimeoutEntry
 */

/**
 * @typedef {{
 *   handle: string,
 *   intervalMs: number,
 *   lastFiredAt: number,
 *   cb: function(): void,
 *   registered: number
 * }} IntervalEntry
 */

/**
 * Creates a deterministic test-only OrchestrationAdapter per SPEC §6.1.
 *
 * Time is advanced explicitly via tick(isoTimestamp); no real timers
 * (setTimeout / setInterval) are used anywhere in this implementation.
 * All scheduling and firing is driven by the caller, making test behaviour
 * repeatable and free of wall-clock races.
 *
 * @returns {TestOrchestrationAdapter}
 */
export function createTestOrchestrationAdapter() {
  /** @type {TimeoutEntry[]} */
  const timeouts = [];

  /** @type {IntervalEntry[]} */
  const intervals = [];

  /** Logical clock in milliseconds; advanced by tick(). Starts at 0. */
  let currentLogicalMs = 0;

  return {
    // ── Scheduling ───────────────────────────────────────────────────────────

    /**
     * Registers a one-shot callback to fire when tick() advances past
     * `isoTimestamp`. No real timer is created; firing is driven by tick().
     *
     * @param {string} isoTimestamp - ISO-8601 target fire time
     * @param {function(): void} callback
     * @returns {string} opaque cancellation handle
     */
    scheduleAt(isoTimestamp, callback) {
      const handle = crypto.randomUUID();
      timeouts.push({
        handle,
        fireAt: new Date(isoTimestamp).getTime(),
        cb: callback,
        fired: false,
      });
      return handle;
    },

    /**
     * Registers a recurring callback to fire every `intervalMs` milliseconds
     * of logical time. No real timer is created; firing is driven by tick().
     *
     * Interval firing is anchored to currentLogicalMs at registration time.
     * For predictable elapsed counts, advance time via tick() before
     * registering intervals so that lastFiredAt reflects a meaningful baseline.
     *
     * @param {number} intervalMs
     * @param {function(): void} callback
     * @returns {string} opaque cancellation handle
     */
    scheduleInterval(intervalMs, callback) {
      const handle = crypto.randomUUID();
      intervals.push({
        handle,
        intervalMs,
        cb: callback,
        registered: currentLogicalMs,
        lastFiredAt: currentLogicalMs,
      });
      return handle;
    },

    // ── Cancellation ─────────────────────────────────────────────────────────

    /**
     * Removes the entry identified by `handle` from both the timeout and
     * interval registries. Silently no-ops if the handle is unknown.
     *
     * @param {string} handle
     * @returns {void}
     */
    cancel(handle) {
      const tIdx = timeouts.findIndex(e => e.handle === handle);
      if (tIdx !== -1) timeouts.splice(tIdx, 1);

      const iIdx = intervals.findIndex(e => e.handle === handle);
      if (iIdx !== -1) intervals.splice(iIdx, 1);
    },

    // ── Resume ───────────────────────────────────────────────────────────────

    /**
     * Updates the internal logical clock to `currentTime` (informational).
     * In the test adapter, tick() is the real driver of time; onResume merely
     * synchronises currentLogicalMs for subsequent scheduleInterval calls.
     *
     * @param {string} currentTime - ISO-8601 timestamp
     * @returns {void}
     */
    onResume(currentTime) {
      currentLogicalMs = new Date(currentTime).getTime();
    },

    // ── Test-only ────────────────────────────────────────────────────────────

    /**
     * Advances logical time to `isoTimestamp` and fires all callbacks whose
     * scheduled times fall at or before the target.
     *
     * Timeout firing: filters entries where fireAt <= targetMs and !fired,
     * sorts ascending by fireAt, then invokes each in order and marks fired.
     *
     * Interval firing: for each interval entry computes
     *   elapsed = Math.floor((targetMs - lastFiredAt) / intervalMs)
     * and invokes the callback `elapsed` times, then updates
     *   lastFiredAt += elapsed * intervalMs.
     *
     * No real timers (setTimeout / setInterval) are used anywhere in this
     * implementation — all time advancement is driven entirely by the caller.
     *
     * @param {string} isoTimestamp - ISO-8601 target time to advance to
     * @returns {void}
     */
    tick(isoTimestamp) {
      const targetMs = new Date(isoTimestamp).getTime();

      // Fire eligible one-shot timeouts in chronological order.
      const due = timeouts
        .filter(e => e.fireAt <= targetMs && !e.fired)
        .sort((a, b) => a.fireAt - b.fireAt);

      for (const entry of due) {
        entry.fired = true;
        entry.cb();
      }

      // Fire recurring intervals for all elapsed periods.
      for (const entry of intervals) {
        const elapsed = Math.floor((targetMs - entry.lastFiredAt) / entry.intervalMs);
        for (let i = 0; i < elapsed; i++) {
          entry.cb();
        }
        entry.lastFiredAt += elapsed * entry.intervalMs;
      }

      currentLogicalMs = targetMs;
    },
  };
}
