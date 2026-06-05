import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { createTier0NotificationAdapter, ftmEmitter } from '../src/adapters/notification/tier0NotificationAdapter.js';

// ---------------------------------------------------------------------------
// Helper factory
// ---------------------------------------------------------------------------

function makePayload(overrides) {
  return {
    recipientUserId: 'u1',
    title: 't',
    body: 'b',
    deepLinkUri: 'ftm://instance/x',
    requestForegroundDisplay: true,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// 3.8 Tier0 NotificationAdapter (Node path)
// ---------------------------------------------------------------------------

describe('3.8 Tier0 NotificationAdapter (Node path)', () => {
  test('send returns receipt with status delivered and adapterTier 0', async () => {
    const adapter = createTier0NotificationAdapter();
    const receipt = await adapter.send(makePayload());
    assert.deepEqual(receipt, { status: 'delivered', adapterTier: 0 });
  });

  test('send emits ftm:alert on ftmEmitter with the payload as the event arg', async () => {
    const adapter = createTier0NotificationAdapter();
    const payload = makePayload();
    let capturedArg;
    ftmEmitter.once('ftm:alert', (arg) => { capturedArg = arg; });
    await adapter.send(payload);
    assert.deepEqual(capturedArg, payload);
  });

  test(`send never throws \u2014 internal error returns { status: 'failed', adapterTier: 0 }`, async () => {
    const adapter = createTier0NotificationAdapter();
    // Force the try/catch path: a throwing once-listener makes ftmEmitter.emit() throw;
    // the once() wrapper removes the listener before calling it, so it cleans up even on throw.
    ftmEmitter.once('ftm:alert', () => { throw new Error('deliberate listener error'); });
    let receipt;
    await assert.doesNotReject(async () => {
      receipt = await adapter.send(makePayload());
    });
    assert.deepEqual(receipt, { status: 'failed', adapterTier: 0 });
  });

  test('requestForegroundDisplay true: no extra behavior at Tier 0; event still dispatched', async () => {
    const adapter = createTier0NotificationAdapter();
    let eventFired = false;
    ftmEmitter.once('ftm:alert', () => { eventFired = true; });
    const receipt = await adapter.send(makePayload({ requestForegroundDisplay: true }));
    assert.deepEqual(receipt, { status: 'delivered', adapterTier: 0 });
    assert.equal(eventFired, true, 'ftm:alert must still be emitted when requestForegroundDisplay is true');
  });
});
