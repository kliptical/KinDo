import { createInMemoryStateAdapter } from './inMemoryStateAdapter.js';

// LocalStorage StateAdapter — same StateAdapter interface as
// inMemoryStateAdapter, persists collections to window.localStorage so
// state survives reload AND is shared between same-origin tabs.
// Per SPEC §5: silent fallback to in-memory when localStorage is unavailable.
// Applies §5.1 LWW conflict resolution symmetrically to all save* methods.

const KEYS = {
  taskDefinitions: 'ftm.taskDefinitions',
  taskInstances: 'ftm.taskInstances',
  users: 'ftm.users',
};

function resolveConflict(existing, incoming) {
  if (!existing) return incoming;
  const eSeq = existing['ftm:clientSequence'] ?? 0;
  const iSeq = incoming['ftm:clientSequence'] ?? 0;
  if (iSeq > eSeq) return incoming;
  if (iSeq < eSeq) return existing;
  const eUpd = existing['ftm:updatedAt']?.['@value'] ?? '';
  const iUpd = incoming['ftm:updatedAt']?.['@value'] ?? '';
  if (iUpd > eUpd) return incoming;
  if (iUpd < eUpd) return existing;
  return incoming;
}

function loadCollection(key) {
  if (typeof localStorage === 'undefined') return {};
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return typeof parsed === 'object' && parsed !== null ? parsed : {};
  } catch {
    return {};
  }
}

function saveCollection(key, collection) {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(key, JSON.stringify(collection));
  } catch (e) {
    // Quota exceeded, private browsing, etc. — best-effort.
    console.warn('[FTM] localStorage save failed for', key, e);
  }
}

function applyInstanceFilter(instances, filter) {
  if (!filter) return instances;
  return instances.filter(inst => {
    if (filter.assignedTo && inst['ftm:assignedTo'] !== filter.assignedTo) return false;
    if (filter.status && inst['ftm:completionState']?.['ftm:status'] !== filter.status) return false;
    if (filter.taskDefinitionId && inst['ftm:taskDefinition'] !== filter.taskDefinitionId) return false;
    if (filter.fromDate && inst['ftm:dueAt']?.['@value'] < filter.fromDate) return false;
    if (filter.toDate && inst['ftm:dueAt']?.['@value'] > filter.toDate) return false;
    return true;
  });
}

export function createLocalStorageStateAdapter() {
  // SPEC §5: silent fallback to in-memory if localStorage unavailable
  if (typeof localStorage === 'undefined') {
    console.warn('[FTM] localStorage unavailable; falling back to in-memory adapter');
    return createInMemoryStateAdapter();
  }

  return {
    // Task Definitions
    async saveTaskDefinition(td) {
      const coll = loadCollection(KEYS.taskDefinitions);
      coll[td['@id']] = resolveConflict(coll[td['@id']], td);
      saveCollection(KEYS.taskDefinitions, coll);
    },
    async getTaskDefinition(id) {
      const coll = loadCollection(KEYS.taskDefinitions);
      return coll[id] ?? null;
    },
    async listTaskDefinitions(filter) {
      const coll = loadCollection(KEYS.taskDefinitions);
      let all = Object.values(coll);
      if (filter?.status) all = all.filter(d => d['ftm:status'] === filter.status);
      return all;
    },

    // Task Instances
    async saveTaskInstance(ti) {
      const coll = loadCollection(KEYS.taskInstances);
      coll[ti['@id']] = resolveConflict(coll[ti['@id']], ti);
      saveCollection(KEYS.taskInstances, coll);
    },
    async getTaskInstance(id) {
      const coll = loadCollection(KEYS.taskInstances);
      return coll[id] ?? null;
    },
    async listTaskInstances(filter) {
      const coll = loadCollection(KEYS.taskInstances);
      return applyInstanceFilter(Object.values(coll), filter);
    },

    // Users
    async saveUser(u) {
      const coll = loadCollection(KEYS.users);
      coll[u['@id']] = resolveConflict(coll[u['@id']], u);
      saveCollection(KEYS.users, coll);
    },
    async getUser(id) {
      const coll = loadCollection(KEYS.users);
      return coll[id] ?? null;
    },
    async listUsers() {
      const coll = loadCollection(KEYS.users);
      return Object.values(coll);
    },
  };
}
