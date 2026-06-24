from pathlib import Path

from Schema.adapters import Neo4jAdapter
from core import db_to_dict


ROOT = Path(__file__).parent


def _without_db_name(meta):
    meta = dict(meta)
    meta.get("__db_meta__", {}).pop("db_name", None)
    return meta


def test_graphql_export_round_trips_graph_meta():
    source_db = Neo4jAdapter.load_from_file(str(ROOT / "northwind_neo4j.graphql"), "source")
    exported = Neo4jAdapter.export(source_db)
    roundtrip_db = Neo4jAdapter().parse(exported, "roundtrip")

    assert _without_db_name(db_to_dict(roundtrip_db)) == _without_db_name(db_to_dict(source_db))
