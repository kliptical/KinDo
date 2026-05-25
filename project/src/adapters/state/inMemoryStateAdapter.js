/**
 * @typedef {Object} InstanceFilter
 * @property {string} [assignedTo]
 * @property {'pending'|'completed'} [status]
 * @property {string} [taskDefinitionId]
 * @property {string} [fromDate] - ISO-8601
 * @property {string} [toDate] - ISO-8601
 */

/**
 * @typedef {Object} StateAdapter
 * @property {function(Object): Promise<void>} saveTaskDefinition
 * @property {function(string): Promise<Object|null>} getTaskDefinition
 * @property {function(Object=): Promise<Object[]>} listTaskDefinitions
 * @property {function(Object): Promise<void>} saveTaskInstance
 * @property {function(string): Promise<Object|null>} getTaskInstance
 * @property {function(InstanceFilter=): Promise<Object[]>} listTaskInstances
 * @property {function(Object): Promise<void>} saveUser
 * @property {function(string): Promise<Object|null>} getUser
 * @property {function(): Promise<Object[]>} listUsers
 */

/**
 * Internal last-writer-wins conflict resolver.
 * Resolution order (SPEC §5.1):
 *   1. No existing entity → incoming wins.
 *   2. Higher ftm:clientSequence wins.
 *   3. On tie, later ftm:updatedAt['@value'] (ISO-8601 lexicographic) wins.
 *   4. Full tie → incoming wins (idempotent re-save is safe).
 *
 * Fields absent on either side are treated as -Infinity / '' so that entities
 * lacking sync metadata (e.g. User) safely fall through to step 4.
 *
 * @param {Object|undefined} existing
 * @param {Object} incoming
 * @returns {Object}
 */
function resolveConflict(existing, incoming) {
  if (!existing) return incoming;

  const existingSeq = existing['ftm:clientSequence'] ?? -Infinity;
  const incomingSeq = incoming['ftm:clientSequence'] ?? -Infinity;

  if (incomingSeq > existingSeq) return incoming;
  if (existingSeq > incomingSeq) return existing;

  // Sequences equal — compare updatedAt timestamps.
  const existingTs = existing['ftm:updatedAt']?.['@value'] ?? '';
  const incomingTs = incoming['ftm:updatedAt']?.['@value'] ?? '';

  if (incomingTs > existingTs) return incoming;
  if (existingTs > incomingTs) return existing;

  // Full tie — incoming wins (idempotent re-save is safe).
  return incoming;
}

/**
 * Creates a canonical in-memory StateAdapter per SPEC §5 and §5.1.
 * State is process-local; not persisted across restarts.
 *
 * @returns {StateAdapter}
 */
export function createInMemoryStateAdapter() {
  /** @type {Map<string, Object>} */
  const taskDefinitions = new Map();
  /** @type {Map<string, Object>} */
  const taskInstances = new Map();
  /** @type {Map<string, Object>} */
  const users = new Map();

  return {
    // â”€â”€ Task Definitions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    /**
     * Saves a TaskDefinition, applying LWW conflict resolution when an entity
     * with the same @id already exists (SPEC §5.1).
     *
     * @param {Object} td
     * @returns {Promise<void>}
     */
    async saveTaskDefinition(td) {
      const existing = taskDefinitions.get(td['@id']);
      taskDefinitions.set(td['@id'], resolveConflict(existing, td));
    },

    /**
     * Returns the TaskDefinition with the given @id, or null if not found.
     *
     * @param {string} id
     * @returns {Promise<Object|null>}
     */
    async getTaskDefinition(id) {
      return taskDefinitions.get(id) ?? null;
    },

    /**
     * Returns all TaskDefinitions, optionally filtered by status.
     *
     * @param {{ status?: string }} [filter]
     * @returns {Promise<Object[]>}
     */
    async listTaskDefinitions(filter) {
      const all = Array.from(taskDefinitions.values());
      if (filter?.status !== undefined) {
        return all.filter(td => td['ftm:status'] === filter.status);
      }
      return all;
    },

    // â”€â”€ Task Instances â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    /**
     * Saves a TaskInstance, applying LWW conflict resolution when an entity
     * with the same @id already exists (SPEC §5.1).
     *
     * @param {Object} ti
     * @returns {Promise<void>}
     */
    async saveTaskInstance(ti) {
      const existing = taskInstances.get(ti['@id']);
      taskInstances.set(ti['@id'], resolveConflict(existing, ti));
    },

    /**
     * Returns the TaskInstance with the given @id, or null if not found.
     *
     * @param {string} id
     * @returns {Promise<Object|null>}
     */
    async getTaskInstance(id) {
      return taskInstances.get(id) ?? null;
    },

    /**
     * Returns all TaskInstances, optionally filtered by any combination of
     * assignedTo, status, taskDefinitionId, fromDate, toDate.
     * All supplied filter fields are ANDed together.
     *
     * @param {InstanceFilter} [filter]
     * @returns {Promise<Object[]>}
     */
    async listTaskInstances(filter) {
      let results = Array.from(taskInstances.values());
      if (!filter) return results;

      if (filter.assignedTo !== undefined) {
        results = results.filter(ti => ti['ftm:assignedTo'] === filter.assignedTo);
      }
      if (filter.status !== undefined) {
        results = results.filter(
          ti => ti['ftm:completionState']?.['ftm:status'] === filter.status,
        );
      }
      if (filter.taskDefinitionId !== undefined) {
        results = results.filter(
          ti => ti['ftm:taskDefinition'] === filter.taskDefinitionId,
        );
      }
      if (filter.fromDate !== undefined) {
        results = results.filter(
          ti => (ti['ftm:dueAt']?.['@value'] ?? '') >= filter.fromDate,
        );
      }
      if (filter.toDate !== undefined) {
        results = results.filter(
          ti => (ti['ftm:dueAt']?.['@value'] ?? '') <= filter.toDate,
        );
      }
      return results;
    },

    // â”€â”€ Users â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    /**
     * Saves a User, applying LWW conflict resolution when an entity with the
     * same @id already exists.
     *
     * Note: SPEC §5.1 scopes conflict resolution to saveTaskDefinition and
     * saveTaskInstance only. LWW is applied here for interface symmetry and
     * defensive consistency (operator decision I7). User entities carry no
     * ftm:clientSequence or ftm:updatedAt fields; the resolveConflict full-tie
     * fallback applies, so incoming always wins on a conflict.
     *
     * @param {Object} u
     * @returns {Promise<void>}
     */
    async saveUser(u) {
      const existing = users.get(u['@id']);
      users.set(u['@id'], resolveConflict(existing, u));
    },

    /**
     * Returns the User with the given @id, or null if not found.
     *
     * @param {string} id
     * @returns {Promise<Object|null>}
     */
    async getUser(id) {
      return users.get(id) ?? null;
    },

    /**
     * Returns all Users.
     *
     * @returns {Promise<Object[]>}
     */
    async listUsers() {
      return Array.from(users.values());
    },
  };
}
