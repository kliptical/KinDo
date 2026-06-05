import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { createTier0OrchestrationAdapter } from '../src/adapters/orchestration/tier0OrchestrationAdapter.js';

// ---------------------------------------------------------------------------
// 3.5 Tier0 OrchestrationAdapter
// ---------------------------------------------------------------------------

describe('3.5 Tier0 OrchestrationAdapter', () => {
  test('scheduleAt returns a string handle', () => {
    const adapter = createTier0OrchestrationAdapter();
    const future = new Date(Date.now() + 60_000).toISOString();
    const handle = adapter.scheduleAt(future, () => {});
    adapter.cancel(handle); // cleanup: clear the underlying setTimeout
    assert.equal(typeof handle, 'string');
    assert.ok(handle.length > 0);
  });

  test('scheduleAt with past timestamp fires callback quickly (within ~50ms via setTimeout(0))', async () => {
    const adapter = createTier0OrchestrationAdapter();
    let fired = false;
    const past = new Date(Date.now() - 1000).toISOString();
    adapter.scheduleAt(past, () => { fired = true; });
    // The implementation uses queueMicrotask for already-elapsed targets.
    // Microtasks are drained before the next macrotask, so awaiting a
    // setTimeout(0) is sufficient to confirm the callback has run.
    await new Promise(resolve => setTimeout(resolve, 0));
    assert.equal(fired, true);
  });

  test('scheduleAt with future timestamp 100ms out fires after delay; callback fired exactly once', async () => {
    const adapter = createTier0OrchestrationAdapter();
    let count = 0;
    const target = new Date(Date.now() + 100).toISOString();
    adapter.scheduleAt(target, () => { count++; });
    assert.equal(count, 0, 'must not fire before delay elapses');
    await new Promise(resolve => setTimeout(resolve, 150));
    assert.equal(count, 1);
  });

  test('scheduleInterval returns a string handle and fires callback at interval boundaries', async () => {
    const adapter = createTier0OrchestrationAdapter();
    let count = 0;
    const handle = adapter.scheduleInterval(50, () => { count++; });
    assert.equal(typeof handle, 'string');
    assert.ok(handle.length > 0);
    await new Promise(resolve => setTimeout(resolve, 150));
    adapter.cancel(handle); // cleanup
    assert.ok(count >= 1, `Expected at least 1 fire, got ${count}`);
  });

  test('cancel(handle) prevents the callback from firing', async () => {
    const adapter = createTier0OrchestrationAdapter();
    let fired = false;
    const target = new Date(Date.now() + 100).toISOString();
    const handle = adapter.scheduleAt(target, () => { fired = true; });
    adapter.cancel(handle);
    await new Promise(resolve => setTimeout(resolve, 150));
    assert.equal(fired, false);
  });

  test('cancel(handle) on an interval prevents subsequent fires', async () => {
    const adapter = createTier0OrchestrationAdapter();
    let count = 0;
    const handle = adapter.scheduleInterval(50, () => { count++; });
    // Wait long enough for at least one fire (interval = 50ms, wait = 80ms)
    await new Promise(resolve => setTimeout(resolve, 80));
    const snapshot = count;
    adapter.cancel(handle);
    // Wait another full interval period; no further fires should occur
    await new Promise(resolve => setTimeout(resolve, 100));
    assert.ok(snapshot >= 1, 'Expected at least 1 fire before cancel');
    assert.equal(count, snapshot, 'No additional fires after cancel');
  });

  test('onResume(now) is callable without error', () => {
    const adapter = createTier0OrchestrationAdapter();
    assert.doesNotThrow(() => {
      adapter.onResume(new Date().toISOString());
    });
  });
});
