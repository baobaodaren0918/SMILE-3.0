"""Neo4j Adapter - Parse Neo4j graph schemas to Unified Meta Schema."""
import json
import logging
import re
from typing import Dict, Any, Optional, List, Union, Tuple
from ..unified_meta_schema import (
    Database, DatabaseType, EntityType, EntityKind, Property,
    UniqueConstraint, UniqueProperty, PKTypeEnum,
    Edge, Cardinality, PrimitiveDataType, PrimitiveType,
    TypeMappings
)
from ._base import DatabaseAdapter

logger = logging.getLogger(__name__)


class Neo4jAdapter(DatabaseAdapter):
    """Adapter to parse Neo4j graph schemas and create Unified Meta Schema.

    Supported inputs:
      * JSON shape: {"nodes": [...], "relationships": [...]}
      * GraphQL SDL using @node, @relationship and @cardinality directives
    """

    TYPE_MAP = TypeMappings.NEO4J_TO_PRIMITIVE
    # NB: no REVERSE_TYPE_MAP here. Unlike the other adapters, GraphQL SDL
    # export does not map primitives via PRIMITIVE_TO_NEO4J; it uses the
    # GraphQL-scalar mapping in _graphql_type_for_property() instead
    # (Int/Float/String/Boolean/ID). PRIMITIVE_TO_NEO4J stays in TypeMappings
    # for display use in core/serialization.py.

    # Cardinality mapping: JSON string -> Cardinality enum
    CARDINALITY_MAP: Dict[str, Cardinality] = {
        "1..1": Cardinality.ONE_TO_ONE,
        "1..n": Cardinality.ONE_TO_MANY,
        "0..1": Cardinality.ZERO_TO_ONE,
        "0..n": Cardinality.ZERO_TO_MANY,
        "n..m": Cardinality.MANY_TO_MANY,
    }

    def __init__(self):
        """Initialize adapter with empty state."""
        self.database: Optional[Database] = None

    def parse(self, schema: Union[Dict[str, Any], str], db_name: str = "database") -> Database:
        """Parse Neo4j graph schema and return Database object."""
        # Auto-detect string input (canonical entry per DatabaseAdapter ABC).
        if isinstance(schema, str):
            stripped = schema.lstrip()
            if stripped.startswith("{") or stripped.startswith("["):
                schema = json.loads(stripped)
            else:
                # Non-JSON string input is treated as GraphQL SDL (the canonical
                # Neo4j schema form). Garbage input yields an empty graph database.
                return self.parse_graphql(schema, db_name)
        self.database = Database(db_name=db_name, db_type=DatabaseType.GRAPH)

        nodes = schema.get("nodes", [])
        for node_def in nodes:
            entity = self._parse_node(node_def)
            self.database.add_entity_type(entity)

        relationships = schema.get("relationships", [])
        for rel_def in relationships:
            self._parse_relationship(rel_def)

        return self.database

    def _parse_node(self, node_def: Dict[str, Any]) -> EntityType:
        """Parse a single node definition into EntityType."""
        label = node_def.get("label", "Unknown")
        primary_key = node_def.get("primary_key")
        # Normalise primary_key to a list so single-column and composite NODE KEYs
        # share the same downstream code path.
        # Accepted shapes:
        #   None       → no PK
        #   "name"     → single-column NODE KEY (legacy shape)
        #   ["a", "b"] → composite NODE KEY (matches the export-side
        #                ``REQUIRE (n.a, n.b) IS NODE KEY`` form)
        if primary_key is None:
            pk_columns: List[str] = []
        elif isinstance(primary_key, str):
            pk_columns = [primary_key]
        elif isinstance(primary_key, (list, tuple)):
            pk_columns = [str(c) for c in primary_key]
        else:
            pk_columns = []
        pk_set = set(pk_columns)

        entity = EntityType(
            object_name=[label],
            entity_kind=EntityKind.VERTEX
        )

        # Additional labels beyond the primary one (e.g. customers:Employee).
        # The GraphQL @node(labels: [...]) directive and the JSON "labels" list
        # both carry these; they would otherwise be dropped.
        extra_labels = node_def.get("labels")
        if extra_labels:
            entity.labels = list(extra_labels)

        properties = node_def.get("properties", [])
        for prop_def in properties:
            prop_name = prop_def.get("name", "")
            prop_type = prop_def.get("type", "string").lower()

            is_key = prop_name in pk_set
            data_type = self._parse_data_type(prop_type)

            attr = Property(
                name=prop_name,
                data_type=data_type,
                is_key=is_key,
                is_optional=not is_key
            )
            entity.add_property(attr)

        # Build a single UniqueConstraint with one UniqueProperty per PK column.
        # Single-column NODE KEY → 1 UniqueProperty (back-compat); composite
        # NODE KEY → N UniqueProperties on a single constraint, mirroring the
        # ``REQUIRE (n.a, n.b) IS NODE KEY`` export form.
        if pk_columns:
            unique_props = []
            for col in pk_columns:
                pk_attr = entity.get_property(col)
                if pk_attr:
                    unique_props.append(UniqueProperty(
                        primary_key_type=PKTypeEnum.NODE_KEY,
                        property_id=pk_attr.meta_id,
                    ))
            if unique_props:
                entity.add_constraint(UniqueConstraint(
                    is_primary_key=True,
                    is_managed=True,
                    unique_properties=unique_props,
                ))

        return entity

    def _parse_relationship(self, rel_def: Dict[str, Any]):
        """Parse a single relationship definition into EntityType(EDGE) and Edge."""
        rel_name = rel_def.get("type", "RELATED_TO")
        source_label = rel_def.get("source", "")
        target_label = rel_def.get("target", "")
        target_end_cardinality_str = rel_def.get("target_end_cardinality", Cardinality.ZERO_TO_MANY.value)
        target_end_cardinality = self.CARDINALITY_MAP.get(target_end_cardinality_str, Cardinality.ZERO_TO_MANY)
        source_end_cardinality_str = rel_def.get("source_end_cardinality")
        source_end_cardinality = self.CARDINALITY_MAP.get(source_end_cardinality_str) if source_end_cardinality_str else None

        edge_properties = []
        for prop_def in rel_def.get("properties", []):
            prop_name = prop_def.get("name", "")
            prop_type = prop_def.get("type", "string").lower()
            data_type = self._parse_data_type(prop_type)

            attr = Property(
                name=prop_name,
                data_type=data_type,
                is_key=False,
                is_optional=True
            )
            edge_properties.append(attr)

        edge_entity = EntityType(
            object_name=[rel_name],
            entity_kind=EntityKind.EDGE,
            source_entity=source_label,
            target_entity=target_label,
            edge_target_end_cardinality=target_end_cardinality,
            edge_source_end_cardinality=source_end_cardinality,
            properties=edge_properties
        )
        self.database.add_entity_type(edge_entity)

        source_entity = self.database.get_entity_type(source_label)
        if not source_entity:
            # ``logger.warning`` instead of ``print`` so the message goes
            # through the same logging pipeline as the rest of the project
            # (core / handlers / parser all use ``logger``). Stays out of
            # stdout, which is owned by main.py / web_server response bodies.
            logger.warning(
                "Neo4j relationship '%s': source entity '%s' not found, Edge not created",
                rel_name, source_label,
            )
        if source_entity:
            # Optionality is derived from target_end_cardinality minimum:
            # 0..1, 0..n → optional (minimum 0), 1..1, 1..n → required (minimum 1)
            is_edge_optional = target_end_cardinality in (Cardinality.ZERO_TO_ONE, Cardinality.ZERO_TO_MANY)
            edge = Edge(
                rel_type_name=rel_name,
                source_entity=source_label,
                target_entity=target_label,
                target_end_cardinality=target_end_cardinality,
                source_end_cardinality=source_end_cardinality,
                is_optional=is_edge_optional
            )
            source_entity.add_relationship(edge)

    def _parse_data_type(self, type_name: str) -> PrimitiveDataType:
        """Parse a Neo4j property type string to PrimitiveDataType."""
        primitive = self.TYPE_MAP.get(type_name, PrimitiveType.STRING)
        return PrimitiveDataType(primitive_type=primitive)

    @staticmethod
    def _strip_graphql_comments(text: str) -> str:
        lines = []
        for raw in text.splitlines():
            in_string = False
            escaped = False
            out = []
            for ch in raw:
                if ch == '"' and not escaped:
                    in_string = not in_string
                if ch == "#" and not in_string:
                    break
                out.append(ch)
                escaped = (ch == "\\" and not escaped)
                if ch != "\\":
                    escaped = False
            lines.append("".join(out))
        return "\n".join(lines)

    @staticmethod
    def _split_graphql_args(args: str) -> List[str]:
        parts: List[str] = []
        cur: List[str] = []
        depth = 0
        in_string = False
        escaped = False
        for ch in args:
            if ch == '"' and not escaped:
                in_string = not in_string
            elif not in_string:
                if ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
                elif ch == "," and depth == 0:
                    part = "".join(cur).strip()
                    if part:
                        parts.append(part)
                    cur = []
                    continue
            cur.append(ch)
            escaped = (ch == "\\" and not escaped)
            if ch != "\\":
                escaped = False
        part = "".join(cur).strip()
        if part:
            parts.append(part)
        return parts

    @classmethod
    def _parse_graphql_value(cls, value: str) -> Any:
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if not inner:
                return []
            return [cls._parse_graphql_value(p) for p in cls._split_graphql_args(inner)]
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        return value

    @classmethod
    def _parse_graphql_directive_args(cls, text: str, directive: str) -> Dict[str, Any]:
        match = re.search(rf'@{re.escape(directive)}\s*\(([^)]*)\)', text, re.DOTALL)
        if not match:
            return {}
        result: Dict[str, Any] = {}
        for part in cls._split_graphql_args(match.group(1)):
            if ":" not in part:
                continue
            key, value = part.split(":", 1)
            result[key.strip()] = cls._parse_graphql_value(value)
        return result

    @staticmethod
    def _iter_graphql_type_blocks(sdl: str) -> List[Tuple[str, str, str]]:
        blocks: List[Tuple[str, str, str]] = []
        pattern = re.compile(r'\b(type|interface)\s+(\w+)\s*([^{]*)\{([^}]*)\}', re.DOTALL)
        for match in pattern.finditer(sdl):
            blocks.append((match.group(2), match.group(3).strip(), match.group(4)))
        return blocks

    @staticmethod
    def _graphql_field_base_type(type_expr: str) -> str:
        return re.sub(r'[\[\]!\s]', '', type_expr)

    @staticmethod
    def _graphql_to_neo4j_type(type_expr: str) -> str:
        base_type = Neo4jAdapter._graphql_field_base_type(type_expr)
        return {
            "ID": "string",
            "String": "string",
            "Int": "integer",
            "Float": "double",
            "Boolean": "boolean",
            "Date": "date",
            "DateTime": "timestamp",
        }.get(base_type, "string")

    def parse_graphql(self, graphql_content: str, db_name: str = "database") -> Database:
        """Parse GraphQL SDL into a graph Database object.

        The SDL form intentionally uses a small project convention:
        @relationship carries the relationship type and target node, while
        @cardinality preserves the M-Model target/source end cardinalities
        that plain GraphQL SDL cannot represent.
        """
        self.database = Database(db_name=db_name, db_type=DatabaseType.GRAPH)
        sdl = self._strip_graphql_comments(graphql_content)
        blocks = self._iter_graphql_type_blocks(sdl)

        relationship_property_types: Dict[str, List[Dict[str, str]]] = {}
        for type_name, header, body in blocks:
            if "@relationshipProperties" not in header:
                continue
            props = []
            for raw_line in body.splitlines():
                line = raw_line.strip().rstrip(",")
                if not line or line.startswith("@"):
                    continue
                field_match = re.match(r'^(\w+)\s*:\s*([^@\s]+)', line)
                if field_match:
                    props.append({
                        "name": field_match.group(1),
                        "type": self._graphql_to_neo4j_type(field_match.group(2)),
                    })
            relationship_property_types[type_name] = props

        pending_relationships: List[Dict[str, Any]] = []
        for type_name, header, body in blocks:
            if "@relationshipProperties" in header:
                continue

            node_args = self._parse_graphql_directive_args(header, "node")
            primary_key = node_args.get("key")
            if isinstance(primary_key, list) and len(primary_key) == 1:
                primary_key = primary_key[0]

            labels = node_args.get("labels", [])
            if isinstance(labels, str):
                labels = [labels]

            properties = []
            for raw_line in body.splitlines():
                line = raw_line.strip().rstrip(",")
                if not line or line.startswith("@"):
                    continue
                field_match = re.match(r'^(\w+)\s*:\s*([^@\s]+)\s*(.*)$', line)
                if not field_match:
                    continue

                field_name = field_match.group(1)
                type_expr = field_match.group(2)
                directives = field_match.group(3)

                rel_args = self._parse_graphql_directive_args(directives, "relationship")
                if rel_args:
                    card_args = self._parse_graphql_directive_args(directives, "cardinality")
                    prop_type_name = rel_args.get("properties")
                    pending_relationships.append({
                        "type": rel_args.get("type", field_name.upper()),
                        "source": type_name,
                        "target": rel_args.get("target") or self._graphql_field_base_type(type_expr),
                        "properties": relationship_property_types.get(prop_type_name, []),
                        "target_end_cardinality": card_args.get("target", Cardinality.ZERO_TO_MANY.value),
                        "source_end_cardinality": card_args.get("source"),
                    })
                    continue

                properties.append({
                    "name": field_name,
                    "type": self._graphql_to_neo4j_type(type_expr),
                })

            entity = self._parse_node({
                "label": type_name,
                "labels": labels,
                "properties": properties,
                "primary_key": primary_key,
            })
            self.database.add_entity_type(entity)

        for rel_def in pending_relationships:
            self._parse_relationship(rel_def)

        return self.database

    @staticmethod
    def load_from_file(file_path: str, db_name: str = None) -> Database:
        """Load Neo4j graph schema from file and parse to Database."""
        from pathlib import Path

        if db_name is None:
            db_name = Path(file_path).stem

        adapter = Neo4jAdapter()

        suffix = Path(file_path).suffix.lower()
        if suffix in ('.graphql', '.gql'):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return adapter.parse_graphql(content, db_name)
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    schema = json.load(f)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON in Neo4j schema file '{file_path}': {e}")
            return adapter.parse(schema, db_name)

    @classmethod
    def _graphql_type_for_property(cls, attr: Property) -> str:
        if not isinstance(attr.data_type, PrimitiveDataType):
            return "String"
        return {
            PrimitiveType.STRING: "String",
            PrimitiveType.INTEGER: "Int",
            PrimitiveType.LONG: "Int",       # Neo4j Int is 64-bit, covers LONG
            PrimitiveType.FLOAT: "Float",
            PrimitiveType.DOUBLE: "Float",
            PrimitiveType.DECIMAL: "Float",  # no decimal scalar in GraphQL SDL
            PrimitiveType.BOOLEAN: "Boolean",
            PrimitiveType.DATE: "Date",
            PrimitiveType.TIMESTAMP: "DateTime",
        }.get(attr.data_type.primitive_type, "String")

    @staticmethod
    def _graphql_list(values: List[str]) -> str:
        return "[" + ", ".join(f'"{v}"' for v in values) + "]"

    @staticmethod
    def _relationship_field_name(rel_name: str) -> str:
        return rel_name.lower()

    @staticmethod
    def _relationship_field_type(target: str, cardinality: Cardinality) -> str:
        if cardinality in (Cardinality.ZERO_TO_MANY, Cardinality.ONE_TO_MANY, Cardinality.MANY_TO_MANY):
            return f"[{target}]"
        return target

    @classmethod
    def export_to_graphql(cls, database: Database) -> str:
        """Export Unified Meta Schema to GraphQL SDL.

        This SDL is compatible with the Neo4j GraphQL style for relationship
        fields, with an additional @cardinality directive for metadata that
        GraphQL does not define natively.
        """
        lines = [
            "# Neo4j Graph Schema",
            "# Generated by SMILE",
            "",
            "directive @node(labels: [String!], key: [String!]) on OBJECT",
            "directive @relationship(type: String!, target: String!, direction: RelationshipDirection = OUT, properties: String) on FIELD_DEFINITION",
            "directive @relationshipProperties on OBJECT",
            "directive @cardinality(target: String!, source: String) on FIELD_DEFINITION",
            "enum RelationshipDirection { OUT IN }",
            "scalar Date",
            "scalar DateTime",
        ]

        for entity in database.entity_types.values():
            if entity.entity_kind != EntityKind.EDGE or not entity.properties:
                continue
            prop_type_name = f"{entity.name}Properties"
            lines.extend(["", f"type {prop_type_name} @relationshipProperties {{"])
            for attr in entity.properties:
                lines.append(f"  {attr.name}: {cls._graphql_type_for_property(attr)}")
            lines.append("}")

        for entity in database.entity_types.values():
            if entity.entity_kind != EntityKind.VERTEX:
                continue

            pk_constraint = entity.get_primary_key()
            pk_attrs = []
            if pk_constraint and pk_constraint.unique_properties:
                for up in pk_constraint.unique_properties:
                    pk_attr = entity.get_property_by_id(up.property_id)
                    if pk_attr:
                        pk_attrs.append(pk_attr.name)

            directive_parts = []
            labels = getattr(entity, 'labels', [])
            if labels:
                directive_parts.append(f"labels: {cls._graphql_list(labels)}")
            if pk_attrs:
                directive_parts.append(f"key: {cls._graphql_list(pk_attrs)}")
            node_directive = f" @node({', '.join(directive_parts)})" if directive_parts else " @node"

            lines.extend(["", f"type {entity.name}{node_directive} {{"])
            for attr in entity.properties:
                gql_type = cls._graphql_type_for_property(attr)
                suffix = "!" if attr.is_key else ""
                lines.append(f"  {attr.name}: {gql_type}{suffix}")

            source_edges = [
                e for e in database.entity_types.values()
                if e.entity_kind == EntityKind.EDGE and e.source_entity == entity.name
            ]
            for edge in source_edges:
                target_card = edge.edge_target_end_cardinality or Cardinality.ZERO_TO_MANY
                source_card = edge.edge_source_end_cardinality
                field_type = cls._relationship_field_type(edge.target_entity, target_card)
                rel_args = [
                    f'type: "{edge.name}"',
                    f'target: "{edge.target_entity}"',
                    "direction: OUT",
                ]
                if edge.properties:
                    rel_args.append(f'properties: "{edge.name}Properties"')
                card_args = [f'target: "{target_card.value}"']
                if source_card is not None:
                    card_args.append(f'source: "{source_card.value}"')
                lines.append(
                    f"  {cls._relationship_field_name(edge.name)}: {field_type} "
                    f"@relationship({', '.join(rel_args)}) "
                    f"@cardinality({', '.join(card_args)})"
                )
            lines.append("}")

        return "\n".join(lines)

    @classmethod
    def export(cls, database: Database) -> str:
        """Convenience method that calls export_to_graphql()."""
        return cls.export_to_graphql(database)
