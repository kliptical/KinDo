import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { createTestOrchestrationAdapter } from '../src/adapters/orchestration/testOrchestrationAdapter.js';

// ---------------------------------------------------------------------------
// Epoch-anchor note: createTestOrchestrationAdapter() initialises
// currentLogicalMs = 0 (Unix epoch, 1970-01-01T00:00:00.000Z).
// Epoch-relative ISO strings keep interval arithmetic readable:
//   '1970-01-01T00:00:01.000Z' == 1000 ms from epoch, etc.
// ---------------------------------------------------------------------------

describe('3.6 Test OrchestrationAdapter', () => {
  test('tick fires all scheduleAt callbacks whose target <= tick timestamp', () => {
    const adapter = createTestOrchestrationAdapter();
    const fired = [];
    adapter.scheduleAt('1970-01-01T00:00:01.000Z', () => fired.push('A')); // fireAt 1000
    adapter.scheduleAt('1970-01-01T00:00:02.000Z', () => fired.push('B')); // fireAt 2000
    adapter.scheduleAt('1970-01-01T00:00:03.000Z', () => fired.push('C')); // fireAt 3000
    // target = 2000: A (1000 <= 2000) and B (2000 <= 2000) fire; C (3000 > 2000) does not
    adapter.tick('1970-01-01T00:00:02.000Z');
    assert.deepEqual(fired, ['A', 'B']);
  });

  test('multiple scheduleAt callbacks fire in ascending timestamp order on tick', () => {
    const adapter = createTestOrchestrationAdapter();
    const order = [];
    // Register deliberately out of chronological order
    adapter.scheduleAt('1970-01-01T00:00:03.000Z', () => order.push('C'));
    adapter.scheduleAt('1970-01-01T00:00:01.000Z', () => order.push('A'));
    adapter.scheduleAt('1970-01-01T00:00:02.000Z', () => order.push('B'));
    adapter.tick('1970-01-01T00:00:03.000Z');
    assert.deepEqual(order, ['A', 'B', 'C']);
  });

  test('each scheduleAt callback fires exactly once per tick (not repeatedly)', () => {
    const adapter = createTestOrchestrationAdapter();
    let count = 0;
    adapter.scheduleAt('1970-01-01T00:00:01.000Z', () => { count++; });
    adapter.tick('1970-01-01T00:00:05.000Z'); // fires; entry marked fired=true
    adapter.tick('1970-01-01T00:00:10.000Z'); // already fired; !e.fired is false → skipped
    assert.equal(count, 1);
  });

  test('scheduleAt callback NOT fired when tick timestamp is before target', () => {
    const adapter = createTestOrchestrationAdapter();
    let fired = false;
    adapter.scheduleAt('1970-01-01T00:00:10.000Z', () => { fired = true; }); // fireAt 10000
    adapter.tick('1970-01-01T00:00:05.000Z'); // target 5000 < fireAt 10000
    assert.equal(fired, false);
  });

  test('scheduleInterval fires once per elapsed interval when tick advances by interval (3 intervals -> 3 fires)', () => {
    const adapter = createTestOrchestrationAdapter();
    let count = 0;
    // lastFiredAt anchors to currentLogicalMs=0 (epoch) at registration time
    adapter.scheduleInterval(1000, () => { count++; });
    // elapsed = Math.floor((3000 - 0) / 1000) = 3
    adapter.tick('1970-01-01T00:00:03.000Z');
    assert.equal(count, 3);
  });

  test('cancel(handle) prevents callback from firing on subsequent tick', () => {
    const adapter = createTestOrchestrationAdapter();
    let fired = false;
    const handle = adapter.scheduleAt('1970-01-01T00:00:01.000Z', () => { fired = true; });
    adapter.cancel(handle); // splices entry from timeouts array
    adapter.tick('1970-01-01T00:00:05.000Z');
    assert.equal(fired, false);
  });

  test('does not use real timers: no setTimeout / setInterval anywhere (assert by elapsed wallclock < 10ms across many ticks)', () => {
    const adapter = createTestOrchestrationAdapter();
    let count = 0;
    // 5ms logical interval; each of the 100 ticks advances by exactly one interval
    adapter.scheduleInterval(5, () => { count++; });
    const start = Date.now();
    for (let i = 1; i <= 100; i++) {
      // new Date(i * 5) == epoch + (i*5) ms
      // elapsed per tick = Math.floor(((i*5) - ((i-1)*5)) / 5) = 1 → 1 fire each tick
      adapter.tick(new Date(i * 5).toISOString());
    }
    const elapsed = Date.now() - start;
    assert.ok(elapsed < 10, `Expected wallclock < 10ms but got ${elapsed}ms — real timer suspected`);
    assert.equal(count, 100);
  });
});
