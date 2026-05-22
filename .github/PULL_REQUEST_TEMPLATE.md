## Summary

<!-- Brief description of what this PR does and why. -->

## Spec Test Checklist

- [ ] `npm run build` succeeds with no TypeScript errors
- [ ] `npm test` passes all three spec tests (determinism, no-network, snapshot)
- [ ] `npm run test:purity` passes the kernel isolation check
- [ ] No new runtime dependencies added
- [ ] `examples/expected-output.jsonld` updated if transform output changed

## Architecture Compliance

- [ ] Kernel code contains no I/O operations
- [ ] All input/output uses JSON-LD format (`@context` required)
- [ ] Determinism is preserved
- [ ] No imports from outside `src/kernel/` in kernel files

## Adversarial Review

<!-- Before merging, adopt the Cynical Auditor perspective (see CLAUDE.md). -->

- [ ] No scope creep — changes are limited to what was requested
- [ ] No unnecessary abstractions or premature generalization
- [ ] No hidden non-determinism (time, randomness, environment)
- [ ] No silent failures — errors are surfaced, not swallowed
- [ ] Kernel boundary is intact — no adapter logic leaked into Layer 0

## Changes

<!-- List the key changes made in this PR. -->

-
