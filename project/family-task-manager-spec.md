# Family Task Manager — Technical Specification

**Version:** 0.2.0  
**Status:** Hardened — Addresses Peer Review Critique v0.1.0-draft  
**Execution Model:** Edge-Canonical (browser / `node index.js`)

---

## Revision History

| Version | Changes |
|---|---|
| 0.1.0-draft | Initial specification |
| 0.2.0 | Addressed: Ghost Materialization (§4.1, §4.5, §8.5), Offline Sync schema (§3.2–3.3, §5), Background Notification Paradox (§6, §7), parent override for completion (§4.3, §11), reminder log bloat (§3.3, §3.4), JSON-LD ergonomics note (§2) |

---

## 1. Purpose

This document specifies the **Family Task Manager**, a system that allows a parent to create, schedule, and track tasks assigned to their children. Children receive in-app and push-style alert notifications on their devices. All core logic is stateless and deterministic; persistence and delivery are pluggable adapters.

---

## 2. Architectural Principles

| Principle | Application |
|---|---|
| Edge-Canonical First | All computation runs unmodified in a browser or via `node index.js` |
| No Required Infrastructure | No database, broker, or server is assumed |
| Determinism Over Deployment | Given the same inputs the system produces the same outputs |
| Separation of Concerns | Computation / State / Orchestration / Integration are strictly separated |
| JSON-LD Canonical Representation | All entities and contracts are expressed as JSON-LD |
| Offline First | Valid behavior is defined for every degraded state |

> **JSON-LD Ergonomics Note:** All computation modules operate on compacted JSON-LD using the `ftm:` prefix. Implementations may internally strip the prefix (e.g. map `ftm:title` → `title`) as a view layer convenience, provided the canonical round-trip to full JSON-LD is lossless. The `ftm:` form is always authoritative for storage and inter-component contracts.

---

## 3. Domain Model (JSON-LD)

All entities use the `ftm:` context namespace. Consumers must be able to round-trip any entity through JSON-LD without loss.

### 3.1 Context

```json
{
  "@context": {
    "ftm": "https://schema.familytaskmanager.local/v1/",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "schema": "https://schema.org/"
  }
}
```

### 3.2 TaskDefinition

A `TaskDefinition` is the **parent-authored specification** of work to be done. It is never mutated after creation; updates produce a new version.

```jsonc
{
  "@context": "https://schema.familytaskmanager.local/v1/",
  "@type": "ftm:TaskDefinition",
  "@id": "urn:ftm:task:550e8400-e29b-41d4-a716-446655440000",

  // --- Identity ---
  "ftm:title": "Clean your room",
  "ftm:description": "Vacuum the floor, make the bed, put laundry away.",
  "ftm:assignedTo": "urn:ftm:child:abc123",
  "ftm:createdBy": "urn:ftm:parent:xyz789",
  "ftm:createdAt": { "@type": "xsd:dateTime", "@value": "2026-05-22T10:00:00Z" },
  "ftm:version": 1,

  // --- Sync Metadata (v0.2.0) ---
  // updatedAt and clientSequence are required on every write.
  // clientSequence is a monotonically increasing integer scoped to a single client.
  // It is never reset; last-writer-wins is resolved by the highest clientSequence.
  "ftm:updatedAt": { "@type": "xsd:dateTime", "@value": "2026-05-22T10:00:00Z" },
  "ftm:clientSequence": 1,

  // --- Recurrence ---
  "ftm:schedule": {
    "@type": "ftm:Schedule",
    "ftm:scheduleType": "one-time",     // "one-time" | "recurring"
    "ftm:dueAt": { "@type": "xsd:dateTime", "@value": "2026-05-22T18:00:00Z" },
    // Only present when scheduleType = "recurring"
    "ftm:recurrenceRule": null,         // RFC 5545 RRULE string, e.g. "FREQ=WEEKLY;BYDAY=MO,WE,FR"
    // Anchor for RRULE expansion; must equal the first occurrence's dueAt
    "ftm:recurrenceStart": null         // ISO-8601 datetime
  },

  // --- Reminder Policy ---
  "ftm:reminderPolicy": {
    "@type": "ftm:ReminderPolicy",
    "ftm:mode": "once",                 // "once" | "persistent"
    // Only present when mode = "persistent"
    "ftm:intervalSeconds": null,        // e.g. 1800 = every 30 minutes
    "ftm:persistUntilSeconds": null     // e.g. 3600 = stop reminding after 1 hour from dueAt
                                        // defaults to 86400 (24 h) when absent; see §10
  },

  "ftm:status": "active"                // "active" | "archived"
}
```

### 3.3 TaskInstance

A `TaskInstance` is the **per-occurrence record** of a specific due event. For one-time tasks, exactly one instance exists. For recurring tasks, a new instance is materialized by `RecurrenceMaterializer` (§4.5) on app boot or sync.

```jsonc
{
  "@context": "https://schema.familytaskmanager.local/v1/",
  "@type": "ftm:TaskInstance",
  "@id": "urn:ftm:instance:7f3d9a12-...",

  "ftm:taskDefinition": "urn:ftm:task:550e8400-...",
  "ftm:assignedTo": "urn:ftm:child:abc123",
  "ftm:dueAt": { "@type": "xsd:dateTime", "@value": "2026-05-22T18:00:00Z" },
  "ftm:createdAt": { "@type": "xsd:dateTime", "@value": "2026-05-22T10:00:00Z" },

  // --- Sync Metadata (v0.2.0) ---
  "ftm:updatedAt": { "@type": "xsd:dateTime", "@value": "2026-05-22T10:00:00Z" },
  "ftm:clientSequence": 1,

  "ftm:completionState": {
    "@type": "ftm:CompletionState",
    "ftm:status": "pending",            // "pending" | "completed"
    "ftm:completedAt": null,
    "ftm:completedBy": null,            // userId of completer (child OR parent)
    "ftm:completedByRole": null         // "child" | "parent" — records who acted
  },

  // Reminder tracking — capped ring buffer; see §3.4
  "ftm:reminderSummary": {
    "@type": "ftm:ReminderSummary",
    "ftm:totalSent": 0,                 // monotonically increasing count
    "ftm:lastSentAt": null,             // ISO-8601 datetime | null
    "ftm:lastDeliveryStatus": null,     // "delivered" | "failed" | "deferred" | null
    "ftm:recentEvents": []              // ring buffer: last 3 ftm:ReminderEvent objects only
  }
}
```

### 3.4 ReminderEvent

`ReminderEvent` objects are stored only in `ftm:recentEvents` (capped at 3). The authoritative sent-count is `ftm:totalSent` in `ReminderSummary`. Full telemetry, if needed, is an optional adapter concern (see §12).

```jsonc
{
  "@type": "ftm:ReminderEvent",
  "ftm:sentAt": { "@type": "xsd:dateTime", "@value": "2026-05-22T17:00:00Z" },
  "ftm:deliveryStatus": "delivered"     // "delivered" | "failed" | "deferred"
}
```

### 3.5 User

```jsonc
{
  "@context": "https://schema.familytaskmanager.local/v1/",
  "@type": "ftm:User",
  "@id": "urn:ftm:child:abc123",
  "ftm:role": "child",                  // "parent" | "child"
  "ftm:displayName": "Alex",
  "ftm:notificationTokens": []          // adapter-supplied push tokens; opaque strings
}
```

---

## 4. Core Computation Modules

All modules are **pure functions**. They accept JSON-LD objects and return JSON-LD objects. They have no side effects and no I/O.

### 4.1 `ScheduleComputer`

**Responsibility:** Given a `TaskDefinition` and a reference timestamp, derive one or more `TaskInstance` skeletons. Does not save; does not read from state. This module is now the single source of truth for all instance derivation — both initial creation and catch-up materialization delegate to it.

```
Input:  TaskDefinition,
        referenceTime: ISO-8601 string,
        options?: { lookAheadSeconds?: number }   // default: 7 days = 604800
Output: TaskInstance[]
```

**Rules:**

- If `scheduleType = "one-time"`:
  - If `dueAt` ≤ `referenceTime`, return `[]`.
  - Otherwise return a single-element array containing one `TaskInstance`.
- If `scheduleType = "recurring"`:
  - Parse `recurrenceRule` anchored at `recurrenceStart`. If unparseable, return `[]` and attach `ftm:error: "invalid-rrule"` to each element of the output.
  - Enumerate all occurrences in the window `(referenceTime, referenceTime + lookAheadSeconds]`.
  - Return one `TaskInstance` per occurrence.
  - If no occurrences exist in the window, return `[]`.
- All returned instances have `ftm:completionState.status = "pending"` and empty `reminderSummary`.

> **Design note:** Returning an array (even of one element for one-time tasks) gives callers a uniform interface regardless of schedule type. `RecurrenceMaterializer` (§4.5) is responsible for deduplicating against already-persisted instances before saving.

### 4.2 `ReminderEvaluator`

**Responsibility:** Given a `TaskInstance` and the current time, decide whether a reminder notification should be dispatched now.

```
Input:  TaskInstance, TaskDefinition, currentTime: ISO-8601 string
Output: { shouldRemind: boolean, reason: string }
```

**Rules:**

- If `completionState.status = "completed"`, return `{ shouldRemind: false, reason: "already-complete" }`.
- If `dueAt` > `currentTime`, return `{ shouldRemind: false, reason: "not-yet-due" }`.
- If `mode = "once"`:
  - If `reminderSummary.totalSent === 0`, return `{ shouldRemind: true, reason: "first-and-only" }`.
  - Otherwise return `{ shouldRemind: false, reason: "once-sent" }`.
- If `mode = "persistent"`:
  - Resolve `persistUntilSeconds`: use the explicit value if present; otherwise default to `86400`.
  - If `currentTime > dueAt + persistUntilSeconds`, return `{ shouldRemind: false, reason: "persistence-window-expired" }`.
  - If `reminderSummary.totalSent === 0`, return `{ shouldRemind: true, reason: "initial-reminder" }`.
  - If `reminderSummary.lastDeliveryStatus === "failed"`, treat `lastSentAt` as though it never occurred and return `{ shouldRemind: true, reason: "retry-after-failure" }`.
  - If `currentTime - lastSentAt >= intervalSeconds`, return `{ shouldRemind: true, reason: "interval-elapsed" }`.
  - Otherwise return `{ shouldRemind: false, reason: "interval-not-elapsed" }`.

### 4.3 `CompletionProcessor`

**Responsibility:** Accept a completion signal from either a child or a parent and return an updated `TaskInstance`.

```
Input:  TaskInstance,
        completedBy: userId,
        completedByRole: "child" | "parent",
        completedAt: ISO-8601 string
Output: TaskInstance (new copy; original is not mutated)
```

**Rules:**

- If `completionState.status = "completed"`, return the instance unchanged with `ftm:warning: "already-complete"`.
- Set `completionState.status = "completed"`, `completedAt`, `completedBy`, `completedByRole`.
- Increment `ftm:clientSequence` by 1.
- Set `ftm:updatedAt` to `completedAt`.

> **Parent Override:** A parent may complete any instance on behalf of a child. `completedByRole = "parent"` is recorded for audit purposes but does not change the completion semantics.

### 4.4 `TaskListComputer`

**Responsibility:** Given a collection of `TaskInstance` objects and filter criteria, return a sorted, filtered view.

```
Input:  TaskInstance[],
        filter: { assignedTo?: string, status?: "pending" | "completed", fromDate?: string, toDate?: string }
Output: TaskInstance[]
```

**Rules:**

- All filtering is pure array transformation; no I/O.
- Default sort: `dueAt` ascending; within equal `dueAt`, pending before completed.

### 4.5 `RecurrenceMaterializer` *(new in v0.2.0)*

**Responsibility:** On app boot or sync event, close the "Ghost Materialization" gap by comparing what instances *should* exist against what *does* exist, and returning the delta that needs to be saved.

This is a pure function. It does not write to state; the orchestration layer saves the result.

```
Input:  TaskDefinition[],           // all active recurring definitions
        existingInstances: TaskInstance[],  // all instances currently in state
        currentTime: ISO-8601 string,
        options?: {
          lookAheadSeconds?: number,    // default: 604800 (7 days forward)
          catchUpPolicy: "all" | "current-only"
          // "all"          — materialize every missed occurrence (creates historical records)
          // "current-only" — skip past occurrences; materialize from now forward only
          // default: "current-only"
        }
Output: { toCreate: TaskInstance[], skipped: number }
```

**Rules:**

1. For each `TaskDefinition` with `scheduleType = "recurring"`:
   a. Call `ScheduleComputer(def, currentTime - catchUpWindowSeconds, { lookAheadSeconds: catchUpWindow + lookAheadSeconds })` to enumerate all occurrences in the catch-up + look-ahead window.
   b. From the result, remove any occurrence whose `dueAt` already has a matching instance in `existingInstances` (match by `taskDefinition @id` + `dueAt`). This is the deduplication step.
   c. If `catchUpPolicy = "current-only"`, further filter out occurrences where `dueAt` < `currentTime`. Increment `skipped` for each filtered occurrence.
   d. Append remaining instances to `toCreate`.
2. Return `{ toCreate, skipped }`.

> **Offline Catch-Up Example:** A user returns after 4 days of inactivity. With `catchUpPolicy = "all"`, missed daily instances for the 4 prior days are created as `pending` historical records. With `catchUpPolicy = "current-only"`, those 4 days are skipped (`skipped = 4`) and only today's and future instances are created. The parent configures this policy per app; the default is `"current-only"` to avoid flooding the child's task list.

---

## 5. State Adapter Interface

State is not part of core logic. The following interface must be implemented by any state adapter. The system ships with an **in-memory adapter** (suitable for browser/Node) and specifies an optional **LocalStorage adapter** for browser persistence.

```typescript
interface StateAdapter {
  // Task Definitions
  saveTaskDefinition(td: TaskDefinition): Promise<void>;
  getTaskDefinition(id: string): Promise<TaskDefinition | null>;
  listTaskDefinitions(filter?: { status?: "active" | "archived" }): Promise<TaskDefinition[]>;

  // Task Instances
  saveTaskInstance(ti: TaskInstance): Promise<void>;
  getTaskInstance(id: string): Promise<TaskInstance | null>;
  listTaskInstances(filter?: InstanceFilter): Promise<TaskInstance[]>;

  // Users
  saveUser(user: User): Promise<void>;
  getUser(id: string): Promise<User | null>;
  listUsers(): Promise<User[]>;
}

interface InstanceFilter {
  assignedTo?: string;
  status?: "pending" | "completed";
  taskDefinitionId?: string;
  fromDate?: string;    // ISO-8601
  toDate?: string;      // ISO-8601
}
```

### 5.1 Conflict Resolution Policy *(new in v0.2.0)*

All state adapters must implement the following last-writer-wins merge rule using the sync metadata fields introduced in §3.2–3.3.

When `saveTaskDefinition` or `saveTaskInstance` is called with an entity whose `@id` already exists in state:

1. Load the existing entity.
2. Compare `ftm:clientSequence`. The entity with the **higher** `clientSequence` wins.
3. If sequences are equal, compare `ftm:updatedAt`. The entity with the **later** timestamp wins.
4. If both are equal, the incoming entity wins (idempotent re-save is safe).
5. The losing entity is discarded; the winning entity is stored.

> **Note:** This last-writer-wins policy is sufficient for a family-scale application where true concurrent edits on the same entity are rare. Applications requiring stronger guarantees (e.g. CRDT merge of reminder logs) should implement a sync adapter extension (§12).

**In-Memory Adapter (canonical):** Stores all data in a `Map<string, object>`. Keyed by `@id`. Implements conflict resolution per §5.1. Resets on page reload or process exit.

**LocalStorage Adapter (optional browser enhancement):** Serializes JSON-LD entities to `localStorage`. Same interface and conflict resolution. Degrades silently to in-memory if `localStorage` is unavailable.

---

## 6. Orchestration Adapter Interface

Orchestration (scheduling timers, polling) is pluggable. Core logic never calls `setTimeout` directly.

```typescript
interface OrchestrationAdapter {
  /**
   * Request that `callback` be invoked at or after `isoTimestamp`.
   * Returns an opaque handle that can be used to cancel.
   * Implementations MUST document their background behavior (see §6.1).
   */
  scheduleAt(isoTimestamp: string, callback: () => void): string;

  /**
   * Request that `callback` be invoked every `intervalMs` milliseconds.
   */
  scheduleInterval(intervalMs: number, callback: () => void): string;

  cancel(handle: string): void;

  /**
   * Called by the application on every boot or foreground resume.
   * Allows the adapter to re-register any timers that were lost while backgrounded.
   */
  onResume(currentTime: string): void;
}
```

### 6.1 Background Timer Reality *(new in v0.2.0)*

JavaScript timers (`setTimeout`, `setInterval`) are **not reliable** when a browser tab or PWA is backgrounded, the screen is locked, or the device enters low-power mode. This is an OS/browser constraint that cannot be overcome in pure JavaScript.

The following table defines what each adapter tier can and cannot guarantee:

| Tier | Implementation | Foreground | Background / Locked Screen |
|---|---|---|---|
| **Tier 0 — In-Process (canonical)** | `setTimeout` / `setInterval` | ✅ Fires on time | ❌ Throttled or frozen |
| **Tier 1 — Service Worker** | `ServiceWorkerRegistration.showNotification` + `PushManager` | ✅ | ⚠️ Fires if SW is alive; still throttled on some platforms |
| **Tier 2 — Notification Triggers API** | `NotificationTrigger` (Chrome 80+, limited support) | ✅ | ✅ OS-scheduled; no JS required at fire time |
| **Tier 3 — Remote Push Relay** | FCM / APNs via a lightweight relay function | ✅ | ✅ Guaranteed OS delivery |

**Adapter selection guidance:**

- Apps that only need in-app reminders (parent and child both have the app open): Tier 0 is sufficient.
- Apps that need reliable background reminders on a web/PWA target: implement Tier 1 + Tier 2 with Tier 0 as fallback.
- Apps that need guaranteed delivery on locked screens on mobile (iOS/Android): Tier 3 is required. This is the only tier that is not edge-canonical; it must be treated as an optional infrastructure adapter (§12).

**Resume Reconciliation (all tiers):** Because any timer may be lost while backgrounded, the `onResume` hook is called every time the app comes to the foreground. The orchestration layer must:

1. Call `RecurrenceMaterializer` to create any missed instances (§4.5, §8.5).
2. Re-evaluate all pending `TaskInstance` objects through `ReminderEvaluator`.
3. Re-dispatch any reminders that should have fired while backgrounded.

This makes catch-up behavior correct regardless of whether a timer fired.

---

## 7. Notification Integration Adapter

Delivery to a child's device is an integration concern, not core logic.

```typescript
interface NotificationAdapter {
  /**
   * Send a notification to the device(s) associated with userId.
   * Returns a delivery receipt (opaque; stored in ReminderSummary).
   * MUST NOT throw on delivery failure; return status "failed" instead.
   */
  send(payload: NotificationPayload): Promise<NotificationReceipt>;
}

interface NotificationPayload {
  recipientUserId: string;
  title: string;
  body: string;
  /** Deep-link URI that opens the specific TaskInstance in the child UI */
  deepLinkUri: string;
  /**
   * Hint to the delivery layer: attempt foreground display if device is active.
   * Adapters that cannot honor this MUST silently ignore it (not error).
   */
  requestForegroundDisplay: boolean;
}

interface NotificationReceipt {
  status: "delivered" | "failed" | "deferred";
  adapterTier: 0 | 1 | 2 | 3;
  /** Opaque; for use by Tier 3 adapters to track external delivery IDs */
  externalId?: string;
}
```

### 7.1 Adapter Implementations

| Adapter | Tier | Description | Required? |
|---|---|---|---|
| **In-Process (canonical)** | 0 | Fires a browser `CustomEvent` or Node `EventEmitter`. No external I/O. | Yes — ships with core |
| **Service Worker Push** | 1 | Uses `ServiceWorkerRegistration.showNotification`. Requires SW registration. | Optional |
| **Notification Triggers API** | 2 | OS-scheduled notification; no JS at fire time. Chrome 80+ only. | Optional |
| **FCM / APNs Relay** | 3 | Server-side push to iOS/Android. Requires a cloud function or relay. | Optional — out of scope for core spec |

### 7.2 Foreground Display

When `requestForegroundDisplay = true`:

- **Tier 0 (In-Process):** Dispatches `CustomEvent("ftm:alert", { detail: payload })` on `window`. The child UI subscribes to this event and renders an in-app modal alert unconditionally, regardless of which view is active.
- **Tier 1 (Service Worker):** Sets `requireInteraction: true` on the `Notification` constructor, keeping the notification visible until dismissed. True OS-level popup on a locked screen is not guaranteed by the web platform.
- **Tier 2 (Notification Triggers):** OS handles display. The app has no further control over foreground vs. background rendering.
- **Tier 3 (Remote Push):** The push payload should set the appropriate native flags: `content-available: 1` + `alert` on APNs; `priority: high` + `notification` channel on FCM. A native wrapper (Capacitor, React Native) is required for heads-up display on a locked screen.

> **Platform Limitation Statement (required in UI):** The application must display a one-time disclosure to users: *"Background reminders require notification permissions. Reliability when the app is closed depends on your device and browser."*

---

## 8. Application Flows

These flows describe how the adapters and computation modules compose. They are non-normative orchestration examples, not architectural requirements.

### 8.1 Parent Creates a Task

```
1. Parent fills out task form (title, description, assignee, schedule, reminder policy).
2. UI constructs a TaskDefinition JSON-LD object (with createdAt, updatedAt, clientSequence: 1).
3. Call ScheduleComputer(taskDef, now, { lookAheadSeconds: 604800 }) → TaskInstance[]
4. StateAdapter.saveTaskDefinition(taskDef)
5. For each instance in result: StateAdapter.saveTaskInstance(instance)
6. For each instance: OrchestrationAdapter.scheduleAt(instance.dueAt, () => triggerReminder(instance.@id))
```

### 8.2 Reminder Trigger

```
1. OrchestrationAdapter fires callback for a TaskInstance at dueAt.
2. Load TaskInstance and TaskDefinition from StateAdapter.
3. ReminderEvaluator.evaluate(instance, taskDef, now) → { shouldRemind, reason }
4. If shouldRemind:
   a. NotificationAdapter.send(payload with requestForegroundDisplay: true) → receipt
   b. Update instance.reminderSummary:
      - Increment totalSent
      - Set lastSentAt = now
      - Set lastDeliveryStatus = receipt.status
      - Prepend new ReminderEvent to recentEvents; truncate array to last 3 elements
   c. Increment instance.clientSequence; set instance.updatedAt = now
   d. StateAdapter.saveTaskInstance(updated instance)
   e. If mode = "persistent" and persistence window not expired:
      OrchestrationAdapter.scheduleAt(now + intervalSeconds, repeatReminderFn)
5. If !shouldRemind: do nothing (reason is available for debug logging).
```

### 8.3 Child Marks Task Complete

```
1. Child taps notification deep-link → UI opens TaskInstance view.
2. Child taps "Mark Complete".
3. CompletionProcessor.complete(instance, childId, "child", now) → updatedInstance
4. StateAdapter.saveTaskInstance(updatedInstance)
5. OrchestrationAdapter.cancel(all reminder handles for this instance)
6. Emit CustomEvent("ftm:taskCompleted", { detail: updatedInstance }) so parent UI updates reactively.
```

### 8.4 Parent Views Task Dashboard

```
1. StateAdapter.listTaskInstances({ assignedTo: childId }) → all instances
2. TaskListComputer.filter(instances, { status: "pending" }) → pending list
3. TaskListComputer.filter(instances, { status: "completed" }) → completed list
4. Render both lists.
```

### 8.5 App Boot / Foreground Resume *(new in v0.2.0)*

This flow runs every time the application starts or returns to the foreground. It closes the Ghost Materialization gap and recovers missed reminders.

```
1. OrchestrationAdapter.onResume(now)
2. Load all active TaskDefinitions from StateAdapter (status = "active", scheduleType = "recurring")
3. Load all existing TaskInstances from StateAdapter
4. RecurrenceMaterializer(taskDefs, existingInstances, now, { catchUpPolicy: appConfig.catchUpPolicy })
   → { toCreate: TaskInstance[], skipped: number }
5. For each instance in toCreate:
   a. StateAdapter.saveTaskInstance(instance)
   b. OrchestrationAdapter.scheduleAt(instance.dueAt, () => triggerReminder(instance.@id))
6. If skipped > 0: (optional) display "X tasks were skipped while you were away" in parent UI.
7. Load all pending TaskInstances (all children)
8. For each pending instance where dueAt <= now:
   a. ReminderEvaluator.evaluate(instance, taskDef, now)
   b. If shouldRemind: dispatch reminder (flow §8.2 steps 4a–4e)
```

### 8.6 Parent Completes Task on Child's Behalf

```
1. Parent opens Task Dashboard → selects a pending TaskInstance.
2. Parent taps "Mark Complete (Override)".
3. CompletionProcessor.complete(instance, parentId, "parent", now) → updatedInstance
4. StateAdapter.saveTaskInstance(updatedInstance)
5. OrchestrationAdapter.cancel(all reminder handles for this instance)
6. Emit CustomEvent("ftm:taskCompleted", { detail: updatedInstance })
```

---

## 9. UI Contract

The UI layer is not specified here beyond its data contract. Any UI framework may be used. The UI must:

- Consume and produce valid JSON-LD entities as defined in §3.
- Never call computation modules with raw form values; always construct well-typed JSON-LD objects first.
- Register a listener for `CustomEvent("ftm:alert")` on `window` and render an in-app modal when received (§7.2).
- Provide deep-link routing: `ftm://instance/{instanceId}` (or a hash-router equivalent) must resolve to the TaskInstance detail view.
- Display the platform limitation statement from §7.2 on first notification permission request.

### 9.1 Parent Views

- **Task Creator** — form producing `TaskDefinition`
- **Task Dashboard** — filterable list of all children's instances (pending / completed); shows `completedByRole` badge when parent completed
- **Task Detail** — full `TaskInstance` view including `reminderSummary.totalSent`, `lastDeliveryStatus`, and recent event log

### 9.2 Child Views

- **My Tasks** — list of pending `TaskInstance` objects for the authenticated child
- **Task Detail** — view of a single instance with a "Mark Complete" action
- **Alert Modal** — rendered on `ftm:alert` event; links to Task Detail; remains visible until dismissed

---

## 10. Offline Behavior

| Scenario | Required Behavior |
|---|---|
| Child device has no connectivity | `TaskInstance` list renders from last cached state. Completion is recorded locally with updated `clientSequence` and synced when connectivity returns via the sync adapter (§12). |
| Notification cannot be delivered | `NotificationAdapter.send` returns `{ status: "failed" }`. `ReminderEvaluator` treats `lastDeliveryStatus = "failed"` as a non-sent event and retries on the next evaluation (§4.2, reason: `"retry-after-failure"`). |
| `recurrenceRule` is unparseable | `ScheduleComputer` returns `[]` with `ftm:error: "invalid-rrule"`. The `TaskDefinition` is flagged in the UI; no instances are created. |
| `persistUntilSeconds` absent, mode is `"persistent"` | `ReminderEvaluator` defaults to `86400` seconds (24 hours). This default is displayed in the UI reminder policy form. |
| App backgrounded; timers lost | On resume, `onResume` flow (§8.5) re-evaluates all pending instances and dispatches any missed reminders. |
| App offline for multiple days (recurring tasks) | `RecurrenceMaterializer` re-runs on resume with the configured `catchUpPolicy`. Default `"current-only"` prevents flooding the child's list; parent may switch to `"all"` to preserve historical records. |
| Concurrent edit conflict (parent edits, child completes simultaneously) | `clientSequence` comparison in `StateAdapter` (§5.1) resolves the conflict deterministically. Higher sequence wins. If equal, later `updatedAt` wins. |

---

## 11. Validation Rules

The following invariants must be enforced at object construction time, before any entity is passed to a computation module.

| Entity | Rule |
|---|---|
| `TaskDefinition` | `title` must be non-empty string ≤ 200 chars |
| `TaskDefinition` | `assignedTo` must resolve to a User with `role = "child"` |
| `TaskDefinition` | If `scheduleType = "recurring"`, `recurrenceRule` and `recurrenceStart` must both be non-empty |
| `TaskDefinition` | If `scheduleType = "recurring"`, `recurrenceStart` must be a valid ISO-8601 datetime |
| `TaskDefinition` | If `mode = "persistent"`, `intervalSeconds` must be a positive integer ≥ 60 |
| `TaskDefinition` | `persistUntilSeconds`, if present, must be ≥ `intervalSeconds` |
| `TaskInstance` | `dueAt` must be a valid ISO-8601 datetime |
| `TaskInstance` | `clientSequence` must be a positive integer; must be incremented on every write |
| `CompletionProcessor` | `completedBy` must be a valid userId present in the User store |
| `CompletionProcessor` | `completedByRole` must be `"child"` or `"parent"` |
| `CompletionProcessor` | If `completedByRole = "child"`, `completedBy` must match `assignedTo` on the `TaskDefinition` |
| `CompletionProcessor` | If `completedByRole = "parent"`, `completedBy` must resolve to a User with `role = "parent"` |

---

## 12. Extension Points (Non-Normative)

The following capabilities are explicitly deferred and must be implemented as optional adapters, never as core dependencies.

| Capability | Adapter Type | Notes |
|---|---|---|
| Multi-device sync | State adapter | `clientSequence` + `updatedAt` fields (§3.2–3.3) already support LWW merge; CRDT merge is a stronger optional upgrade |
| Cloud persistence | State adapter | e.g. Firestore, Supabase; swap `StateAdapter` implementation only |
| Tier 3 remote push (iOS/Android) | Notification adapter | Requires FCM/APNs credentials and a relay function; not edge-canonical |
| Full reminder telemetry log | State adapter extension | Persist all `ReminderEvent` objects to a separate key-space beyond the 3-event ring buffer |
| `catchUpPolicy` UI toggle | UI + orchestration | Expose `"all"` vs `"current-only"` as a parent preference in settings |
| Parent approval before marking complete | Computation module extension | Add `ftm:requiresApproval` flag to `TaskDefinition`; `CompletionProcessor` emits `pending-approval` state |
| Task reward / points system | Separate module | Consumes `ftm:taskCompleted` CustomEvents |

---

## 13. Spec Test Checklist

> A developer must be able to answer **yes** to each of the following using only a browser, a local Node.js runtime, and JSON-LD files.

- [ ] Can I instantiate a `TaskDefinition` JSON-LD object and pass it to `ScheduleComputer` without any network call?
- [ ] Can I call `ScheduleComputer` with a recurring `TaskDefinition` and a reference time 4 days in the past, and receive a deterministic array of `TaskInstance` objects covering the catch-up window?
- [ ] Can I call `RecurrenceMaterializer` with a fixture set of `TaskDefinition` and `TaskInstance` objects and get a deterministic `{ toCreate, skipped }` result?
- [ ] Can I run `ReminderEvaluator` against a fixture `TaskInstance` (with `lastDeliveryStatus: "failed"`) and confirm `shouldRemind = true` with `reason: "retry-after-failure"`?
- [ ] Can I complete a task as a parent (`completedByRole: "parent"`) with `CompletionProcessor` and confirm the output passes validation (§11)?
- [ ] Can I complete a task as a child (`completedByRole: "child"`) with a non-matching `completedBy` and confirm the validator rejects it?
- [ ] Can I render the parent dashboard using only `TaskListComputer` output and no server?
- [ ] Can I confirm that two conflicting `TaskInstance` saves resolve to the higher `clientSequence` version in the in-memory `StateAdapter`?
- [ ] Can I swap the `NotificationAdapter` for a no-op stub and have all other modules function correctly?
- [ ] Can I run the entire app boot / resume flow (§8.5) using the **Test OrchestrationAdapter** (manual `tick()`) with no real timers and no network?

---

## 14. Glossary

| Term | Definition |
|---|---|
| **TaskDefinition** | The parent-authored template describing what, when, and how often |
| **TaskInstance** | A single occurrence of a TaskDefinition that a child can complete |
| **ReminderPolicy** | The rule governing how many times and how often a child is reminded |
| **ReminderSummary** | Compact reminder state embedded in a TaskInstance; replaces the unbounded log |
| **ScheduleComputer** | Pure function that derives one or more TaskInstances from a TaskDefinition |
| **RecurrenceMaterializer** | Pure function that computes the delta of missing instances on boot/resume |
| **ReminderEvaluator** | Pure function that decides whether a reminder should fire right now |
| **CompletionProcessor** | Pure function that records a completion signal from a child or parent |
| **TaskListComputer** | Pure function that filters and sorts TaskInstance arrays |
| **clientSequence** | Monotonically increasing integer used for last-writer-wins conflict resolution |
| **catchUpPolicy** | Controls whether missed recurring instances are created retroactively or skipped |
| **State Adapter** | Pluggable persistence layer; in-memory by default |
| **Orchestration Adapter** | Pluggable timer layer; browser/Node timers by default; see tier table §6.1 |
| **Notification Adapter** | Pluggable delivery layer; CustomEvent (Tier 0) by default |
| **Edge-Canonical** | Runs unmodified in a browser or `node index.js` with no cloud dependencies |
| **Ghost Materialization** | The gap where recurring instances are never created after the first one |
