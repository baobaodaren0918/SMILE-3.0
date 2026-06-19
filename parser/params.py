"""Operation parameter types for SMILE operations."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union


# Shared discriminators

class KeyType(str, Enum):
    """Surface-level key discriminator for ADD_KEY / DELETE_KEY ops."""
    PRIMARY = "PRIMARY"
    UNIQUE = "UNIQUE"
    PARTITION = "PARTITION"
    CLUSTERING = "CLUSTERING"


# Operation result

@dataclass
class OperationResult:
    """Outcome of a single _handle_* invocation."""
    success: bool
    reason: Optional[str] = None

    def __bool__(self) -> bool:
        return self.success

    @classmethod
    def ok(cls) -> "OperationResult":
        return cls(success=True)

    @classmethod
    def skipped(cls, reason: str) -> "OperationResult":
        return cls(success=False, reason=reason)


# Validation helper

def _require_nonempty(obj: Any, *names: str) -> None:
    """Raise ValueError if any named field on `obj` is empty (None, "", [])."""
    for n in names:
        v = getattr(obj, n)
        if v is None or v == "" or v == []:
            raise ValueError(
                f"{type(obj).__name__}.{n} must be non-empty"
            )


# Structural operations

@dataclass
class NestParams:
    source: str
    target: str
    alias: str
    properties: List[str] = field(default_factory=list)
    nested: List[Dict[str, Any]] = field(default_factory=list)
    source_fk: str = ""
    join_conditions: List[Dict[str, Any]] = field(default_factory=list)
    target_pk: str = ""

    def __post_init__(self) -> None:
        _require_nonempty(self, "source", "target", "alias")


@dataclass
class UnnestParams:
    source_path: str
    target: str
    properties: List[str] = field(default_factory=list)
    nested: List[Dict[str, Any]] = field(default_factory=list)
    carry_fields: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_nonempty(self, "source_path", "target")


@dataclass
class FlattenParams:
    source: str

    def __post_init__(self) -> None:
        _require_nonempty(self, "source")


@dataclass
class UnflattenParams:
    entity: str
    fields: List[str]
    nested_name: str

    def __post_init__(self) -> None:
        _require_nonempty(self, "entity", "fields", "nested_name")


@dataclass
class WindParams:
    source: str

    def __post_init__(self) -> None:
        _require_nonempty(self, "source")


@dataclass
class UnwindParams:
    mode: str  # "create_table" or "expand_in_place"
    source: str
    target: Optional[str] = None

    def __post_init__(self) -> None:
        _require_nonempty(self, "mode", "source")


# Entity operations

@dataclass
class AddEntityParams:
    name: str
    # list of clause dicts (see _parse_entity_clauses); dict/list shape varies by op
    clauses: List[Dict[str, Any]] = field(default_factory=list)
    source_entity: Optional[str] = None
    target_entity: Optional[str] = None
    cardinality: Optional[str] = None

    def __post_init__(self) -> None:
        _require_nonempty(self, "name")


@dataclass
class DeleteEntityParams:
    name: str

    def __post_init__(self) -> None:
        _require_nonempty(self, "name")


@dataclass
class RenameEntityParams:
    old_name: str
    new_name: Optional[str] = None

    def __post_init__(self) -> None:
        _require_nonempty(self, "old_name")


@dataclass
class CopyEntityParams:
    source: str
    target: str
    source_entity: Optional[str] = None
    target_entity: Optional[str] = None

    def __post_init__(self) -> None:
        _require_nonempty(self, "source", "target")


# Property operations

@dataclass
class AddPropertyParams:
    name: str
    entity: Optional[str] = None
    # list of clause dicts (see _parse_property_clauses)
    clauses: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_nonempty(self, "name")


@dataclass
class DeletePropertyParams:
    target: str

    def __post_init__(self) -> None:
        _require_nonempty(self, "target")


@dataclass
class RenamePropertyParams:
    old_name: str
    new_name: Optional[str] = None
    entity: Optional[str] = None

    def __post_init__(self) -> None:
        _require_nonempty(self, "old_name")


@dataclass
class CopyPropertyParams:
    source: str
    target: str
    join_conditions: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_nonempty(self, "source", "target")


@dataclass
class MovePropertyParams:
    source: str
    target: str
    join_conditions: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_nonempty(self, "source", "target")


# Key / Constraint operations

@dataclass
class AddKeyParams:
    key_type: KeyType
    key_columns: List[str] = field(default_factory=list)
    entity: Optional[str] = None
    data_type: Optional[str] = None
    clauses: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Coerce raw strings produced by older listener code to the enum.
        if isinstance(self.key_type, str) and not isinstance(self.key_type, KeyType):
            self.key_type = KeyType(self.key_type)
        _require_nonempty(self, "key_columns")


@dataclass
class DeleteKeyParams:
    key_type: KeyType
    key_columns: List[str] = field(default_factory=list)
    entity: Optional[str] = None

    def __post_init__(self) -> None:
        if isinstance(self.key_type, str) and not isinstance(self.key_type, KeyType):
            self.key_type = KeyType(self.key_type)
        _require_nonempty(self, "key_columns")


@dataclass
class AddForeignKeyParams:
    """Foreign-key parameters supporting both single-column and composite FKs."""
    field_names: List[str]
    target_table: str
    target_columns: List[str]
    entity: Optional[str] = None
    clauses: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_nonempty(self, "target_table")
        if not self.field_names:
            raise ValueError("AddForeignKeyParams.field_names must be non-empty")
        if not self.target_columns:
            raise ValueError("AddForeignKeyParams.target_columns must be non-empty")
        if len(self.field_names) != len(self.target_columns):
            raise ValueError(
                f"AddForeignKeyParams: field_names ({len(self.field_names)}) "
                f"and target_columns ({len(self.target_columns)}) must have "
                f"the same length"
            )


@dataclass
class DeleteForeignKeyParams:
    reference: str

    def __post_init__(self) -> None:
        _require_nonempty(self, "reference")


@dataclass
class CastConstraintParams:
    target: str
    constraint_type: str

    def __post_init__(self) -> None:
        _require_nonempty(self, "target", "constraint_type")


# ADD_CONSTRAINT / DELETE_CONSTRAINT operations
# These cover the constraint kinds NOT addressed by the narrow operators
# (PRIMARY KEY / UNIQUE KEY / FOREIGN KEY / PARTITION KEY / CLUSTERING KEY /
# LABEL). Three sub-bodies, discriminated by ``body_kind``:
#   "REFERENCE"  -> creates Reference(is_enforced=True|False) and (when enforced)
#                   a paired ForeignKeyConstraint. Used for Mongo cross-coll
#                   refs, Cass denormalised columns, and PG soft references.
#   "CHECK"      -> creates a CheckConstraint carrying a structured AST tree.
#   "EXISTENCE"  -> creates an ExistenceConstraint (post-hoc NOT NULL).

class ConstraintBodyKind(str, Enum):
    REFERENCE = "REFERENCE"
    CHECK = "CHECK"
    EXISTENCE = "EXISTENCE"


@dataclass
class AddConstraintParams:
    """Payload for ADD_CONSTRAINT."""
    target: str
    body_kind: ConstraintBodyKind
    # REFERENCE body fields
    ref_target_table: Optional[str] = None
    ref_target_columns: List[str] = field(default_factory=list)
    ref_cardinality: Optional[str] = None
    # CHECK body field — CheckExpr AST root (typed via Any here to avoid a
    # circular import; the listener stores a Schema.unified_meta_schema.CheckExpr).
    check_expression: Optional[Any] = None

    def __post_init__(self) -> None:
        _require_nonempty(self, "target", "body_kind")
        if self.body_kind == ConstraintBodyKind.REFERENCE:
            _require_nonempty(self, "ref_target_table", "ref_target_columns")
        elif self.body_kind == ConstraintBodyKind.CHECK:
            if self.check_expression is None:
                raise ValueError(
                    "AddConstraintParams.check_expression must be set for CHECK body"
                )
        # EXISTENCE has no further fields to validate.


@dataclass
class DeleteConstraintParams:
    """Payload for DELETE_CONSTRAINT. ``target`` is the qualified property"""
    target: str

    def __post_init__(self) -> None:
        _require_nonempty(self, "target")


@dataclass
class CastEntityParams:
    target: str
    entity_kind: str

    def __post_init__(self) -> None:
        _require_nonempty(self, "target", "entity_kind")


# Embedded operations

@dataclass
class AddEmbeddedParams:
    name: str
    entity: Optional[str] = None
    # list of clause dicts (see _parse_embedded_clauses)
    clauses: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_nonempty(self, "name")


@dataclass
class DeleteEmbeddedParams:
    embedded: str

    def __post_init__(self) -> None:
        _require_nonempty(self, "embedded")


# Label operations (Graph)

@dataclass
class AddLabelParams:
    label: str
    entity: Optional[str] = None

    def __post_init__(self) -> None:
        _require_nonempty(self, "label")


@dataclass
class DeleteLabelParams:
    label: str
    entity: Optional[str] = None

    def __post_init__(self) -> None:
        _require_nonempty(self, "label")


# Transformation / cast / cardinality operations

@dataclass
class CastPropertyParams:
    target: str
    type: str
    data_type: Optional[str] = None

    def __post_init__(self) -> None:
        _require_nonempty(self, "target", "type")


@dataclass
class MergeParams:
    source1: str
    source2: str
    target: str
    alias: Optional[str] = None
    join_conditions: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_nonempty(self, "source1", "source2", "target")


@dataclass
class SplitParams:
    source: str
    parts: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        _require_nonempty(self, "source", "parts")


@dataclass
class RecardParams:
    target: str
    cardinality: str

    def __post_init__(self) -> None:
        _require_nonempty(self, "target", "cardinality")


@dataclass
class TransformParams:
    name: str
    target_type: str  # "ENTITY" or "RELATIONSHIP"
    source_entity: Optional[str] = None
    target_entity: Optional[str] = None
    cardinality: Optional[str] = None

    def __post_init__(self) -> None:
        _require_nonempty(self, "name", "target_type")


# Union type alias for Operation.params annotation

OpParams = Union[
    NestParams, UnnestParams, FlattenParams, UnflattenParams,
    WindParams, UnwindParams,
    AddEntityParams, DeleteEntityParams, RenameEntityParams, CopyEntityParams,
    AddPropertyParams, DeletePropertyParams, RenamePropertyParams,
    CopyPropertyParams, MovePropertyParams,
    AddKeyParams, DeleteKeyParams,
    AddForeignKeyParams, DeleteForeignKeyParams, CastConstraintParams,
    AddConstraintParams, DeleteConstraintParams,
    CastEntityParams,
    AddEmbeddedParams, DeleteEmbeddedParams,
    AddLabelParams, DeleteLabelParams,
    CastPropertyParams, MergeParams, SplitParams,
    RecardParams, TransformParams,
]
