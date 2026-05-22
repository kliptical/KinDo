# Technical Specification

<!--
  Define what your service transforms. This document is the source of truth
  for your domain logic. AI agents read this to understand what the kernel
  should do.

  The kernel contract is defined in docs/COMPUTATION_MODEL.md.
  This document defines YOUR domain within that contract.
-->

## Domain

<!-- What does this service do? One paragraph. -->

This service transforms [DESCRIBE YOUR DOMAIN] JSON-LD documents by applying [DESCRIBE YOUR RULES].

## Input Schema

The kernel accepts JSON-LD documents with the following structure:

```json
{
  "@context": "https://schema.org",
  "@type": "[YOUR TYPE]"
}
```

**Required fields:**
- `@context` — MUST be present (enforced by kernel)
- `@type` — [DESCRIBE EXPECTED TYPE(S)]

**Optional fields:**
<!-- List fields the transform can handle but doesn't require -->

## Output Schema

The kernel produces JSON-LD documents with the following structure:

```json
{
  "@context": "https://schema.org",
  "@type": "[YOUR TYPE]",
  "provenance": {
    "@type": "Provenance",
    "kernelVersion": "0.1.0",
    "rulesApplied": ["rule-1", "rule-2"]
  }
}
```

**Derived fields:**
<!-- List fields the transform adds or modifies -->

**Provenance:**
- `rulesApplied` lists every rule that executed, in order

## Transformation Rules

<!--
  Each rule should be a named pure function.
  List them in the order they execute.
-->

| # | Rule Name | Description |
|---|-----------|-------------|
| 1 | `example-rule` | Describe what this rule does |

## Error Cases

| Error Code | Condition | Behavior |
|------------|-----------|----------|
| `INVALID_INPUT` | Input is null, non-object, or array | Return error object |
| `INVALID_CONTEXT` | Missing `@context` property | Return error object |

<!-- Add domain-specific error cases -->

## Uncertainty Cases

<!--
  Fields that might be missing, ambiguous, or require human review.
  These get UncertaintyAnnotation objects in the output.
  See docs/COMPUTATION_MODEL.md for the annotation spec.
-->

| Field | Condition | Annotation Status | Reason |
|-------|-----------|-------------------|--------|
| `example` | Field is absent in input | `unknown` | Describe why |

## Context Strategy

<!--
  How does this service handle JSON-LD @context?
  See docs/COOKBOOK.md "How do I handle JSON-LD context expansion?" for options.
-->

- [ ] Embedded contexts (inline in documents)
- [ ] Pre-resolved at adapter boundary
- [ ] Static context maps
