"""SMILE transformer base — operation registry + state holder + shared helpers."""
import copy
import logging
from typing import Any, Dict, List, Optional, Tuple

from Schema.unified_meta_schema import (
    Cardinality, Database, EntityType, Property, PrimitiveDataType, PrimitiveType,
    RelationshipTrace, TraceOrigin,
)

logger = logging.getLogger(__name__)


# Handler registry — populated at class-definition time by @register_handler
# decorators on each mixin's _handle_* methods. Stores method *names*
# (not function objects) so the registry stays valid across subclassing and
# overrides — the binding to ``self`` happens later in
# ``SchemaTransformerBase.__init__`` via ``getattr``.
_HANDLER_REGISTRY: Dict["OpType", str] = {}  # noqa: F821 — OpType is a forward ref


def register_handler(op_type):
    """Bind an OpType to its handler method by name."""
    def decorator(method):
        if op_type in _HANDLER_REGISTRY:
            raise RuntimeError(
                f"Duplicate handler registration for {op_type}: "
                f"{_HANDLER_REGISTRY[op_type]} vs {method.__name__}"
            )
        _HANDLER_REGISTRY[op_type] = method.__name__
        return method
    return decorator


class SchemaTransformerBase:
    """The instance state every ``_handle_*`` mixin operates on."""

    def __init__(self, database: Database):
        self.database = copy.deepcopy(database)
        self.changes: List[str] = []
        # Snapshot of source-schema primary keys taken at construction; NOT
        # updated as handlers run. Consumed by the web UI to render key badges
        # and resolve FK targets; exported below under the JSON key
        # "key_registry" for backward compatibility with the frontend.
        self.source_key_snapshot: Dict[str, Dict[str, Any]] = {}
        # Per-operation change-tracking hint. Handlers MAY append entity names
        # via _touch(); if non-empty after a handler returns, run_apply() uses
        # it to skip deep-compare on entities the handler didn't touch. Empty
        # = fall back to full-DB diff (legacy behavior).
        self._touched: Optional[List[str]] = None
        # Relationship trace: typed records of relationships destroyed mid-
        # script (by DELETE_FOREIGN_KEY, DELETE_PROPERTY, or UNNEST) so a
        # subsequent ADD_ENTITY / TRANSFORM can reconstruct an Edge with the
        # original bidirectional cardinality preserved. The relationship trace
        # is engine state, NOT part of the canonical schema, and is discarded
        # once the migration script terminates.
        self._relationship_trace: List[RelationshipTrace] = []
        self._init_source_keys()
        # Handler registry: OpType -> bound method (populated from
        # _HANDLER_REGISTRY, which @register_handler decorators below filled
        # in at class-definition time).
        self._handlers = {
            op_type: getattr(self, method_name)
            for op_type, method_name in _HANDLER_REGISTRY.items()
        }

    def _touch(self, *entity_names: str) -> None:
        """Hint to run_apply that this handler only modified the listed entities."""
        if self._touched is None:
            return  # not tracking right now (handler called outside run_apply)
        for n in entity_names:
            if n and n not in self._touched:
                self._touched.append(n)

    def _remember_relationship_trace(
        self, holder: str, ref_name: str, target: str,
        target_end_cardinality: Cardinality,
        source_end_cardinality: Optional[Cardinality] = None,
        origin: TraceOrigin = TraceOrigin.DELETED_REFERENCE,
    ) -> None:
        """Append a relationship trace entry for a relationship destroyed by
        an operation, so a later ADD_ENTITY / TRANSFORM can recover its
        bidirectional cardinality."""
        if not holder or not target:
            return
        self._relationship_trace.append(RelationshipTrace(
            holder=holder, ref_name=ref_name or "", target=target,
            target_end_cardinality=target_end_cardinality, source_end_cardinality=source_end_cardinality,
            origin=origin,
        ))

    def _remember_deleted_fk(self, fk_holder: str, ref_name: str,
                             fk_target: str, was_required: bool,
                             source_end_cardinality: Optional[Cardinality] = None) -> None:
        """Convenience helper for FK deletion: maps NOT NULL → 1..1, nullable
        → 0..1, and forwards to _remember_relationship_trace."""
        target_end_cardinality = Cardinality.ONE_TO_ONE if was_required else Cardinality.ZERO_TO_ONE
        self._remember_relationship_trace(
            holder=fk_holder, ref_name=ref_name, target=fk_target,
            target_end_cardinality=target_end_cardinality, source_end_cardinality=source_end_cardinality,
            origin=TraceOrigin.DELETED_REFERENCE,
        )

    def _consume_deleted_fk_for_edge(
        self, edge_source: str, edge_target: str
    ) -> Tuple[Optional[Cardinality], Optional[Cardinality]]:
        """Return ``(target_end_card, source_end_card)`` recovered from the
        relationship trace for the given Edge endpoints. Both ends of the trace
        entry's bidirectional cardinality are mapped to the new Edge: when the
        FK direction matches the Edge direction (same-dir), entry's two ends
        map straight through to the Edge's two ends; when the FK direction is
        reversed (opp-dir), the two ends swap.

        Lookup ignores ref_name because ADD_ENTITY does not carry the
        original FK column name. If multiple relationship trace entries
        match the same endpoint pair, the lookup logs a warning and refuses
        to guess; the caller falls back to the default cardinality.
        """
        same_dir = [t for t in self._relationship_trace
                    if t.holder == edge_source and t.target == edge_target]
        opp_dir = [t for t in self._relationship_trace
                   if t.holder == edge_target and t.target == edge_source]

        is_self_ref = edge_source == edge_target

        # Self-referential edge: same_dir and opp_dir collapse to the same
        # entries. Treat them as same-direction (the typical convention for
        # self-refs like REPORTS_TO).
        if is_self_ref:
            if not same_dir:
                return None, None
            if len(same_dir) > 1:
                logger.warning(
                    "Ambiguous relationship trace for self-ref Edge (%s, %s): "
                    "%d candidates; refusing to guess cardinality",
                    edge_source, edge_target, len(same_dir),
                )
                return None, None
            t = same_dir[0]
            self._relationship_trace.remove(t)
            return t.target_end_cardinality, t.source_end_cardinality

        # Non-self-ref: both directions matching is genuinely ambiguous.
        if same_dir and opp_dir:
            logger.warning(
                "Conflicting relationship traces for Edge (%s -> %s): both "
                "directions have matches; refusing to guess cardinality",
                edge_source, edge_target,
            )
            return None, None

        if same_dir:
            if len(same_dir) > 1:
                logger.warning(
                    "Ambiguous relationship trace for Edge (%s -> %s): "
                    "%d same-direction candidates; refusing to guess",
                    edge_source, edge_target, len(same_dir),
                )
                return None, None
            t = same_dir[0]
            self._relationship_trace.remove(t)
            return t.target_end_cardinality, t.source_end_cardinality

        if opp_dir:
            if len(opp_dir) > 1:
                logger.warning(
                    "Ambiguous relationship trace for Edge (%s -> %s): "
                    "%d opposite-direction candidates; refusing to guess",
                    edge_source, edge_target, len(opp_dir),
                )
                return None, None
            t = opp_dir[0]
            self._relationship_trace.remove(t)
            # FK direction reversed: swap the trace's two ends —
            # trace.target_end_cardinality (per trace-source, how many targets)
            # becomes the Edge's source_end_cardinality, and vice versa.
            return t.source_end_cardinality, t.target_end_cardinality

        return None, None

    @staticmethod
    def _default_source_end_cardinality(value: Optional[Cardinality]) -> Cardinality:
        """When the handler cannot recover a source-end cardinality from the
        relationship trace, substitute the unconstrained default ZERO_TO_MANY
        so the new Edge carries an explicit value instead of None. The default
        reflects the typical multiplicity at the source end of a relational FK
        (any PK admits 0..n references); it is not a universal semantic
        equivalence.
        """
        return value if value is not None else Cardinality.ZERO_TO_MANY

    @staticmethod
    def _fk_was_required(rel_target_end_cardinality: Cardinality, fk_attr: Optional[Property]) -> bool:
        """A FK / Reference is required iff its declared target-end cardinality
        has a non-zero lower bound (``is_required()``) OR the underlying property
        has NOT NULL (is_optional=False)."""
        return rel_target_end_cardinality.is_required() or (
            fk_attr is not None and not fk_attr.is_optional
        )

    def _init_source_keys(self) -> None:
        """Populate source_key_snapshot from the source schema's primary keys."""
        for entity_name, entity in self.database.entity_types.items():
            pk = entity.get_primary_key()
            if not (pk and pk.unique_properties):
                continue
            pk_attrs = [
                entity.get_property_by_id(up.property_id)
                for up in pk.unique_properties
            ]
            pk_attrs = [a for a in pk_attrs if a is not None]
            if not pk_attrs:
                continue
            first = pk_attrs[0]
            self.source_key_snapshot[entity_name] = {
                "key_field": first.name,                       # backward compat (scalar)
                "key_fields": [a.name for a in pk_attrs],      # full composite tuple
                "key_type": first.data_type.primitive_type.value if hasattr(first.data_type, 'primitive_type') else "string",
                "prefix": None,
                "generated": False,
            }

    # ── Helper utilities (shared by multiple handlers) ──────────────────
    def _get_entity(self, name: str, op_name: str = "") -> Optional[EntityType]:
        """Look up an entity by name; print [NOTICE] and return None if missing."""
        entity = self.database.get_entity_type(name)
        if not entity and op_name:
            logger.info(f"{op_name} skipped: entity '{name}' not found")
        return entity

    def _split_path(self, path: str) -> tuple:
        """Split 'entity.attr' path into (entity_name, attr_or_field_name)."""
        parts = path.split(".")
        if len(parts) < 2:
            return ("", "")
        return ".".join(parts[:-1]), parts[-1]

    def _resolve_entity_attr(self, path: str, op_name: str = "") -> tuple:
        """Parse 'entity.attr' path, look up the entity, and return (entity, attr_name)."""
        entity_name, attr_name = self._split_path(path)
        if not entity_name:
            return (None, "")
        entity = self._get_entity(entity_name, op_name)
        return (entity, attr_name)

    def _validate_join_conditions(self, join_conditions, operand_entities, op_name):
        """Validate a WHERE join condition for a cross-entity operation.

        Returns a skip reason string if a side references an entity outside the
        operation's own operands (a likely typo); otherwise ``None``. The
        condition is recorded for traceability and does not change schema
        output. Edge conditions are checked at entity level only, since the
        named relationship may already have been removed by an earlier step."""
        operand_entities = [e for e in operand_entities if e]

        def _belongs(path: str) -> bool:
            return any(path == e or path.startswith(e + ".") for e in operand_entities)

        for jc in (join_conditions or []):
            if jc.get("type") == "edge":
                if not jc.get("rel"):
                    return f"{op_name}: edge join condition is missing a relationship type"
                sides = [jc.get("from", ""), jc.get("to", "")]
            else:
                sides = [jc.get("left", ""), jc.get("right", "")]
            for s in sides:
                if s and not _belongs(s):
                    return (f"{op_name}: WHERE references '{s}', which is not part of "
                            f"this operation's entities {operand_entities}")
        return None
