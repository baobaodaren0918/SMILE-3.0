# Unified Meta Schema - Supports: PostgreSQL, MongoDB, Neo4j, Cassandra
# Based on AC's meta_model design with extensions

import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar, Dict, List, Optional, Any, Union

logger = logging.getLogger(__name__)


# ENUMS

class DatabaseType(str, Enum):
    """Abstract database model types (not product-specific)."""
    RELATIONAL = "relational"   # PostgreSQL, MySQL, Oracle, SQL Server...
    DOCUMENT = "document"       # MongoDB, CouchDB, DocumentDB, Firestore...
    GRAPH = "graph"             # Neo4j, ArangoDB, JanusGraph, TigerGraph...
    COLUMNAR = "columnar"       # Cassandra, HBase, ScyllaDB, ClickHouse...


class EntityKind(str, Enum):
    TABLE = "table"                       # Standard relational table
    DOCUMENT = "document"                 # Top-level collection document (root entity)
    EMBEDDED = "embedded"                 # Nested/embedded document (non-root entity)
    VERTEX = "vertex"                     # Graph node (also called "Node")
    EDGE = "edge"                         # Graph relationship/edge
    WIDE_COLUMN_TABLE = "wide_column_table"  # Cassandra table with partition/clustering keys


class PrimitiveType(str, Enum):
    STRING = "string"
    TEXT = "text"
    INTEGER = "integer"
    LONG = "long"
    DOUBLE = "double"
    FLOAT = "float"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    TIMESTAMP = "timestamp"  # Use TIMESTAMP for datetime (DATETIME removed as duplicate)
    UUID = "uuid"
    BINARY = "binary"
    NULL = "null"
    OBJECT_ID = "objectId"
    INT32 = "int32"
    INT64 = "int64"
    DECIMAL128 = "decimal128"


class PKTypeEnum(str, Enum):
    """Primary key type for different database systems (from AC)."""
    SIMPLE = "simple"           # Relational PRIMARY KEY
    PARTITION = "partition"     # Cassandra partition key
    CLUSTERING = "clustering"   # Cassandra clustering key
    NODE_KEY = "node_key"       # Neo4j NODE KEY
    DOCUMENT_ID = "document_id" # MongoDB DOCUMENT_ID


class Cardinality(str, Enum):
    ZERO_TO_ONE = "0..1"    # Optional, at most one
    ONE_TO_ONE = "1..1"     # Required, exactly one
    ZERO_TO_MANY = "0..n"   # Optional, unlimited
    ONE_TO_MANY = "1..n"    # Required, at least one
    MANY_TO_MANY = "n..m"   # Many on both ends (uncommon; M:N relationships
                            # are normally resolved via a junction/edge/embedding)

    @classmethod
    def from_symbol(cls, s: str) -> 'Cardinality':
        mapping = {
            "?": cls.ZERO_TO_ONE, "0..1": cls.ZERO_TO_ONE,
            "&": cls.ONE_TO_ONE, "1..1": cls.ONE_TO_ONE,
            "*": cls.ZERO_TO_MANY, "0..n": cls.ZERO_TO_MANY,
            "+": cls.ONE_TO_MANY, "1..n": cls.ONE_TO_MANY,
            "n..m": cls.MANY_TO_MANY
        }
        return mapping.get(s, cls.ONE_TO_ONE)

    def to_bounds(self) -> tuple:
        """Returns (min, max) bounds. -1 means unlimited."""
        return {
            self.ZERO_TO_ONE: (0, 1),
            self.ONE_TO_ONE: (1, 1),
            self.ZERO_TO_MANY: (0, -1),
            self.ONE_TO_MANY: (1, -1),
            self.MANY_TO_MANY: (0, -1)
        }[self]

    def is_multiple(self) -> bool:
        return self in (self.ZERO_TO_MANY, self.ONE_TO_MANY, self.MANY_TO_MANY)

    def is_required(self) -> bool:
        return self in (self.ONE_TO_ONE, self.ONE_TO_MANY)


# SMILE STRING <-> META ENUM MAPPINGS
# Translate SMILE-script literals into meta-model enum values. Centralized here
# so that the transformer, validators, and any future consumer share one
# canonical vocabulary instead of reaching into SchemaTransformer or cloning
# the mappings.

CARDINALITY_MAP: Dict[str, Cardinality] = {
    "ONE_TO_ONE": Cardinality.ONE_TO_ONE,
    "ONE_TO_MANY": Cardinality.ONE_TO_MANY,
    "ZERO_TO_ONE": Cardinality.ZERO_TO_ONE,
    "ZERO_TO_MANY": Cardinality.ZERO_TO_MANY,
    "MANY_TO_MANY": Cardinality.MANY_TO_MANY,
}

KEY_TYPE_MAP: Dict[str, Any] = {
    "PRIMARY": "primary",
    "UNIQUE": "unique",
    "PARTITION": PKTypeEnum.PARTITION,
    "CLUSTERING": PKTypeEnum.CLUSTERING,
}

TYPE_STR_MAP: Dict[str, PrimitiveType] = {
    "STRING": PrimitiveType.STRING, "TEXT": PrimitiveType.TEXT,
    "INT": PrimitiveType.INTEGER, "INTEGER": PrimitiveType.INTEGER,
    "LONG": PrimitiveType.LONG, "DOUBLE": PrimitiveType.DOUBLE,
    "FLOAT": PrimitiveType.FLOAT, "DECIMAL": PrimitiveType.DECIMAL,
    "BOOLEAN": PrimitiveType.BOOLEAN, "DATE": PrimitiveType.DATE,
    "TIMESTAMP": PrimitiveType.TIMESTAMP,
    "UUID": PrimitiveType.UUID, "BINARY": PrimitiveType.BINARY,
    "DATETIME": PrimitiveType.TIMESTAMP,
}


# TYPE MAPPINGS

# DatabaseType -> TypeMappings PRIMITIVE_TO_* dict (single source of truth)
_NATIVE_TYPE_REGISTRY: Dict[DatabaseType, Dict] = {}  # populated after TypeMappings class


def _get_native_type(ptype: PrimitiveType, db: DatabaseType) -> str:
    """Get native type string from PrimitiveType, using TypeMappings as single source."""
    return _NATIVE_TYPE_REGISTRY[db].get(ptype, 'VARCHAR')


# ADAPTER TYPE MAPPINGS (Centralized)
# These mappings are used by adapters for parsing and exporting schemas.
# All adapters should import these from here to avoid duplication.

class TypeMappings:
    """Centralized type mappings for all database adapters."""

    # -------------------------------------------------------------------------
    # PostgreSQL Mappings
    # -------------------------------------------------------------------------
    # SQL type string -> PrimitiveType (for parsing DDL)
    POSTGRESQL_TO_PRIMITIVE = {
        # Auto-increment types
        'SERIAL': PrimitiveType.INTEGER,
        'BIGSERIAL': PrimitiveType.LONG,
        # Integer types
        'INTEGER': PrimitiveType.INTEGER,
        'INT': PrimitiveType.INTEGER,
        'BIGINT': PrimitiveType.LONG,
        'SMALLINT': PrimitiveType.INTEGER,
        # Decimal types
        'DECIMAL': PrimitiveType.DECIMAL,
        'NUMERIC': PrimitiveType.DECIMAL,
        'REAL': PrimitiveType.FLOAT,
        'DOUBLE PRECISION': PrimitiveType.DOUBLE,
        'FLOAT': PrimitiveType.FLOAT,
        # String types
        'VARCHAR': PrimitiveType.STRING,
        'CHAR': PrimitiveType.STRING,
        'TEXT': PrimitiveType.TEXT,
        # Boolean
        'BOOLEAN': PrimitiveType.BOOLEAN,
        'BOOL': PrimitiveType.BOOLEAN,
        # Date/Time types
        'DATE': PrimitiveType.DATE,
        'TIMESTAMP': PrimitiveType.TIMESTAMP,
        'TIME': PrimitiveType.TIMESTAMP,
        # Other types
        'UUID': PrimitiveType.UUID,
        'BYTEA': PrimitiveType.BINARY,
        'JSON': PrimitiveType.STRING,
        'JSONB': PrimitiveType.STRING,
    }

    # PrimitiveType -> SQL type string (for exporting DDL)
    PRIMITIVE_TO_POSTGRESQL = {
        PrimitiveType.INTEGER: 'INTEGER',
        PrimitiveType.LONG: 'BIGINT',
        PrimitiveType.STRING: 'VARCHAR',
        PrimitiveType.TEXT: 'TEXT',
        PrimitiveType.DECIMAL: 'DECIMAL',
        PrimitiveType.FLOAT: 'REAL',
        PrimitiveType.DOUBLE: 'DOUBLE PRECISION',
        PrimitiveType.BOOLEAN: 'BOOLEAN',
        PrimitiveType.DATE: 'DATE',
        PrimitiveType.TIMESTAMP: 'TIMESTAMP',
        PrimitiveType.UUID: 'UUID',
        PrimitiveType.BINARY: 'BYTEA',
        PrimitiveType.OBJECT_ID: 'VARCHAR',
        PrimitiveType.INT32: 'INTEGER',
        PrimitiveType.INT64: 'BIGINT',
        PrimitiveType.DECIMAL128: 'DECIMAL',
        PrimitiveType.NULL: 'VARCHAR',
    }

    # -------------------------------------------------------------------------
    # MongoDB Mappings
    # -------------------------------------------------------------------------
    # BSON type string -> PrimitiveType (for parsing JSON Schema)
    MONGODB_TO_PRIMITIVE = {
        'string': PrimitiveType.STRING,
        'int': PrimitiveType.INTEGER,
        'long': PrimitiveType.LONG,
        'double': PrimitiveType.DOUBLE,
        'decimal': PrimitiveType.DECIMAL,
        'bool': PrimitiveType.BOOLEAN,
        'date': PrimitiveType.DATE,
        'timestamp': PrimitiveType.TIMESTAMP,
        'objectId': PrimitiveType.OBJECT_ID,
        'binData': PrimitiveType.BINARY,
        'null': PrimitiveType.NULL,
    }

    # PrimitiveType -> BSON type string (for exporting JSON Schema)
    PRIMITIVE_TO_MONGODB = {
        PrimitiveType.STRING: 'string',
        PrimitiveType.INTEGER: 'int',
        PrimitiveType.LONG: 'long',
        PrimitiveType.DOUBLE: 'double',
        PrimitiveType.DECIMAL: 'decimal',
        PrimitiveType.FLOAT: 'double',
        PrimitiveType.BOOLEAN: 'bool',
        PrimitiveType.DATE: 'date',
        PrimitiveType.TIMESTAMP: 'timestamp',
        PrimitiveType.BINARY: 'binData',
        PrimitiveType.UUID: 'string',
        PrimitiveType.NULL: 'null',
        PrimitiveType.TEXT: 'string',
        PrimitiveType.OBJECT_ID: 'objectId',
        PrimitiveType.INT32: 'int',
        PrimitiveType.INT64: 'long',
        PrimitiveType.DECIMAL128: 'decimal',
    }

    # -------------------------------------------------------------------------
    # Neo4j Mappings
    # -------------------------------------------------------------------------
    # JSON type string -> PrimitiveType (for parsing graph schema JSON)
    NEO4J_TO_PRIMITIVE = {
        'string':    PrimitiveType.STRING,
        'integer':   PrimitiveType.INTEGER,
        'int':       PrimitiveType.INTEGER,
        'long':      PrimitiveType.LONG,
        'double':    PrimitiveType.DOUBLE,
        'float':     PrimitiveType.FLOAT,
        'boolean':   PrimitiveType.BOOLEAN,
        'date':      PrimitiveType.DATE,
        'timestamp': PrimitiveType.TIMESTAMP,
        'uuid':      PrimitiveType.UUID,
    }

    # PrimitiveType -> Neo4j type string (for exporting GraphQL SDL)
    PRIMITIVE_TO_NEO4J = {
        PrimitiveType.STRING:    'string',
        PrimitiveType.TEXT:      'string',
        PrimitiveType.INTEGER:   'integer',
        PrimitiveType.LONG:      'long',
        PrimitiveType.DOUBLE:    'double',
        PrimitiveType.FLOAT:     'float',
        PrimitiveType.BOOLEAN:   'boolean',
        PrimitiveType.DATE:      'date',
        PrimitiveType.TIMESTAMP: 'timestamp',
        PrimitiveType.UUID:      'uuid',
        PrimitiveType.DECIMAL:   'double',
        PrimitiveType.BINARY:    'string',
        PrimitiveType.NULL:      'string',
        PrimitiveType.OBJECT_ID: 'string',
        PrimitiveType.INT32:     'integer',
        PrimitiveType.INT64:     'long',
        PrimitiveType.DECIMAL128: 'double',
    }

    # -------------------------------------------------------------------------
    # Cassandra Mappings
    # -------------------------------------------------------------------------
    # CQL type string -> PrimitiveType (for parsing CQL DDL)
    CASSANDRA_TO_PRIMITIVE = {
        # String types
        'TEXT': PrimitiveType.STRING,
        'VARCHAR': PrimitiveType.STRING,
        'ASCII': PrimitiveType.STRING,
        # Integer types
        'INT': PrimitiveType.INTEGER,
        'SMALLINT': PrimitiveType.INTEGER,
        'TINYINT': PrimitiveType.INTEGER,
        'VARINT': PrimitiveType.INTEGER,
        # Long types
        'BIGINT': PrimitiveType.LONG,
        'COUNTER': PrimitiveType.LONG,
        # Floating point
        'DOUBLE': PrimitiveType.DOUBLE,
        'FLOAT': PrimitiveType.FLOAT,
        'DECIMAL': PrimitiveType.DECIMAL,
        # Boolean
        'BOOLEAN': PrimitiveType.BOOLEAN,
        # Date/Time
        'DATE': PrimitiveType.DATE,
        'TIMESTAMP': PrimitiveType.TIMESTAMP,
        # UUID
        'UUID': PrimitiveType.UUID,
        'TIMEUUID': PrimitiveType.UUID,
        # Binary
        'BLOB': PrimitiveType.BINARY,
    }

    # PrimitiveType -> CQL type string (for exporting CQL DDL)
    PRIMITIVE_TO_CASSANDRA = {
        PrimitiveType.STRING:    'TEXT',
        PrimitiveType.TEXT:      'TEXT',
        PrimitiveType.INTEGER:   'INT',
        PrimitiveType.LONG:      'BIGINT',
        PrimitiveType.DOUBLE:    'DOUBLE',
        PrimitiveType.FLOAT:     'FLOAT',
        PrimitiveType.DECIMAL:   'DECIMAL',
        PrimitiveType.BOOLEAN:   'BOOLEAN',
        PrimitiveType.DATE:      'DATE',
        PrimitiveType.TIMESTAMP: 'TIMESTAMP',
        PrimitiveType.UUID:      'UUID',
        PrimitiveType.BINARY:    'BLOB',
        PrimitiveType.OBJECT_ID: 'TEXT',
        PrimitiveType.NULL:      'TEXT',
        PrimitiveType.INT32:     'INT',
        PrimitiveType.INT64:     'BIGINT',
        PrimitiveType.DECIMAL128: 'DECIMAL',
    }

    # -------------------------------------------------------------------------
    # Display Mappings (for UI/reports)
    # -------------------------------------------------------------------------
    # PrimitiveType -> PostgreSQL display format
    PRIMITIVE_TO_PG_DISPLAY = {
        PrimitiveType.INTEGER: 'INTEGER',
        PrimitiveType.LONG: 'BIGINT',
        PrimitiveType.STRING: 'VARCHAR',
        PrimitiveType.TEXT: 'TEXT',
        PrimitiveType.DECIMAL: 'DECIMAL',
        PrimitiveType.FLOAT: 'REAL',
        PrimitiveType.DOUBLE: 'DOUBLE PRECISION',
        PrimitiveType.BOOLEAN: 'BOOLEAN',
        PrimitiveType.DATE: 'DATE',
        PrimitiveType.TIMESTAMP: 'TIMESTAMP',
        PrimitiveType.UUID: 'UUID',
        PrimitiveType.BINARY: 'BYTEA',
    }

    # PrimitiveType -> MongoDB display format
    PRIMITIVE_TO_MONGO_DISPLAY = {
        PrimitiveType.STRING: 'string',
        PrimitiveType.INTEGER: 'int',
        PrimitiveType.LONG: 'long',
        PrimitiveType.DOUBLE: 'double',
        PrimitiveType.DECIMAL: 'decimal',
        PrimitiveType.FLOAT: 'double',
        PrimitiveType.BOOLEAN: 'bool',
        PrimitiveType.DATE: 'date',
        PrimitiveType.TIMESTAMP: 'timestamp',
        PrimitiveType.UUID: 'string',
        PrimitiveType.BINARY: 'binData',
        PrimitiveType.OBJECT_ID: 'objectId',
    }


# Populate _NATIVE_TYPE_REGISTRY from TypeMappings (single source of truth)
_NATIVE_TYPE_REGISTRY[DatabaseType.RELATIONAL] = TypeMappings.PRIMITIVE_TO_POSTGRESQL
_NATIVE_TYPE_REGISTRY[DatabaseType.DOCUMENT] = TypeMappings.PRIMITIVE_TO_MONGODB
_NATIVE_TYPE_REGISTRY[DatabaseType.GRAPH] = TypeMappings.PRIMITIVE_TO_NEO4J
_NATIVE_TYPE_REGISTRY[DatabaseType.COLUMNAR] = TypeMappings.PRIMITIVE_TO_CASSANDRA


# DATA TYPES

def _uid() -> str:
    return str(uuid.uuid4())


def _apply_id_map(obj: Any, id_map: Dict[str, str]) -> Any:
    """Recursively rebuild ``obj`` with every string value rewritten via ``id_map``."""
    if isinstance(obj, dict):
        return {k: _apply_id_map(v, id_map) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_apply_id_map(v, id_map) for v in obj]
    if isinstance(obj, str):
        return id_map.get(obj, obj)
    return obj


@dataclass
class DataType(ABC):
    @abstractmethod
    def to_native(self, db: DatabaseType) -> str:
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        pass

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DataType':
        """Factory method to create appropriate DataType subclass."""
        kind = data.get("kind", "primitive")
        if kind == "primitive":
            return PrimitiveDataType.from_dict(data)
        elif kind == "list":
            return ListDataType.from_dict(data)
        elif kind == "set":
            return SetDataType.from_dict(data)
        elif kind == "map":
            return MapDataType.from_dict(data)
        elif kind == "tuple":
            return TupleDataType.from_dict(data)
        raise ValueError(f"Unknown DataType kind: {kind}")


@dataclass
class PrimitiveDataType(DataType):
    primitive_type: PrimitiveType
    max_length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None

    def to_native(self, db: DatabaseType) -> str:
        base = _get_native_type(self.primitive_type, db)
        if db == DatabaseType.RELATIONAL:
            if self.primitive_type == PrimitiveType.STRING and self.max_length:
                return f"VARCHAR({self.max_length})"
            if self.primitive_type == PrimitiveType.DECIMAL and self.precision:
                return f"DECIMAL({self.precision},{self.scale or 0})"
        return base

    def to_dict(self) -> Dict[str, Any]:
        d = {"kind": "primitive", "type": self.primitive_type.value}
        if self.max_length is not None:
            d["max_length"] = self.max_length
        if self.precision is not None:
            d["precision"] = self.precision
        if self.scale is not None:
            d["scale"] = self.scale
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PrimitiveDataType':
        try:
            pt = PrimitiveType(data.get("type", "string"))
        except ValueError:
            pt = PrimitiveType.STRING
        return cls(
            primitive_type=pt,
            max_length=data.get("max_length"),
            precision=data.get("precision"),
            scale=data.get("scale")
        )


@dataclass
class ListDataType(DataType):
    element_type: DataType

    def to_native(self, db: DatabaseType) -> str:
        m = {
            DatabaseType.RELATIONAL: f"{self.element_type.to_native(db)}[]",
            DatabaseType.DOCUMENT: "array",
            DatabaseType.GRAPH: f"List<{self.element_type.to_native(db)}>",
            DatabaseType.COLUMNAR: f"list<{self.element_type.to_native(db)}>"
        }
        return m.get(db, "array")

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "list", "element_type": self.element_type.to_dict()}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ListDataType':
        element_type = DataType.from_dict(data.get("element_type", {"kind": "primitive", "type": "string"}))
        return cls(element_type=element_type)


@dataclass
class SetDataType(DataType):
    element_type: DataType

    def to_native(self, db: DatabaseType) -> str:
        if db == DatabaseType.COLUMNAR:
            return f"set<{self.element_type.to_native(db)}>"
        return f"{self.element_type.to_native(db)}[]" if db == DatabaseType.RELATIONAL else "array"

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "set", "element_type": self.element_type.to_dict()}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SetDataType':
        element_type = DataType.from_dict(data.get("element_type", {"kind": "primitive", "type": "string"}))
        return cls(element_type=element_type)


@dataclass
class MapDataType(DataType):
    key_type: DataType
    value_type: DataType

    def to_native(self, db: DatabaseType) -> str:
        if db == DatabaseType.COLUMNAR:
            return f"map<{self.key_type.to_native(db)}, {self.value_type.to_native(db)}>"
        return {"RELATIONAL": "JSONB", "DOCUMENT": "object", "GRAPH": "Map"}.get(db.name, "JSONB")

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "map", "key_type": self.key_type.to_dict(), "value_type": self.value_type.to_dict()}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MapDataType':
        key_type = DataType.from_dict(data.get("key_type", {"kind": "primitive", "type": "string"}))
        value_type = DataType.from_dict(data.get("value_type", {"kind": "primitive", "type": "string"}))
        return cls(key_type=key_type, value_type=value_type)


@dataclass
class TupleDataType(DataType):
    """Tuple data type: ordered collection of typed elements. M-Model+ extension."""
    elem_types: List[DataType] = field(default_factory=list)

    def to_native(self, db: DatabaseType) -> str:
        inner = ", ".join(e.to_native(db) for e in self.elem_types)
        if db == DatabaseType.COLUMNAR:
            return f"tuple<{inner}>"
        if db == DatabaseType.GRAPH:
            return f"Tuple<{inner}>"
        return f"({inner})"

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "tuple", "elem_types": [e.to_dict() for e in self.elem_types]}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TupleDataType':
        elem_types = [DataType.from_dict(e) for e in data.get("elem_types", [])]
        return cls(elem_types=elem_types)


# PROPERTY (formerly Attribute)

@dataclass
class Property:
    name: str
    data_type: DataType
    is_key: bool = False
    is_optional: bool = True
    description: Optional[str] = None
    # ``is_auto_generated`` flags database-side generated values (PG SERIAL,
    # MySQL AUTO_INCREMENT, SQL Server IDENTITY, Oracle SEQUENCE-default,
    # etc.). Source adapters set this when reverse-engineering an
    # auto-generated PK; the PostgreSQL forward-engineering path uses it to
    # decide between ``SERIAL`` and ``INTEGER``. Without this flag the meta
    # model cannot distinguish "DB generates the value" from "user provides
    # the value" — both look like ``INTEGER + is_key=True`` — and any
    # cross-paradigm migration into PG would have to assume one of them and
    # silently change the other's semantics. Defaults to ``False`` so all
    # existing constructions (handlers, other adapters, manual instantiation)
    # behave exactly as before; only adapters that explicitly understand the
    # concept opt in.
    is_auto_generated: bool = False
    meta_id: str = field(default_factory=_uid)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "kind": "property",
            "meta_id": self.meta_id,
            "name": self.name,
            "data_type": self.data_type.to_dict(),
            "is_key": self.is_key,
            "is_optional": self.is_optional
        }
        if self.description:
            d["description"] = self.description
        # Emit only when True so all existing JSON snapshots stay
        # byte-identical for non-auto-generated properties (which are the
        # vast majority — only PG SERIAL columns flip this flag today).
        if self.is_auto_generated:
            d["is_auto_generated"] = True
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Property':
        dt = DataType.from_dict(data.get("data_type", {"kind": "primitive", "type": "string"}))
        return cls(
            name=data.get("name", data.get("attr_name", "")),
            data_type=dt,
            is_key=data.get("is_key", False),
            is_optional=data.get("is_optional", True),
            description=data.get("description"),
            # Default to False so older JSON snapshots (pre-Patch-7) that
            # do not carry this key round-trip cleanly. Symmetric with
            # ``to_dict`` which emits the key only when True.
            is_auto_generated=data.get("is_auto_generated", False),
            meta_id=data.get("meta_id", _uid())
        )


# CONSTRAINTS (from AC)

@dataclass
class UniqueProperty:
    """Property that is part of a unique/primary key constraint (from AC)."""
    primary_key_type: PKTypeEnum
    property_id: str  # References Property.meta_id
    # ``clustering_order`` is meaningful only when ``primary_key_type ==
    # CLUSTERING`` (Cassandra). It captures whether the row order within
    # a partition is ascending or descending (``WITH CLUSTERING ORDER BY
    # (col DESC)``). Without this field the order would silently default
    # to ASC on round-trip — affecting query physical plans (newest-first
    # reads become slower). Default ``None`` preserves byte-stable output
    # for every non-Cassandra case and for Cassandra columns without an
    # explicit ORDER BY clause (CQL's own default is ASC).
    clustering_order: Optional[str] = None  # None | 'asc' | 'desc'
    meta_id: str = field(default_factory=_uid)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "meta_id": self.meta_id,
            "primary_key_type": self.primary_key_type.value,
            "property_id": self.property_id,
        }
        # Emit only when set (non-None) so existing JSON snapshots stay
        # byte-identical for non-Cassandra UniqueProperties.
        if self.clustering_order is not None:
            d["clustering_order"] = self.clustering_order
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UniqueProperty':
        try:
            pk_type = PKTypeEnum(data.get("primary_key_type", "simple"))
        except ValueError:
            pk_type = PKTypeEnum.SIMPLE
        return cls(
            primary_key_type=pk_type,
            property_id=data.get("property_id", ""),
            clustering_order=data.get("clustering_order"),
            meta_id=data.get("meta_id", _uid())
        )


@dataclass
class ForeignKeyProperty:
    """Property that is part of a foreign key constraint (from AC)."""
    property_id: str  # References Property.meta_id (the FK column)
    points_to_unique_property_id: str  # References target UniqueProperty.meta_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "property_id": self.property_id,
            "points_to_unique_property_id": self.points_to_unique_property_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ForeignKeyProperty':
        return cls(
            property_id=data.get("property_id", ""),
            points_to_unique_property_id=data.get("points_to_unique_property_id", "")
        )


class Constraint(ABC):
    """Abstract base class for constraints."""

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        pass

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Constraint':
        """Factory method to create appropriate Constraint subclass."""
        constraint_type = data.get("constraint_type")
        if constraint_type == "unique":
            return UniqueConstraint.from_dict(data)
        elif constraint_type == "foreign_key":
            return ForeignKeyConstraint.from_dict(data)
        elif constraint_type == "check":
            return CheckConstraint.from_dict(data)
        elif constraint_type == "existence":
            return ExistenceConstraint.from_dict(data)
        raise ValueError(f"Unknown constraint type: {constraint_type}")


@dataclass
class UniqueConstraint(Constraint):
    """Unique or Primary Key constraint (from AC)."""
    kind: ClassVar[str] = "unique"
    is_primary_key: bool
    is_managed: bool
    unique_properties: List[UniqueProperty] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "constraint_type": "unique",
            "is_primary_key": self.is_primary_key,
            "is_managed": self.is_managed,
            "unique_properties": [up.to_dict() for up in self.unique_properties]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UniqueConstraint':
        unique_props = [UniqueProperty.from_dict(up) for up in data.get("unique_properties", [])]
        return cls(
            is_primary_key=data.get("is_primary_key", False),
            is_managed=data.get("is_managed", True),
            unique_properties=unique_props
        )

    def get_property_ids(self) -> List[str]:
        """Get list of property IDs (Property meta_ids) in this constraint."""
        return [up.property_id for up in self.unique_properties]


@dataclass
class ForeignKeyConstraint(Constraint):
    """Foreign Key constraint (from AC)."""
    kind: ClassVar[str] = "foreign_key"
    is_managed: bool
    foreign_key_properties: List[ForeignKeyProperty] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "constraint_type": "foreign_key",
            "is_managed": self.is_managed,
            "foreign_key_properties": [fkp.to_dict() for fkp in self.foreign_key_properties]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ForeignKeyConstraint':
        fk_props = [ForeignKeyProperty.from_dict(fkp) for fkp in data.get("foreign_key_properties", [])]
        return cls(
            is_managed=data.get("is_managed", True),
            foreign_key_properties=fk_props
        )

    def get_property_ids(self) -> List[str]:
        """Get list of property IDs (Property meta_ids) in this constraint."""
        return [fkp.property_id for fkp in self.foreign_key_properties]


# CHECK EXPRESSION AST
# Tree representation of CHECK predicates produced by the ADD_CONSTRAINT AS
# CHECK grammar branch. Atoms (Cmp / In / Between / Regex / IsNull) carry the
# structured form for clean cross-paradigm translation; And / Or / Not compose
# them; Raw is the escape hatch for predicates the structured grammar cannot
# represent.

@dataclass
class CheckExpr(ABC):
    """Abstract base for CHECK expression nodes."""

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        pass

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckExpr':
        kind = data.get("kind")
        if kind == "cmp":     return CheckCmp.from_dict(data)
        elif kind == "in":    return CheckIn.from_dict(data)
        elif kind == "between": return CheckBetween.from_dict(data)
        elif kind == "regex": return CheckRegex.from_dict(data)
        elif kind == "isnull": return CheckIsNull.from_dict(data)
        elif kind == "and":   return CheckAnd.from_dict(data)
        elif kind == "or":    return CheckOr.from_dict(data)
        elif kind == "not":   return CheckNot.from_dict(data)
        elif kind == "raw":   return CheckRaw.from_dict(data)
        raise ValueError(f"Unknown CheckExpr kind: {kind}")


@dataclass
class CheckCmp(CheckExpr):
    """Atomic comparison: <field_name> <op> <literal>. op in {<, >, <=, >=, ==, !=}."""
    field_name: str = ""
    op: str = "=="
    literal: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "cmp", "field": self.field_name, "op": self.op, "literal": self.literal}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckCmp':
        return cls(field_name=data["field"], op=data["op"], literal=data.get("literal"))


@dataclass
class CheckIn(CheckExpr):
    """Membership: <field_name> IN (v1, v2, ...)."""
    field_name: str = ""
    values: List[Any] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "in", "field": self.field_name, "values": list(self.values)}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckIn':
        return cls(field_name=data["field"], values=list(data.get("values", [])))


@dataclass
class CheckBetween(CheckExpr):
    """Range: <field_name> BETWEEN <low> AND <high>."""
    field_name: str = ""
    low: Any = None
    high: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "between", "field": self.field_name, "low": self.low, "high": self.high}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckBetween':
        return cls(field_name=data["field"], low=data.get("low"), high=data.get("high"))


@dataclass
class CheckRegex(CheckExpr):
    """Pattern match: <field_name> MATCHES "<pattern>"."""
    field_name: str = ""
    pattern: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "regex", "field": self.field_name, "pattern": self.pattern}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckRegex':
        return cls(field_name=data["field"], pattern=data.get("pattern", ""))


@dataclass
class CheckIsNull(CheckExpr):
    """Null check: <field_name> IS NULL or IS NOT NULL (is_null flips meaning)."""
    field_name: str = ""
    is_null: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "isnull", "field": self.field_name, "is_null": self.is_null}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckIsNull':
        return cls(field_name=data["field"], is_null=data.get("is_null", True))


@dataclass
class CheckAnd(CheckExpr):
    """Conjunction: <left> AND <right>."""
    left: Optional[CheckExpr] = None
    right: Optional[CheckExpr] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "and",
                "left": self.left.to_dict() if self.left else None,
                "right": self.right.to_dict() if self.right else None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckAnd':
        l = CheckExpr.from_dict(data["left"]) if data.get("left") else None
        r = CheckExpr.from_dict(data["right"]) if data.get("right") else None
        return cls(left=l, right=r)


@dataclass
class CheckOr(CheckExpr):
    """Disjunction: <left> OR <right>."""
    left: Optional[CheckExpr] = None
    right: Optional[CheckExpr] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "or",
                "left": self.left.to_dict() if self.left else None,
                "right": self.right.to_dict() if self.right else None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckOr':
        l = CheckExpr.from_dict(data["left"]) if data.get("left") else None
        r = CheckExpr.from_dict(data["right"]) if data.get("right") else None
        return cls(left=l, right=r)


@dataclass
class CheckNot(CheckExpr):
    """Negation: NOT <expr>."""
    expr: Optional[CheckExpr] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "not", "expr": self.expr.to_dict() if self.expr else None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckNot':
        e = CheckExpr.from_dict(data["expr"]) if data.get("expr") else None
        return cls(expr=e)


@dataclass
class CheckRaw(CheckExpr):
    """Escape hatch: arbitrary predicate text. Adapter visitors fall back to"""
    raw_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "raw", "raw_text": self.raw_text}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckRaw':
        return cls(raw_text=data.get("raw_text", ""))


# CHECK + EXISTENCE CONSTRAINTS
# These cover the gaps left by the narrow constraint operators
# (ADD_PRIMARY_KEY / ADD_UNIQUE_KEY / ADD_FOREIGN_KEY / ADD_PARTITION_KEY /
# ADD_CLUSTERING_KEY / ADD_LABEL). They are produced by the ADD_CONSTRAINT
# operator's CHECK and EXISTENCE branches respectively. Logical references
# (the third ADD_CONSTRAINT branch) re-use the existing ``Reference`` object
# with ``is_enforced=False``, not a dedicated Constraint subclass.

@dataclass
class CheckConstraint(Constraint):
    """CHECK predicate over one or more properties of an entity."""
    kind: ClassVar[str] = "check"
    expression: Optional[CheckExpr] = None
    target_property_id: str = ""
    constraint_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"constraint_type": "check"}
        if self.expression is not None:
            d["expression"] = self.expression.to_dict()
        if self.target_property_id:
            d["target_property_id"] = self.target_property_id
        if self.constraint_name:
            d["constraint_name"] = self.constraint_name
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CheckConstraint':
        expr_data = data.get("expression")
        expr = CheckExpr.from_dict(expr_data) if expr_data else None
        return cls(expression=expr,
                   target_property_id=data.get("target_property_id", ""),
                   constraint_name=data.get("constraint_name", ""))


@dataclass
class ExistenceConstraint(Constraint):
    """A property must always have a value. Equivalent to NOT NULL but expressed"""
    kind: ClassVar[str] = "existence"
    target_property_id: str = ""
    constraint_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"constraint_type": "existence",
                             "target_property_id": self.target_property_id}
        if self.constraint_name:
            d["constraint_name"] = self.constraint_name
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExistenceConstraint':
        return cls(target_property_id=data.get("target_property_id", ""),
                   constraint_name=data.get("constraint_name", ""))


# RELATIONSHIPS

class TraceOrigin(str, Enum):
    """Why a RelationshipTrace entry was created. Each value identifies the
    operation that destroyed the original relationship and seeded the trace."""
    DELETED_REFERENCE = "deleted_reference"          # DELETE_FOREIGN_KEY / DELETE_PROPERTY
    UNNESTED_EMBEDDED = "unnested_embedded"          # UNNEST extracting an embedded entity
    UNNESTED_SELF_REF = "unnested_self_ref"          # UNNEST preserving a self-referential Reference
    UNNESTED_EMBEDDED_REF = "unnested_embedded_ref"  # UNNEST preserving a cross-collection Reference
    TRANSFORMED_EDGE = "transformed_edge"            # TRANSFORM ... INTO ENTITY (edge -> vertex); scoped to its edge name


@dataclass
class RelationshipTrace:
    """Transformation-time auxiliary structure: a typed record of a relationship
    that was destroyed by an operation (DELETE_FOREIGN_KEY, DELETE_PROPERTY,
    UNNEST) so a later operation can preserve its semantic cardinality across
    representation changes.

    This is NOT part of the canonical schema and is NEVER serialised into
    ``Database.to_dict()``. It lives on the transformer for the duration of a
    single migration script and is discarded afterwards.
    """
    holder: str                 # source entity that held the original relationship
    ref_name: str               # Reference/Embedded name (e.g. "customer_id", "employee")
    target: str                 # target entity of the original relationship
    target_end_cardinality: Cardinality                          # multiplicity at the target end (per source, how many targets)
    source_end_cardinality: Optional[Cardinality] = None         # multiplicity at the source end (per target, how many sources), if known
    origin: TraceOrigin = TraceOrigin.DELETED_REFERENCE


@dataclass
class Relationship(ABC):
    """Base for Reference / Embedded / Edge.

    Cardinality is bidirectional. Each field is named after the end of the
    relationship whose multiplicity it stores: ``target_end_cardinality`` is
    the multiplicity at the target end of the association — i.e., for each
    source entity, how many target entities it references.
    ``source_end_cardinality`` is the multiplicity at the source end — i.e.,
    for each target entity, how many source entities reference it. ``None``
    on the source end means "not declared" — distinct from the explicit
    unconstrained default ``ZERO_TO_MANY``.
    """
    target_end_cardinality: Cardinality = Cardinality.ONE_TO_ONE
    source_end_cardinality: Optional[Cardinality] = None
    is_optional: bool = True
    description: Optional[str] = None
    meta_id: str = field(default_factory=_uid)

    @property
    def lower_bound(self) -> int:
        return self.target_end_cardinality.to_bounds()[0]

    @property
    def upper_bound(self) -> int:
        return self.target_end_cardinality.to_bounds()[1]

    @abstractmethod
    def get_target_entity_name(self) -> str:
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        pass

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Relationship':
        """Factory method to create appropriate Relationship subclass."""
        kind = data.get("kind")
        if kind == "reference":
            return Reference.from_dict(data)
        elif kind in ("aggregate", "embedded"):
            return Embedded.from_dict(data)
        elif kind == "edge":
            return Edge.from_dict(data)
        raise ValueError(f"Unknown relationship kind: {kind}")


@dataclass
class Reference(Relationship):
    ref_name: str = ""
    refs_to: str = ""  # Entity name (string only, not object reference)
    edge_properties: List[Property] = field(default_factory=list)
    # ``True`` (default) = Reference is paired with a ForeignKeyConstraint and the
    # target paradigm enforces referential integrity (PostgreSQL FK).
    # ``False`` = logical-only reference: the relationship exists in the meta model
    # but no paradigm-level enforcement is requested (Mongo cross-collection
    # ObjectId reference, Cassandra denormalised column pointing at another table,
    # PostgreSQL soft references that cross schemas/databases).
    is_enforced: bool = True

    def get_target_entity_name(self) -> str:
        return self.refs_to

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "kind": "reference",
            "meta_id": self.meta_id,
            "ref_name": self.ref_name,
            "refs_to": self.refs_to,
            "target_end_cardinality": self.target_end_cardinality.value,
            "is_optional": self.is_optional
        }
        if self.source_end_cardinality is not None:
            d["source_end_cardinality"] = self.source_end_cardinality.value
        # Emit ``is_enforced`` only when the reference is logical so that JSON
        # output for every existing Reference (which all default to enforced)
        # remains byte-identical to the pre-feature serialization.
        if not self.is_enforced:
            d["is_enforced"] = False
        if self.edge_properties:
            d["edge_properties"] = [a.to_dict() for a in self.edge_properties]
        if self.description:
            d["description"] = self.description
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Reference':
        edge_props = [Property.from_dict(a) for a in data.get("edge_properties", [])]
        source_end_card_str = data.get("source_end_cardinality")
        source_end_cardinality = Cardinality.from_symbol(source_end_card_str) if source_end_card_str else None
        return cls(
            ref_name=data.get("ref_name", ""),
            refs_to=data.get("refs_to", ""),
            target_end_cardinality=Cardinality.from_symbol(data.get("target_end_cardinality", "1..1")),
            source_end_cardinality=source_end_cardinality,
            is_optional=data.get("is_optional", True),
            description=data.get("description"),
            meta_id=data.get("meta_id", _uid()),
            edge_properties=edge_props,
            is_enforced=data.get("is_enforced", True)
        )


@dataclass
class Embedded(Relationship):
    """Embedded/Aggregate relationship for nested documents (MongoDB style)."""
    aggr_name: str = ""
    aggregates: str = ""  # Entity name (string only, not object reference)

    def get_target_entity_name(self) -> str:
        return self.aggregates

    def is_array(self) -> bool:
        return self.target_end_cardinality.is_multiple()

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "kind": "embedded",
            "meta_id": self.meta_id,
            "aggr_name": self.aggr_name,
            "aggregates": self.aggregates,
            "target_end_cardinality": self.target_end_cardinality.value,
            "is_optional": self.is_optional,
            "is_array": self.is_array()
        }
        if self.source_end_cardinality is not None:
            d["source_end_cardinality"] = self.source_end_cardinality.value
        if self.description:
            d["description"] = self.description
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Embedded':
        source_end_card_str = data.get("source_end_cardinality")
        source_end_cardinality = Cardinality.from_symbol(source_end_card_str) if source_end_card_str else None
        return cls(
            aggr_name=data.get("aggr_name", data.get("em_name", "")),
            aggregates=data.get("aggregates", data.get("embeds", "")),
            target_end_cardinality=Cardinality.from_symbol(data.get("target_end_cardinality", "1..1")),
            source_end_cardinality=source_end_cardinality,
            is_optional=data.get("is_optional", True),
            description=data.get("description"),
            meta_id=data.get("meta_id", _uid())
        )


@dataclass
class Edge(Relationship):
    """Graph edge relationship. M-Model+ extension: part of the Reference / Embedded / Edge hierarchy that replaces the original flat connector model."""
    rel_type_name: str = ""    # Name of the EDGE relationship type (e.g. "PURCHASED")
    source_entity: str = ""    # Source entity name
    target_entity: str = ""    # Target entity name

    def get_target_entity_name(self) -> str:
        return self.target_entity

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "kind": "edge",
            "meta_id": self.meta_id,
            "rel_type_name": self.rel_type_name,
            "source_entity": self.source_entity,
            "target_entity": self.target_entity,
            "target_end_cardinality": self.target_end_cardinality.value,
            "is_optional": self.is_optional
        }
        if self.source_end_cardinality is not None:
            d["source_end_cardinality"] = self.source_end_cardinality.value
        if self.description:
            d["description"] = self.description
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Edge':
        source_end_card_str = data.get("source_end_cardinality")
        source_end_cardinality = Cardinality.from_symbol(source_end_card_str) if source_end_card_str else None
        return cls(
            rel_type_name=data.get("rel_type_name", ""),
            source_entity=data.get("source_entity", ""),
            target_entity=data.get("target_entity", ""),
            target_end_cardinality=Cardinality.from_symbol(data.get("target_end_cardinality", "0..n")),
            source_end_cardinality=source_end_cardinality,
            is_optional=data.get("is_optional", True),
            description=data.get("description"),
            meta_id=data.get("meta_id", _uid())
        )


# ENTITY TYPE

@dataclass
class EntityType:
    """Unifies the definition of database entities (from AC with List[str] naming)."""
    object_name: List[str]  # from AC: ["schema", "table"] or ["collection", "embedded"]
    entity_kind: EntityKind = EntityKind.TABLE
    is_root: bool = True
    constraints: List[Constraint] = field(default_factory=list)
    properties: List[Property] = field(default_factory=list)
    relationships: List[Relationship] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)  # Graph-specific: additional node labels (e.g. customers:Employee)
    source_entity: Optional[str] = None  # EDGE only: source node entity name
    target_entity: Optional[str] = None  # EDGE only: target node entity name
    edge_target_end_cardinality: Optional[Cardinality] = None  # EDGE only: multiplicity at the target end (per source, how many targets)
    edge_source_end_cardinality: Optional[Cardinality] = None  # EDGE only: multiplicity at the source end (per target, how many sources)
    description: Optional[str] = None
    # When True, _normalize_entity_kinds() leaves this entity's entity_kind alone
    # (set by CAST_ENTITY handler so the user's explicit choice is preserved
    # through target-paradigm normalization).
    kind_locked: bool = False
    meta_id: str = field(default_factory=_uid)

    @property
    def name(self) -> str:
        """Get simple name (last element of path)."""
        return self.object_name[-1] if self.object_name else ""

    @property
    def full_path(self) -> str:
        """Get full path as dot-separated string."""
        return ".".join(self.object_name)

    @property
    def parent_path(self) -> List[str]:
        """Get parent path (all elements except last)."""
        return self.object_name[:-1] if len(self.object_name) > 1 else []

    # Constraint methods
    def add_constraint(self, constraint: Constraint):
        self.constraints.append(constraint)

    def get_primary_key(self) -> Optional[UniqueConstraint]:
        """Get the primary key constraint."""
        for c in self.constraints:
            if c.kind == "unique" and c.is_primary_key:
                return c
        return None

    def get_unique_constraints(self) -> List[UniqueConstraint]:
        """Get all unique constraints (non-primary)."""
        return [c for c in self.constraints if c.kind == "unique" and not c.is_primary_key]

    def get_foreign_keys(self) -> List[ForeignKeyConstraint]:
        """Get all foreign key constraints."""
        return [c for c in self.constraints if c.kind == "foreign_key"]

    def remove_fk_constraint_for_property(self, property_meta_id: str) -> None:
        """Drop any foreign-key constraint that covers the given property.

        Mirrors SQL ``DROP CONSTRAINT`` semantics: the FK constraint is removed
        while the underlying column/property is left untouched. Centralizes the
        filter previously duplicated across NEST, DELETE_PROPERTY,
        DELETE_FOREIGN_KEY and ADD_CONSTRAINT ... AS REFERENCE.
        """
        self.constraints = [
            c for c in self.constraints
            if not (c.kind == "foreign_key" and
                    any(fkp.property_id == property_meta_id
                        for fkp in c.foreign_key_properties))
        ]

    # Property methods
    def add_property(self, attr: Property):
        self.properties.append(attr)

    def get_property(self, name: str) -> Optional[Property]:
        return next((a for a in self.properties if a.name == name), None)

    def get_property_by_id(self, meta_id: str) -> Optional[Property]:
        """Get property by its meta_id (used for constraint property_id lookup)."""
        return next((a for a in self.properties if a.meta_id == meta_id), None)

    def remove_property(self, name: str) -> Optional[Property]:
        for i, a in enumerate(self.properties):
            if a.name == name:
                return self.properties.pop(i)
        return None

    # Relationship methods
    def add_relationship(self, rel: Relationship):
        self.relationships.append(rel)

    def get_references(self) -> List[Reference]:
        return [r for r in self.relationships if isinstance(r, Reference)]

    def get_embedded(self) -> List[Embedded]:
        """Get all embedded relationships."""
        return [r for r in self.relationships if isinstance(r, Embedded)]

    def get_edges(self) -> List['Edge']:
        """Get all edge relationships (graph database)."""
        return [r for r in self.relationships if isinstance(r, Edge)]

    def remove_relationship(self, name: str) -> Optional[Relationship]:
        for i, r in enumerate(self.relationships):
            if isinstance(r, Reference):
                rel_name = r.ref_name
            elif isinstance(r, Embedded):
                rel_name = r.aggr_name
            elif isinstance(r, Edge):
                rel_name = r.rel_type_name
            else:
                continue
            if rel_name == name:
                return self.relationships.pop(i)
        return None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "meta_id": self.meta_id,
            "object_name": self.object_name,  # from AC: List[str]
            "entity_kind": self.entity_kind.value,
            "is_root": self.is_root,
            "constraints": [c.to_dict() for c in self.constraints],
            "properties": [a.to_dict() for a in self.properties],
            "relationships": [r.to_dict() for r in self.relationships],
        }
        if self.source_entity is not None:
            d["source_entity"] = self.source_entity
        if self.target_entity is not None:
            d["target_entity"] = self.target_entity
        if self.edge_target_end_cardinality is not None:
            d["edge_target_end_cardinality"] = self.edge_target_end_cardinality.value
        if self.edge_source_end_cardinality is not None:
            d["edge_source_end_cardinality"] = self.edge_source_end_cardinality.value
        if self.description:
            d["description"] = self.description
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EntityType':
        try:
            kind = EntityKind(data.get("entity_kind", "table"))
        except ValueError:
            kind = EntityKind.TABLE

        constraints = [Constraint.from_dict(c) for c in data.get("constraints", [])]
        attrs = [Property.from_dict(a) for a in data.get("properties", [])]
        rels = [Relationship.from_dict(r) for r in data.get("relationships", [])]

        object_name = data.get("object_name") or [""]

        edge_target_card_str = data.get("edge_target_end_cardinality")
        edge_target_end_cardinality = Cardinality.from_symbol(edge_target_card_str) if edge_target_card_str else None

        edge_source_card_str = data.get("edge_source_end_cardinality")
        edge_source_end_cardinality = Cardinality.from_symbol(edge_source_card_str) if edge_source_card_str else None

        return cls(
            object_name=object_name,
            entity_kind=kind,
            is_root=data.get("is_root", True),
            constraints=constraints,
            properties=attrs,
            relationships=rels,
            source_entity=data.get("source_entity"),
            target_entity=data.get("target_entity"),
            edge_target_end_cardinality=edge_target_end_cardinality,
            edge_source_end_cardinality=edge_source_end_cardinality,
            description=data.get("description"),
            meta_id=data.get("meta_id", _uid())
        )


# DATABASE (TOP-LEVEL)

@dataclass
class Database:
    db_name: str
    db_type: DatabaseType = DatabaseType.RELATIONAL
    entity_types: Dict[str, EntityType] = field(default_factory=dict)
    version: int = 1
    description: Optional[str] = None
    meta_id: str = field(default_factory=_uid)

    # Entity management
    def add_entity_type(self, e: EntityType):
        """Add entity using full_path as key."""
        self.entity_types[e.full_path] = e

    def get_entity_strict(self, full_path: str) -> Optional[EntityType]:
        """Look up an entity by its exact ``full_path`` (no simple-name fallback)."""
        return self.entity_types.get(full_path)

    def get_entity_type(self, name: str) -> Optional[EntityType]:
        """Look up an entity by full path or simple name (lenient)."""
        if name in self.entity_types:
            return self.entity_types[name]
        matches = [e for e in self.entity_types.values() if e.name == name]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            logger.warning(
                "Ambiguous entity name '%s' matches %d entities (%s). "
                "Use a fully-qualified path to disambiguate.",
                name, len(matches), [e.full_path for e in matches],
            )
        return None

    def remove_entity_type(self, name: str) -> Optional[EntityType]:
        """Remove entity by name (supports both full_path and simple name)."""
        if name in self.entity_types:
            return self.entity_types.pop(name, None)
        # Fallback: search by simple name
        for key, entity in list(self.entity_types.items()):
            if entity.name == name:
                return self.entity_types.pop(key, None)
        return None

    # EDGE relationship-type management (derived from EDGE entities)
    @property
    def relationship_types(self) -> Dict[str, EntityType]:
        """Get all EDGE entities as relationship types (computed view)."""
        return {name: e for name, e in self.entity_types.items() if e.entity_kind == EntityKind.EDGE}

    def get_relationship_type(self, name: str) -> Optional[EntityType]:
        """Get EDGE entity by name."""
        entity = self.get_entity_type(name)
        return entity if entity and entity.entity_kind == EntityKind.EDGE else None

    def remove_relationship_type(self, name: str) -> Optional[EntityType]:
        """Remove EDGE entity by name."""
        entity = self.get_entity_type(name)
        if entity and entity.entity_kind == EntityKind.EDGE:
            return self.remove_entity_type(name)
        return None

    def increment_version(self) -> int:
        self.version += 1
        return self.version

    # Serialization
    def to_dict(self) -> Dict[str, Any]:
        """Serialize the Database to a JSON-ready dict with deterministic ids."""
        # Build the dict with the raw UUIDs first — keeps the per-class
        # to_dict() implementations untouched.
        d: Dict[str, Any] = {
            "meta_id": self.meta_id,
            "db_name": self.db_name,
            "db_type": self.db_type.value,
            "version": self.version,
            "entity_types": {n: e.to_dict() for n, e in self.entity_types.items()},
        }
        edge_entities = self.relationship_types
        if edge_entities:
            d["relationship_types"] = {n: {
                "rel_name": e.name,
                "source_entity": e.source_entity or "",
                "target_entity": e.target_entity or "",
                "properties": [a.to_dict() for a in e.properties],
                "target_end_cardinality": (e.edge_target_end_cardinality or Cardinality.ZERO_TO_MANY).value,
            } for n, e in edge_entities.items()}
        if self.description:
            d["description"] = self.description

        return _apply_id_map(d, self._build_deterministic_id_map())

    def _build_deterministic_id_map(self) -> Dict[str, str]:
        """Map every runtime UUID in this Database to a path-based id."""
        m: Dict[str, str] = {self.meta_id: "db"}
        for ent_path, entity in self.entity_types.items():
            m[entity.meta_id] = f"E:{ent_path}"
            for prop in entity.properties:
                m[prop.meta_id] = f"P:{ent_path}:{prop.name}"
            for ci, c in enumerate(entity.constraints):
                if isinstance(c, UniqueConstraint):
                    for upi, up in enumerate(c.unique_properties):
                        m[up.meta_id] = f"UP:{ent_path}:{ci}:{upi}"
            for rel in entity.relationships:
                if isinstance(rel, Reference):
                    m[rel.meta_id] = f"REF:{ent_path}:{rel.ref_name}"
                    for ep in rel.edge_properties:
                        m[ep.meta_id] = f"EP:{ent_path}:{rel.ref_name}:{ep.name}"
                elif isinstance(rel, Embedded):
                    m[rel.meta_id] = f"EMB:{ent_path}:{rel.aggr_name}"
                elif isinstance(rel, Edge):
                    m[rel.meta_id] = f"EDG:{ent_path}:{rel.rel_type_name}"
        return m

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def save_to_file(self, path: str):
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.to_json())

    # Deserialization
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Database':
        try:
            db_type = DatabaseType(data.get("db_type", "relational"))
        except ValueError:
            db_type = DatabaseType.RELATIONAL

        db = cls(
            db_name=data.get("db_name", "unknown"),
            db_type=db_type,
            version=data.get("version", 1),
            description=data.get("description"),
            meta_id=data.get("meta_id", _uid())
        )

        # Load entity types
        for e_data in data.get("entity_types", {}).values():
            entity = EntityType.from_dict(e_data)
            db.add_entity_type(entity)

        # Load relationship types as EDGE entities
        for r_data in data.get("relationship_types", {}).values():
            rel_name = r_data.get("rel_name", "")
            attrs = [Property.from_dict(a) for a in r_data.get("properties", [])]
            card_str = r_data.get("target_end_cardinality", "0..n")
            edge_entity = EntityType(
                object_name=[rel_name],
                entity_kind=EntityKind.EDGE,
                source_entity=r_data.get("source_entity", ""),
                target_entity=r_data.get("target_entity", ""),
                edge_target_end_cardinality=Cardinality.from_symbol(card_str),
                properties=attrs,
                meta_id=r_data.get("meta_id", _uid())
            )
            db.add_entity_type(edge_entity)

        return db

    @classmethod
    def load_from_file(cls, path: str) -> 'Database':
        with open(path, 'r', encoding='utf-8') as f:
            return cls.from_dict(json.load(f))


# Alias
UnifiedMetaSchema = Database

__all__ = [
    'DatabaseType', 'EntityKind', 'PrimitiveType', 'PKTypeEnum', 'Cardinality',
    'DataType', 'PrimitiveDataType', 'ListDataType', 'SetDataType', 'MapDataType', 'TupleDataType',
    'Property', 'Constraint', 'UniqueProperty', 'ForeignKeyProperty',
    'UniqueConstraint', 'ForeignKeyConstraint',
    'Relationship', 'Reference', 'Embedded', 'Edge',
    'EntityType',
    'Database', 'UnifiedMetaSchema', 'TypeMappings'
]
