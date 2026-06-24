"""Structural invariants for the 4 native Northwind source schemas.

These guard against accidental drift of tests/northwind_*.{sql,json,graphql,cql}:
if someone edits a schema file and changes the entity / property / relationship
counts, this test fails loudly instead of silently shifting every downstream
migration's expected output. The numbers below are the agreed baseline (the
4 schemas model the same domain but are deliberately non-isomorphic).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from Schema.adapters import ADAPTER_REGISTRY
from Schema.unified_meta_schema import EntityKind
from config import NORTHWIND_SCHEMA_FILES, PRODUCT_TO_SOURCE_TYPE


# key -> (entities, properties, edge_entities, relationships)
_EXPECTED = {
    "postgresql": (8, 69, 0, 8),    # 8 tables, 8 FK references
    "mongodb":    (11, 58, 0, 11),  # 2 roots + embedded sub-docs; 11 relationships
    "neo4j":      (14, 61, 7, 7),   # 7 vertices + 7 edge entities; 7 edges
    "cassandra":  (8, 69, 0, 0),    # 8 tables, no enforced relationships
}


def _counts(db):
    ents = list(db.entity_types.values())
    return (
        len(ents),
        sum(len(e.properties) for e in ents),
        sum(1 for e in ents if e.entity_kind == EntityKind.EDGE),
        sum(len(e.relationships) for e in ents),
    )


@pytest.mark.parametrize("key", sorted(_EXPECTED))
def test_native_schema_structure_is_stable(key):
    fpath = NORTHWIND_SCHEMA_FILES[key]
    adapter = ADAPTER_REGISTRY.get(PRODUCT_TO_SOURCE_TYPE.get(key))
    assert adapter is not None, f"no adapter registered for {key}"
    db = adapter.load_from_file(str(fpath), key)
    assert _counts(db) == _EXPECTED[key], (
        f"{key} schema drifted from baseline. "
        f"got (entities, properties, edge_entities, relationships)={_counts(db)}, "
        f"expected {_EXPECTED[key]}. If this change is intentional, update _EXPECTED."
    )
