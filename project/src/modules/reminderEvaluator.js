/**
 * Decide whether a reminder notification should be dispatched now.
 * Pure function — no I/O, no side effects.
 *
 * @param {Object} instance    - ftm:TaskInstance JSON-LD object
 * @param {Object} taskDef     - ftm:TaskDefinition JSON-LD object
 * @param {string} currentTime - ISO-8601 current timestamp
 * @returns {{ shouldRemind: boolean, reason: string }}
 */
export function reminderEvaluator(instance, taskDef, currentTime) {
  // Rule 1 — already complete
  if (instance['ftm:completionState']['ftm:status'] === 'completed') {
    return { shouldRemind: false, reason: 'already-complete' };
  }

  // Rule 2 — not yet due (ISO-8601 string comparison is lexicographically safe)
  if (instance['ftm:dueAt']['@value'] > currentTime) {
    return { shouldRemind: false, reason: 'not-yet-due' };
  }

  const mode = taskDef['ftm:reminderPolicy']['ftm:mode'];

  // Rule 4 — once mode
  if (mode === 'once') {
    if (instance['ftm:reminderSummary']['ftm:totalSent'] === 0) {
      return { shouldRemind: true, reason: 'first-and-only' };
    }
    return { shouldRemind: false, reason: 'once-sent' };
  }

  // Rule 5 — persistent mode
  if (mode === 'persistent') {
    const persistUntilSeconds =
      taskDef['ftm:reminderPolicy']['ftm:persistUntilSeconds'] ?? 86400;
    const dueAtMs = new Date(instance['ftm:dueAt']['@value']).getTime();
    const currentMs = new Date(currentTime).getTime();

    if (currentMs > dueAtMs + persistUntilSeconds * 1000) {
      return { shouldRemind: false, reason: 'persistence-window-expired' };
    }

    if (instance['ftm:reminderSummary']['ftm:totalSent'] === 0) {
      return { shouldRemind: true, reason: 'initial-reminder' };
    }

    if (instance['ftm:reminderSummary']['ftm:lastDeliveryStatus'] === 'failed') {
      return { shouldRemind: true, reason: 'retry-after-failure' };
    }

    const lastSentMs = new Date(
      instance['ftm:reminderSummary']['ftm:lastSentAt']
    ).getTime();
    const intervalMs = taskDef['ftm:reminderPolicy']['ftm:intervalSeconds'] * 1000;

    if (currentMs - lastSentMs >= intervalMs) {
      return { shouldRemind: true, reason: 'interval-elapsed' };
    }

    return { shouldRemind: false, reason: 'interval-not-elapsed' };
  }
}
