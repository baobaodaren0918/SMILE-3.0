"""Cassandra collection-type round-trip (list/set/map/tuple/frozen).

Regression guard for the adapter fragility found in the 2026-06-28 audit:
the old single-word type regex (``^(\\w+)\\s+(\\w+)``) and the ``TEXT``
fallback in ``_get_cql_type`` silently dropped CQL collection types. The
meta-schema already models them (ListDataType/SetDataType/MapDataType/
TupleDataType), so parse and export must now preserve them.
"""
from Schema.adapters.cassandra_adapter import CassandraAdapter
from Schema.unified_meta_schema import (
    ListDataType, SetDataType, MapDataType, TupleDataType,
    PrimitiveDataType, PrimitiveType,
)

CQL = """
CREATE TABLE catalog (
    id uuid PRIMARY KEY,
    tags list<text>,
    aliases set<text>,
    prefs map<text, int>,
    coord tuple<double, double>,
    archived frozen<list<int>>
);
"""


def _prop(entity, name):
    return entity.get_property(name)


def test_parse_collection_types():
    db = CassandraAdapter().parse(CQL, "shop")
    cat = db.get_entity_type("catalog")
    assert cat is not None

    tags = _prop(cat, "tags")
    assert isinstance(tags.data_type, ListDataType)
    assert isinstance(tags.data_type.element_type, PrimitiveDataType)
    assert tags.data_type.element_type.primitive_type == PrimitiveType.STRING

    assert isinstance(_prop(cat, "aliases").data_type, SetDataType)

    prefs = _prop(cat, "prefs").data_type
    assert isinstance(prefs, MapDataType)
    assert prefs.key_type.primitive_type == PrimitiveType.STRING
    assert prefs.value_type.primitive_type == PrimitiveType.INTEGER

    coord = _prop(cat, "coord").data_type
    assert isinstance(coord, TupleDataType)
    assert len(coord.elem_types) == 2

    # frozen<...> is unwrapped to the inner collection.
    assert isinstance(_prop(cat, "archived").data_type, ListDataType)


def test_export_emits_collection_syntax():
    db = CassandraAdapter().parse(CQL, "shop")
    out = CassandraAdapter.export(db).lower()
    assert "list<text>" in out
    assert "set<text>" in out
    assert "map<text, int>" in out
    assert "tuple<double, double>" in out


def test_collections_survive_round_trip():
    """parse -> export -> parse keeps every collection's kind (no TEXT drop)."""
    db1 = CassandraAdapter().parse(CQL, "shop")
    cql2 = CassandraAdapter.export(db1)
    db2 = CassandraAdapter().parse(cql2, "shop")
    cat = db2.get_entity_type("catalog")
    assert isinstance(_prop(cat, "tags").data_type, ListDataType)
    assert isinstance(_prop(cat, "aliases").data_type, SetDataType)
    assert isinstance(_prop(cat, "prefs").data_type, MapDataType)
    assert isinstance(_prop(cat, "coord").data_type, TupleDataType)


def test_scanner_not_truncated_by_quoted_paren_semicolon():
    """A ')' / ';' inside a single-quoted literal must not end the table body
    early. The old non-greedy `\\((.*?)\\);` regex truncated at the first ');'
    inside the literal; the quote-aware _scan_create_tables does not."""
    # The literal 'a);b' contains ');' — the exact sequence the old regex broke on.
    ddl = "CREATE TABLE t (id int, note text DEFAULT 'a);b'); CREATE TABLE u (x int);"
    tables = CassandraAdapter()._scan_create_tables(ddl)
    names = [name for name, _body, _with in tables]
    assert names == ["t", "u"], names           # both tables found, not truncated
    t_body = tables[0][1]
    assert "DEFAULT 'a);b'" in t_body            # full column survived intact
    assert "note" in t_body