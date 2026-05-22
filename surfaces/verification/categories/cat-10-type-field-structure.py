"""Cat 10 — Type-Field-Structure Consistency (subject-project hook stub).

Per FNSR Spec 02 + Aaron's Gap A adjudication (CP2): the substrate ships
this stub because the canonical-interface-declaration parser is
subject-project-specific. Subject projects with TypeScript interface
declarations, Rust trait declarations, OWL ontology constraint
declarations, etc. overlay this file with a real implementation.

The barcode-template repo ships the stub indefinitely (templates have
no subject-specific canonical-interface declarations to parse). The
GraphWrite subject project later overlays with a real TypeScript-
interface-parsing implementation.

The predicate signature matches the v2.8.0-alpha.2 substrate contract:
`cat_10_type_field_structure(artifact, canonical_sources, metadata)`.
"""
from typing import Optional, Any


def cat_10_type_field_structure(
    artifact: str,
    canonical_sources: dict,
    metadata: Optional[Any] = None,
) -> dict:
    """Stub: returns categorical_coverage_miss with reason
    not_implemented_for_this_subject_project.

    Subject projects overlaying this file should implement:
      1. Parse canonical interface declarations from
         canonical_sources['interface_declarations']
      2. Scan artifact for @type-tagged objects
      3. For each, verify object field shape matches the @type's
         declared interface field shape
      4. Return {status, evidence: {...}} per the substrate contract
    """
    return {
        "status": "miss",
        "evidence": {
            "miss_class": "categorical_coverage_miss",
            "reason": "not_implemented_for_this_subject_project",
            "details": (
                "Cat 10 requires parsing the subject project's canonical "
                "interface declarations. This is the substrate stub; the "
                "subject project should overlay surfaces/verification/"
                "categories/cat-10-type-field-structure.py with a real "
                "implementation that parses its interface-declaration "
                "format (TypeScript interfaces, Rust traits, OWL ontology "
                "constraints, etc.). The barcode-template ships this stub "
                "permanently; subject projects with type-field-structure "
                "discipline overlay it."
            ),
        },
    }
