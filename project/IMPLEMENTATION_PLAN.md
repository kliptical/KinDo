# Family Task Manager — Implementation Plan

**SPEC:** `project/family-task-manager-spec.md` v0.2.0  
**ROADMAP:** `project/ROADMAP.md`  
**Generated from:** FNSR kickoff ritual, implementation-plan mode

> Each sub-task carries a **priority** (P0 = must-have for phase exit; P1 = should-have; P2 = nice-to-have deferred).  
> Each acceptance criterion is falsifiable: a reader can inspect code or test output and answer "pass" or "fail" without judgment.  
> Exit gates state the observable condition that signals a phase is done and the next may begin.  
> SPEC clause references appear in parentheses (e.g., §4.1, §11).

---

## Phase 1: Domain Model and Validation

**Goal:** Establish the canonical JSON-LD entity schemas, sync metadata, and entity-level validation invariants.

**Dependencies:** None — first phase. Operator must resolve the three deferred decisions below before work begins.

**Deferred decisions blocking Phase 1:**
- Implementation language and module format (JavaScript vs TypeScript; ESM vs CJS). SPEC mandates `browser / node index.js` compatibility but does not prescribe a build system or type system.
- Validation library choice (hand-rolled checks vs JSON Schema vs Zod vs AJV). Must be edge-canonical.
- `assignedTo` role-check scope (ROADMAP I10): §11 requires `assignedTo` to resolve to a `User` with `role = "child"`, but that lookup requires `StateAdapter.getUser()` — a Phase 3 artifact. Operator must choose: (a) Phase 1 implements against a fixture/stub user registry; (b) check is deferred to Phase 4 application flow; or (c) check is deferred explicitly to Phase 4 with a comment in the validator.

---

### 1.1 JSON-LD Context Module [P0]

**SPEC:** §3.1

Define and export the canonical `ftm:` context object.

**Acceptance criteria:**
- Importing the context module and reading `context["ftm"]` returns exactly `"https://schema.familytaskmanager.local/v1/"`.
- `context["xsd"]` returns exactly `"http://www.w3.org/2001/XMLSchema#"`.
- `context["schema"]` returns exactly `"https://schema.org/"`.
- The module has no side effects and no I/O on import.

---

### 1.2 TaskDefinition Entity Factory [P0]

**SPEC:** §3.2

Factory function that constructs a valid `TaskDefinition` JSON-LD object.

**Acceptance criteria:**
- Factory output includes `@context`, `@type: "ftm:TaskDefinition"`, `@id` matching the pattern `urn:ftm:task:<uuid>`.
- Output includes all identity fields: `ftm:title`, `ftm:description`, `ftm:assignedTo`, `ftm:createdBy`, `ftm:createdAt` (xsd:dateTime shape), `ftm:version: 1`.
- Output includes sync metadata: `ftm:updatedAt` (xsd:dateTime shape), `ftm:clientSequence: 1`.
- Output for a one-time task includes `ftm:schedule` with `ftm:scheduleType: "one-time"`, `ftm:dueAt` (xsd:dateTime shape), `ftm:recurrenceRule: null`, `ftm:recurrenceStart: null`.
- Output for a recurring task includes `ftm:schedule` with `ftm:scheduleType: "recurring"`, a non-null `ftm:recurrenceRule` string, and a non-null `ftm:recurrenceStart` ISO-8601 string.
- Output includes `ftm:reminderPolicy` with `ftm:mode`, `ftm:intervalSeconds: null`, `ftm:persistUntilSeconds: null` for `once` mode.
- Output includes `ftm:status: "active"`.
- The factory does not call any I/O or external API.

---

### 1.3 TaskInstance Entity Factory [P0]

**SPEC:** §3.3

Factory function that constructs a valid `TaskInstance` JSON-LD object.

**Acceptance criteria:**
- Output includes `@context`, `@type: "ftm:TaskInstance"`, `@id` matching `urn:ftm:instance:<uuid>`.
- Output includes `ftm:taskDefinition` (reference IRI), `ftm:assignedTo`, `ftm:dueAt` (xsd:dateTime), `ftm:createdAt` (xsd:dateTime).
- Output includes sync metadata: `ftm:updatedAt`, `ftm:clientSequence: 1`.
- Output includes `ftm:completionState` with `ftm:status: "pending"`, `ftm:completedAt: null`, `ftm:completedBy: null`, `ftm:completedByRole: null`.
- Output includes `ftm:reminderSummary` with `ftm:totalSent: 0`, `ftm:lastSentAt: null`, `ftm:lastDeliveryStatus: null`, `ftm:recentEvents: []`.
- The factory does not call any I/O or external API.

---

### 1.4 ReminderEvent Schema [P1]

**SPEC:** §3.4

Define the `ReminderEvent` shape (used only in `ftm:recentEvents` ring buffer).

**Acceptance criteria:**
- A `ReminderEvent` object has `@type: "ftm:ReminderEvent"`, `ftm:sentAt` (xsd:dateTime shape), `ftm:deliveryStatus` whose value is one of `"delivered"`, `"failed"`, or `"deferred"`.
- A `ReminderEvent` with any other `ftm:deliveryStatus` value is rejected by its constructor/factory.

---

### 1.5 User Entity Factory [P0]

**SPEC:** §3.5

Factory function that constructs a valid `User` JSON-LD object.

**Acceptance criteria:**
- Output includes `@context`, `@type: "ftm:User"`, `@id`.
- `ftm:role` is one of `"parent"` or `"child"`.
- `ftm:displayName` is a non-empty string.
- `ftm:notificationTokens` is an empty array by default.
- The factory does not call any I/O.

---

### 1.6 JSON-LD Round-Trip Utility [P1]

**SPEC:** §2, §3

Utility that verifies lossless serialization and the prefix-stripping view-layer convention.

**Acceptance criteria:**
- `JSON.parse(JSON.stringify(entity))` is deep-equal to the original for all entity types (`TaskDefinition`, `TaskInstance`, `User`, `ReminderEvent`).
- A helper that strips the `ftm:` prefix from keys (e.g., maps `ftm:title` → `title`) and a corresponding re-expansion helper produce an object that is deep-equal to the original canonical form — no fields are lost or added.
- The stripping utility is clearly identified as a view-layer convenience; the canonical factories always produce the `ftm:` form.

---

### 1.7 TaskDefinition Validation Rules [P0]

**SPEC:** §11

Validation function enforcing all §11 `TaskDefinition` invariants.

**Acceptance criteria:**
- Calling the validator with `ftm:title = ""` returns a result with at least one error.
- Calling with `ftm:title` of length 201 returns a result with at least one error.
- Calling with `ftm:title` of length 200 returns no title-length error.
- Calling with `ftm:scheduleType = "recurring"` and `ftm:recurrenceRule: null` returns an error.
- Calling with `ftm:scheduleType = "recurring"` and `ftm:recurrenceStart: null` returns an error.
- Calling with `ftm:scheduleType = "recurring"` and `ftm:recurrenceStart: "not-a-date"` returns an error.
- Calling with `ftm:mode = "persistent"` and `ftm:intervalSeconds: 59` returns an error.
- Calling with `ftm:mode = "persistent"` and `ftm:intervalSeconds: 60` returns no intervalSeconds error.
- Calling with `ftm:persistUntilSeconds: 100` and `ftm:intervalSeconds: 200` returns an error.
- Calling with `ftm:persistUntilSeconds: 200` and `ftm:intervalSeconds: 200` returns no persistUntilSeconds error.
- A fully valid one-time `TaskDefinition` object passes the validator with zero errors.
- **Note on `assignedTo` role check:** Behavior of this check is blocked on the operator's I10 scope decision. When deferred, the validator must have a comment explicitly marking this rule as deferred and citing the decision requirement.

---

### 1.8 TaskInstance Validation Rules [P0]

**SPEC:** §11

Validation function enforcing all §11 `TaskInstance` invariants.

**Acceptance criteria:**
- Calling with `ftm:dueAt: "not-a-datetime"` returns an error.
- Calling with `ftm:clientSequence: 0` returns an error.
- Calling with `ftm:clientSequence: -1` returns an error.
- Calling with `ftm:clientSequence: 1.5` returns an error.
- Calling with `ftm:dueAt: "2026-05-22T18:00:00Z"` and `ftm:clientSequence: 1` returns no errors.

---

### Phase 1 Exit Gate

All of the following must be true before Phase 2 begins:

1. Running the test suite produces 0 failures across all Phase 1 tests.
2. Each entity factory is importable in Node.js and can be invoked without any network call, file system access, or I/O.
3. Each of the §11 validation rules has at least one passing test (valid input) and at least one failing test (invalid input that triggers the rule).
4. No adapter code (`StateAdapter`, `OrchestrationAdapter`, `NotificationAdapter`) is imported or referenced by any Phase 1 module.
5. The three operator decisions above are documented (even if deferred) before Phase 2 begins.

---

## Phase 2: Core Computation Modules

**Goal:** Implement all five pure-function computation modules and pass all ten items of the §13 Spec Test Checklist in a Node.js environment with no network access.

**Dependencies:** Phase 1 complete. Additionally:
- RRULE parsing library approved by operator (must be edge-canonical — runs in browser and Node without a server).
- Operator resolution of ROADMAP I3 (`invalid-rrule` error-attachment target) before that branch is implemented.
- Operator resolution of ROADMAP I9 (`catchUpWindowSeconds` undefined in §4.5 rule 1a) before full `"all"` catch-up policy is implemented.
- Operator resolution of ROADMAP I4 (CompletionProcessor §11 user-store checks scope) before CompletionProcessor validation is finalized.

---

### 2.1 ScheduleComputer [P0]

**SPEC:** §4.1

Pure function: `ScheduleComputer(taskDef, referenceTime, options?) → TaskInstance[]`

**Acceptance criteria:**
- Given a one-time `TaskDefinition` with `dueAt` strictly after `referenceTime`, returns an array of exactly 1 `TaskInstance`.
- Given a one-time `TaskDefinition` with `dueAt` equal to `referenceTime`, returns `[]`.
- Given a one-time `TaskDefinition` with `dueAt` before `referenceTime`, returns `[]`.
- Given a recurring `TaskDefinition` with `FREQ=DAILY` anchored at `recurrenceStart`, called with `lookAheadSeconds: 604800`, returns exactly 7 instances (one per day in the 7-day window).
- Given a recurring `TaskDefinition`, all returned instances have `dueAt` strictly greater than `referenceTime` and less than or equal to `referenceTime + lookAheadSeconds`.
- When `options` is omitted, `lookAheadSeconds` defaults to 604800.
- Given an unparseable `recurrenceRule`, returns `[]` with the `ftm:error: "invalid-rrule"` attachment in the canonical location determined by the operator's I3 resolution.
- All returned instances have `ftm:completionState.status: "pending"`, `ftm:reminderSummary.totalSent: 0`, `ftm:reminderSummary.recentEvents: []`.
- The function has no I/O and no side effects; calling it twice with the same arguments produces identical output.

---

### 2.2 ReminderEvaluator [P0]

**SPEC:** §4.2

Pure function: `ReminderEvaluator(instance, taskDef, currentTime) → { shouldRemind: boolean, reason: string }`

**Acceptance criteria:**
- Input with `completionState.status: "completed"` → `{ shouldRemind: false, reason: "already-complete" }`.
- Input with `dueAt` strictly after `currentTime` → `{ shouldRemind: false, reason: "not-yet-due" }`.
- `once` mode, `totalSent: 0`, `dueAt <= currentTime` → `{ shouldRemind: true, reason: "first-and-only" }`.
- `once` mode, `totalSent: 1` → `{ shouldRemind: false, reason: "once-sent" }`.
- `persistent` mode, `currentTime > dueAt + persistUntilSeconds` → `{ shouldRemind: false, reason: "persistence-window-expired" }`.
- `persistent` mode, `persistUntilSeconds` absent from policy, `currentTime = dueAt + 86401` → `{ shouldRemind: false, reason: "persistence-window-expired" }` (confirms 86400 s default).
- `persistent` mode, `persistUntilSeconds` absent, `currentTime = dueAt + 86399` → NOT `persistence-window-expired` (confirms default applies correctly).
- `persistent` mode, `lastDeliveryStatus: "failed"` → `{ shouldRemind: true, reason: "retry-after-failure" }` regardless of `lastSentAt`.
- `persistent` mode, `totalSent: 0` → `{ shouldRemind: true, reason: "initial-reminder" }`.
- `persistent` mode, `currentTime - lastSentAt >= intervalSeconds`, window not expired → `{ shouldRemind: true, reason: "interval-elapsed" }`.
- `persistent` mode, `currentTime - lastSentAt < intervalSeconds`, window not expired → `{ shouldRemind: false, reason: "interval-not-elapsed" }`.
- The function has no I/O and no side effects.

---

### 2.3 CompletionProcessor [P0]

**SPEC:** §4.3, §11

Pure function: `CompletionProcessor(instance, completedBy, completedByRole, completedAt) → TaskInstance`

**Acceptance criteria:**
- Returns a new object (strict reference inequality to the input instance).
- Output `ftm:completionState.status: "completed"`.
- Output `ftm:completionState.completedAt` equals the `completedAt` argument.
- Output `ftm:completionState.completedBy` equals the `completedBy` argument.
- Output `ftm:completionState.completedByRole` equals the `completedByRole` argument.
- Output `ftm:clientSequence` equals input `ftm:clientSequence + 1`.
- Output `ftm:updatedAt` equals `completedAt`.
- Input with `completionState.status: "completed"` returns the instance unchanged and the output includes `ftm:warning: "already-complete"`.
- `completedByRole: "parent"` is stored correctly; completion semantics are unchanged (§4.3 parent override).
- **§11 validation (if scoped to this phase per operator I4 resolution):**
  - `completedByRole: "child"` with `completedBy` not matching `instance.ftm:assignedTo` → validator rejects before processor runs.
  - `completedByRole: "parent"` with `completedBy` resolving to a user with `role: "child"` → validator rejects.
  - `completedByRole: "child"` with `completedBy` matching `instance.ftm:assignedTo` → accepted.

---

### 2.4 TaskListComputer [P1]

**SPEC:** §4.4

Pure function: `TaskListComputer(instances, filter) → TaskInstance[]`

**Acceptance criteria:**
- Filtering by `assignedTo: "urn:ftm:child:abc"` returns only instances where `ftm:assignedTo = "urn:ftm:child:abc"`; instances for other children are excluded.
- Filtering by `status: "pending"` excludes all instances with `completionState.status: "completed"`.
- Filtering by `status: "completed"` excludes all pending instances.
- Filtering by `fromDate: "2026-05-20T00:00:00Z"` excludes instances with `dueAt` before that timestamp.
- Filtering by `toDate: "2026-05-22T23:59:59Z"` excludes instances with `dueAt` after that timestamp.
- An empty filter object returns all instances.
- Default sort: result array is ordered by `ftm:dueAt` ascending.
- Two instances with equal `dueAt` where one is pending and one is completed: the pending instance appears first.
- The function has no I/O and does not mutate the input array.

---

### 2.5 RecurrenceMaterializer [P0]

**SPEC:** §4.5

Pure function: `RecurrenceMaterializer(taskDefs, existingInstances, currentTime, options?) → { toCreate: TaskInstance[], skipped: number }`

**Acceptance criteria:**
- Given one recurring `TaskDefinition` and an empty `existingInstances`, returns `{ toCreate: [...], skipped: 0 }` with instances covering the look-ahead window.
- Deduplication: if `existingInstances` already contains an instance whose `ftm:taskDefinition` and `ftm:dueAt` match a candidate, that candidate is absent from `toCreate`.
- `catchUpPolicy: "current-only"` (default): instances with `dueAt < currentTime` that are not already in `existingInstances` are excluded from `toCreate` and each increments `skipped` by 1.
- `catchUpPolicy: "current-only"`, 3 missed occurrences: `skipped = 3`, and `toCreate` contains only present and future occurrences.
- `catchUpPolicy: "all"`: missed past instances are included in `toCreate`; `skipped = 0` (blocked pending I9 resolution; implement to the extent possible with a documented placeholder for `catchUpWindowSeconds`).
- When all occurrences in the window are already in `existingInstances`: returns `{ toCreate: [], skipped: 0 }`.
- The function has no I/O and does not mutate any input.
- **Risk (I9):** `catchUpWindowSeconds` / `catchUpWindow` in §4.5 rule 1a are undefined in the SPEC. The `"all"` policy implementation must document a placeholder value (e.g., 604800 s = 7 days) and include a `// FIXME: catchUpWindowSeconds not defined in SPEC §4.5 — awaiting operator resolution` comment.

---

### 2.6 §13 Spec Test Checklist Coverage [P0]

**SPEC:** §13

All ten items of the §13 Spec Test Checklist must be covered by automated tests executable via `node` (or equivalent test runner) with no network call.

**Acceptance criteria (one AC per checklist item):**

1. **§13 item 1:** A test instantiates a `TaskDefinition` JSON-LD object and passes it to `ScheduleComputer`; the test passes without any network call.
2. **§13 item 2:** A test calls `ScheduleComputer` with a recurring `TaskDefinition` and a reference time 4 days in the past; the result is a deterministic array of `TaskInstance` objects covering the catch-up window; calling the function a second time with identical arguments produces an identical array.
3. **§13 item 3:** A test calls `RecurrenceMaterializer` with a fixture set of `TaskDefinition` and `TaskInstance` objects and asserts a deterministic `{ toCreate, skipped }` result; two runs with identical inputs produce identical results.
4. **§13 item 4:** A test calls `ReminderEvaluator` with a fixture `TaskInstance` where `lastDeliveryStatus: "failed"` and asserts `shouldRemind: true` and `reason: "retry-after-failure"`.
5. **§13 item 5:** A test completes a task as a parent (`completedByRole: "parent"`) via `CompletionProcessor` and asserts the output passes all §11 validation rules.
6. **§13 item 6:** A test attempts to complete a task as a child with a `completedBy` value that does not match `assignedTo` and asserts the validator rejects it.
7. **§13 item 7:** A test renders the parent dashboard using only `TaskListComputer` output (no `StateAdapter` call in the test); the test passes with no server.
8. **§13 item 8:** A test saves two conflicting `TaskInstance` objects to the in-memory `StateAdapter` (same `@id`, higher `clientSequence` second) and asserts `getTaskInstance` returns the higher-sequence version.
9. **§13 item 9:** A test swaps `NotificationAdapter` for a no-op stub; all other modules (`ScheduleComputer`, `ReminderEvaluator`, `CompletionProcessor`, `TaskListComputer`, `RecurrenceMaterializer`) run to completion without error.
10. **§13 item 10:** A test runs the entire §8.5 app boot / resume flow using the Test OrchestrationAdapter (manual `tick()`) with no real timers and no network; test asserts that missed reminders are dispatched after `tick()` advances past their `dueAt`.

---

### Phase 2 Exit Gate

All of the following must be true before Phase 3 begins:

1. Running the full test suite produces 0 failures across all Phase 2 module tests.
2. All 10 §13 checklist items have a passing automated test executable via `node` without network access.
3. Each of the five computation modules can be imported and invoked in Node.js without any I/O (pure function contract per §4).
4. `RecurrenceMaterializer` with `catchUpPolicy: "current-only"` is tested and green. Any `"all"` policy stub that is blocked by I9 is annotated with a `// FIXME` comment and has a skipped/pending test marker.
5. No `StateAdapter`, `OrchestrationAdapter`, or `NotificationAdapter` code is imported inside any of the five computation modules.

---

## Phase 3: Adapter Implementations

**Goal:** Deliver the canonical in-memory state adapter, Tier 0 orchestration adapter (including Test adapter), and Tier 0 notification adapter; implement the resume reconciliation hook.

**Dependencies:** Phases 1 and 2 complete. Additionally:
- Operator resolution of ROADMAP I7 (`TaskDefinition` immutability invariant and `ftm:version` mechanic) before `saveTaskDefinition` conflict-resolution behavior is finalized.
- Operator decision on whether the LocalStorage adapter ships in Phase 3 or is deferred entirely.

---

### 3.1 StateAdapter Interface [P0]

**SPEC:** §5

Define the `StateAdapter` interface and `InstanceFilter` type.

**Acceptance criteria:**
- Interface declares all nine methods: `saveTaskDefinition`, `getTaskDefinition`, `listTaskDefinitions`, `saveTaskInstance`, `getTaskInstance`, `listTaskInstances`, `saveUser`, `getUser`, `listUsers`.
- Each `save*` method returns `Promise<void>`.
- Each `get*` method returns `Promise<EntityType | null>`.
- Each `list*` method returns `Promise<EntityType[]>`.
- `InstanceFilter` type declares all optional fields: `assignedTo?`, `status?`, `taskDefinitionId?`, `fromDate?`, `toDate?`.

---

### 3.2 In-Memory StateAdapter (canonical) [P0]

**SPEC:** §5, §5.1

Reference implementation using `Map<string, object>` keyed by `@id`.

**Acceptance criteria:**
- `saveTaskDefinition(td)` stores `td` keyed by `td["@id"]`.
- `getTaskDefinition(id)` returns the stored entity or `null` when absent.
- `listTaskDefinitions({ status: "active" })` returns only entities where `ftm:status = "active"`; archived tasks are excluded.
- **Conflict — higher clientSequence wins:** saving an entity with the same `@id` and `ftm:clientSequence` strictly greater than the stored value replaces the stored entity. Calling `getTaskDefinition` afterward returns the new entity.
- **Conflict — lower clientSequence loses:** saving an entity with `ftm:clientSequence` strictly less than the stored value leaves the stored entity unchanged.
- **Conflict — equal clientSequence, later updatedAt wins:** saving an entity with equal `clientSequence` but later `ftm:updatedAt` replaces the stored entity.
- **Conflict — equal clientSequence, equal updatedAt:** incoming entity wins (idempotent re-save). Calling `getTaskDefinition` afterward returns the incoming entity.
- `saveTaskInstance`, `getTaskInstance`, `listTaskInstances`, `saveUser`, `getUser`, `listUsers` behave analogously.
- `listTaskInstances` with `InstanceFilter.taskDefinitionId` returns only instances whose `ftm:taskDefinition` matches.
- State is not persisted across process restarts (in-memory contract).
- **Risk (I7):** If the operator decides `TaskDefinition` is immutable (same-`@id` overwrites refused), the save behavior above must be replaced with a version-append mechanic. The in-memory adapter MUST NOT finalize this behavior until I7 is resolved.

---

### 3.3 LocalStorage StateAdapter (optional) [P1]

**SPEC:** §5, §5.1

*Conditional on operator scope decision. If deferred, this sub-task is removed from Phase 3 scope.*

**Acceptance criteria:**
- Implements identical `StateAdapter` interface and §5.1 conflict-resolution policy as the in-memory adapter.
- Entities are serialized as JSON strings to `localStorage` keyed by `@id`.
- `JSON.parse(localStorage.getItem(id))` after `saveTaskDefinition(td)` returns a deep-equal object to `td`.
- When `localStorage` is unavailable (e.g., private browsing, quota exceeded), the adapter silently falls back to in-memory storage; no exception is thrown to the caller.

---

### 3.4 OrchestrationAdapter Interface [P0]

**SPEC:** §6

Define the `OrchestrationAdapter` interface.

**Acceptance criteria:**
- Interface declares: `scheduleAt(isoTimestamp: string, callback: () => void): string`, `scheduleInterval(intervalMs: number, callback: () => void): string`, `cancel(handle: string): void`, `onResume(currentTime: string): void`.
- Return type of `scheduleAt` and `scheduleInterval` is a string handle (opaque).

---

### 3.5 Tier 0 OrchestrationAdapter [P0]

**SPEC:** §6, §6.1

`setTimeout`/`setInterval`-backed adapter for foreground use.

**Acceptance criteria:**
- `scheduleAt("2026-05-22T18:00:00Z", cb)` calls `setTimeout` with a delay equal to the delta between now and the target timestamp and returns a string handle.
- `scheduleInterval(1000, cb)` calls `setInterval` with 1000 ms and returns a string handle.
- `cancel(handle)` calls `clearTimeout` or `clearInterval` for the registered handle; the callback does not fire after cancellation.
- The adapter's documentation comment (or JSDoc) states that background throttling is a known limitation per §6.1 Tier 0.
- `onResume(now)` is callable without error and triggers any registered resume handlers.

---

### 3.6 Test OrchestrationAdapter [P0]

**SPEC:** §6, §13 item 10

Manual `tick(isoTimestamp)` adapter for deterministic testing without real timers.

**Acceptance criteria:**
- `tick(isoTimestamp)` fires all callbacks registered via `scheduleAt` whose target timestamp is less than or equal to `isoTimestamp`, in ascending timestamp order.
- Each such callback fires exactly once per `tick` call (not repeatedly).
- Callbacks registered via `scheduleInterval` fire once per elapsed interval when `tick` advances by that interval (e.g., advancing by 3 Ã— interval fires the callback 3 times).
- After `cancel(handle)` is called, the associated callback does not fire on any subsequent `tick`.
- The adapter has no real timers (`setTimeout` / `setInterval` are never called).

---

### 3.7 NotificationAdapter Interface [P0]

**SPEC:** §7

Define the `NotificationAdapter` interface, `NotificationPayload`, and `NotificationReceipt` types.

**Acceptance criteria:**
- Interface declares `send(payload: NotificationPayload): Promise<NotificationReceipt>`.
- `NotificationPayload` has fields: `recipientUserId: string`, `title: string`, `body: string`, `deepLinkUri: string`, `requestForegroundDisplay: boolean`.
- `NotificationReceipt` has fields: `status: "delivered" | "failed" | "deferred"`, `adapterTier: 0 | 1 | 2 | 3`, optional `externalId?: string`.

---

### 3.8 Tier 0 NotificationAdapter (canonical) [P0]

**SPEC:** §7, §7.1, §7.2

In-process adapter using `CustomEvent` (browser) or `EventEmitter` (Node).

**Acceptance criteria:**
- In a browser environment: `send(payload)` dispatches `CustomEvent("ftm:alert", { detail: payload })` on `window`.
- In a Node.js environment: `send(payload)` emits `"ftm:alert"` with the payload on an exported `EventEmitter` instance.
- `send()` never throws; on any internal error it returns `Promise.resolve({ status: "failed", adapterTier: 0 })`.
- Receipt always includes `adapterTier: 0`.
- When `requestForegroundDisplay: true`, Tier 0 dispatches the event as specified (no additional behavior required at Tier 0 beyond the event dispatch per §7.2).

---

### 3.9 No-Op Stub NotificationAdapter [P1]

**SPEC:** §13 item 9

Minimal stub for testing; returns success without dispatching any event.

**Acceptance criteria:**
- `send(payload)` immediately resolves with `{ status: "delivered", adapterTier: 0 }` without dispatching any `CustomEvent` or `EventEmitter` event.
- All Phase 2 and Phase 3 tests that do not explicitly verify notification delivery use this stub by default.

---

### 3.10 Resume Reconciliation Logic [P0]

**SPEC:** §6.1, §8.5

Implement the `onResume` body: catch-up materialization + missed-reminder re-dispatch.

**Acceptance criteria:**
- `onResume(now)` loads all active recurring `TaskDefinition`s from `StateAdapter`.
- `onResume` loads all existing `TaskInstance`s from `StateAdapter`.
- `RecurrenceMaterializer` is called with the loaded definitions, instances, and `now`.
- Each instance in `toCreate` is saved via `StateAdapter.saveTaskInstance`.
- Each instance in `toCreate` is scheduled via `OrchestrationAdapter.scheduleAt(instance.dueAt, ...)`.
- All pending instances where `dueAt <= now` are passed through `ReminderEvaluator`.
- For each instance where `shouldRemind: true`, a notification is dispatched via `NotificationAdapter.send`.
- When using the Test OrchestrationAdapter and no-op NotificationAdapter, a test calling `onResume(t+5)` with 3 pending overdue instances asserts that `NotificationAdapter.send` was called 3 times.

---

### Phase 3 Exit Gate

All of the following must be true before Phase 4 begins:

1. A test instantiates the in-memory `StateAdapter`, saves 3 `TaskInstance` objects (including one conflict case for each of the four §5.1 conflict branches), and all four conflict-resolution assertions pass.
2. A test uses the Test `OrchestrationAdapter`, registers 3 `scheduleAt` callbacks at different timestamps, calls `tick(latest_timestamp)`, and asserts all 3 callbacks fired in ascending timestamp order.
3. `NotificationAdapter.send()` called with any payload never throws; receipt always has `adapterTier: 0`.
4. §13 checklist item 9 passes: replacing `NotificationAdapter` with the no-op stub causes no test failures in Phase 1 or Phase 2 suites.
5. Operator I7 resolution is documented (even if deferred to Phase 4) before Phase 4 `saveTaskDefinition` usage is finalized.

---

## Phase 4: Application Flow Wiring and Entry Point

**Goal:** Compose all modules and adapters into a runnable edge-canonical application that correctly executes all six §8 application flows; provide `node index.js` and browser entry points.

**Dependencies:** Phases 1, 2, and 3 complete. Additionally:
- Operator decision on `node index.js` CLI semantics (CLI flags / interactive prompts vs programmatic-only API).
- Operator decision on browser entry point delivery format (single HTML file, bundled JS module, unbundled ESM).
- Operator resolution of I9 (catchUpWindowSeconds) for full §8.5 historical backfill end-to-end.

---

### 4.1 §8.1 Parent Creates a Task Flow [P0]

**SPEC:** §8.1

**Acceptance criteria:**
- Calling the flow with a valid one-time `TaskDefinition` results in the definition stored in `StateAdapter` (`getTaskDefinition(def["@id"])` returns the definition).
- `ScheduleComputer` is called with the definition and current time; each returned instance is stored via `saveTaskInstance`.
- An orchestration callback is registered for each instance's `dueAt` via `OrchestrationAdapter.scheduleAt`.
- A one-time task produces exactly 1 stored instance.
- A recurring task with 3 occurrences in the look-ahead window produces exactly 3 stored instances and 3 registered callbacks.
- The `TaskDefinition` includes `ftm:updatedAt` and `ftm:clientSequence: 1` at construction time.

---

### 4.2 §8.2 Reminder Trigger Flow [P0]

**SPEC:** §8.2

**Acceptance criteria:**
- Flow loads the `TaskInstance` and associated `TaskDefinition` from `StateAdapter` by ID.
- `ReminderEvaluator` is called with the loaded instance and definition.
- When `shouldRemind: true`: `NotificationAdapter.send` is called with `requestForegroundDisplay: true`.
- After a successful send: `reminderSummary.totalSent` equals the previous value + 1.
- After a send: `reminderSummary.lastSentAt` equals the current time used by the flow.
- After a send: `reminderSummary.lastDeliveryStatus` reflects `receipt.status`.
- After a send: a new `ReminderEvent` is prepended to `recentEvents`; if the array exceeds 3 elements it is truncated to the last 3.
- After a send: `ftm:clientSequence` equals previous value + 1.
- After a send: `ftm:updatedAt` equals the current time.
- The updated instance is saved via `StateAdapter.saveTaskInstance`.
- When `mode: "persistent"` and the persistence window is not expired: a new callback is scheduled for `now + intervalSeconds`.
- When `shouldRemind: false`: `NotificationAdapter.send` is never called; state is not mutated.

---

### 4.3 §8.3 Child Marks Task Complete Flow [P0]

**SPEC:** §8.3

**Acceptance criteria:**
- Flow calls `CompletionProcessor(instance, childId, "child", now)` and saves the result.
- After the flow, `StateAdapter.getTaskInstance(instanceId)` returns an instance with `completionState.status: "completed"` and `completedByRole: "child"`.
- `OrchestrationAdapter.cancel` is called for all reminder handles associated with the instance.
- `CustomEvent("ftm:taskCompleted", { detail: updatedInstance })` is emitted on `window` (browser) or the `EventEmitter` (Node).

---

### 4.4 §8.4 Parent Views Task Dashboard Flow [P1]

**SPEC:** §8.4

**Acceptance criteria:**
- Flow returns two lists: a pending list and a completed list.
- Both lists are derived from `TaskListComputer` output; no direct `StateAdapter` calls occur after the initial `listTaskInstances`.
- Pending list contains only instances with `completionState.status: "pending"`, sorted by `dueAt` ascending.
- Completed list contains only instances with `completionState.status: "completed"`.

---

### 4.5 §8.5 App Boot / Foreground Resume Flow [P0]

**SPEC:** §8.5

**Acceptance criteria:**
- `OrchestrationAdapter.onResume(now)` is called at flow entry.
- All active recurring `TaskDefinition`s (status = "active") are loaded.
- All existing `TaskInstance`s are loaded.
- `RecurrenceMaterializer` is called with the loaded data and current time.
- Each instance in `toCreate` is saved and scheduled.
- All pending instances where `dueAt <= now` are evaluated via `ReminderEvaluator`.
- Instances where `shouldRemind: true` trigger notification dispatch.
- When `skipped > 0`, the flow exposes the `skipped` count in its return value (for optional parent UI notice per §8.5 step 6).
- A test using the Test OrchestrationAdapter and no-op NotificationAdapter: create 2 recurring task definitions, call the boot flow, assert that instances are created and callbacks registered.

---

### 4.6 §8.6 Parent Completes Task on Child's Behalf Flow [P0]

**SPEC:** §8.6

**Acceptance criteria:**
- Flow calls `CompletionProcessor(instance, parentId, "parent", now)`.
- After the flow, the saved instance has `completedByRole: "parent"`.
- Reminder handles for the instance are cancelled.
- `CustomEvent("ftm:taskCompleted")` is emitted.

---

### 4.7 `node index.js` Entry Point [P0]

**SPEC:** §2 (Edge-Canonical First), §8

**Acceptance criteria:**
- `node index.js` runs to completion with exit code 0.
- The entry point demonstrates: creating a parent user, creating a child user, creating a task, calling the §8.5 boot flow, and triggering a reminder (via Test OrchestrationAdapter or real timeout in foreground).
- No Node-specific APIs (`fs`, `path`, `child_process`, `process.env`) are imported inside any shared core module; only in the entry point or adapter boundary files.
- No network call is made during the run.

---

### 4.8 Browser Entry Point [P1]

**SPEC:** §2 (Edge-Canonical First)

**Acceptance criteria:**
- Loading the browser entry point (via file:// or localhost, no dev server) does not produce a JavaScript error in the browser console.
- The same shared modules used by `node index.js` are used unchanged by the browser entry point (no module duplication or forking).
- No `require()` call or Node.js built-in is present in any shared module.

---

### 4.9 Deep-Link Route Stub [P1]

**SPEC:** §9

**Acceptance criteria:**
- A function `resolveDeepLink("ftm://instance/INSTANCE_ID")` returns the `TaskInstance` loaded from `StateAdapter` for the given ID, or `null` if not found.
- Navigating to the deep-link for a non-existent instance returns `null` (no unhandled exception).
- A comment explicitly notes that UI rendering for this route is deferred to Phase 5.

---

### 4.10 §10 Offline Behavior Scenarios [P1]

**SPEC:** §10

**Acceptance criteria:**
- **Failed notification retry:** `NotificationAdapter.send` returning `{ status: "failed" }`, followed by a `ReminderEvaluator` call on the updated instance, returns `{ shouldRemind: true, reason: "retry-after-failure" }`.
- **Conflict resolution end-to-end:** Saving a `TaskInstance` with a higher `clientSequence` over an existing one; `getTaskInstance` afterward returns the higher-sequence version.
- **Invalid RRULE:** `ScheduleComputer` with an unparseable `recurrenceRule` returns `[]` with the `ftm:error` attachment in the canonical location (per I3 resolution).
- **Missed persistent window:** `ReminderEvaluator` with `persistUntilSeconds` absent and `currentTime = dueAt + 86401` returns `{ shouldRemind: false, reason: "persistence-window-expired" }`.
- **Multi-day offline catch-up:** `RecurrenceMaterializer` with `catchUpPolicy: "current-only"` and 3 missed past occurrences returns `skipped: 3`.
- **Background timers:** Full §8.5 boot/resume flow using Test OrchestrationAdapter fires all overdue reminders after `tick()` without any real timer.
- **Concurrent edit:** Saving two conflicting `TaskInstance`s with different `clientSequence` values; the higher-sequence version is the one retrievable afterward.

---

### Phase 4 Exit Gate

All of the following must be true before Phase 5 begins:

1. `node index.js` runs to completion with exit code 0, no network calls, no unhandled exceptions.
2. All six §8 application flows have integration tests using the Test OrchestrationAdapter and no-op NotificationAdapter; 0 test failures.
3. All §10 offline scenario tests pass.
4. All ten §13 checklist items pass (some may have been established in Phase 2; all must still be green after Phase 4 integration).
5. Browser entry point loads without console errors in at least one tested browser.

---

## Phase 5: UI Layer

**Goal:** Implement all parent and child UI views in compliance with the §9 data contract.

**Dependencies:** All prior phases complete. Additionally:
- UI framework choice confirmed by operator before Phase 5 begins.
- Authentication mechanism decided by operator (hardcoded identity, local login, or explicit deferral).
- Browser entry point from Phase 4 complete.

---

### 5.1 `ftm:alert` CustomEvent Listener + Alert Modal [P0]

**SPEC:** §7.2, §9, §9.2

**Acceptance criteria:**
- `window.addEventListener("ftm:alert", handler)` is registered on app start.
- When the Tier 0 `NotificationAdapter.send()` dispatches the `ftm:alert` event, the Alert Modal renders within the same event loop tick (no deferred rendering).
- The modal renders regardless of which view is currently active.
- The modal contains a visible link to the deep-link URI from the notification payload.
- The modal is not dismissed automatically; it remains visible until the user explicitly dismisses it.

---

### 5.2 Platform Limitation Disclosure [P0]

**SPEC:** §7.2

**Acceptance criteria:**
- On the first notification permission request, the UI displays exactly: *"Background reminders require notification permissions. Reliability when the app is closed depends on your device and browser."*
- After the disclosure has been shown once, subsequent permission requests (within the same session) do not re-display the disclosure.
- The disclosure text is stored as a constant; it is not hardcoded inline in a template string (makes future updates easier to audit).

---

### 5.3 Deep-Link Routing [P1]

**SPEC:** §9

**Acceptance criteria:**
- Navigating to `ftm://instance/{instanceId}` (or the hash-router equivalent, e.g., `#/instance/{instanceId}`) renders the TaskInstance detail view for the specified ID.
- If the instance ID does not exist in `StateAdapter`, the route renders a "task not found" message — no unhandled JavaScript error.
- The Alert Modal deep-link triggers this route when clicked.

---

### 5.4 Task Creator Form — Parent [P0]

**SPEC:** §9.1, §11

**Acceptance criteria:**
- Submitting the form with an empty title displays an inline validation error message; no `TaskDefinition` is created.
- Submitting with a title of 201 characters displays an inline validation error; no `TaskDefinition` is created.
- The form includes a schedule type toggle (`one-time` / `recurring`). Selecting `recurring` reveals `recurrenceRule` and `recurrenceStart` fields; selecting `one-time` hides them.
- The form includes a reminder mode toggle (`once` / `persistent`). Selecting `persistent` reveals `intervalSeconds` and `persistUntilSeconds` fields; selecting `once` hides them.
- The `persistUntilSeconds` field displays `86400` as its default value when the field is first revealed.
- A valid form submission constructs a `TaskDefinition` JSON-LD object (with `@context`, `@type`, `ftm:` prefix fields) before passing it to any computation module. Raw form string values are never passed directly to `ScheduleComputer` or `StateAdapter`.
- After a successful submission, the Task Dashboard view reflects the newly created task and instances (either via reactive state or explicit re-render).

---

### 5.5 Task Dashboard — Parent [P0]

**SPEC:** §9.1, §8.4, §8.6

**Acceptance criteria:**
- Dashboard shows all pending and completed instances for all children.
- A task completed by a parent displays a visually distinct badge (e.g., label "Parent Override") distinguishable from a child-completed task.
- A pending task has an action button for "Mark Complete (Override)"; clicking it executes the §8.6 parent-override flow.
- When `CustomEvent("ftm:taskCompleted")` is received on `window`, the dashboard updates to reflect the completion without requiring a full page reload.

---

### 5.6 Task Detail — Parent [P1]

**SPEC:** §9.1

**Acceptance criteria:**
- Detail view displays `reminderSummary.totalSent` as a human-readable count (e.g., "Reminders sent: 3").
- Detail view displays `reminderSummary.lastDeliveryStatus` ("delivered", "failed", or "deferred").
- Detail view displays up to 3 entries from `recentEvents`; if the ring buffer has fewer than 3 entries, all are shown.
- If `recentEvents` is empty, the view displays a "No reminders sent yet" message rather than an empty or errored state.

---

### 5.7 My Tasks — Child [P0]

**SPEC:** §9.2

**Acceptance criteria:**
- View shows only `TaskInstance` objects with `completionState.status: "pending"` assigned to the currently authenticated child.
- Instances are displayed in ascending `dueAt` order.
- If there are no pending instances, the view renders an explicit empty-state message rather than a blank screen.
- **Note on authentication:** If the operator defers authentication, a hardcoded or locally-configured `userId` is acceptable for this view, provided it is explicitly annotated as a placeholder.

---

### 5.8 Task Detail + Mark Complete — Child [P0]

**SPEC:** §9.2, §8.3

**Acceptance criteria:**
- The "Mark Complete" button calls `CompletionProcessor(instance, childId, "child", now)` and saves the result.
- After marking complete, the instance disappears from the "My Tasks" pending list.
- After marking complete, all reminder handles for the instance are cancelled via `OrchestrationAdapter.cancel`.
- Tapping "Mark Complete" on an already-completed instance does not produce an error; the UI reflects the completed state.

---

### Phase 5 Exit Gate

All of the following must be true to declare Phase 5 complete:

1. All ten §13 Spec Test Checklist items can be answered "yes" using only a browser, a local Node.js runtime, and JSON-LD files — no server required.
2. All parent views (Task Creator, Task Dashboard, Task Detail) render and function without JavaScript console errors in at least one tested browser.
3. All child views (My Tasks, Task Detail, Alert Modal) render and function without JavaScript console errors.
4. The platform limitation disclosure text is visible when first requesting notification permission and matches the exact string in §7.2.
5. The following complete end-to-end scenario runs successfully (manual test):
   - Parent creates a recurring daily task assigned to a child.
   - App boot materializes instances for the coming week.
   - Test OrchestrationAdapter (or real foreground timer) fires the first reminder.
   - Child receives and dismisses the Alert Modal.
   - Child navigates to Task Detail via the modal deep-link and taps "Mark Complete".
   - Parent Dashboard reflects the completed task with the correct `completedByRole` badge.

---

## Cross-Cutting: Deferred Extension Points (§12)

These capabilities are out of scope for all five phases. They MUST be implemented as optional adapters and MUST NOT become core dependencies.

| Capability | Blocked By |
|---|---|
| Multi-device sync (CRDT) | Optional upgrade; `clientSequence` + `updatedAt` LWW already in place |
| Cloud persistence (Firestore, Supabase) | Swap `StateAdapter` only |
| Tier 1 — Service Worker Push | Optional; requires SW registration |
| Tier 2 — Notification Triggers API | Optional; Chrome 80+ only |
| Tier 3 — FCM/APNs Remote Push | Out of scope; requires cloud relay + native wrapper |
| Full reminder telemetry log | Beyond the 3-event ring buffer; separate key-space |
| `catchUpPolicy` UI toggle | Expose `"all"` vs `"current-only"` as parent preference |
| Parent approval before marking complete | `ftm:requiresApproval` flag; `pending-approval` state |
| Task reward / points system | Separate module; consumes `ftm:taskCompleted` events |

---

## Open Issues Requiring Operator Resolution

The following SPEC ambiguities block implementation as noted. They must be resolved before the affected phase begins.

| ID | Phase | Description |
|---|---|---|
| I3 | Phase 2 | `ftm:error: "invalid-rrule"` attachment target: §4.1 says attach to each element of the output array (empty); §10 says attach to the array object itself. SPEC author must designate one formulation as canonical. |
| I4 | Phase 2 | `CompletionProcessor` §11 user-store validation (completedBy userId check, role-to-assignedTo cross-check): §4.3 defines `CompletionProcessor` as a pure function with no User collection parameter. If §11 "construction time" checks are interpreted as pre-flow enforcement in Phase 4 orchestration, these rules must be removed from Phase 2 scope. |
| I7 | Phase 3 | `TaskDefinition` immutability invariant (§3.2 "never mutated; updates produce a new version") vs §5.1 LWW conflict-resolution for `saveTaskDefinition`. Operator must define: (a) whether same-`@id` overwrites are refused; (b) the `ftm:version` increment mechanic; (c) the relationship between `ftm:version` and `clientSequence` for updates. |
| I9 | Phase 2 | `catchUpWindowSeconds` / `catchUpWindow` in `RecurrenceMaterializer` §4.5 rule 1a are undefined in the SPEC signature and options block. The `catchUpPolicy: "all"` path is incomputable without this value. SPEC author must add this variable to §4.5 or clarify its derivation. |
| I10 | Phase 1 | `assignedTo` role check (§11) requires `StateAdapter.getUser()` — a Phase 3 artifact. Operator must choose one of three resolution paths before Phase 1 begins (see Phase 1 deferred decisions). |
