---
category_id: cat-10
name: Type-Field-Structure Consistency
implementation_mode: deterministic
cadence: pre-routing
verification_mode: STRUCTURAL
python_predicate: subject.verification.cat_10_type_field_structure
canonical_source_keys: [interface_declarations]
ratification_status: candidacy
---

# Cat 10 Candidacy — Type-Field-Structure Consistency

Per FNSR Protocol Spec 02 §"Cat 10 Candidacy — Type-Field-Structure Consistency".

## Status: Candidacy (Phase 4 exit retro candidate #6)

Forward-tracked per Q-4-Step6-A Pass 2b corrective sub-amendment §8.4. Ratification depends on subject-project specifics; the substrate provides the framework but the canonical-interface-declaration parser is subject-project-specific (Gap A v2.8.0).

## Inputs
- Path-fence-authored fixtures' tagged objects (objects with `@type: "X"`)
- Canonical interface declarations (canonical source key: `interface_declarations`; Logic Team instance: `src/kernel/owl-types.ts` interface declarations like `SubObjectPropertyOfAxiom`, `ObjectPropertyChainAxiom`)

## Verification mode
**STRUCTURAL only.** Cat 10 verifies the OBJECT'S FIELD SHAPE matches the canonical interface declaration's field shape. Cat 10 ≠ Cat 5 (Cat 5 = does `"X"` exist as canonical @type; Cat 10 = does the X-tagged object's field shape match X's interface declaration?).

## Veto criteria
Object tagged with @type "X" has field shape diverging from the canonical interface "X" declaration → ritual veto.

## Cadence
Single (pre-routing).

## Production history
Q-4-Step6-A Miss 2 (2026-05-14) — both `regularityCheck` fixtures' rbox used `{ "@type": "SubObjectPropertyOf", subPropertyChain: { "@type": "ObjectPropertyChain", properties: [...] } }`. "SubObjectPropertyOf" exists as canonical OWL @type (Cat 5 passes); "ObjectPropertyChain" exists as canonical OWL @type (Cat 5 passes). But `src/kernel/owl-types.ts:210-214` declares `SubObjectPropertyOfAxiom` with `subProperty: string` (single IRI; NO chain field); `ObjectPropertyChainAxiom` is a top-level RBoxAxiom with `chain: string[]` plus `superProperty: string` (not nested under SubObjectPropertyOf). Field shape mismatch caused lifter `IRIFormatError` at Developer Pass 2b activation-time ritual run; Catch 6.

## Subject-project hook framework (Gap A v2.8.0)

Cat 10 requires parsing the canonical-interface declarations. The format is subject-project-specific:

- Logic Team / GraphWrite instance: TypeScript interface declarations in `src/kernel/owl-types.ts` and similar
- Other subject projects may use Rust trait declarations, Go interface declarations, OWL ontology constraint declarations, etc.

The substrate is canonical-declaration-format-neutral. The category spec references `subject.verification.cat_10_type_field_structure`, which the loader auto-resolves to the sibling `cat-10-type-field-structure.py` file in this same directory.

Per Aaron's CP2 adjudication: when v2.8.0-alpha.2 ships, the sibling `cat-10-type-field-structure.py` is a **stub** returning `status: miss, evidence.miss_class: categorical_coverage_miss, details.reason: not_implemented_for_this_subject_project`. The GraphWrite subject project later overlays this file with a real TypeScript-interface-parsing implementation. The barcode-template repo ships the stub indefinitely (template doesn't have subject-specific canonical-interface declarations to parse).

## Predicate signature (for subject-project overlays)

```python
def cat_10_type_field_structure(
    artifact: str,
    canonical_sources: dict,
    metadata: PredicateMetadata,
) -> dict:
    """Returns {status: pass|veto|miss, evidence: {...}}.

    Subject-project implementations should:
    1. Parse the canonical interface declarations from
       canonical_sources['interface_declarations']
    2. Scan the artifact for @type-tagged objects
    3. For each, verify the object's field shape matches the
       interface declaration named by @type
    """
```
