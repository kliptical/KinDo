# Roadmap

<!--
  This is your project's north star. Structure work into phases with
  explicit scope boundaries. AI agents read this at session start to
  understand what to work on and — critically — what NOT to touch.
-->

## Phase 1: Replace Identity Transform with Domain Logic

**Goal:** Replace the template's identity transform in `src/kernel/transform.ts` with domain-specific transformation rules.

**Status:** Not Started

### 1.1 Define Input/Output Contract

**Status:** Not Started | **Priority:** High

Define the JSON-LD types this service accepts and what the transformed output looks like. Document in [SPEC.md](./SPEC.md).

**Acceptance Criteria:**
- [ ] Input schema documented with required `@context` and `@type`
- [ ] Output schema documented with all derived fields
- [ ] `examples/input.jsonld` updated with a representative input
- [ ] `examples/expected-output.jsonld` updated with the expected transform result

### 1.2 Implement Transformation Rules

**Status:** Not Started | **Priority:** High

Implement the named transformation rules in `src/kernel/transform.ts`.

**Acceptance Criteria:**
- [ ] Each rule is a named pure function
- [ ] `provenance.rulesApplied` lists every rule that executed
- [ ] Missing or ambiguous fields use `UncertaintyAnnotation`
- [ ] `npm test` passes all spec tests
- [ ] `npm run test:purity` passes

### 1.3 Write Domain Tests

**Status:** Not Started | **Priority:** Medium

Write domain-specific tests following the patterns in [docs/TESTING_GUIDE.md](../docs/TESTING_GUIDE.md).

**Acceptance Criteria:**
- [ ] Test file created in `tests/` with `*.test.ts` convention
- [ ] Tests cover happy path, error cases, and uncertainty annotations
- [ ] All tests pass via `npm test`

**NOT in scope:**
- Adapters (HTTP, persistence, orchestration) — that is Phase 2
- Composition layer (Concepts, Synchronizations) — that is Phase 3
- Deployment — that is Phase 4

**Decisions Deferred:**
- Choice of JSON-LD vocabulary/context (await Orchestrator input)
- Whether to use embedded or remote contexts (see [Cookbook: Context Resolution](../docs/COOKBOOK.md#how-do-i-handle-json-ld-context-expansion))

---

## Phase 2: Build Adapters

**Goal:** Expose the kernel through infrastructure adapters.

**Status:** Not Started

<!-- Define sub-tasks when Phase 1 is complete. -->

**NOT in scope:**
- Modifying the kernel
- Adding runtime dependencies to the kernel

---

## Phase 3: Composition Layer

**Goal:** Orchestrate multiple Concepts and Synchronizations around the kernel.

**Status:** Not Started

<!-- Define sub-tasks when Phase 2 is complete. -->

---

## Phase 4: Deployment

**Goal:** Deploy the service to its target environment.

**Status:** Not Started

<!-- Define sub-tasks when Phase 3 is complete. -->
