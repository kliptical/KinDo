# Family Task Manager — Project Roadmap

**SPEC:** `project/family-task-manager-spec.md` v0.2.0
**Execution Model:** Edge-Canonical (browser / `node index.js`)

> This roadmap covers the full normative scope of SPEC v0.2.0. Extension points listed in §12 are explicitly deferred and enumerated at the bottom of this document. All five phases are dependency-ordered: each phase assumes all prior phases are complete.

---

## Phase 1: Domain Model and Validation

**Goal:** Establish the canonical JSON-LD entity schemas, sync metadata, and entity-level validation invariants.

**Status:** Not Started

### Scope

- JSON-LD context declaration (`ftm:` namespace, `xsd:`, `schema:`) per §3.1
- `TaskDefinition` entity schema: identity fields, sync metadata (`ftm:updatedAt`, `ftm:clientSequence`), `ftm:Schedule` (one-time / recurring, `recurrenceRule`, `recurrenceStart`), `ftm:ReminderPolicy` (once / persistent, `intervalSeconds`, `persistUntilSeconds`), `ftm:status` per §3.2
- `TaskInstance` entity schema: `ftm:CompletionState` (pending / completed, `completedBy`, `completedByRole`), `ftm:ReminderSummary` (totalSent, lastSentAt, lastDeliveryStatus, recentEvents ring buffer capped at 3), sync metadata per §3.3
- `ReminderEvent` schema stored only in `ftm:recentEvents` per §3.4
- `User` schema: `ftm:role` (parent / child), `ftm:displayName`, `ftm:notificationTokens` per §3.5
- JSON-LD round-trip guarantee: any entity serializes and deserializes without data loss (§3)
- JSON-LD ergonomics: `ftm:` prefix compaction / expansion; internal prefix-stripping is acceptable as a view-layer convenience; canonical storage always uses the `ftm:` form (§2)
- §11 `TaskDefinition` and `TaskInstance` construction validation rules: title length, `assignedTo` role check, recurring schedule completeness, `intervalSeconds` minimum, `persistUntilSeconds` â‰¥ `intervalSeconds`; `TaskInstance` `dueAt` format, `clientSequence` positive-integer requirement

**NOT in scope:**
- Computation module logic (ScheduleComputer, ReminderEvaluator, etc.) — Phase 2
- `CompletionProcessor` validation rules from §11 (`completedBy` userId check, role-to-`assignedTo` cross-check) — Phase 2
- Any adapter implementations (state, orchestration, notification) — Phase 3
- Application flow wiring — Phase 4
- UI rendering — Phase 5

**Decisions Deferred:**
- Implementation language and module format (JavaScript vs TypeScript; ESM vs CJS). The SPEC mandates `browser / node index.js` compatibility but does not prescribe a build system or type system. Operator must decide before Phase 1 begins.
- Validation library choice (hand-rolled checks vs JSON Schema vs Zod vs AJV). Must be edge-canonical (no server required). Operator must approve any runtime dependency.
- **`assignedTo` role check — scope assignment unresolved (I10):** §11 requires `assignedTo` to resolve to a User with `role = "child"`, but this lookup requires `StateAdapter.getUser()` — a Phase 3 artifact. Three resolution paths: (a) Phase 1 implements against a stub/fixture user registry; (b) the §11 preamble pre-hoist interpretation moves this check to Phase 4 application flow; (c) the rule is deferred explicitly to Phase 4. Must be resolved before Phase 1 begins. See also I4 in Phase 2.

---

## Phase 2: Core Computation Modules

**Goal:** Implement all five pure-function computation modules and pass all ten items of the §13 Spec Test Checklist in a Node.js environment with no network access.

**Status:** Not Started

### Scope

- **`ScheduleComputer`** (§4.1): one-time instance derivation (dueAt guard); recurring instance derivation via RFC 5545 RRULE anchored at `recurrenceStart`; invalid-rrule error attachment; uniform `TaskInstance[]` return for both schedule types; `lookAheadSeconds` default of 604800 (7 days)
- **`ReminderEvaluator`** (§4.2): already-complete guard; not-yet-due guard; `once` mode (first-and-only / once-sent); `persistent` mode with `persistUntilSeconds` window (default 86400 s per §2 and §10), failure-retry logic (`lastDeliveryStatus = "failed"` → `shouldRemind: true, reason: "retry-after-failure"`), interval-elapsed check
- **`CompletionProcessor`** (§4.3): child completion; parent override (`completedByRole = "parent"` recorded, semantics unchanged); already-complete idempotency with `ftm:warning`; `clientSequence` increment; `updatedAt` set to `completedAt`; validation rules from §11 (completedBy userId check, role-to-assignedTo cross-check)
- **`TaskListComputer`** (§4.4): `assignedTo` / `status` / `fromDate` / `toDate` filter; `dueAt`-ascending sort; pending-before-completed tiebreak for equal `dueAt`
- **`RecurrenceMaterializer`** (§4.5): catch-up + look-ahead window enumeration via `ScheduleComputer`; deduplication by `taskDefinition @id` + `dueAt`; `catchUpPolicy = "current-only"` default (skip past occurrences, increment `skipped`); `"all"` policy for historical backfill; returns `{ toCreate: TaskInstance[], skipped: number }`
- All 10 items of the §13 Spec Test Checklist, each covered by at least one automated test executable via `node` without any network call

**NOT in scope:**
- State persistence — Phase 3
- Orchestration timers or adapter wiring — Phase 3
- Application flow composition — Phase 4
- UI rendering — Phase 5

**Decisions Deferred:**
- RRULE parsing library. Must be edge-canonical (runs in browser and Node without a server). Operator must approve any runtime dependency or mandate a bundled pure-JS implementation before Phase 2 begins.
- **`invalid-rrule` error-attachment target — ambiguous SPEC (I3):** §4.1 says "attach `ftm:error: "invalid-rrule"` to each element of the output" (null-iteration on `[]`); §10 says "`ScheduleComputer` returns `[]` with `ftm:error: "invalid-rrule"`" (error on the array object itself). These are structurally different attach targets. SPEC author must designate one formulation as canonical before Phase 2 implements this behavior.
- **`catchUpWindowSeconds` / `catchUpWindow` undefined — blocking SPEC defect (I9):** `RecurrenceMaterializer` rule 1a (§4.5) calls `ScheduleComputer(def, currentTime - catchUpWindowSeconds, { lookAheadSeconds: catchUpWindow + lookAheadSeconds })`. Neither variable appears in the §4.5 function signature or options block. The `catchUpPolicy = "all"` path is incomputable as specified. Phase 2 implementation of historical backfill is blocked pending SPEC author clarification.
- **`CompletionProcessor` §11 User-store checks — scope assignment unresolved (I4):** §4.3 defines `CompletionProcessor` as a pure function with no User collection parameter, yet the scope above claims its §11 validation rules (`completedBy` userId check, role-to-`assignedTo` cross-check) as Phase 2 scope. If the §11 preamble pre-hoist interpretation applies (checks enforced at construction time before the module is invoked), these checks belong in Phase 4 application flow and must be removed from Phase 2 scope. Must be resolved before Phase 2 begins. See also I10 in Phase 1.

---

## Phase 3: Adapter Implementations

**Goal:** Deliver the canonical in-memory state adapter, Tier 0 orchestration adapter (including Test adapter), and Tier 0 notification adapter; implement the resume reconciliation hook.

**Status:** Not Started

### Scope

- **`StateAdapter` interface** per §5: `saveTaskDefinition`, `getTaskDefinition`, `listTaskDefinitions`, `saveTaskInstance`, `getTaskInstance`, `listTaskInstances`, `saveUser`, `getUser`, `listUsers`; `InstanceFilter` shape
- **In-Memory adapter (canonical)**: `Map<string, object>` keyed by `@id`; last-writer-wins conflict resolution per §5.1 — higher `clientSequence` wins; equal sequence → later `updatedAt` wins; both equal → incoming entity wins
- **LocalStorage adapter (optional browser enhancement)**: same `StateAdapter` interface; same §5.1 conflict-resolution policy as in-memory adapter (higher `clientSequence` wins; equal sequence → later `updatedAt` wins; both equal → incoming entity wins); serializes JSON-LD to `localStorage`; silent fallback to in-memory if `localStorage` unavailable per §5
- **`OrchestrationAdapter` interface** per §6: `scheduleAt`, `scheduleInterval`, `cancel`, `onResume`
- **Tier 0 OrchestrationAdapter**: `setTimeout` / `setInterval` backed; foreground-reliable; background throttling documented as a known limitation per §6.1 tier table
- **Test OrchestrationAdapter**: manual `tick(isoTimestamp)` method advances logical time without real timers; required for §13 checklist item 10
- **`NotificationAdapter` interface** per §7: `send(payload): Promise<NotificationReceipt>`; MUST NOT throw; returns `{ status: "failed" }` on error
- **Tier 0 NotificationAdapter (canonical)**: `CustomEvent("ftm:alert", { detail: payload })` on `window` (browser); `EventEmitter` emit (Node); `requestForegroundDisplay: true` handled per §7.2 Tier 0; `adapterTier: 0` in receipt
- **Resume reconciliation** (`onResume` hook body, §6.1 + §8.5): calls `RecurrenceMaterializer` on all active recurring definitions + existing instances; saves `toCreate` instances; re-evaluates all pending instances via `ReminderEvaluator`; re-dispatches any missed reminders
- Platform limitation disclosure text defined per §7.2 (display deferred to Phase 5 UI)

**NOT in scope:**
- Tier 1 (Service Worker Push), Tier 2 (Notification Triggers API), Tier 3 (FCM/APNs) — extension points per §12
- Cloud persistence adapters (Firestore, Supabase, etc.) — extension points per §12
- UI rendering — Phase 5

**Decisions Deferred:**
- Whether the LocalStorage adapter ships in Phase 3 or is deferred entirely as an extension. It is marked "optional" in §5; Operator confirms scope before Phase 3 begins.
- **`TaskDefinition` immutability invariant and `ftm:version` mechanic — unaddressed (I7):** §3.2 declares `TaskDefinition` as "never mutated after creation; updates produce a new version," yet §5.1 applies `saveTaskDefinition` via `clientSequence`/`updatedAt` conflict resolution with no reference to `ftm:version`. Before Phase 3 adapter implementation begins, define: (a) whether `saveTaskDefinition` enforces immutability by refusing same-`@id` overwrites; (b) the version-increment mechanic for `TaskDefinition` updates; (c) the relationship between `ftm:version` and `clientSequence` for `TaskDefinition` updates.

---

## Phase 4: Application Flow Wiring and Entry Point

**Goal:** Compose all modules and adapters into a runnable edge-canonical application that correctly executes all six application flows from §8; provide `node index.js` and browser entry points.

**Status:** Not Started

### Scope

- **Application flows** (§8), all six:
  - §8.1 Parent Creates a Task: construct `TaskDefinition`, call `ScheduleComputer`, save definition + instances, schedule orchestration callbacks
  - §8.2 Reminder Trigger: load instance + definition, evaluate via `ReminderEvaluator`, send notification, update `reminderSummary` (totalSent, lastSentAt, lastDeliveryStatus, recentEvents ring buffer trim to 3), increment `clientSequence`, re-schedule persistent reminders
  - §8.3 Child Marks Task Complete: `CompletionProcessor`, save, cancel reminder handles, emit `CustomEvent("ftm:taskCompleted")`
  - §8.4 Parent Views Task Dashboard: `listTaskInstances` → `TaskListComputer` filter for pending and completed lists
  - §8.5 App Boot / Foreground Resume: `onResume` → `RecurrenceMaterializer` → save `toCreate` → re-evaluate all pending instances → dispatch missed reminders; optional parent UI notice when `skipped > 0`
  - §8.6 Parent Completes Task on Child's Behalf: `CompletionProcessor` with `completedByRole = "parent"`, save, cancel handles, emit `CustomEvent("ftm:taskCompleted")`
- **`node index.js` entry point**: initializes adapters, demonstrates / exercises flows; edge-canonical — no Node-specific APIs leak into core modules
- **Browser entry point**: same logic as Node entry; no `require()` / Node built-ins in shared modules; validated runnable in a browser without a dev server
- **Deep-link routing contract**: `ftm://instance/{instanceId}` (or hash-router equivalent) resolves to TaskInstance detail view per §9; route registration / handler stub (UI rendering deferred to Phase 5)
- **`CustomEvent("ftm:taskCompleted")` emission** on §8.3 and §8.6 completion flows
- **Offline behavior verification** (§10): all seven scenarios (no connectivity, failed notification, invalid rrule, missing `persistUntilSeconds` default, backgrounded timers, multi-day offline catch-up, concurrent edit conflict with `clientSequence` resolution per §5.1) handled correctly by the composed system

**NOT in scope:**
- UI view rendering (Task Creator form, Dashboard, Alert Modal, etc.) — Phase 5
- Tier 1–3 adapter wiring — extension points per §12

**Decisions Deferred:**
- Whether to provide a CLI interface for `node index.js` (flags, interactive prompts) or only a programmatic API surface. The SPEC specifies `node index.js` as an execution target but does not define CLI semantics. Operator decides before Phase 4 begins.
- Browser entry point delivery format (single HTML file with inline script, bundled JS module, unbundled ESM). Must remain edge-canonical (no build server required at runtime).

---

## Phase 5: UI Layer

**Goal:** Implement all parent and child UI views in compliance with the §9 data contract.

**Status:** Not Started

### Scope

- **UI data contract** (§9): UI always constructs valid JSON-LD objects (with `@context`, `@type`, `ftm:` fields) before calling any computation module; never passes raw form values directly
- **`CustomEvent("ftm:alert")` listener** on `window`: renders in-app modal when received; modal remains visible until explicitly dismissed (§7.2, §9.2)
- **Platform limitation disclosure** displayed on first notification permission request: *"Background reminders require notification permissions. Reliability when the app is closed depends on your device and browser."* (§7.2)
- **Deep-link routing**: `ftm://instance/{instanceId}` (or hash-router equivalent) navigates to TaskInstance detail view (§9)
- **Parent views (§9.1)**:
  - Task Creator — form producing `TaskDefinition`; §11 validation errors surfaced inline; schedule type toggle (one-time / recurring); reminder policy fields; `persistUntilSeconds` defaults to 86400 displayed in form
  - Task Dashboard — filterable list of all children's instances (pending / completed); `completedByRole` badge when a parent completed a task; parent override action (§8.6)
  - Task Detail — full `TaskInstance` view: `reminderSummary.totalSent`, `lastDeliveryStatus`, recent event log (up to 3 events from ring buffer)
- **Child views (§9.2)**:
  - My Tasks — list of pending `TaskInstance` objects for the authenticated child
  - Task Detail — view of a single instance with "Mark Complete" action
  - Alert Modal — rendered on `ftm:alert` event; deep-links to Task Detail; visible until dismissed

**NOT in scope:**
- Authentication / session management — not addressed in SPEC v0.2.0
- Multi-child account management beyond `User` entity support
- Extension point UIs (reward system, parent approval workflow, catchUpPolicy settings toggle) — §12
- UI framework selection is not mandated by the SPEC; Operator picks the framework

**Decisions Deferred:**
- UI framework choice (React, Vue, Svelte, plain HTML/JS, etc.) — Operator decision; must be confirmed before Phase 5 begins
- Authentication mechanism — not specified in SPEC v0.2.0; Operator must decide whether parent/child identity is hardcoded for a single-family deployment, handled by a simple local login, or deferred entirely
- Whether parent and child UIs are separate apps or route-separated views within a single app

---

## Deferred: Extension Points (§12)

The following capabilities are explicitly out of scope for all five phases. They MUST be implemented as optional adapters and MUST NOT become core dependencies.

| Capability | Notes (from §12) |
|---|---|
| Multi-device sync (CRDT) | `clientSequence` + `updatedAt` LWW fields already in place; CRDT is a stronger optional upgrade |
| Cloud persistence (Firestore, Supabase, etc.) | Swap `StateAdapter` implementation only; core is untouched |
| Tier 1 — Service Worker Push | Optional; requires SW registration; background reliability still platform-dependent |
| Tier 2 — Notification Triggers API | Optional; Chrome 80+ only; OS-scheduled |
| Tier 3 — FCM / APNs Remote Push | Out of scope for core spec; requires cloud relay function + native wrapper (Capacitor / React Native) |
| Full reminder telemetry log | All `ReminderEvent` objects beyond the 3-event in-instance ring buffer; separate key-space in state adapter |
| `catchUpPolicy` UI toggle | Expose `"all"` vs `"current-only"` as a parent preference in settings |
| Parent approval before marking complete | `ftm:requiresApproval` flag on `TaskDefinition`; `pending-approval` intermediate state in `CompletionProcessor` |
| Task reward / points system | Separate module consuming `ftm:taskCompleted` CustomEvents |
