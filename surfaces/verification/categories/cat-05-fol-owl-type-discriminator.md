---
category_id: cat-05
name: FOL @type vs OWL @type Discriminator Verification
implementation_mode: deterministic
cadence: pre-routing
verification_mode: STRUCTURAL
python_predicate: fnsr_daemon.cat_05_fol_owl_type_discriminator
canonical_source_keys: [fol_types, owl_types]
ratification_status: ratified
---

# Cat 5 — FOL @type vs OWL @type Discriminator Verification

Per FNSR Protocol Spec 02 §"Cat 5 — FOL @type vs OWL @type Discriminator Verification".

## Inputs
- Path-fence-authored fixtures' `@type` strings
- Canonical FOL @type set (canonical source key: `fol_types`; Logic Team instance: `src/kernel/fol-types.ts` — `fol:Implication`, `fol:Conjunction`, `fol:Disjunction`, `fol:Negation`, `fol:Universal`, `fol:Existential`, `fol:Atom`, `fol:Equality`, `fol:False`)
- Canonical OWL @type set (canonical source key: `owl_types`; Logic Team instance: `src/kernel/owl-types.ts`)

## Verification mode
**STRUCTURAL only.** Is `"@type": "X"` a member of the canonical type union? Does NOT verify the object's field structure matches the canonical interface declaration. (Cat 10 candidacy covers field-structure consistency.)

## Veto criteria
`@type` string not in canonical set → ritual veto.

## Cadence
Single (pre-routing).

## Production history
Q-4-C amendment Catch 2 — `canary_connected_with_overlap` fixture's `forbiddenPatterns[0]` used `"@type": "fol:Biconditional"` which does NOT exist in canonical FOL @type set. Corrected to reverse-direction `fol:Implication` pattern per ADR-007 §4 decomposition convention. Second production catch in engagement.

## Implementation note
The predicate scans the artifact text for `"@type"\s*:\s*"X"` patterns. The canonical type sets are extracted from the canonical source texts; Logic Team's instances use TypeScript string-literal unions (`type FolType = "fol:Implication" | "fol:Conjunction" | ...`). The predicate accepts any `@type` value that appears in EITHER canonical set (FOL union OWL). Returns `evidence` listing all cited `@type` values, with which are matched vs unmatched.

## Gap candidacy
This category is STRUCTURAL only on the `@type` string. The field-structure-consistency gap — does the object's field shape match the canonical interface declaration for `@type` X? — is **Cat 10 candidacy** (see `cat-10-type-field-structure.md` in v2.8.0 Checkpoint 2).
