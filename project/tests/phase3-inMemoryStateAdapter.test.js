import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { createInMemoryStateAdapter } from '../src/adapters/state/inMemoryStateAdapter.js';
import { createTaskDefinition } from '../src/entities/taskDefinition.js';
import { createTaskInstance } from '../src/entities/taskInstance.js';
import { createUser } from '../src/entities/user.js';

// ---------------------------------------------------------------------------
// Helper factories (module-level, not inside describe blocks)
// ---------------------------------------------------------------------------

function makeUser(role = 'child') {
  return createUser({ role, displayName: 'Test ' + role });
}

function makeTaskDef(overrides = {}) {
  const td = createTaskDefinition({
    title: 'Test Task',
    description: 'A test task definition',
    assignedTo: 'urn:ftm:user:test-child',
    createdBy: 'urn:ftm:user:test-parent',
    dueAt: '2026-06-01T12:00:00Z',
    scheduleType: 'one-time',
  });
  return { ...td, ...overrides };
}

// ---------------------------------------------------------------------------
// 3.2 InMemoryStateAdapter – basic CRUD
// ---------------------------------------------------------------------------

describe('3.2 InMemoryStateAdapter - basic CRUD', () => {
  test('saveTaskDefinition stores entity by @id', async () => {
    const adapter = createInMemoryStateAdapter();
    const td = makeTaskDef();
    await adapter.saveTaskDefinition(td);
    const result = await adapter.getTaskDefinition(td['@id']);
    assert.deepEqual(result, td);
  });

  test('getTaskDefinition returns null for unknown id', async () => {
    const adapter = createInMemoryStateAdapter();
    const result = await adapter.getTaskDefinition('urn:ftm:task:does-not-exist');
    assert.equal(result, null);
  });

  test('listTaskDefinitions with status active returns only active entities', async () => {
    const adapter = createInMemoryStateAdapter();
    const tdActive = makeTaskDef();                             // ftm:status defaults to 'active'
    const tdArchived = makeTaskDef({ 'ftm:status': 'archived' });
    await adapter.saveTaskDefinition(tdActive);
    await adapter.saveTaskDefinition(tdArchived);
    const results = await adapter.listTaskDefinitions({ status: 'active' });
    assert.equal(results.length, 1);
    assert.equal(results[0]['@id'], tdActive['@id']);
  });

  test('saveTaskInstance + getTaskInstance round-trip', async () => {
    const adapter = createInMemoryStateAdapter();
    const ti = createTaskInstance({
      taskDefinitionId: 'urn:ftm:task:def-rt',
      assignedTo: 'urn:ftm:user:child-rt',
      dueAt: '2026-06-01T12:00:00Z',
    });
    await adapter.saveTaskInstance(ti);
    const result = await adapter.getTaskInstance(ti['@id']);
    assert.deepEqual(result, ti);
  });

  test('listTaskInstances with empty filter returns all', async () => {
    const adapter = createInMemoryStateAdapter();
    const ti1 = createTaskInstance({
      taskDefinitionId: 'urn:ftm:task:def-1',
      assignedTo: 'urn:ftm:user:child-a',
      dueAt: '2026-06-01T12:00:00Z',
    });
    const ti2 = createTaskInstance({
      taskDefinitionId: 'urn:ftm:task:def-2',
      assignedTo: 'urn:ftm:user:child-b',
      dueAt: '2026-06-02T12:00:00Z',
    });
    await adapter.saveTaskInstance(ti1);
    await adapter.saveTaskInstance(ti2);
    const results = await adapter.listTaskInstances();
    assert.equal(results.length, 2);
  });

  test('listTaskInstances with assignedTo filter excludes other children', async () => {
    const adapter = createInMemoryStateAdapter();
    const userA = makeUser('child');
    const userB = makeUser('child');
    const ti1 = createTaskInstance({
      taskDefinitionId: 'urn:ftm:task:def-1',
      assignedTo: userA['@id'],
      dueAt: '2026-06-01T12:00:00Z',
    });
    const ti2 = createTaskInstance({
      taskDefinitionId: 'urn:ftm:task:def-1',
      assignedTo: userB['@id'],
      dueAt: '2026-06-01T12:00:00Z',
    });
    await adapter.saveTaskInstance(ti1);
    await adapter.saveTaskInstance(ti2);
    const results = await adapter.listTaskInstances({ assignedTo: userA['@id'] });
    assert.equal(results.length, 1);
    assert.equal(results[0]['ftm:assignedTo'], userA['@id']);
  });

  test('listTaskInstances with status filter (pending vs completed) works', async () => {
    const adapter = createInMemoryStateAdapter();
    const tiPending = createTaskInstance({
      taskDefinitionId: 'urn:ftm:task:def-1',
      assignedTo: 'urn:ftm:user:child-a',
      dueAt: '2026-06-01T12:00:00Z',
    });
    const tiCompleted = createTaskInstance({
      taskDefinitionId: 'urn:ftm:task:def-1',
      assignedTo: 'urn:ftm:user:child-a',
      dueAt: '2026-06-02T12:00:00Z',
    });
    tiCompleted['ftm:completionState']['ftm:status'] = 'completed';
    tiCompleted['ftm:completionState']['ftm:completedAt'] = '2026-06-02T13:00:00Z';
    await adapter.saveTaskInstance(tiPending);
    await adapter.saveTaskInstance(tiCompleted);
    const pendingResults = await adapter.listTaskInstances({ status: 'pending' });
    assert.equal(pendingResults.length, 1);
    assert.equal(pendingResults[0]['@id'], tiPending['@id']);
    const completedResults = await adapter.listTaskInstances({ status: 'completed' });
    assert.equal(completedResults.length, 1);
    assert.equal(completedResults[0]['@id'], tiCompleted['@id']);
  });

  test('listTaskInstances with taskDefinitionId filter works', async () => {
    const adapter = createInMemoryStateAdapter();
    const td1 = makeTaskDef();
    const td2 = makeTaskDef();
    const ti1 = createTaskInstance({
      taskDefinitionId: td1['@id'],
      assignedTo: 'urn:ftm:user:child-a',
      dueAt: '2026-06-01T12:00:00Z',
    });
    const ti2 = createTaskInstance({
      taskDefinitionId: td2['@id'],
      assignedTo: 'urn:ftm:user:child-a',
      dueAt: '2026-06-01T12:00:00Z',
    });
    await adapter.saveTaskInstance(ti1);
    await adapter.saveTaskInstance(ti2);
    const results = await adapter.listTaskInstances({ taskDefinitionId: td1['@id'] });
    assert.equal(results.length, 1);
    assert.equal(results[0]['ftm:taskDefinition'], td1['@id']);
  });

  test('listTaskInstances with fromDate / toDate filters work', async () => {
    const adapter = createInMemoryStateAdapter();
    const tiEarly = createTaskInstance({
      taskDefinitionId: 'urn:ftm:task:def-1',
      assignedTo: 'urn:ftm:user:child-a',
      dueAt: '2026-06-01T12:00:00Z',
    });
    const tiMid = createTaskInstance({
      taskDefinitionId: 'urn:ftm:task:def-1',
      assignedTo: 'urn:ftm:user:child-a',
      dueAt: '2026-06-15T12:00:00Z',
    });
    const tiLate = createTaskInstance({
      taskDefinitionId: 'urn:ftm:task:def-1',
      assignedTo: 'urn:ftm:user:child-a',
      dueAt: '2026-06-30T12:00:00Z',
    });
    await adapter.saveTaskInstance(tiEarly);
    await adapter.saveTaskInstance(tiMid);
    await adapter.saveTaskInstance(tiLate);
    // fromDate only: >= 2026-06-10 → mid + late
    const fromResults = await adapter.listTaskInstances({ fromDate: '2026-06-10T00:00:00Z' });
    assert.equal(fromResults.length, 2);
    // toDate only: <= 2026-06-20 → early + mid
    const toResults = await adapter.listTaskInstances({ toDate: '2026-06-20T00:00:00Z' });
    assert.equal(toResults.length, 2);
    // range [2026-06-10, 2026-06-20] → mid only
    const rangeResults = await adapter.listTaskInstances({
      fromDate: '2026-06-10T00:00:00Z',
      toDate: '2026-06-20T00:00:00Z',
    });
    assert.equal(rangeResults.length, 1);
    assert.equal(rangeResults[0]['@id'], tiMid['@id']);
  });

  test('saveUser + getUser + listUsers round-trip', async () => {
    const adapter = createInMemoryStateAdapter();
    const parent = makeUser('parent');
    const child = makeUser('child');
    await adapter.saveUser(parent);
    await adapter.saveUser(child);
    const fetchedParent = await adapter.getUser(parent['@id']);
    assert.deepEqual(fetchedParent, parent);
    const allUsers = await adapter.listUsers();
    assert.equal(allUsers.length, 2);
    const ids = allUsers.map(u => u['@id']);
    assert.ok(ids.includes(parent['@id']));
    assert.ok(ids.includes(child['@id']));
  });
});

// ---------------------------------------------------------------------------
// 3.2 InMemoryStateAdapter – §5.1 LWW conflict resolution
// ---------------------------------------------------------------------------

describe('3.2 InMemoryStateAdapter - \u00a75.1 LWW conflict resolution', () => {
  test('higher clientSequence wins: save seq=1 then seq=2; get returns seq=2 entity', async () => {
    const adapter = createInMemoryStateAdapter();
    const v1 = createTaskInstance({
      taskDefinitionId: 'urn:ftm:task:def-1',
      assignedTo: 'urn:ftm:user:child-a',
      dueAt: '2026-06-01T12:00:00Z',
    });
    v1['ftm:clientSequence'] = 1;
    v1['ftm:updatedAt']['@value'] = '2026-01-01T00:00:00Z';

    const v2 = createTaskInstance({
      taskDefinitionId: 'urn:ftm:task:def-1',
      assignedTo: 'urn:ftm:user:child-b',
      dueAt: '2026-06-01T12:00:00Z',
    });
    v2['@id'] = v1['@id'];
    v2['ftm:clientSequence'] = 2;
    v2['ftm:updatedAt']['@value'] = '2026-01-01T00:00:00Z';

    await adapter.saveTaskInstance(v1);
    await adapter.saveTaskInstance(v2);
    const result = await adapter.getTaskInstance(v1['@id']);
    assert.equal(result['ftm:clientSequence'], 2);
    assert.equal(result['ftm:assignedTo'], 'urn:ftm:user:child-b');
  });

  test('lower clientSequence loses: save seq=2 then seq=1; get returns seq=2 entity (unchanged)', async () => {
    const adapter = createInMemoryStateAdapter();
    const vHigh = createTaskInstance({
      taskDefinitionId: 'urn:ftm:task:def-1',
      assignedTo: 'urn:ftm:user:child-a',
      dueAt: '2026-06-01T12:00:00Z',
    });
    vHigh['ftm:clientSequence'] = 2;
    vHigh['ftm:updatedAt']['@value'] = '2026-01-02T00:00:00Z';

    const vLow = createTaskInstance({
      taskDefinitionId: 'urn:ftm:task:def-1',
      assignedTo: 'urn:ftm:user:child-b',
      dueAt: '2026-06-01T12:00:00Z',
    });
    vLow['@id'] = vHigh['@id'];
    vLow['ftm:clientSequence'] = 1;
    vLow['ftm:updatedAt']['@value'] = '2026-01-01T00:00:00Z';

    await adapter.saveTaskInstance(vHigh);
    await adapter.saveTaskInstance(vLow);
    const result = await adapter.getTaskInstance(vHigh['@id']);
    assert.equal(result['ftm:clientSequence'], 2);
    assert.equal(result['ftm:assignedTo'], 'urn:ftm:user:child-a');
  });

  test('equal clientSequence, later updatedAt wins: save seq=1 ts=A then seq=1 ts=B (B later); get returns B-version', async () => {
    const adapter = createInMemoryStateAdapter();
    const vA = createTaskInstance({
      taskDefinitionId: 'urn:ftm:task:def-1',
      assignedTo: 'urn:ftm:user:child-a',
      dueAt: '2026-06-01T12:00:00Z',
    });
    vA['ftm:clientSequence'] = 1;
    vA['ftm:updatedAt']['@value'] = '2026-01-01T00:00:00Z';

    const vB = createTaskInstance({
      taskDefinitionId: 'urn:ftm:task:def-1',
      assignedTo: 'urn:ftm:user:child-b',
      dueAt: '2026-06-01T12:00:00Z',
    });
    vB['@id'] = vA['@id'];
    vB['ftm:clientSequence'] = 1;
    vB['ftm:updatedAt']['@value'] = '2026-01-02T00:00:00Z';    // later

    await adapter.saveTaskInstance(vA);
    await adapter.saveTaskInstance(vB);
    const result = await adapter.getTaskInstance(vA['@id']);
    assert.equal(result['ftm:updatedAt']['@value'], '2026-01-02T00:00:00Z');
    assert.equal(result['ftm:assignedTo'], 'urn:ftm:user:child-b');
  });

  test('equal clientSequence, equal updatedAt: incoming wins (idempotent re-save)', async () => {
    const adapter = createInMemoryStateAdapter();
    const v1 = createTaskInstance({
      taskDefinitionId: 'urn:ftm:task:def-1',
      assignedTo: 'urn:ftm:user:child-a',
      dueAt: '2026-06-01T12:00:00Z',
    });
    v1['ftm:clientSequence'] = 1;
    v1['ftm:updatedAt']['@value'] = '2026-01-01T00:00:00Z';

    const v2 = createTaskInstance({
      taskDefinitionId: 'urn:ftm:task:def-1',
      assignedTo: 'urn:ftm:user:child-b',   // distinguishable field
      dueAt: '2026-06-01T12:00:00Z',
    });
    v2['@id'] = v1['@id'];
    v2['ftm:clientSequence'] = 1;
    v2['ftm:updatedAt']['@value'] = '2026-01-01T00:00:00Z';    // identical timestamp

    await adapter.saveTaskInstance(v1);
    await adapter.saveTaskInstance(v2);
    const result = await adapter.getTaskInstance(v1['@id']);
    // Full tie → incoming wins
    assert.equal(result['ftm:assignedTo'], 'urn:ftm:user:child-b');
  });

  test('same LWW rules apply to saveTaskDefinition (operator I7: ignore \u00a73.2 immutability; apply LWW symmetrically)', async () => {
    const adapter = createInMemoryStateAdapter();
    // Create two TDs sharing the same @id; higher sequence should win regardless of save order.
    const tdHigh = makeTaskDef();
    tdHigh['ftm:clientSequence'] = 2;
    tdHigh['ftm:updatedAt'] = { '@type': 'xsd:dateTime', '@value': '2026-01-02T00:00:00Z' };
    tdHigh['ftm:title'] = 'High-seq version';

    const tdLow = makeTaskDef({ '@id': tdHigh['@id'] });
    tdLow['ftm:clientSequence'] = 1;
    tdLow['ftm:updatedAt'] = { '@type': 'xsd:dateTime', '@value': '2026-01-01T00:00:00Z' };
    tdLow['ftm:title'] = 'Low-seq version';

    // Save seq=2 first, then attempt to overwrite with seq=1 — seq=2 must survive.
    await adapter.saveTaskDefinition(tdHigh);
    await adapter.saveTaskDefinition(tdLow);
    const result = await adapter.getTaskDefinition(tdHigh['@id']);
    assert.equal(result['ftm:clientSequence'], 2);
    assert.equal(result['ftm:title'], 'High-seq version');
  });

  test('same LWW rules apply to saveUser', async () => {
    const adapter = createInMemoryStateAdapter();
    // User entities carry no ftm:clientSequence / ftm:updatedAt;
    // resolveConflict always reaches the full-tie branch → incoming wins.
    const u1 = makeUser('parent');
    const u2 = makeUser('parent');
    u2['@id'] = u1['@id'];
    u2['ftm:displayName'] = 'Updated Parent';

    await adapter.saveUser(u1);
    await adapter.saveUser(u2);
    const result = await adapter.getUser(u1['@id']);
    assert.equal(result['ftm:displayName'], 'Updated Parent');
  });
});

// ---------------------------------------------------------------------------
// 3.2 SPEC §13 item 8 – conflicting TaskInstance
// ---------------------------------------------------------------------------

// SPEC \u00a713 item 8
describe('3.2 SPEC \u00a713 item 8 - conflicting TaskInstance', () => {
  test('save two conflicting TaskInstance @id with different clientSequence; getTaskInstance returns higher-sequence version', async () => {
    const adapter = createInMemoryStateAdapter();
    const tiLow = createTaskInstance({
      taskDefinitionId: 'urn:ftm:task:def-conflict',
      assignedTo: 'urn:ftm:user:child-a',
      dueAt: '2026-06-01T12:00:00Z',
    });
    tiLow['ftm:clientSequence'] = 1;
    tiLow['ftm:updatedAt']['@value'] = '2026-01-01T00:00:00Z';

    const tiHigh = createTaskInstance({
      taskDefinitionId: 'urn:ftm:task:def-conflict',
      assignedTo: 'urn:ftm:user:child-b',
      dueAt: '2026-06-01T12:00:00Z',
    });
    tiHigh['@id'] = tiLow['@id'];
    tiHigh['ftm:clientSequence'] = 5;
    tiHigh['ftm:updatedAt']['@value'] = '2026-01-05T00:00:00Z';

    await adapter.saveTaskInstance(tiLow);
    await adapter.saveTaskInstance(tiHigh);
    const result = await adapter.getTaskInstance(tiLow['@id']);
    assert.equal(result['ftm:clientSequence'], 5);
    assert.equal(result['ftm:assignedTo'], 'urn:ftm:user:child-b');
  });
});
