import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { createNoopNotificationAdapter } from '../src/adapters/notification/noopNotificationAdapter.js';
import { ftmEmitter } from '../src/adapters/notification/tier0NotificationAdapter.js';

// ---------------------------------------------------------------------------
// 3.9 No-op NotificationAdapter
// ---------------------------------------------------------------------------

describe('3.9 No-op NotificationAdapter', () => {
  test('send returns receipt with status delivered and adapterTier 0', async () => {
    const adapter = createNoopNotificationAdapter();
    const receipt = await adapter.send({
      recipientUserId: 'u1',
      title: 't',
      body: 'b',
      deepLinkUri: 'ftm://instance/x',
      requestForegroundDisplay: false,
    });
    assert.deepEqual(receipt, { status: 'delivered', adapterTier: 0 });
  });

  test('send does NOT emit ftm:alert (register a listener on ftmEmitter; call send; assert listener never invoked)', async () => {
    const adapter = createNoopNotificationAdapter();
    let listenerInvoked = false;
    const listener = () => { listenerInvoked = true; };
    ftmEmitter.on('ftm:alert', listener);
    await adapter.send({
      recipientUserId: 'u1',
      title: 't',
      body: 'b',
      deepLinkUri: 'ftm://instance/x',
      requestForegroundDisplay: false,
    });
    ftmEmitter.removeListener('ftm:alert', listener);
    assert.equal(listenerInvoked, false, 'noop adapter must not emit ftm:alert');
  });
});
