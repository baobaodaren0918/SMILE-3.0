"""Neo4j Adapter - Parse Neo4j Graph JSON Schema to Unified Meta Schema."""
import json
import logging
import re
from typing import Dict, Any, Optional, List, Union
from ..unified_meta_schema import (
    Database, DatabaseType, EntityType, EntityKind, Property,
    UniqueConstraint, UniqueProperty, PKTypeEnum,
    Edge, Cardinality, PrimitiveDataType, PrimitiveType,
    TypeMappings
)
from ._base import DatabaseAdapter

logger = logging.getLogger(__name__)


class Neo4jAdapter(DatabaseAdapter):
    """Adapter to parse Neo4j graph schema JSON and create Unified Meta Schema."""

    # =========================================================================
    # TYPE MAPPING (from centralized TypeMappings)
    # =========================================================================
    TYPE_MAP = TypeMappings.NEO4J_TO_PRIMITIVE
    REVERSE_TYPE_MAP = TypeMappings.PRIMITIVE_TO_NEO4J

    # Cardinality mapping: JSON string -> Cardinality enum
    CARDINALITY_MAP: Dict[str, Cardinality] = {
        "1..1": Cardinality.ONE_TO_ONE,
        "1..n": Cardinality.ONE_TO_MANY,
        "0..1": Cardinality.ZERO_TO_ONE,
        "0..n": Cardinality.ZERO_TO_MANY,
    }

    # =========================================================================
    # INITIALIZATION
    # =========================================================================

    def __init__(self):
        """Initialize adapter with empty state."""
        self.database: Optional[Database] = None

    # =========================================================================
    # PARSE METHODS (JSON -> Unified Meta Schema)
    # =========================================================================

    def parse(self, schema: Union[Dict[str, Any], str], db_name: str = "database") -> Database:
        """Parse Neo4j graph schema and return Database object."""
        # Auto-detect string input (canonical entry per DatabaseAdapter ABC).
        if isinstance(schema, str):
            stripped = schema.lstrip()
            if stripped.startswith("{") or stripped.startswith("["):
                schema = json.loads(stripped)
            else:
                return self.parse_cypher(schema, db_name)
        self.database = Database(db_name=db_name, db_type=DatabaseType.GRAPH)

        # Step 1: Parse nodes -> EntityType with entity_kind=VERTEX
        nodes = schema.get("nodes", [])
        for node_def in nodes:
            entity = self._parse_node(node_def)
            self.database.add_entity_type(entity)

        # Step 2: Parse relationships -> EntityType(EDGE) + Edge
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
        # The Cypher block path sets this after the call; the JSON path carries
        # them in a "labels" list and would otherwise drop them.
        extra_labels = node_def.get("labels")
        if extra_labels:
            entity.labels = list(extra_labels)

        # Parse properties -> Property objects
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

        # Parse relationship properties -> Property objects
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

        # Create EDGE EntityType (schema-level definition)
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

        # Create Edge on source entity's relationships list
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

    # =========================================================================
    # CYPHER DDL PARSING
    # =========================================================================

    def parse_cypher(self, cypher_content: str, db_name: str = "database") -> Database:
        """Parse Neo4j Cypher DDL text and return Database object."""
        self.database = Database(db_name=db_name, db_type=DatabaseType.GRAPH)

        lines = cypher_content.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Parse node blocks: "// Node: <Label>" or "// Node: <Label>:<Extra1>:<Extra2>"
            node_match = re.match(r'^// Node:\s+([\w:]+)', line)
            if node_match:
                label_str = node_match.group(1)
                label_parts = label_str.split(':')
                label = label_parts[0]
                extra_labels = label_parts[1:] if len(label_parts) > 1 else []
                primary_key = None
                properties = []

                # Look ahead for Key/CREATE CONSTRAINT and Properties
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()

                    # // Key: <field> (comment-based format)
                    key_match = re.match(r'^// Key:\s+(\w+)', next_line)
                    if key_match:
                        primary_key = key_match.group(1)
                        j += 1
                        continue

                    # CREATE CONSTRAINT ... REQUIRE n.<field> IS UNIQUE/NODE KEY (executable format)
                    # Single-column form. Symmetric to the export side that
                    # writes ``REQUIRE n.<field> IS NODE KEY`` for length-1 PKs.
                    constraint_match = re.match(
                        r'CREATE CONSTRAINT .+ FOR \(n:[\w:]+\) REQUIRE n\.(\w+) IS (?:UNIQUE|NODE KEY);',
                        next_line
                    )
                    if constraint_match:
                        primary_key = constraint_match.group(1)
                        j += 1
                        continue

                    # Composite NODE KEY: REQUIRE (n.a, n.b) IS NODE KEY.
                    # Round-trip counterpart of the export side at line ~568:
                    # ``REQUIRE (n.<col1>, n.<col2>) IS NODE KEY``.
                    composite_match = re.match(
                        r'CREATE CONSTRAINT .+ FOR \(n:[\w:]+\) REQUIRE \(([^)]+)\) IS NODE KEY;',
                        next_line
                    )
                    if composite_match:
                        # Inner list: "n.col1, n.col2" → strip the "n." prefix.
                        cols = []
                        for part in composite_match.group(1).split(','):
                            part = part.strip()
                            if part.startswith('n.'):
                                cols.append(part[2:])
                            else:
                                cols.append(part)
                        # Pass the list onwards as primary_key; _parse_node
                        # accepts both str and list-of-str for primary_key.
                        primary_key = cols
                        j += 1
                        continue

                    # // Properties: field1 (type), field2 (type)
                    props_match = re.match(r'^// Properties:\s+(.+)', next_line)
                    if props_match:
                        props_str = props_match.group(1)
                        for prop in re.findall(r'(\w+)\s+\((\w+)\)', props_str):
                            properties.append({"name": prop[0], "type": prop[1]})
                        j += 1
                        break  # Properties line ends the node block

                    # Empty line or next block -> end of this node
                    if next_line == '' or next_line.startswith('// Node:') or next_line.startswith('// Relationship:'):
                        break
                    j += 1

                # Build node definition and parse it
                node_def = {
                    "label": label,
                    "properties": properties,
                    "primary_key": primary_key
                }
                entity = self._parse_node(node_def)
                entity.labels = extra_labels
                self.database.add_entity_type(entity)
                i = j
                continue

            # Parse relationship blocks: "// Relationship: <NAME> (<Source> -> <Target>)"
            rel_match = re.match(r'^// Relationship:\s+(\w+)\s+\((\w+)\s+->\s+(\w+)\)', line)
            if rel_match:
                rel_name = rel_match.group(1)
                source_label = rel_match.group(2)
                target_label = rel_match.group(3)
                rel_properties = []
                target_end_cardinality_str = Cardinality.ZERO_TO_MANY.value
                source_end_cardinality_str = None

                # Cardinality and Source-Cardinality may appear on consecutive
                # lines, so consume both and stop only at an empty line or a
                # new Node/Relationship block.
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()

                    props_match = re.match(r'^// Properties:\s+(.+)', next_line)
                    if props_match:
                        props_str = props_match.group(1)
                        for prop in re.findall(r'(\w+)\s+\((\w+)\)', props_str):
                            rel_properties.append({"name": prop[0], "type": prop[1]})
                        j += 1
                        continue

                    card_match = re.match(r'^// Cardinality:\s+(.+)', next_line)
                    if card_match:
                        target_end_cardinality_str = card_match.group(1).strip()
                        j += 1
                        continue

                    source_card_match = re.match(r'^// Source-Cardinality:\s+(.+)', next_line)
                    if source_card_match:
                        source_end_cardinality_str = source_card_match.group(1).strip()
                        j += 1
                        continue

                    # Empty line or next block -> end
                    if next_line == '' or next_line.startswith('// Node:') or next_line.startswith('// Relationship:'):
                        break
                    j += 1

                # Build relationship definition and parse it
                rel_def = {
                    "type": rel_name,
                    "source": source_label,
                    "target": target_label,
                    "properties": rel_properties,
                    "target_end_cardinality": target_end_cardinality_str,
                    "source_end_cardinality": source_end_cardinality_str,
                }
                self._parse_relationship(rel_def)
                i = j
                continue

            i += 1

        return self.database

    # =========================================================================
    # LOAD FROM FILE
    # =========================================================================

    @staticmethod
    def load_from_file(file_path: str, db_name: str = None) -> Database:
        """Load Neo4j graph schema from file and parse to Database."""
        from pathlib import Path

        if db_name is None:
            db_name = Path(file_path).stem

        adapter = Neo4jAdapter()

        if file_path.endswith('.cypher'):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return adapter.parse_cypher(content, db_name)
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    schema = json.load(f)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON in Neo4j schema file '{file_path}': {e}")
            return adapter.parse(schema, db_name)

    # =========================================================================
    # EXPORT METHODS (Unified Meta Schema -> Cypher DDL)
    # =========================================================================

    @classmethod
    def export_to_cypher(cls, database: Database) -> str:
        """Export Unified Meta Schema to Neo4j Cypher DDL format."""
        lines = []
        lines.append("// Neo4j Graph Schema")
        lines.append("// Generated by SMILE")

        # Export node entities (VERTEX kind only)
        for entity in database.entity_types.values():
            if entity.entity_kind == EntityKind.VERTEX:
                lines.append("")
                node_lines = cls._export_node(entity)
                lines.extend(node_lines)

        # Export relationship types (EDGE entities)
        for entity in database.entity_types.values():
            if entity.entity_kind == EntityKind.EDGE:
                lines.append("")
                rel_lines = cls._export_relationship(entity)
                lines.extend(rel_lines)

        return "\n".join(lines)

    @classmethod
    def _export_node(cls, entity: EntityType) -> List[str]:
        """Export a single node entity to Cypher constraint and property comments."""
        lines = []
        label = entity.name
        # Include additional labels (e.g. customers:Employee)
        extra_labels = getattr(entity, 'labels', [])
        label_display = label + (''.join(f':{l}' for l in extra_labels) if extra_labels else '')
        lines.append(f"// Node: {label_display}")

        # Generate constraint for primary key property(s)
        pk_constraint = entity.get_primary_key()
        if pk_constraint and pk_constraint.unique_properties:
            pk_attrs = []
            for up in pk_constraint.unique_properties:
                pk_attr = entity.get_property_by_id(up.property_id)
                if pk_attr:
                    pk_attrs.append(pk_attr.name)
            if len(pk_attrs) == 1:
                # Native ground-truth files use the ``// Key: <field>`` comment
                # form rather than an executable ``CREATE CONSTRAINT``. The
                # parser at ``_parse_node_block`` already accepts both, so
                # exporting comments keeps round-trip intact while aligning
                # with the project's chosen Cypher style.
                lines.append(f"// Key: {pk_attrs[0]}")
            elif len(pk_attrs) > 1:
                constraint_name = f"{label.lower()}_pk"
                props = ", ".join(f"n.{a}" for a in pk_attrs)
                lines.append(
                    f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS "
                    f"FOR (n:{label_display}) REQUIRE ({props}) IS NODE KEY;"
                )

        # Generate property comment listing all properties with types
        if entity.properties:
            prop_strs = []
            for attr in entity.properties:
                type_str = cls.REVERSE_TYPE_MAP.get(
                    attr.data_type.primitive_type, "string"
                ) if isinstance(attr.data_type, PrimitiveDataType) else "string"
                prop_strs.append(f"{attr.name} ({type_str})")
            lines.append(f"// Properties: {', '.join(prop_strs)}")

        return lines

    @classmethod
    def _export_relationship(cls, edge_entity: EntityType) -> List[str]:
        """Export a single EDGE entity type to Cypher comments."""
        lines = []
        lines.append(
            f"// Relationship: {edge_entity.name} "
            f"({edge_entity.source_entity} -> {edge_entity.target_entity})"
        )

        # List relationship properties if any
        if edge_entity.properties:
            prop_strs = []
            for attr in edge_entity.properties:
                type_str = cls.REVERSE_TYPE_MAP.get(
                    attr.data_type.primitive_type, "string"
                ) if isinstance(attr.data_type, PrimitiveDataType) else "string"
                prop_strs.append(f"{attr.name} ({type_str})")
            lines.append(f"// Properties: {', '.join(prop_strs)}")

        # Cardinality comment
        target_end_cardinality = edge_entity.edge_target_end_cardinality or Cardinality.ZERO_TO_MANY
        lines.append(f"// Cardinality: {target_end_cardinality.value}")

        if edge_entity.edge_source_end_cardinality is not None:
            lines.append(f"// Source-Cardinality: {edge_entity.edge_source_end_cardinality.value}")

        return lines

    @classmethod
    def export(cls, database: Database) -> str:
        """Convenience method that calls export_to_cypher()."""
        return cls.export_to_cypher(database)

    @classmethod
    def export_to_cypher_file(cls, database: Database, file_path: str) -> None:
        """Export to Cypher DDL file."""
        cypher = cls.export_to_cypher(database)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(cypher)
