"""SMILE serialization layer — Database -> JSON-shaped dicts for the web UI / CLI."""
import json
import re
from typing import Any, Dict, List, Optional

from Schema.unified_meta_schema import (
    Cardinality,
    Database,
    EntityKind,
    Embedded,
    Edge,
    Property,
    Reference,
    TypeMappings,
    UniqueConstraint,
)
from config import (
    SOURCE_TYPE_COLUMNAR,
    SOURCE_TYPE_DOCUMENT,
    SOURCE_TYPE_GRAPH,
    SOURCE_TYPE_RELATIONAL,
)


def _get_type_str(data_type) -> str:
    """Convert a DataType (Primitive/List/Set/Map) to a short label string."""
    if hasattr(data_type, 'primitive_type'):
        return data_type.primitive_type.value
    elif hasattr(data_type, 'key_type'):
        # MapDataType — check before element_type since Map may also have element_type
        key = _get_type_str(data_type.key_type)
        val = _get_type_str(data_type.value_type)
        return f"map[{key},{val}]"
    elif hasattr(data_type, 'element_type'):
        # ListDataType / SetDataType
        element = _get_type_str(data_type.element_type)
        if type(data_type).__name__ == 'SetDataType':
            return f"set[{element}]"
        return f"array[{element}]"
    return 'unknown'


def _resolve_unique_property_name(db: Optional[Database], up_meta_id: str) -> str:
    """Resolve a ``UniqueProperty.meta_id`` reference to the property name."""
    if not db or not up_meta_id:
        return ""
    for entity in db.entity_types.values():
        for c in entity.constraints:
            if isinstance(c, UniqueConstraint):
                for up in c.unique_properties:
                    if up.meta_id == up_meta_id:
                        prop = entity.get_property_by_id(up.property_id)
                        if prop:
                            return prop.name
    return ""


def _serialize_entity(name: str, entity, db: Optional[Database] = None) -> Dict[str, Any]:
    """Serialize a single EntityType to dict (shared by db_to_dict and db_to_source_dict)."""
    constraints = []
    for c in entity.constraints:
        if c.kind == "unique":
            pk_attr_names = []
            pk_types = []
            for up in c.unique_properties:
                attr = entity.get_property_by_id(up.property_id)
                pk_attr_names.append(attr.name if attr else up.property_id)
                pk_types.append(up.primary_key_type.value)
            constraint_dict = {
                "type": "PRIMARY_KEY" if c.is_primary_key else "UNIQUE",
                "columns": pk_attr_names,
            }
            # Include primary_key_type for Cassandra PARTITION/CLUSTERING distinction
            if any(t != "simple" for t in pk_types):
                constraint_dict["primary_key_types"] = pk_types
            constraints.append(constraint_dict)
        elif c.kind == "foreign_key":
            for fkp in c.foreign_key_properties:
                attr = entity.get_property_by_id(fkp.property_id)
                col_name = attr.name if attr else fkp.property_id
                # Resolve target entity from Reference relationships matching this FK column
                ref_target = ""
                for rel in entity.relationships:
                    if isinstance(rel, Reference) and rel.ref_name == col_name:
                        ref_target = rel.get_target_entity_name()
                        break
                constraints.append({
                    "type": "FOREIGN_KEY",
                    "column": col_name,
                    "references_entity": ref_target,
                    "references_property": _resolve_unique_property_name(db, fkp.points_to_unique_property_id),
                })
        elif c.kind == "check":
            # CHECK constraint serialization. ``target`` is the anchor
            # property name (resolved from target_property_id); ``expression``
            # is the structured AST as an emit-able dict.
            anchor_attr = entity.get_property_by_id(c.target_property_id) \
                if c.target_property_id else None
            check_dict = {
                "type": "CHECK",
                "target": anchor_attr.name if anchor_attr else "",
                "expression": c.expression.to_dict() if c.expression else None,
            }
            if c.constraint_name:
                check_dict["constraint_name"] = c.constraint_name
            constraints.append(check_dict)
        elif c.kind == "existence":
            # ExistenceConstraint is a meta-model marker for "NOT NULL applied
            # post-hoc by ADD_CONSTRAINT ... AS EXISTENCE", distinct from a
            # property declared NOT NULL on creation. The adapters never
            # produce these markers when parsing source schemas — they just
            # set ``Property.is_optional = False`` on the parsed property —
            # so emitting the marker into the comparison dict would create
            # spurious Layer 1 / Layer 2 mismatches. The canonical NOT NULL
            # signal stays on ``Property.is_optional`` (already serialized in
            # the properties list), and the marker is kept in-memory only
            # so UI / tooling can distinguish post-hoc EXISTENCE from
            # declared-on-creation.
            pass

    # Build pk_type_map for Cassandra PARTITION/CLUSTERING key_type
    pk_type_map = {}
    for c in entity.constraints:
        if c.kind == "unique" and c.is_primary_key:
            for up in c.unique_properties:
                attr = entity.get_property_by_id(up.property_id)
                attr_name = attr.name if attr else up.property_id
                pk_val = up.primary_key_type.value
                if pk_val != "simple":
                    pk_type_map[attr_name] = pk_val

    serialized_attrs = []
    for a in entity.properties:
        attr_dict = {
            "name": a.name,
            "type": _get_type_str(a.data_type),
            "is_key": a.is_key,
            "is_optional": a.is_optional,
        }
        if a.name in pk_type_map:
            attr_dict["key_type"] = pk_type_map[a.name]
        serialized_attrs.append(attr_dict)

    return {
        "name": name,
        "entity_kind": entity.entity_kind.value,
        "properties": serialized_attrs,
        "constraints": constraints,
        "references": [
            {
                "name": r.ref_name,
                "target": r.get_target_entity_name(),
                "target_end_cardinality": r.target_end_cardinality.value if hasattr(r, 'target_end_cardinality') else '1..1',
                # ``is_enforced`` is emitted only when False (the non-default)
                # so that the JSON for every existing enforced Reference stays
                # byte-identical to the pre-feature serialization.
                **({"is_enforced": False} if r.is_enforced is False else {}),
                **({"edge_properties": [
                    {"name": a.name, "type": _get_type_str(a.data_type)}
                    for a in r.edge_properties
                ]} if r.edge_properties else {})
            }
            for r in entity.relationships if isinstance(r, Reference)
        ],
        "embedded": [
            {
                "name": r.aggr_name,
                "target": r.get_target_entity_name(),
                "target_end_cardinality": r.target_end_cardinality.value
            }
            for r in entity.relationships if isinstance(r, Embedded)
        ],
        "edges": [
            {
                "name": r.rel_type_name,
                "target": r.get_target_entity_name(),
                "source": r.source_entity,
                "target_end_cardinality": r.target_end_cardinality.value
            }
            for r in entity.relationships if isinstance(r, Edge)
        ],
        "labels": getattr(entity, 'labels', [])
    }


def _serialize_relationship_types(db: Database) -> Dict[str, Any]:
    """Serialize EDGE entities as relationship_types."""
    result = {}
    for name, e in db.entity_types.items():
        if e.entity_kind != EntityKind.EDGE:
            continue
        d = {
            "rel_name": e.name,
            "source_entity": e.source_entity or "",
            "target_entity": e.target_entity or "",
            "properties": [
                {"name": a.name, "type": _get_type_str(a.data_type)}
                for a in e.properties
            ],
            "target_end_cardinality": (e.edge_target_end_cardinality or Cardinality.ZERO_TO_MANY).value
        }
        if e.edge_source_end_cardinality is not None:
            d["source_end_cardinality"] = e.edge_source_end_cardinality.value
        result[name] = d
    return result


def db_to_dict(db: Database) -> Dict[str, Any]:
    """Convert Database to a JSON-serializable dict (Unified Meta Schema format)."""
    entities = {}
    for name, entity in db.entity_types.items():
        if entity.entity_kind == EntityKind.EDGE:
            continue  # EDGE entities are serialized as relationship_types
        entities[name] = _serialize_entity(name, entity, db)

    result = entities  # Keep flat entity dict for backward compatibility with web UI

    rel_types = _serialize_relationship_types(db)
    if rel_types:
        result["__relationship_types__"] = rel_types

    result["__db_meta__"] = {
        "db_name": db.db_name,
        "db_type": db.db_type.value,
    }

    return result


def _get_source_type_str(attr: Property, source_type: str) -> str:
    """Get the original native-paradigm type string for a property."""
    if not hasattr(attr.data_type, 'primitive_type'):
        if source_type == SOURCE_TYPE_RELATIONAL:
            if hasattr(attr.data_type, 'key_type'):
                return "JSONB"
            elif hasattr(attr.data_type, 'element_type'):
                return "JSONB"
            return "VARCHAR"
        elif source_type == SOURCE_TYPE_COLUMNAR:
            if hasattr(attr.data_type, 'key_type'):
                return "MAP"
            elif hasattr(attr.data_type, 'element_type'):
                return "LIST"
            return "TEXT"
        elif source_type == SOURCE_TYPE_GRAPH:
            if hasattr(attr.data_type, 'element_type'):
                return "list"
            return "string"
        elif source_type == SOURCE_TYPE_DOCUMENT:
            if hasattr(attr.data_type, 'key_type'):
                return "object"
            elif hasattr(attr.data_type, 'element_type'):
                return "array"
            return "string"
        else:
            return "unknown"

    primitive = attr.data_type.primitive_type

    if source_type == SOURCE_TYPE_RELATIONAL:
        base_type = TypeMappings.PRIMITIVE_TO_PG_DISPLAY.get(primitive, 'VARCHAR')
        if base_type == 'INTEGER' and attr.is_key:
            return 'SERIAL'
        if base_type == 'VARCHAR':
            max_len = attr.data_type.max_length if hasattr(attr.data_type, 'max_length') and attr.data_type.max_length else 255
            return f"VARCHAR({max_len})"
        if base_type == 'DECIMAL':
            precision = attr.data_type.precision if hasattr(attr.data_type, 'precision') and attr.data_type.precision else 13
            scale = attr.data_type.scale if hasattr(attr.data_type, 'scale') and attr.data_type.scale else 2
            return f"DECIMAL({precision},{scale})"
        return base_type
    elif source_type == SOURCE_TYPE_GRAPH:
        return TypeMappings.PRIMITIVE_TO_NEO4J.get(primitive, 'string')
    elif source_type == SOURCE_TYPE_COLUMNAR:
        return TypeMappings.PRIMITIVE_TO_CASSANDRA.get(primitive, 'TEXT')
    elif source_type == SOURCE_TYPE_DOCUMENT:
        return TypeMappings.PRIMITIVE_TO_MONGO_DISPLAY.get(primitive, 'string')
    else:
        return str(primitive.value) if primitive else 'unknown'


def db_to_source_dict(db: Database, source_type: str) -> Dict[str, Any]:
    """Convert Database to dict with property types in the source-paradigm's native format."""
    entities = {}
    for name, entity in db.entity_types.items():
        if entity.entity_kind == EntityKind.EDGE:
            continue
        entity_dict = _serialize_entity(name, entity, db)
        for i, a in enumerate(entity.properties):
            if i < len(entity_dict["properties"]):
                entity_dict["properties"][i]["type"] = _get_source_type_str(a, source_type)
        entities[name] = entity_dict

    rel_types = _serialize_relationship_types(db)
    if rel_types:
        entities["__relationship_types__"] = rel_types

    entities["__db_meta__"] = {
        "db_name": db.db_name,
        "db_type": db.db_type.value,
    }

    return entities


def parse_original_source(raw_source: str, source_type: str) -> Dict[str, Any]:
    """Parse raw source schema text directly into a nested tree for the UI."""
    if source_type == SOURCE_TYPE_DOCUMENT:
        # Parse MongoDB JSON schema - return nested structure for the web UI.
        # Two input shapes are supported, mirroring MongoDBAdapter.parse():
        #   * multi-root: {"collections": {name: schema, ...}}
        #   * single-root (legacy): top-level object IS the root document
        try:
            schema = json.loads(raw_source)

            def parse_properties(properties: Dict) -> List[Dict]:
                """Recursively parse properties into nested structure."""
                result = []
                for prop_name, prop_def in properties.items():
                    bson_type = prop_def.get("bsonType", "string")

                    if bson_type == "object":
                        nested_props = prop_def.get("properties", {})
                        result.append({
                            "name": prop_name,
                            "type": "object",
                            "nested": parse_properties(nested_props)
                        })
                    elif bson_type == "array":
                        items = prop_def.get("items", {})
                        item_type = items.get("bsonType", "string")
                        entry = {
                            "name": prop_name,
                            "type": "array",
                            "description": prop_def.get("description", "")
                        }
                        if item_type == "object" and "properties" in items:
                            entry["nested"] = parse_properties(items["properties"])
                        result.append(entry)
                    else:
                        result.append({
                            "name": prop_name,
                            "type": bson_type,
                            "is_key": prop_name == "_id"
                        })
                return result

            def render_collection(name: str, coll_schema: Dict) -> Dict:
                """Render one collection schema dict into the UI tree shape."""
                return {
                    "name": name,
                    "type": "collection",
                    "properties": parse_properties(coll_schema.get("properties", {})),
                }

            collections = schema.get("collections")
            if isinstance(collections, dict) and collections:
                # Multi-root: render every collection as a sibling top-level entry.
                # The frontend already iterates over the returned dict, so any
                # number of roots renders without further changes.
                out: Dict[str, Any] = {}
                for coll_name, coll_schema in collections.items():
                    inner_title = coll_schema.get("title") if isinstance(coll_schema, dict) else None
                    name = (inner_title or coll_name)
                    out[name] = render_collection(name, coll_schema)
                return out

            # Single-root (legacy): the top-level object IS the root collection.
            collection_name = schema.get("title", "document")
            return {collection_name: render_collection(collection_name, schema)}
        except json.JSONDecodeError:
            return {}

    elif source_type == SOURCE_TYPE_GRAPH:
        # Parse graph schemas through the adapter so GraphQL SDL and legacy
        # JSON render consistently in the UI.
        try:
            from Schema.adapters import Neo4jAdapter
            db = Neo4jAdapter().parse(raw_source, "source")
        except Exception:
            return {}

        result = {}
        for name, entity in db.entity_types.items():
            if entity.entity_kind == EntityKind.VERTEX:
                result[name] = {
                    "name": name,
                    "type": "vertex",
                    "properties": [
                        {"name": p.name, "type": _get_type_str(p.data_type), "is_key": p.is_key}
                        for p in entity.properties
                    ],
                }
            elif entity.entity_kind == EntityKind.EDGE:
                result[f"[{name}]"] = {
                    "name": f"{entity.source_entity} -[{name}]-> {entity.target_entity}",
                    "type": "edge",
                    "properties": [
                        {"name": p.name, "type": _get_type_str(p.data_type), "is_key": False}
                        for p in entity.properties
                    ],
                }
        return result

    elif source_type == SOURCE_TYPE_COLUMNAR:
        # Parse Cassandra CQL DDL - return table structure with key_type
        tables = {}
        cql = re.sub(r'--.*$', '', raw_source, flags=re.MULTILINE)
        cql = re.sub(r'/\*.*?\*/', '', cql, flags=re.DOTALL)
        pattern = re.compile(
            r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:[\w.]+\.)?(\w+)\s*\((.*?)\)\s*(?:WITH\s+.*?)?;',
            re.DOTALL | re.IGNORECASE
        )
        for match in pattern.finditer(cql):
            table_name = match.group(1)
            table_body = match.group(2)

            partition_keys = []
            clustering_keys = []
            pk_match = re.search(
                r'PRIMARY\s+KEY\s*\(\s*\(([^)]+)\)\s*(?:,\s*(.+))?\)',
                table_body, re.IGNORECASE
            )
            if pk_match:
                partition_keys = [k.strip() for k in pk_match.group(1).split(',')]
                if pk_match.group(2):
                    clustering_keys = [k.strip() for k in pk_match.group(2).split(',')]
            else:
                pk_simple = re.search(
                    r'PRIMARY\s+KEY\s*\(([^)]+)\)',
                    table_body, re.IGNORECASE
                )
                if pk_simple:
                    partition_keys = [pk_simple.group(1).strip()]

            attrs = []
            for col_def in table_body.split(','):
                col_def = col_def.strip()
                if not col_def or re.match(r'PRIMARY\s+KEY', col_def, re.IGNORECASE):
                    continue
                parts = col_def.split()
                if len(parts) >= 2:
                    col_name = parts[0]
                    col_type = parts[1]
                    inline_pk = 'PRIMARY KEY' in col_def.upper()
                    if inline_pk:
                        partition_keys = [col_name]

                    key_type = None
                    if col_name in partition_keys:
                        key_type = "partition"
                    elif col_name in clustering_keys:
                        key_type = "clustering"

                    attrs.append({
                        "name": col_name,
                        "type": col_type,
                        "is_key": col_name in partition_keys or col_name in clustering_keys or inline_pk,
                        "key_type": key_type
                    })
            tables[table_name] = {
                "name": table_name,
                "type": "wide_column_table",
                "properties": attrs
            }
        return tables

    elif source_type == SOURCE_TYPE_RELATIONAL:
        # Relational (PostgreSQL) - parse SQL DDL
        tables = {}
        current_table = None
        lines = raw_source.split('\n')

        for line in lines:
            line = line.strip()
            if line.upper().startswith('CREATE TABLE'):
                parts = line.split()
                if len(parts) >= 3:
                    table_name = parts[2].rstrip('(').strip()
                    current_table = table_name
                    tables[table_name] = {
                        "name": table_name,
                        "type": "table",
                        "properties": []
                    }
            elif current_table and line and not line.startswith('--') and not line.startswith(')'):
                if 'PRIMARY KEY' in line.upper() and '(' in line:
                    continue
                parts = line.rstrip(',').split()
                if len(parts) >= 2:
                    col_name = parts[0]
                    stop_keywords = {'PRIMARY', 'NOT', 'NULL', 'REFERENCES', 'DEFAULT', 'UNIQUE', 'CHECK', 'CONSTRAINT'}
                    type_parts = []
                    for p in parts[1:]:
                        if p.upper() in stop_keywords:
                            break
                        type_parts.append(p)
                    col_type = ' '.join(type_parts) if type_parts else parts[1]
                    is_key = 'PRIMARY KEY' in line.upper()
                    is_fk = 'REFERENCES' in line.upper()
                    tables[current_table]["properties"].append({
                        "name": col_name,
                        "type": col_type,
                        "is_key": is_key,
                        "is_fk": is_fk
                    })
            elif line.startswith(')'):
                current_table = None

        return tables

    else:
        return {}


__all__ = [
    'db_to_dict',
    'db_to_source_dict',
    'parse_original_source',
    # The underscore-prefixed helpers are exported because core.py and the
    # web server already reference some of them by name. They aren't part of
    # the stable public surface, but breaking those imports just to add a
    # leading underscore would force a needless API churn.
    '_serialize_entity',
    '_serialize_relationship_types',
    '_get_type_str',
    '_get_source_type_str',
    '_resolve_unique_property_name',
]
