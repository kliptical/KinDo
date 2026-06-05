// Browser entry — same shared modules as src/index.js but uses Tier 0
// NotificationAdapter (CustomEvent) and Tier 0 OrchestrationAdapter
// (real timers) instead of test variants.
import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './ui/App.js';
import { createInMemoryStateAdapter } from './adapters/state/inMemoryStateAdapter.js';
import { createTier0OrchestrationAdapter } from './adapters/orchestration/tier0OrchestrationAdapter.js';
import { createTier0NotificationAdapter } from './adapters/notification/tier0NotificationAdapter.js';
import { createUser } from './entities/user.js';
import { parentCreatesTask } from './flows/parentCreatesTask.js';
import { bootResume } from './flows/bootResume.js';
import { resolveDeepLink } from './routing/deepLink.js';

/**
 * Creates the FTM browser application with Tier 0 adapters.
 *
 * Returns the same shape as createApp() in src/index.js:
 *   { stateAdapter, orchestrationAdapter, notificationAdapter }
 *
 * Tier 0 adapters used:
 *   - OrchestrationAdapter: real setTimeout / setInterval (SPEC §6.1 Tier 0)
 *   - NotificationAdapter: CustomEvent("ftm:alert") on window (SPEC §7.2)
 *   - StateAdapter: in-memory (same as Node entry)
 *
 * Note: rrule resolves via the import map declared in project/index.html
 * (mapped to esm.sh CDN). No code change needed in shared modules.
 *
 * @returns {Promise<{stateAdapter: Object, orchestrationAdapter: Object, notificationAdapter: Object}>}
 */
export async function createBrowserApp() {
  const stateAdapter = createInMemoryStateAdapter();
  const orchestrationAdapter = createTier0OrchestrationAdapter();
  const notificationAdapter = createTier0NotificationAdapter();
  return { stateAdapter, orchestrationAdapter, notificationAdapter };
}

// IIFE: log banner and expose the app + utility helpers on window.FTM
// for manual exploration in the browser console.
(async () => {
  console.log('FTM browser app loaded');
  window.FTM = await createBrowserApp();
  // Expose shared utility functions alongside the app adapters.
  window.FTM.createUser = createUser;
  window.FTM.parentCreatesTask = parentCreatesTask;
  window.FTM.bootResume = bootResume;
  window.FTM.resolveDeepLink = resolveDeepLink;
  const root = createRoot(document.getElementById('app'));
  root.render(React.createElement(App, { ftm: window.FTM }));
})();
