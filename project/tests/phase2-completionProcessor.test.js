import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { completionProcessor } from '../src/modules/completionProcessor.js';
import { createTaskInstance } from '../src/entities/taskInstance.js';

// ---------------------------------------------------------------------------
// Helper factory (module-level, not inside describe blocks)
// ---------------------------------------------------------------------------

/**
 * Returns a pending TaskInstance. Pass top-level key overrides to customise.
 * Default assignedTo is 'urn:ftm:child:child-1'.
 *
 * @param {Object} [overrides={}] - Top-level key overrides spread onto base instance.
 * @returns {Object} ftm:TaskInstance JSON-LD object
 */
function makeInstance(overrides = {}) {
  const base = createTaskInstance({
    taskDefinitionId: 'urn:ftm:taskdef:test',
    assignedTo: 'urn:ftm:child:child-1',
    dueAt: '2026-06-01T09:00:00Z',
  });
  return { ...base, ...overrides };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('2.3 CompletionProcessor', () => {
  test('returns a NEW object (strict reference inequality with input)', () => {
    const instance = makeInstance();
    const result = completionProcessor(
      instance,
      'urn:ftm:user:child-1',
      'child',
      '2026-06-01T10:00:00Z'
    );
    assert.notStrictEqual(result, instance);
  });

  test('output completionState.status is completed', () => {
    const instance = makeInstance();
    const result = completionProcessor(
      instance,
      'urn:ftm:user:child-1',
      'child',
      '2026-06-01T10:00:00Z'
    );
    assert.equal(result['ftm:completionState']['ftm:status'], 'completed');
  });

  test('output completedAt equals the completedAt argument', () => {
    const instance = makeInstance();
    const completedAt = '2026-06-01T10:00:00Z';
    const result = completionProcessor(instance, 'urn:ftm:user:child-1', 'child', completedAt);
    assert.equal(result['ftm:completionState']['ftm:completedAt'], completedAt);
  });

  test('output completedBy equals the completedBy argument', () => {
    const instance = makeInstance();
    const completedBy = 'urn:ftm:user:child-1';
    const result = completionProcessor(instance, completedBy, 'child', '2026-06-01T10:00:00Z');
    assert.equal(result['ftm:completionState']['ftm:completedBy'], completedBy);
  });

  test('output completedByRole equals the completedByRole argument', () => {
    const instance = makeInstance();
    const result = completionProcessor(
      instance,
      'urn:ftm:user:child-1',
      'child',
      '2026-06-01T10:00:00Z'
    );
    assert.equal(result['ftm:completionState']['ftm:completedByRole'], 'child');
  });

  test('output clientSequence equals input clientSequence + 1', () => {
    const instance = makeInstance();
    const inputSeq = instance['ftm:clientSequence'];
    const result = completionProcessor(
      instance,
      'urn:ftm:user:child-1',
      'child',
      '2026-06-01T10:00:00Z'
    );
    assert.equal(result['ftm:clientSequence'], inputSeq + 1);
  });

  test('output updatedAt @value equals completedAt', () => {
    const instance = makeInstance();
    const completedAt = '2026-06-01T10:00:00Z';
    const result = completionProcessor(instance, 'urn:ftm:user:child-1', 'child', completedAt);
    assert.equal(result['ftm:updatedAt']['@value'], completedAt);
  });

  test('already-completed input returns instance with ftm:warning already-complete (no other mutation)', () => {
    // Override the whole completionState sub-object to set status=completed
    const alreadyDone = makeInstance({
      'ftm:completionState': {
        '@type': 'ftm:CompletionState',
        'ftm:status': 'completed',
        'ftm:completedAt': '2026-06-01T09:30:00Z',
        'ftm:completedBy': 'urn:ftm:user:child-1',
        'ftm:completedByRole': 'child',
      },
    });
    const seqBefore = alreadyDone['ftm:clientSequence'];
    const result = completionProcessor(
      alreadyDone,
      'urn:ftm:user:child-1',
      'child',
      '2026-06-01T10:00:00Z'
    );
    // Warning flag set
    assert.equal(result['ftm:warning'], 'already-complete');
    // clientSequence NOT incremented
    assert.equal(result['ftm:clientSequence'], seqBefore);
    // Original completion fields unchanged
    assert.equal(result['ftm:completionState']['ftm:completedAt'], '2026-06-01T09:30:00Z');
    assert.equal(result['ftm:completionState']['ftm:completedBy'], 'urn:ftm:user:child-1');
    assert.equal(result['ftm:completionState']['ftm:status'], 'completed');
  });

  test('completedByRole parent is recorded; completion semantics unchanged', () => {
    const instance = makeInstance();
    const result = completionProcessor(
      instance,
      'urn:ftm:user:parent-1',
      'parent',
      '2026-06-01T10:00:00Z'
    );
    assert.equal(result['ftm:completionState']['ftm:completedByRole'], 'parent');
    assert.equal(result['ftm:completionState']['ftm:status'], 'completed');
  });

  // SPEC §13 item 5
  test('§13.5 parent completion via completionProcessor: output has completionState.status completed, completedByRole parent, clientSequence incremented', () => {
    const instance = makeInstance();
    const inputSeq = instance['ftm:clientSequence'];
    const completedAt = '2026-06-01T10:00:00Z';
    const result = completionProcessor(instance, 'urn:ftm:user:parent-1', 'parent', completedAt);
    assert.equal(result['ftm:completionState']['ftm:status'], 'completed');
    assert.equal(result['ftm:completionState']['ftm:completedByRole'], 'parent');
    assert.equal(result['ftm:clientSequence'], inputSeq + 1);
  });

  // SPEC §13 item 6 — note user-store check is Phase 4 deferred (I4)
  test('§13.6 NOTE: §11 completedBy userId match check is Phase 4 deferred. This test confirms the structural contract: child completion with matching assignedTo passes through completionProcessor without throwing', () => {
    // assignedTo = 'urn:ftm:child:child-1' (makeInstance default)
    // completedBy intentionally matches the assignedTo URN.
    // Pure-function contract: no User-store access, so no throw expected.
    const instance = makeInstance();
    let result;
    assert.doesNotThrow(() => {
      result = completionProcessor(
        instance,
        'urn:ftm:child:child-1',
        'child',
        '2026-06-01T10:00:00Z'
      );
    });
    assert.equal(result['ftm:completionState']['ftm:status'], 'completed');
  });
});
