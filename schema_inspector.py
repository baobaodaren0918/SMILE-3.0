"""Schema Inspector — Reverse Engineering interface for SMILE."""
import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from Schema.adapters import ADAPTER_REGISTRY
from config import (
    SOURCE_TYPE_RELATIONAL, SOURCE_TYPE_DOCUMENT,
    SOURCE_TYPE_GRAPH, SOURCE_TYPE_COLUMNAR,
    DB_TYPE_DISPLAY_NAME, TARGET_SCHEMA_FILES,
)

# Map file extensions to db_type for auto-detection
EXT_TO_DB_TYPE = {
    ".sql": SOURCE_TYPE_RELATIONAL,
    ".json": SOURCE_TYPE_DOCUMENT,
    ".graphql": SOURCE_TYPE_GRAPH,
    ".gql": SOURCE_TYPE_GRAPH,
    ".cql": SOURCE_TYPE_COLUMNAR,
}

# Map user-friendly type names to internal SOURCE_TYPE constants
TYPE_ALIASES = {
    "relational": SOURCE_TYPE_RELATIONAL,
    "document": SOURCE_TYPE_DOCUMENT,
    "graph": SOURCE_TYPE_GRAPH,
    "columnar": SOURCE_TYPE_COLUMNAR,
    "postgresql": SOURCE_TYPE_RELATIONAL,
    "mongodb": SOURCE_TYPE_DOCUMENT,
    "neo4j": SOURCE_TYPE_GRAPH,
    "cassandra": SOURCE_TYPE_COLUMNAR,
    "pg": SOURCE_TYPE_RELATIONAL,
    "mongo": SOURCE_TYPE_DOCUMENT,
    "cass": SOURCE_TYPE_COLUMNAR,
}


def _resolve_db_type(db_type_str: str) -> str:
    """Resolve a user-friendly type string to internal SOURCE_TYPE constant."""
    key = db_type_str.strip().lower()
    if key in TYPE_ALIASES:
        return TYPE_ALIASES[key]
    raise ValueError(
        f"Unknown db_type: '{db_type_str}'. "
        f"Valid values: {', '.join(sorted(TYPE_ALIASES.keys()))}"
    )


def _detect_db_type(file_path: str) -> str:
    """Auto-detect db_type from file extension."""
    ext = Path(file_path).suffix.lower()
    if ext in EXT_TO_DB_TYPE:
        return EXT_TO_DB_TYPE[ext]
    raise ValueError(
        f"Cannot auto-detect db_type from extension '{ext}'. "
        f"Supported: {', '.join(EXT_TO_DB_TYPE.keys())}. "
        f"Use --type to specify explicitly."
    )


def _build_summary(db) -> dict:
    """Build a summary of the Meta Schema."""
    total_attrs = 0
    total_keys = 0
    total_constraints = 0
    total_relationships = 0
    entities = []

    for name, entity in db.entity_types.items():
        attr_count = len(entity.properties)
        key_count = sum(1 for a in entity.properties if a.is_key)
        constraint_count = len(entity.constraints) if hasattr(entity, 'constraints') else 0
        rel_count = len(entity.relationships) if hasattr(entity, 'relationships') else 0

        total_attrs += attr_count
        total_keys += key_count
        total_constraints += constraint_count
        total_relationships += rel_count

        entities.append({
            "name": name,
            "entity_kind": str(entity.entity_kind.value) if hasattr(entity.entity_kind, 'value') else str(entity.entity_kind),
            "properties": attr_count,
            "keys": key_count,
            "constraints": constraint_count,
            "relationships": rel_count,
        })

    return {
        "entity_count": len(db.entity_types),
        "property_count": total_attrs,
        "key_count": total_keys,
        "constraint_count": total_constraints,
        "relationship_count": total_relationships,
        "relationship_type_count": len(db.relationship_types),
        "entities": entities,
    }


def _build_smile_template(db_type: str) -> str:
    """Generate a SMILE script template header."""
    db_label = db_type.upper()
    lines = [
        f"MIGRATION my_migration:1.0",
        f"FROM {db_label} TO <TARGET_TYPE>",
        f"USING my_schema:1",
        f"",
        f"-- Your operations here, for example:",
        f"-- RENAME_ENTITY old_name TO new_name",
        f"-- ADD_PROPERTY prop_name TO entity WITH TYPE String",
        f"-- DELETE_PROPERTY entity.prop_name",
        f"-- NEST source:field1, field2 IN parent.alias WHERE parent.fk = source.pk",
        f"-- FLATTEN entity.nested_name",
    ]
    return "\n".join(lines)


def inspect_schema(source: str, db_type: str, input_mode: str = "file",
                    db_name: str = "database") -> dict:
    """Inspect a source schema and return Meta Schema V1 as JSON."""
    # Resolve db_type
    resolved_type = _resolve_db_type(db_type)
    adapter_class = ADAPTER_REGISTRY.get(resolved_type)
    if not adapter_class:
        raise ValueError(f"No adapter found for db_type: {resolved_type}")

    adapter = adapter_class()

    # Perform Reverse Engineering — uniform DatabaseAdapter API: every adapter's
    # parse(content: str) handles its native format internally (json.loads /
    # JSON-vs-GraphQL detection / DDL parsing).
    if input_mode == "file":
        db = adapter_class.load_from_file(source, db_name)
    elif input_mode == "text":
        db = adapter.parse(source, db_name)
    else:
        raise ValueError(f"Invalid input_mode: {input_mode}. Use 'file' or 'text'.")

    return {
        "db_type": resolved_type,
        "db_type_display": DB_TYPE_DISPLAY_NAME.get(resolved_type, resolved_type),
        "meta_schema": db.to_dict(),
        "summary": _build_summary(db),
        "smile_template": _build_smile_template(resolved_type),
    }


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Schema Inspector — Reverse Engineer a schema into Meta Schema V1 (M-Model)"
    )
    parser.add_argument("--file", "-f", help="Path to schema file (.sql/.json/.graphql/.gql/.cql)")
    parser.add_argument("--type", "-t", dest="db_type",
                        help="Database type: relational, document, graph, columnar "
                             "(auto-detected from file extension if omitted)")
    parser.add_argument("--text", action="store_true",
                        help="Read schema text from stdin instead of file")
    parser.add_argument("--name", "-n", default="database",
                        help="Database name for Meta Schema (default: database)")
    parser.add_argument("--summary-only", "-s", action="store_true",
                        help="Only print summary, not full Meta Schema JSON")

    args = parser.parse_args()

    # Validate args
    if not args.file and not args.text:
        parser.error("Either --file or --text is required")

    if args.text and not args.db_type:
        parser.error("--type is required when using --text mode")

    # Determine db_type
    if args.db_type:
        db_type = args.db_type
    else:
        db_type = _detect_db_type(args.file)

    # Get source
    if args.text:
        source = sys.stdin.read()
        input_mode = "text"
    else:
        source = args.file
        input_mode = "file"

    try:
        result = inspect_schema(source, db_type, input_mode, args.name)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.summary_only:
        print(f"\n{'='*60}")
        print(f"Schema Inspector — {result['db_type_display']}")
        print(f"{'='*60}")
        summary = result["summary"]
        print(f"\nEntities: {summary['entity_count']}")
        print(f"Properties: {summary['property_count']}")
        print(f"Keys: {summary['key_count']}")
        print(f"Constraints: {summary['constraint_count']}")
        print(f"Relationships: {summary['relationship_count']}")
        print(f"Relationship Types: {summary['relationship_type_count']}")
        print(f"\n--- Entities ---")
        for e in summary["entities"]:
            print(f"  {e['name']} ({e['entity_kind']}): "
                  f"{e['properties']} attrs, {e['keys']} keys, "
                  f"{e['constraints']} constraints, {e['relationships']} rels")
        print(f"\n--- SMILE Template ---")
        print(result["smile_template"])
    else:
        # Full JSON output
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
