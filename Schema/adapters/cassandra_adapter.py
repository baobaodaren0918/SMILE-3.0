"""Cassandra Adapter - Parse CQL DDL to Unified Meta Schema."""
import re
from typing import Dict, List, Optional, Tuple
from ..unified_meta_schema import (
    Database, DatabaseType, EntityType, EntityKind, Property,
    UniqueConstraint, UniqueProperty, PKTypeEnum,
    PrimitiveDataType, PrimitiveType, Cardinality, TypeMappings
)
from ._base import DatabaseAdapter


class CassandraAdapter(DatabaseAdapter):
    """Adapter to parse Cassandra CQL DDL and create Unified Meta Schema."""

    # =========================================================================
    # TYPE MAPPING (from centralized TypeMappings)
    # =========================================================================
    TYPE_MAP = TypeMappings.CASSANDRA_TO_PRIMITIVE
    REVERSE_TYPE_MAP = TypeMappings.PRIMITIVE_TO_CASSANDRA

    # =========================================================================
    # INITIALIZATION
    # =========================================================================

    def __init__(self):
        """Initialize adapter with empty state."""
        self.database: Optional[Database] = None

    # =========================================================================
    # PARSE METHODS (CQL DDL -> Unified Meta Schema)
    # =========================================================================

    def parse(self, cql_content: str, db_name: str = "database") -> Database:
        """Parse CQL DDL content and return Database object."""
        self.database = Database(db_name=db_name, db_type=DatabaseType.COLUMNAR)

        # Step 1: Remove comments (helper inherited from DatabaseAdapter)
        cql = self._remove_sql_comments(cql_content)

        # Step 2: Extract CREATE TABLE statements
        tables = self._extract_create_tables(cql)

        # Step 3: Parse each table
        for table_name, table_body, with_clause in tables:
            entity = self._parse_table(table_name, table_body, with_clause)
            self.database.add_entity_type(entity)

        return self.database

    def _extract_create_tables(self, cql: str) -> List[Tuple[str, str, str]]:
        """Extract CREATE TABLE statements from CQL DDL."""
        # Match CREATE TABLE with optional IF NOT EXISTS. The WITH clause is
        # captured in its own group (group 3) so downstream parsing can read
        # the directives it cares about (CLUSTERING ORDER BY).
        pattern = re.compile(
            r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:\w+\.)?(\w+)\s*\((.*?)\)\s*(?:WITH\s+(.*?))?;',
            re.DOTALL | re.IGNORECASE
        )
        matches = pattern.findall(cql)
        return matches

    def _parse_table(self, table_name: str, table_body: str,
                     with_clause: str = "") -> EntityType:
        """Parse a single CREATE TABLE body into EntityType."""
        entity = EntityType(
            object_name=[table_name.lower()],
            entity_kind=EntityKind.WIDE_COLUMN_TABLE
        )

        # Split by comma, but handle parentheses in type definitions and PK clauses
        columns = self._split_columns(table_body)

        # Track inline PRIMARY KEY (single column with "PRIMARY KEY" suffix)
        inline_pk_col: Optional[str] = None
        # Track table-level PRIMARY KEY clause
        table_pk_clause: Optional[str] = None

        for col_def in columns:
            col_def = col_def.strip()
            if not col_def:
                continue

            upper = col_def.upper().strip()

            # Detect table-level PRIMARY KEY clause
            # e.g., "PRIMARY KEY (user_id)" or "PRIMARY KEY ((user_id), activity_time)"
            if upper.startswith('PRIMARY KEY'):
                table_pk_clause = col_def
                continue

            # Parse column definition
            attr, is_inline_pk = self._parse_column(col_def)
            if attr:
                entity.add_property(attr)
                if is_inline_pk:
                    inline_pk_col = attr.name

        # Build primary key constraint
        if table_pk_clause:
            # Table-level PRIMARY KEY clause
            # Parse partition and clustering columns
            partition_cols, clustering_cols = self._parse_primary_key_clause(table_pk_clause)
            self._build_pk_constraint(entity, partition_cols, clustering_cols)
        elif inline_pk_col:
            # Inline PRIMARY KEY (single column)
            # e.g., "user_id UUID PRIMARY KEY"
            attr = entity.get_property(inline_pk_col)
            if attr:
                attr.is_key = True
                constraint = UniqueConstraint(
                    is_primary_key=True,
                    is_managed=True,
                    unique_properties=[UniqueProperty(
                        primary_key_type=PKTypeEnum.PARTITION,
                        property_id=attr.meta_id
                    )]
                )
                entity.add_constraint(constraint)

        # Apply CLUSTERING ORDER BY directives from the WITH clause, if any.
        # Has to happen after the PK constraint is built so the matching
        # clustering UniqueProperty already exists to attach the order to.
        if with_clause:
            self._apply_clustering_order(entity, with_clause)

        return entity

    @staticmethod
    def _apply_clustering_order(entity: EntityType, with_clause: str) -> None:
        """Read ``CLUSTERING ORDER BY (col DIR, col2 DIR2, ...)`` from a WITH"""
        m = re.search(
            r'CLUSTERING\s+ORDER\s+BY\s*\(([^)]+)\)',
            with_clause, re.IGNORECASE,
        )
        if not m:
            return

        # Map column name -> 'asc' / 'desc'
        order_map: Dict[str, str] = {}
        for part in m.group(1).split(','):
            tokens = part.strip().split()
            if not tokens:
                continue
            col_name = tokens[0]
            direction = (tokens[1].lower() if len(tokens) > 1 else 'asc')
            if direction not in ('asc', 'desc'):
                direction = 'asc'
            order_map[col_name] = direction

        if not order_map:
            return

        pk = entity.get_primary_key()
        if not pk:
            return
        for up in pk.unique_properties:
            if up.primary_key_type != PKTypeEnum.CLUSTERING:
                continue
            attr = entity.get_property_by_id(up.property_id)
            if attr and attr.name in order_map:
                up.clustering_order = order_map[attr.name]

    # ``_split_columns`` is inherited from DatabaseAdapter (shared with PostgreSQL).

    def _parse_column(self, col_def: str) -> Tuple[Optional[Property], bool]:
        """Parse a single column definition."""
        # Normalize whitespace (handle multi-line definitions)
        col_def = ' '.join(col_def.split())

        # Check for inline PRIMARY KEY
        # e.g., "user_id UUID PRIMARY KEY"
        is_inline_pk = bool(re.search(r'PRIMARY\s+KEY', col_def, re.IGNORECASE))

        # Remove PRIMARY KEY from the definition for cleaner parsing
        clean_def = re.sub(r'\s*PRIMARY\s+KEY\s*', ' ', col_def, flags=re.IGNORECASE).strip()

        # Pattern: column_name TYPE
        # Handles: "user_id UUID", "name TEXT", "value DOUBLE"
        match = re.match(r'^(\w+)\s+(\w+)', clean_def.strip(), re.IGNORECASE)

        if not match:
            return None, False

        col_name = match.group(1).lower()
        col_type = match.group(2).upper()

        # Determine data type
        data_type = self._parse_data_type(col_type)

        # is_key will be set later when building the PK constraint
        attr = Property(
            name=col_name,
            data_type=data_type,
            is_key=is_inline_pk,
            is_optional=not is_inline_pk
        )

        return attr, is_inline_pk

    def _parse_data_type(self, type_name: str) -> PrimitiveDataType:
        """Parse CQL type to PrimitiveDataType."""
        primitive = self.TYPE_MAP.get(type_name, PrimitiveType.STRING)
        return PrimitiveDataType(primitive_type=primitive)

    def _parse_primary_key_clause(self, pk_clause: str) -> Tuple[List[str], List[str]]:
        """Parse PRIMARY KEY clause into partition and clustering columns."""
        # Extract everything inside PRIMARY KEY (...)
        pk_match = re.search(r'PRIMARY\s+KEY\s*\((.+)\)', pk_clause, re.IGNORECASE)
        if not pk_match:
            return [], []

        pk_content = pk_match.group(1).strip()

        # Composite partition key has an inner ((...)) group, e.g.
        # ((part1, part2), clust1). Detect it on pk_content directly.
        inner_match = re.match(r'\((.+?)\)\s*(?:,\s*(.+))?$', pk_content)

        if inner_match:
            # Composite partition key: ((part1, part2), clust1, clust2)
            partition_str = inner_match.group(1)
            clustering_str = inner_match.group(2)

            partition_cols = [c.strip().lower() for c in partition_str.split(',')]
            clustering_cols = []
            if clustering_str:
                clustering_cols = [c.strip().lower() for c in clustering_str.split(',')]

            return partition_cols, clustering_cols
        else:
            # Simple primary key: PRIMARY KEY (col) or PRIMARY KEY (a, b, c).
            # Per CQL, the FIRST column is the partition key and the rest are
            # clustering columns. (A composite partition key requires an inner
            # ((...)) group, handled by the branch above.)
            cols = [c.strip().lower() for c in pk_content.split(',') if c.strip()]
            if not cols:
                return [], []
            return cols[:1], cols[1:]

    def _build_pk_constraint(self, entity: EntityType, partition_cols: List[str], clustering_cols: List[str]):
        """Build UniqueConstraint with PARTITION and CLUSTERING key types."""
        unique_props = []

        # Add partition key columns
        for col_name in partition_cols:
            attr = entity.get_property(col_name)
            if attr:
                attr.is_key = True
                attr.is_optional = False
                unique_props.append(UniqueProperty(
                    primary_key_type=PKTypeEnum.PARTITION,
                    property_id=attr.meta_id
                ))

        # Add clustering key columns
        for col_name in clustering_cols:
            attr = entity.get_property(col_name)
            if attr:
                attr.is_key = True
                attr.is_optional = False
                unique_props.append(UniqueProperty(
                    primary_key_type=PKTypeEnum.CLUSTERING,
                    property_id=attr.meta_id
                ))

        if unique_props:
            constraint = UniqueConstraint(
                is_primary_key=True,
                is_managed=True,
                unique_properties=unique_props
            )
            entity.add_constraint(constraint)

    @staticmethod
    def load_from_file(file_path: str, db_name: str = None) -> Database:
        """Load CQL DDL from file and parse to Database."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if db_name is None:
            from pathlib import Path
            db_name = Path(file_path).stem

        adapter = CassandraAdapter()
        return adapter.parse(content, db_name)

    # =========================================================================
    # EXPORT METHODS (Unified Meta Schema -> CQL DDL)
    # =========================================================================

    @classmethod
    def export_to_cql(cls, database: Database) -> str:
        """Export Unified Meta Schema to Cassandra CQL DDL format."""
        lines = []
        lines.append("-- Cassandra Schema")
        lines.append("-- Generated by SMILE")
        lines.append("")

        for entity in database.entity_types.values():
            ddl = cls._export_entity_to_cql(entity)
            lines.append(ddl)
            lines.append("")

        return "\n".join(lines)

    @classmethod
    def _export_entity_to_cql(cls, entity: EntityType) -> str:
        """Export a single entity to CREATE TABLE CQL format."""
        lines = []
        lines.append(f"CREATE TABLE {entity.name} (")

        columns = []

        # Process properties -> column definitions
        for attr in entity.properties:
            col_def = cls._export_property_to_column(attr)
            columns.append(f"    {col_def}")

        # Build PRIMARY KEY clause
        pk_clause = cls._build_primary_key_clause(entity)
        if pk_clause:
            columns.append(f"    {pk_clause}")

        lines.append(",\n".join(columns))

        # Emit ``WITH CLUSTERING ORDER BY (...)`` when any clustering
        # UniqueProperty carries an explicit order. CQL's own default is
        # ASC, so to keep round-trip output minimal we only emit the WITH
        # clause when at least one order is actually set (and skip it when
        # all clustering columns are None or ``asc``). Without this guard
        # every Cassandra table would gain a redundant ``WITH CLUSTERING
        # ORDER BY (... ASC)`` line, breaking byte-stable comparison
        # against schemas written without an explicit ORDER BY.
        order_by = cls._build_clustering_order_clause(entity)
        if order_by:
            lines.append(f")\nWITH {order_by};")
        else:
            lines.append(");")

        return "\n".join(lines)

    @classmethod
    def _build_clustering_order_clause(cls, entity: EntityType) -> Optional[str]:
        """Return ``CLUSTERING ORDER BY (col1 DIR, col2 DIR)`` or ``None`` when"""
        pk = entity.get_primary_key()
        if not pk:
            return None
        # Collect clustering columns with their declared order.
        clustering_entries: List[Tuple[str, str]] = []
        any_explicit = False
        for up in pk.unique_properties:
            if up.primary_key_type != PKTypeEnum.CLUSTERING:
                continue
            attr = entity.get_property_by_id(up.property_id)
            if not attr:
                continue
            order = up.clustering_order
            if order is not None:
                any_explicit = True
            clustering_entries.append((attr.name, (order or 'asc').upper()))

        if not any_explicit or not clustering_entries:
            return None
        rendered = ", ".join(f"{c} {d}" for c, d in clustering_entries)
        return f"CLUSTERING ORDER BY ({rendered})"

    @classmethod
    def _export_property_to_column(cls, attr: Property) -> str:
        """Export a property to CQL column definition."""
        cql_type = cls._get_cql_type(attr)
        return f"{attr.name} {cql_type}"

    @classmethod
    def _get_cql_type(cls, attr: Property) -> str:
        """Get CQL type string from property."""
        if not isinstance(attr.data_type, PrimitiveDataType):
            return 'TEXT'

        primitive = attr.data_type.primitive_type
        return cls.REVERSE_TYPE_MAP.get(primitive, 'TEXT')

    @classmethod
    def _build_primary_key_clause(cls, entity: EntityType) -> Optional[str]:
        """Build PRIMARY KEY clause from entity constraints."""
        pk_constraint = entity.get_primary_key()
        if not pk_constraint or not pk_constraint.unique_properties:
            return None

        partition_cols = []
        clustering_cols = []

        for up in pk_constraint.unique_properties:
            attr = entity.get_property_by_id(up.property_id)
            if not attr:
                continue

            if up.primary_key_type == PKTypeEnum.PARTITION:
                partition_cols.append(attr.name)
            elif up.primary_key_type == PKTypeEnum.CLUSTERING:
                clustering_cols.append(attr.name)
            else:
                # SIMPLE or unknown -> treat as partition key
                partition_cols.append(attr.name)

        if not partition_cols:
            return None

        partition_str = ", ".join(partition_cols)
        if clustering_cols:
            # Partition + clustering: PRIMARY KEY ((part1, part2), clust1, clust2)
            clustering_str = ", ".join(clustering_cols)
            return f"PRIMARY KEY (({partition_str}), {clustering_str})"
        if len(partition_cols) > 1:
            # Composite partition, no clustering: PRIMARY KEY ((p1, p2)).
            # Single parens here would mean "p1 partition, p2 clustering" in
            # CQL — semantically different from a composite partition.
            return f"PRIMARY KEY (({partition_str}))"
        # Single partition: PRIMARY KEY (col)
        return f"PRIMARY KEY ({partition_str})"

    @classmethod
    def export_to_cql_file(cls, database: Database, file_path: str) -> None:
        """Export to CQL file."""
        cql = cls.export_to_cql(database)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(cql)

    @classmethod
    def export(cls, database: Database) -> str:
        """Convenience method that calls export_to_cql(db)."""
        return cls.export_to_cql(database)
