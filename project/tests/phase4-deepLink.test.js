import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { resolveDeepLink } from '../src/routing/deepLink.js';
import { createInMemoryStateAdapter } from '../src/adapters/state/inMemoryStateAdapter.js';
import { createTaskInstance } from '../src/entities/taskInstance.js';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Creates a fresh in-memory state, saves one TaskInstance, and returns
 * the adapter, the saved instance, and the short id (the segment after
 * the last `:` in the instance's @id — the part used in deep-link URIs).
 *
 * @returns {Promise<{ state: object, savedInstance: object, savedId: string }>}
 */
async function setup() {
  const state = createInMemoryStateAdapter();
  const savedInstance = createTaskInstance({
    taskDefinitionId: 'urn:ftm:taskdef:test-def',
    assignedTo: 'urn:ftm:user:test-child',
    dueAt: new Date(Date.now() + 86_400_000).toISOString(),
  });
  await state.saveTaskInstance(savedInstance);
  // @id shape: urn:ftm:instance:<uuid>  →  short id is the last segment
  const savedId = savedInstance['@id'].split(':').at(-1);
  return { state, savedInstance, savedId };
}

// ---------------------------------------------------------------------------
// 4.9 deepLink resolution
// ---------------------------------------------------------------------------

describe('4.9 deepLink resolution', () => {
  test('ftm:// scheme: resolveDeepLink(ftm://instance/<id>, ...) returns the saved instance', async () => {
    const { state, savedInstance, savedId } = await setup();
    const result = await resolveDeepLink(`ftm://instance/${savedId}`, { stateAdapter: state });
    assert.deepEqual(result, savedInstance);
  });

  test('hash-router scheme: resolveDeepLink(#/instance/<id>, ...) returns the saved instance', async () => {
    const { state, savedInstance, savedId } = await setup();
    const result = await resolveDeepLink(`#/instance/${savedId}`, { stateAdapter: state });
    assert.deepEqual(result, savedInstance);
  });

  test('non-existent id: returns null (no throw)', async () => {
    const { state } = await setup();
    const result = await resolveDeepLink('ftm://instance/does-not-exist', { stateAdapter: state });
    assert.equal(result, null);
  });

  test('malformed URI: returns null', async () => {
    const { state } = await setup();
    const result = await resolveDeepLink('not-a-valid-uri', { stateAdapter: state });
    assert.equal(result, null);
  });
});
