"""Handlers for constraint-aware ops — keys, FKs, labels, target_end_cardinality, vertex/edge transforms."""

import logging
from typing import Dict, List

from Schema.unified_meta_schema import (
    EntityType, EntityKind, Property,
    UniqueConstraint, ForeignKeyConstraint, UniqueProperty, ForeignKeyProperty, PKTypeEnum,
    CheckConstraint, ExistenceConstraint,
    Reference, Edge, Cardinality,
    PrimitiveDataType, PrimitiveType,
    CARDINALITY_MAP, KEY_TYPE_MAP, TYPE_STR_MAP,
    TraceOrigin,
)
from parser.params import (
    OperationResult,
    AddKeyParams, DeleteKeyParams,
    AddForeignKeyParams, DeleteForeignKeyParams, CastConstraintParams,
    AddConstraintParams, DeleteConstraintParams, ConstraintBodyKind,
    AddLabelParams, DeleteLabelParams,
    RecardParams, TransformParams,
)
from parser.listeners import OpType
from core.transformer import register_handler

logger = logging.getLogger(__name__)



class KeysConstraintsHandlersMixin:
    """Mixin contributing one focused subset of `_handle_*` methods to ``SchemaTransformer``."""

    @register_handler(OpType.DELETE_FOREIGN_KEY)
    def _handle_delete_foreign_key(self, params: DeleteForeignKeyParams) -> OperationResult:
        entity_name, ref_name = self._split_path(params.reference)
        entity = self._get_entity(entity_name) if entity_name else None
        if entity:
            # Append a relationship trace entry before removing the Reference
            # so a subsequent ADD_ENTITY (EDGE) in a cross-paradigm script can
            # recover the bidirectional target_end_cardinality the FK encoded.
            fk_attr_for_trace = entity.get_property(ref_name)
            for rel in entity.relationships:
                if isinstance(rel, Reference) and rel.ref_name == ref_name:
                    self._remember_deleted_fk(
                        entity_name, ref_name, rel.refs_to,
                        self._fk_was_required(rel.target_end_cardinality, fk_attr_for_trace),
                        source_end_cardinality=rel.source_end_cardinality,
                    )
                    break

            # Remove the Reference relationship
            entity.remove_relationship(ref_name)
            # Also remove the matching ForeignKeyConstraint from entity.constraints
            # (matches SQL semantics: DROP CONSTRAINT removes FK but keeps the column)
            fk_attr = entity.get_property(ref_name)
            if fk_attr:
                entity.constraints = [
                    c for c in entity.constraints
                    if not (c.kind == "foreign_key" and
                            any(fkp.property_id == fk_attr.meta_id for fkp in c.foreign_key_properties))
                ]
            self._touch(entity_name)
            self.changes.append(f"DELETE_FOREIGN_KEY:{entity_name}.{ref_name}")
            return OperationResult.ok()
        return OperationResult.skipped("delete_foreign_key: precondition not met")

    @register_handler(OpType.ADD_FOREIGN_KEY)
    def _handle_add_foreign_key(self, params: AddForeignKeyParams) -> OperationResult:
        """ADD_FOREIGN_KEY <columns> [TO entity] REFERENCES target(<columns>)."""
        field_names = params.field_names
        target_table = params.target_table
        target_columns = params.target_columns
        entity_name = params.entity

        if not entity_name or not field_names or not target_table or not target_columns:
            return OperationResult.skipped("add_foreign_key: precondition not met")

        entity = self._get_entity(entity_name, "ADD_FOREIGN_KEY")
        if not entity:
            return OperationResult.skipped("add_foreign_key: precondition not met")

        target_entity = self._get_entity(target_table)

        # Cardinality applies to the FK as a whole, not to individual columns.
        target_end_cardinality = Cardinality.ONE_TO_ONE
        clauses = params.clauses
        if 'cardinality' in clauses:
            target_end_cardinality = CARDINALITY_MAP.get(clauses['cardinality'], Cardinality.ONE_TO_ONE)

        fk_props: List[ForeignKeyProperty] = []
        for src_col, tgt_col in zip(field_names, target_columns):
            fk_type = self._resolve_fk_type(target_entity, tgt_col)

            if not entity.get_property(src_col):
                entity.add_property(Property(src_col, fk_type, False, True))

            # Source-end cardinality: 0..1 if FK column is unique / sole PK,
            # otherwise 0..n (relational-algebra default).
            src_attr_for_uniq = entity.get_property(src_col)
            source_end_card = (
                Cardinality.ZERO_TO_ONE
                if self._is_fk_column_unique(entity, src_attr_for_uniq)
                else Cardinality.ZERO_TO_MANY
            )

            existing_ref = next(
                (r for r in entity.relationships
                 if isinstance(r, Reference) and r.ref_name == src_col),
                None,
            )
            if existing_ref:
                existing_ref.refs_to = target_table
                existing_ref.target_end_cardinality = target_end_cardinality
                existing_ref.source_end_cardinality = source_end_card
                # ADD_FOREIGN_KEY always produces an *enforced* reference. If
                # the existing Reference came from a previous logical-only
                # declaration (e.g. parsed from a Mongo cross-collection
                # description, or set by ADD_CONSTRAINT ... AS REFERENCE),
                # this op upgrades it. Without this flip the FKConstraint
                # below would be created on top of a Reference still flagged
                # as logical, leaving the meta model in an inconsistent
                # "FK enforcement enabled but Reference still labelled
                # logical" state.
                existing_ref.is_enforced = True
            else:
                entity.add_relationship(Reference(
                    ref_name=src_col, refs_to=target_table,
                    target_end_cardinality=target_end_cardinality,
                    source_end_cardinality=source_end_card,
                    is_optional=not target_end_cardinality.is_required(),
                ))

            fk_attr = entity.get_property(src_col)
            if fk_attr and target_end_cardinality.is_required():
                fk_attr.is_optional = False

            if fk_attr:
                target_up_id = self._get_target_unique_property_id(target_table, tgt_col)
                fk_props.append(ForeignKeyProperty(
                    property_id=fk_attr.meta_id,
                    points_to_unique_property_id=target_up_id,
                ))

        # One ForeignKeyConstraint per ADD_FOREIGN_KEY call — collects every
        # (src_col, tgt_col) pair as a ForeignKeyProperty entry. Skip if a
        # constraint covering exactly these source columns already exists,
        # to keep the operation idempotent.
        existing_property_id_sets = [
            {fkp.property_id for fkp in c.foreign_key_properties}
            for c in entity.constraints if c.kind == "foreign_key"
        ]
        new_property_ids = {fp.property_id for fp in fk_props}
        if fk_props and new_property_ids not in existing_property_id_sets:
            entity.add_constraint(ForeignKeyConstraint(
                is_managed=True, foreign_key_properties=fk_props,
            ))

        self._touch(entity_name)
        # Change description: name the columns for diff readability.
        cols_str = ",".join(field_names) if len(field_names) > 1 else field_names[0]
        self.changes.append(f"ADD_REF:{entity_name}.{cols_str}")
        return OperationResult.ok()

    # ------------------------------------------------------------------
    # ADD_CONSTRAINT / DELETE_CONSTRAINT
    # ------------------------------------------------------------------
    # ADD_CONSTRAINT covers the constraint kinds NOT addressed by the narrow
    # operators (PK / UNIQUE / FK / PARTITION / CLUSTERING / LABEL):
    #   * REFERENCE          -> Reference(is_enforced=False) — non-enforced
    #     cross-entity reference (Mongo cross-collection, Cass denormalised
    #     columns, self-references). The enforced FK case is intentionally
    #     not covered here: ``ADD_FOREIGN_KEY`` is the SQL-traditional path
    #     and the only one that supports composite multi-column FKs.
    #   * CHECK <expr>       -> CheckConstraint(expression=<AST>, target_property_id=<id>)
    #   * EXISTENCE          -> Property.is_optional=False (+ ExistenceConstraint marker)
    # DELETE_CONSTRAINT inspects the entity at ``entity.field`` and removes
    # whichever logical Reference / CheckConstraint / ExistenceConstraint
    # is currently anchored there.

    @register_handler(OpType.ADD_CONSTRAINT)
    def _handle_add_constraint(self, params: AddConstraintParams) -> OperationResult:
        """Dispatcher for ADD_CONSTRAINT. Delegates to a body-kind-specific"""
        if params.body_kind == ConstraintBodyKind.REFERENCE:
            return self._handle_add_constraint_reference(params)
        if params.body_kind == ConstraintBodyKind.CHECK:
            return self._handle_add_constraint_check(params)
        if params.body_kind == ConstraintBodyKind.EXISTENCE:
            return self._handle_add_constraint_existence(params)
        return OperationResult.skipped(
            f"add_constraint: unknown body kind {params.body_kind!r}")

    def _handle_add_constraint_reference(self, params: AddConstraintParams) -> OperationResult:
        """ADD_CONSTRAINT entity.field AS REFERENCE TO target(col)."""
        entity_name, field_name = self._split_path(params.target)
        if not entity_name or not field_name:
            return OperationResult.skipped(
                "add_constraint: target must be entity.field")
        entity = self._get_entity(entity_name, "ADD_CONSTRAINT")
        if not entity:
            return OperationResult.skipped(
                "add_constraint: precondition not met")
        target_table = params.ref_target_table
        target_columns = params.ref_target_columns
        if not target_table or not target_columns:
            return OperationResult.skipped(
                "add_constraint: REFERENCE body needs target table and columns")
        target_entity = self._get_entity(target_table)

        # Resolve the source-property data type. Carry the target property's
        # type if available so the meta model is consistent with the
        # equivalent ADD_FOREIGN_KEY behaviour.
        fk_type = self._resolve_fk_type(target_entity, target_columns[0])

        target_end_cardinality = Cardinality.ONE_TO_ONE
        if params.ref_cardinality:
            target_end_cardinality = CARDINALITY_MAP.get(
                params.ref_cardinality, Cardinality.ONE_TO_ONE)

        # Ensure the source property exists.
        if not entity.get_property(field_name):
            entity.add_property(Property(field_name, fk_type, False, True))

        # Mirror the target_end_cardinality's required-ness onto the source property's
        # ``is_optional``. The Reference itself records target_end_cardinality, but the
        # Mongo / PG adapters read ``Property.is_optional`` to decide whether
        # the column appears in ``required[]`` / carries ``NOT NULL``. Without
        # this propagation, an ADD_CONSTRAINT REFERENCE WITH CARDINALITY
        # ONE_TO_* would silently leave the property nullable.
        src_attr = entity.get_property(field_name)
        if src_attr is not None:
            src_attr.is_optional = not target_end_cardinality.is_required()

        # Source-end cardinality: default ZERO_TO_MANY (logical Reference
        # bears no uniqueness signal). Override to ZERO_TO_ONE only if the
        # source column happens to be unique / sole PK.
        source_end_card = (
            Cardinality.ZERO_TO_ONE
            if self._is_fk_column_unique(entity, src_attr)
            else Cardinality.ZERO_TO_MANY
        )

        # Upsert the Reference. If one already exists for this column,
        # update its target / target_end_cardinality and force ``is_enforced=False``
        # so this op cleanly downgrades a previously-enforced reference.
        existing_ref = next(
            (r for r in entity.relationships
             if isinstance(r, Reference) and r.ref_name == field_name),
            None,
        )
        if existing_ref:
            existing_ref.refs_to = target_table
            existing_ref.target_end_cardinality = target_end_cardinality
            existing_ref.source_end_cardinality = source_end_card
            existing_ref.is_enforced = False
        else:
            entity.add_relationship(Reference(
                ref_name=field_name,
                refs_to=target_table,
                target_end_cardinality=target_end_cardinality,
                source_end_cardinality=source_end_card,
                is_optional=not target_end_cardinality.is_required(),
                is_enforced=False,
            ))

        # Drop any FK constraint covering this column — logical-only state.
        fk_attr = entity.get_property(field_name)
        if fk_attr is not None:
            entity.constraints = [
                c for c in entity.constraints
                if not (c.kind == "foreign_key"
                        and any(fkp.property_id == fk_attr.meta_id
                                for fkp in c.foreign_key_properties))
            ]

        self._touch(entity_name)
        self.changes.append(
            f"ADD_CONSTRAINT:{entity_name}.{field_name}=REFERENCE_LOGICAL->"
            f"{target_table}({target_columns[0]})")
        return OperationResult.ok()

    def _handle_add_constraint_check(self, params: AddConstraintParams) -> OperationResult:
        """ADD_CONSTRAINT entity.field AS CHECK <expr>."""
        entity, field_name = self._resolve_entity_attr(
            params.target, "ADD_CONSTRAINT")
        if not entity or not field_name:
            return OperationResult.skipped(
                "add_constraint: precondition not met")
        anchor_attr = entity.get_property(field_name)
        if anchor_attr is None:
            return OperationResult.skipped(
                f"add_constraint: anchor property {params.target!r} not found")

        entity.add_constraint(CheckConstraint(
            expression=params.check_expression,
            target_property_id=anchor_attr.meta_id,
        ))
        self._touch(entity.full_path)
        self.changes.append(
            f"ADD_CONSTRAINT:{params.target}=CHECK")
        return OperationResult.ok()

    def _handle_add_constraint_existence(self, params: AddConstraintParams) -> OperationResult:
        """ADD_CONSTRAINT entity.field AS EXISTENCE."""
        entity, field_name = self._resolve_entity_attr(
            params.target, "ADD_CONSTRAINT")
        if not entity or not field_name:
            return OperationResult.skipped(
                "add_constraint: precondition not met")
        attr = entity.get_property(field_name)
        if attr is None:
            return OperationResult.skipped(
                f"add_constraint: property {params.target!r} not found")
        attr.is_optional = False

        already = any(
            c.kind == "existence" and c.target_property_id == attr.meta_id
            for c in entity.constraints
        )
        if not already:
            entity.add_constraint(ExistenceConstraint(
                target_property_id=attr.meta_id,
            ))
        self._touch(entity.full_path)
        self.changes.append(f"ADD_CONSTRAINT:{params.target}=EXISTENCE")
        return OperationResult.ok()

    @register_handler(OpType.DELETE_CONSTRAINT)
    def _handle_delete_constraint(self, params: DeleteConstraintParams) -> OperationResult:
        """DELETE_CONSTRAINT entity.field."""
        entity, field_name = self._resolve_entity_attr(
            params.target, "DELETE_CONSTRAINT")
        if not entity or not field_name:
            return OperationResult.skipped(
                "delete_constraint: precondition not met")

        removed_kinds = []

        # 1. Logical references (Reference.is_enforced == False).
        # Mirrors DELETE_FOREIGN_KEY's trace hook: append a relationship trace
        # entry before removing the Reference, so a later ADD_ENTITY (EDGE) /
        # TRANSFORM can recover its bidirectional target_end_cardinality.
        new_relationships = []
        removed_logical_ref = False
        for rel in entity.relationships:
            if (isinstance(rel, Reference)
                    and rel.ref_name == field_name
                    and rel.is_enforced is False):
                self._remember_relationship_trace(
                    holder=entity.full_path,
                    ref_name=field_name,
                    target=rel.refs_to,
                    target_end_cardinality=rel.target_end_cardinality,
                    source_end_cardinality=rel.source_end_cardinality,
                )
                removed_kinds.append("REFERENCE_LOGICAL")
                removed_logical_ref = True
                continue
            new_relationships.append(rel)
        entity.relationships = new_relationships

        # Restore is_optional=True on the anchor property when the deleted
        # logical Reference had imposed a required target_end_cardinality. Symmetric with
        # the EXISTENCE branch below — the property's nullability constraint
        # was an artefact of the now-removed Reference, so the default
        # (optional) state is reasserted. Without this restoration, scripts
        # that briefly declare a logical FK only to capture target_end_cardinality for
        # the relationship trace would leave the column NOT NULL even after
        # the FK is dropped.
        if removed_logical_ref:
            attr = entity.get_property(field_name)
            if attr is not None:
                attr.is_optional = True

        # 2. CheckConstraint and ExistenceConstraint anchored to this property.
        attr = entity.get_property(field_name)
        if attr is not None:
            anchor_id = attr.meta_id
            kept = []
            for c in entity.constraints:
                if c.kind == "check" and c.target_property_id == anchor_id:
                    removed_kinds.append("CHECK")
                    continue
                if c.kind == "existence" and c.target_property_id == anchor_id:
                    removed_kinds.append("EXISTENCE")
                    # Restore is_optional default — symmetric with how the
                    # EXISTENCE handler set it to False.
                    attr.is_optional = True
                    continue
                kept.append(c)
            entity.constraints = kept

        if not removed_kinds:
            return OperationResult.skipped(
                f"delete_constraint: no ADD_CONSTRAINT object anchored at "
                f"{params.target!r}")

        self._touch(entity.full_path)
        self.changes.append(
            f"DELETE_CONSTRAINT:{params.target}={'+'.join(removed_kinds)}")
        return OperationResult.ok()

    @register_handler(OpType.DELETE_KEY)
    def _handle_delete_key(self, params: DeleteKeyParams) -> OperationResult:
        """DELETE PRIMARY/FOREIGN/UNIQUE KEY - destructive removal"""
        return self._remove_key_constraint(params, operation="DELETE")

    @register_handler(OpType.ADD_KEY)
    def _handle_add_key(self, params: AddKeyParams) -> OperationResult:
        """ADD KEY id AS String — or ADD PRIMARY KEY (id1, id2) TO Customer (composite)."""
        entity_name = params.entity
        key_columns = params.key_columns
        if not key_columns:
            return OperationResult.skipped("add_key: precondition not met")

        key_data_type = (
            PrimitiveDataType(TYPE_STR_MAP.get(params.data_type.upper(), PrimitiveType.STRING))
            if params.data_type
            else PrimitiveDataType(PrimitiveType.INTEGER)
        )

        entity = self.database.get_entity_type(entity_name) if entity_name else None

        # Validate the whole key BEFORE mutating anything (auto-creating the
        # entity or promoting properties). A reject must leave the meta-model
        # untouched: previously the entity was auto-created and the earlier
        # columns of a composite key were already promoted to ``is_key`` before
        # a later column triggered the reject — leaking a half-applied mutation
        # into Meta V2 while the op was reported as a clean skip.
        explicit = bool(params.data_type)
        for col_name in key_columns:
            reject_reason = self._check_key_property(
                entity, entity_name, col_name, key_data_type, explicit
            )
            if reject_reason:
                return OperationResult.skipped(reject_reason)

        if not entity:
            logger.info(f"ADD_KEY: entity '{entity_name}' not found, auto-creating")
            entity = EntityType(object_name=[entity_name] if entity_name else ["unnamed"])
            self.database.add_entity_type(entity)

        key_attrs = self._upsert_key_properties(entity, key_columns, key_data_type)
        key_type_str, pk_type_enum = self._resolve_pk_type(params.key_type)
        constraint = self._build_key_constraint(
            key_attrs, key_type_str, pk_type_enum
        )

        # For PK constraints, Cassandra PARTITION/CLUSTERING may append to an
        # existing PK (and short-circuit this handler), while a regular PK
        # replaces any existing one. FK / UNIQUE just get added at the end.
        cleared_up_map: Dict[str, str] = {}
        if constraint.kind == "unique" and constraint.is_primary_key:
            if self._append_to_existing_pk(entity, constraint, pk_type_enum):
                self._touch(entity_name)
                self.changes.append(f"ADD_KEY:{entity_name}.({', '.join(key_columns)})")
                return OperationResult.ok()
            if pk_type_enum == PKTypeEnum.SIMPLE:
                cleared_up_map = self._clear_existing_pk(entity, key_columns)

        entity.add_constraint(constraint)
        relinked_entities = (
            self._relink_fks_after_pk_replacement(entity, cleared_up_map, constraint)
            if cleared_up_map else []
        )
        self._touch(entity_name, *relinked_entities)
        self.changes.append(f"ADD_KEY:{entity_name}.({', '.join(key_columns)})")
        return OperationResult.ok()

    def _check_key_property(self, entity, entity_name, col_name, key_data_type, data_type_explicit):
        """Non-mutating validation for one ADD_KEY column.

        Returns a user-facing reject reason when ADD_KEY must refuse — so the
        caller can ``skip`` *before* touching the meta-model — or ``None`` when
        the column is acceptable. Two strict rules guard the silent mutations
        this used to allow:

        - Case ④: the property does not exist and no type was declared via
          ``AS`` (a silent INTEGER fallback would invent a type). ``entity``
          may be ``None`` here when the target entity does not yet exist —
          treat that the same as a missing property.
        - Case ②b: the property exists with a different type than the ``AS``
          clause requests (a silent type rewrite); point at CAST_PROPERTY.
        """
        attr = entity.get_property(col_name) if entity else None
        label = entity.name if entity else entity_name
        if not attr:
            if not data_type_explicit:
                # Case ④: refuse rather than guess; tell the user the two
                # explicit paths that resolve the situation.
                return (
                    f"property '{col_name}' does not exist on "
                    f"'{label}'; ADD_KEY requires either an "
                    f"explicit type via 'AS <Type>' or a preceding "
                    f"'ADD_PROPERTY {col_name} TO {label} "
                    f"WITH TYPE <Type>'"
                )
            return None
        if data_type_explicit:
            # Case ②: AS clause given on a property that already has a type.
            # Compare to detect a silent rewrite.
            old_primitive = (
                attr.data_type.primitive_type.value
                if hasattr(attr.data_type, 'primitive_type')
                else 'unknown'
            )
            new_primitive = (
                key_data_type.primitive_type.value
                if hasattr(key_data_type, 'primitive_type')
                else 'unknown'
            )
            if old_primitive != new_primitive:
                # Case ②b: the error message includes the literal command
                # the user needs so they can copy-paste the fix.
                return (
                    f"property '{label}.{col_name}' already "
                    f"exists with type '{old_primitive}'; the AS "
                    f"clause requested '{new_primitive}'. ADD_KEY "
                    f"does not change property types — use "
                    f"'CAST_PROPERTY {label}.{col_name} TO "
                    f"<Type>' first if you intended to change the "
                    f"type."
                )
        return None

    def _upsert_key_properties(self, entity, key_columns, key_data_type):
        """Promote (or create) the Property for each member of a (possibly
        composite) key, returning the resolved Property objects.

        ``_check_key_property`` has already validated every column, so the two
        remaining cases are both safe to mutate: a missing property is created
        with the explicitly declared type (case ③ — validation guarantees the
        type was declared); an existing property is promoted to key without
        touching its ``data_type`` (cases ① / ②a — preserving any max_length /
        precision the AS form would lose)."""
        key_attrs = []
        for col_name in key_columns:
            attr = entity.get_property(col_name)
            if not attr:
                # Validated case ③: create with the explicitly declared type.
                attr = Property(col_name, key_data_type, True, False)
                entity.add_property(attr)
            else:
                # Validated case ① / ②a: promote without rewriting data_type.
                attr.is_key = True
                attr.is_optional = False
            key_attrs.append(attr)
        return key_attrs

    def _resolve_pk_type(self, key_type_param):
        """Translate the SMILE key_type string into (sql_kind, PKTypeEnum)."""
        mapped = KEY_TYPE_MAP.get(key_type_param, "primary")
        if isinstance(mapped, PKTypeEnum):
            return "primary", mapped
        return mapped, PKTypeEnum.SIMPLE

    def _build_key_constraint(self, key_attrs, key_type_str, pk_type_enum):
        """Construct a UniqueConstraint from the resolved key attributes.

        ADD_KEY only handles PRIMARY / UNIQUE / PARTITION / CLUSTERING. Foreign
        keys are routed to ADD_FOREIGN_KEY (``_handle_add_foreign_key``), so no
        foreign-key branch is needed here.
        """
        unique_props = [
            UniqueProperty(primary_key_type=pk_type_enum, property_id=attr.meta_id)
            for attr in key_attrs
        ]
        return UniqueConstraint(
            is_primary_key=(key_type_str == "primary"),
            is_managed=True,
            unique_properties=unique_props,
        )

    def _append_to_existing_pk(self, entity, constraint, pk_type_enum):
        """If the new key is a Cassandra PARTITION/CLUSTERING column and the"""
        if pk_type_enum not in (PKTypeEnum.PARTITION, PKTypeEnum.CLUSTERING):
            return OperationResult.skipped("add_key: precondition not met")
        existing_pk = next(
            (c for c in entity.constraints
             if c.kind == "unique" and c.is_primary_key),
            None,
        )
        if not existing_pk:
            return OperationResult.skipped("add_key: precondition not met")
        existing_ids = {up.property_id for up in existing_pk.unique_properties}
        for up in constraint.unique_properties:
            if up.property_id not in existing_ids:
                existing_pk.unique_properties.append(up)
        return OperationResult.ok()

    def _clear_existing_pk(self, entity, incoming_key_columns):
        """Drop existing PK constraint; return {cleared_up_meta_id: prop_name}
        so the caller can relink dangling FK pointers."""
        cleared_up_map: Dict[str, str] = {}
        for old_c in entity.constraints:
            if old_c.kind == "unique" and old_c.is_primary_key:
                for up in old_c.unique_properties:
                    old_attr = entity.get_property_by_id(up.property_id)
                    if old_attr:
                        cleared_up_map[up.meta_id] = old_attr.name
                        if old_attr.name not in incoming_key_columns:
                            old_attr.is_key = False
        entity.constraints = [
            c for c in entity.constraints
            if not (c.kind == "unique" and c.is_primary_key)
        ]
        return cleared_up_map

    def _relink_fks_after_pk_replacement(
        self, target_entity, cleared_up_map: Dict[str, str], new_constraint
    ) -> List[str]:
        """Rewrite FK pointers from cleared UniqueProperty meta_ids to the
        new constraint's, matched by property name. Returns the list of
        entity names whose FKs were modified, so the caller can _touch() them."""
        if not cleared_up_map:
            return []
        new_name_to_up_id: Dict[str, str] = {}
        for up in new_constraint.unique_properties:
            attr = target_entity.get_property_by_id(up.property_id)
            if attr:
                new_name_to_up_id[attr.name] = up.meta_id
        if not new_name_to_up_id:
            return []
        modified: List[str] = []
        for entity in self.database.entity_types.values():
            entity_was_modified = False
            for c in entity.constraints:
                if c.kind != "foreign_key":
                    continue
                for fkp in c.foreign_key_properties:
                    old_up_id = fkp.points_to_unique_property_id
                    if old_up_id in cleared_up_map:
                        new_up_id = new_name_to_up_id.get(
                            cleared_up_map[old_up_id])
                        if new_up_id:
                            fkp.points_to_unique_property_id = new_up_id
                            entity_was_modified = True
            if entity_was_modified:
                modified.append(entity.full_path)
        return modified

    @staticmethod
    def _is_fk_column_unique(entity, attr) -> bool:
        """A FK column counts as ``unique`` if it has a single-column UNIQUE
        constraint of its own, or if it is the sole column of the entity's PK.
        Used to derive Reference.source_end_cardinality: unique → 0..1, else 0..n."""
        if not attr:
            return False
        for c in entity.constraints:
            if (c.kind == "unique" and not c.is_primary_key
                    and len(c.unique_properties) == 1
                    and c.unique_properties[0].property_id == attr.meta_id):
                return True
        pk = entity.get_primary_key()
        if (pk and len(pk.unique_properties) == 1
                and pk.unique_properties[0].property_id == attr.meta_id):
            return True
        return False

    @staticmethod
    def _resolve_fk_type(target_entity, target_col: str) -> PrimitiveDataType:
        """Resolve an FK column's data type from the target's column or, failing
        that, from the target's primary key. Defaults to INTEGER when nothing
        is resolvable."""
        fallback = PrimitiveDataType(PrimitiveType.INTEGER)
        if not target_entity:
            return fallback
        tgt_attr = target_entity.get_property(target_col)
        if tgt_attr is not None:
            return tgt_attr.data_type
        target_pk = target_entity.get_primary_key()
        if target_pk and target_pk.unique_properties:
            pk_attr = target_entity.get_property_by_id(target_pk.unique_properties[0].property_id)
            if pk_attr:
                return pk_attr.data_type
        return fallback

    def _get_target_unique_property_id(self, target_entity_name: str, target_attr_name: str) -> str:
        """Get the UniqueProperty meta_id for a target entity's property (for FK references)."""
        if not target_entity_name:
            return ""
        target_entity = self.database.get_entity_type(target_entity_name)
        if not target_entity:
            return ""
        target_pk = target_entity.get_primary_key()
        if not target_pk or not target_pk.unique_properties:
            return ""
        # If target_attr_name is specified, find matching UniqueProperty
        if target_attr_name:
            for up in target_pk.unique_properties:
                attr = target_entity.get_property_by_id(up.property_id)
                if attr and attr.name == target_attr_name:
                    return up.meta_id
        # Default to first UniqueProperty
        return target_pk.unique_properties[0].meta_id

    def _remove_key_constraint(self, params: DeleteKeyParams, operation: str = "DELETE") -> bool:
        """Helper method for DELETE_KEY operations"""
        entity_name = params.entity
        key_columns = params.key_columns  # List of column names
        key_type_str = KEY_TYPE_MAP.get(params.key_type, "primary")

        entity = self.database.get_entity_type(entity_name) if entity_name else None
        if not entity or not key_columns:
            return OperationResult.skipped("delete_key: precondition not met")

        key_columns_set = set(key_columns)

        for constraint in list(entity.constraints):
            if key_type_str in ("primary", "unique") and constraint.kind == "unique":
                is_primary = (key_type_str == "primary")
                if constraint.is_primary_key == is_primary:
                    # Check if all constraint columns match
                    constraint_attr_names = set()
                    for up in constraint.unique_properties:
                        up_attr = entity.get_property_by_id(up.property_id)
                        if up_attr:
                            constraint_attr_names.add(up_attr.name)
                    if constraint_attr_names == key_columns_set:
                        entity.constraints.remove(constraint)
                        for up in constraint.unique_properties:
                            up_attr = entity.get_property_by_id(up.property_id)
                            if up_attr:
                                up_attr.is_key = False
                        key_names_str = ", ".join(key_columns)
                        self.changes.append(f"{operation}_KEY:{entity_name}.({key_names_str})")
                        return OperationResult.ok()

            elif isinstance(key_type_str, PKTypeEnum) and constraint.kind == "unique":
                # Cassandra PARTITION/CLUSTERING keys: remove matching properties
                removed_any = False
                for up in list(constraint.unique_properties):
                    if up.primary_key_type == key_type_str:
                        up_attr = entity.get_property_by_id(up.property_id)
                        if up_attr and up_attr.name in key_columns_set:
                            constraint.unique_properties.remove(up)
                            up_attr.is_key = False
                            # In Cassandra, the only way for a column to be
                            # non-null is to be part of the partition or
                            # clustering key. Removing it from the key must
                            # therefore restore is_optional=True, mirroring
                            # ADD_KEY's symmetric is_optional=False on
                            # promotion. A subsequent SMILE op (ADD_KEY,
                            # ADD_FOREIGN_KEY, ADD_CONSTRAINT REFERENCE with
                            # required target_end_cardinality) is responsible for
                            # re-asserting non-null if intended.
                            up_attr.is_optional = True
                            removed_any = True
                if removed_any:
                    key_names_str = ", ".join(key_columns)
                    self.changes.append(f"{operation}_KEY:{entity_name}.({key_names_str})")
                    if not constraint.unique_properties:
                        entity.constraints.remove(constraint)
                    self._touch(entity_name)
                    return OperationResult.ok()
        return OperationResult.skipped("delete_key: precondition not met")

    @register_handler(OpType.DELETE_LABEL)
    def _handle_delete_label(self, params: DeleteLabelParams) -> OperationResult:
        """DELETE LABEL Vendor FROM suppliers (graph database)"""
        label = params.label
        entity_name = params.entity

        entity = self._get_entity(entity_name, "DELETE_LABEL") if entity_name else None
        if not entity:
            return OperationResult.skipped("delete_label: precondition not met")

        if label in entity.labels:
            entity.labels.remove(label)
        self._touch(entity_name)
        self.changes.append(f"DELETE_LABEL:{entity_name}.{label}")
        return OperationResult.ok()

    @register_handler(OpType.ADD_LABEL)
    def _handle_add_label(self, params: AddLabelParams) -> OperationResult:
        """ADD LABEL Vendor TO suppliers (graph database)"""
        label = params.label
        entity_name = params.entity

        entity = self._get_entity(entity_name, "ADD_LABEL") if entity_name else None
        if not entity or not label:
            return OperationResult.skipped("add_label: precondition not met")

        if entity.entity_kind == EntityKind.EDGE:
            reason = (
                f"add_label: edge '{entity_name}' cannot take an extra label "
                f"'{label}', since Neo4j relationships carry a single type"
            )
            logger.warning("%s", reason)
            return OperationResult.skipped(reason)

        if label not in entity.labels:
            entity.labels.append(label)
        self._touch(entity_name)
        self.changes.append(f"ADD_LABEL:{entity_name}.{label}")
        return OperationResult.ok()

    @register_handler(OpType.CAST_CONSTRAINT)
    def _handle_cast_constraint(self, params: CastConstraintParams) -> OperationResult:
        """CAST_CONSTRAINT: Change the type of a constraint."""
        target = params.target
        new_type = params.constraint_type  # PRIMARY_KEY, UNIQUE_KEY, PARTITION_KEY, CLUSTERING_KEY, NODE_KEY, DOCUMENT_ID

        entity, attr_name = self._resolve_entity_attr(target)
        if not entity:
            return OperationResult.skipped("cast_constraint: precondition not met")

        # Find the property
        attr = entity.get_property(attr_name)
        if not attr:
            return OperationResult.skipped("cast_constraint: precondition not met")

        # Find constraint containing this property and modify its type
        for constraint in entity.constraints:
            if constraint.kind == "unique":
                for up in constraint.unique_properties:
                    if up.property_id == attr.meta_id:
                        if new_type == "PRIMARY_KEY":
                            constraint.is_primary_key = True
                            up.primary_key_type = PKTypeEnum.SIMPLE
                        elif new_type == "UNIQUE_KEY":
                            constraint.is_primary_key = False
                        elif new_type == "PARTITION_KEY":
                            constraint.is_primary_key = True
                            up.primary_key_type = PKTypeEnum.PARTITION
                        elif new_type == "CLUSTERING_KEY":
                            constraint.is_primary_key = True
                            up.primary_key_type = PKTypeEnum.CLUSTERING
                        elif new_type == "NODE_KEY":
                            constraint.is_primary_key = True
                            up.primary_key_type = PKTypeEnum.NODE_KEY
                        elif new_type == "DOCUMENT_ID":
                            constraint.is_primary_key = True
                            up.primary_key_type = PKTypeEnum.DOCUMENT_ID
                        self._touch(entity.name)
                        self.changes.append(f"CAST_CONSTRAINT:{target}->{new_type}")
                        return OperationResult.ok()
        return OperationResult.skipped("cast_constraint: precondition not met")

    @register_handler(OpType.RECARD)
    def _handle_recard(self, params: RecardParams) -> OperationResult:
        """RECARD: Change the target-end cardinality of a Reference or Edge.

        ``source_end_cardinality`` is intentionally preserved across this operation;
        SMILE currently has no TARGET_CARDINALITY grammar clause, so the reverse
        side is only mutated by re-derivation from the trace at the next Edge
        construction (or by explicit ADD_FOREIGN_KEY re-declaration).
        """
        target = params.target
        new_target_end_cardinality_str = params.cardinality

        entity, ref_name = self._resolve_entity_attr(target)
        if not entity:
            return OperationResult.skipped("recard: precondition not met")

        new_target_end_cardinality = CARDINALITY_MAP.get(new_target_end_cardinality_str, None)
        if not new_target_end_cardinality:
            return OperationResult.skipped("recard: precondition not met")

        # Find the reference relationship and update its target_end_cardinality
        for rel in entity.relationships:
            if isinstance(rel, Reference) and rel.ref_name == ref_name:
                rel.target_end_cardinality = new_target_end_cardinality
                self._touch(entity.name)
                self.changes.append(f"RECARD:{target}->{new_target_end_cardinality_str}")
                return OperationResult.ok()
            elif isinstance(rel, Edge) and rel.rel_type_name == ref_name:
                # Edge target_end_cardinality is duplicated on the EDGE entity and on the
                # Edge relationship object; sync both via helper so they
                # cannot drift apart.
                self._sync_edge_target_end_cardinality(ref_name, new_target_end_cardinality)
                self._touch(entity.name, ref_name)
                self.changes.append(f"RECARD:{target}->{new_target_end_cardinality_str}")
                return OperationResult.ok()
        return OperationResult.skipped("recard: precondition not met")

    def _sync_edge_target_end_cardinality(self, edge_name: str, new_target_end_cardinality: Cardinality) -> None:
        """Keep the target_end_cardinality of an EDGE consistent across its two storage sites."""
        edge_entity = self.database.get_entity_type(edge_name)
        if not edge_entity or edge_entity.entity_kind != EntityKind.EDGE:
            return
        edge_entity.edge_target_end_cardinality = new_target_end_cardinality
        if edge_entity.source_entity:
            source_ent = self.database.get_entity_type(edge_entity.source_entity)
            if source_ent:
                for rel in source_ent.relationships:
                    if isinstance(rel, Edge) and rel.rel_type_name == edge_name:
                        rel.target_end_cardinality = new_target_end_cardinality
                        break

    @register_handler(OpType.TRANSFORM)
    def _handle_transform(self, params: TransformParams) -> OperationResult:
        """TRANSFORM: Convert between entity (node) and relationship type (edge)."""
        name = params.name
        target_type = params.target_type

        if target_type == "RELATIONSHIP":
            source_entity_name = params.source_entity
            target_entity_name = params.target_entity

            entity = self._get_entity(name, "TRANSFORM")
            if not entity:
                return OperationResult.skipped("transform: precondition not met")

            # Resolve target_end_cardinality (default: ZERO_TO_MANY)
            script_set_target_end_cardinality = bool(params.cardinality)
            target_end_cardinality = Cardinality.ZERO_TO_MANY
            if script_set_target_end_cardinality:
                target_end_cardinality = CARDINALITY_MAP.get(params.cardinality, Cardinality.ZERO_TO_MANY)

            recovered_source, recovered_target = self._consume_deleted_fk_for_edge(
                source_entity_name, target_entity_name, edge_name=name
            )
            if recovered_source is not None and not script_set_target_end_cardinality:
                target_end_cardinality = recovered_source
            recovered_target = self._default_source_end_cardinality(recovered_target)

            # Convert VERTEX -> EDGE
            entity.entity_kind = EntityKind.EDGE
            entity.source_entity = source_entity_name
            entity.target_entity = target_entity_name
            entity.edge_target_end_cardinality = target_end_cardinality
            entity.edge_source_end_cardinality = recovered_target

            # Add Edge to source entity's relationships (avoid duplicates)
            source_ent = self.database.get_entity_type(source_entity_name)
            if source_ent:
                existing_edge = any(
                    isinstance(r, Edge) and r.rel_type_name == name
                    for r in source_ent.relationships
                )
                if not existing_edge:
                    edge = Edge(
                        rel_type_name=name,
                        source_entity=source_entity_name,
                        target_entity=target_entity_name,
                        target_end_cardinality=target_end_cardinality,
                        source_end_cardinality=recovered_target,
                    )
                    source_ent.add_relationship(edge)

            self.changes.append(f"TRANSFORM:{name}->RELATIONSHIP({source_entity_name},{target_entity_name})")
            return OperationResult.ok()

        elif target_type == "ENTITY":
            edge_entity = self._get_entity(name, "TRANSFORM")
            if not edge_entity or edge_entity.entity_kind != EntityKind.EDGE:
                return OperationResult.skipped("transform: precondition not met")

            # Remember the edge's bidirectional cardinality (scoped to this
            # edge name via the TRANSFORMED_EDGE origin) BEFORE nulling the
            # fields, so a later VERTEX->EDGE TRANSFORM of the same name can
            # recover it. The scoping (origin + ref_name match in
            # _consume_deleted_fk_for_edge) stops an unrelated ADD_ENTITY /
            # TRANSFORM on the same endpoint pair from claiming this cardinality.
            # Skip the write when there is nothing to remember (both ends None):
            # an all-None trace would only ever yield the same defaults a missing
            # trace does, so omitting it keeps the trace list free of dead entries.
            if (edge_entity.edge_target_end_cardinality is not None
                    or edge_entity.edge_source_end_cardinality is not None):
                self._remember_relationship_trace(
                    holder=edge_entity.source_entity,
                    ref_name=name,
                    target=edge_entity.target_entity,
                    target_end_cardinality=edge_entity.edge_target_end_cardinality,
                    source_end_cardinality=edge_entity.edge_source_end_cardinality,
                    origin=TraceOrigin.TRANSFORMED_EDGE,
                )

            # Remove Edge from source entity's relationships
            if edge_entity.source_entity:
                source_ent = self.database.get_entity_type(edge_entity.source_entity)
                if source_ent:
                    source_ent.remove_relationship(name)

            # Convert EDGE -> VERTEX
            edge_entity.entity_kind = EntityKind.VERTEX
            edge_entity.source_entity = None
            edge_entity.target_entity = None
            edge_entity.edge_target_end_cardinality = None
            edge_entity.edge_source_end_cardinality = None

            self.changes.append(f"TRANSFORM:{name}->ENTITY")
            return OperationResult.ok()
        return OperationResult.skipped("transform: precondition not met")
