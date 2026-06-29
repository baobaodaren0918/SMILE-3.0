"""Handlers for plain schema-edit ops — ADD/DELETE/RENAME × {PROPERTY, ENTITY, EMBEDDED} + COPY/MOVE."""

import copy
import logging
from typing import List

from Schema.unified_meta_schema import (
    EntityType, EntityKind, Property,
    UniqueConstraint, UniqueProperty, PKTypeEnum,
    Reference, Embedded, Edge, Cardinality,
    PrimitiveDataType, PrimitiveType,
    CARDINALITY_MAP, TYPE_STR_MAP,
)
from parser.params import (
    OperationResult,
    AddEntityParams, DeleteEntityParams, RenameEntityParams, CopyEntityParams,
    AddPropertyParams, DeletePropertyParams, RenamePropertyParams,
    CopyPropertyParams, MovePropertyParams,
    AddEmbeddedParams, DeleteEmbeddedParams,
)
from parser.listeners import OpType
from core.transformer import register_handler

logger = logging.getLogger(__name__)



class CRUDHandlersMixin:
    """Mixin contributing one focused subset of `_handle_*` methods to ``SchemaTransformer``."""

    @register_handler(OpType.ADD_PROPERTY)
    def _handle_add_property(self, params: AddPropertyParams) -> OperationResult:
        """ADD PROPERTY email TO Customer WITH TYPE String NOT NULL"""
        name = params.name
        entity_name = params.entity
        clauses = params.clauses

        # Parse data type and options from clauses
        data_type = PrimitiveDataType(PrimitiveType.STRING)
        is_optional = True

        for c in clauses:
            if c["type"] == "TYPE":
                type_str = c["data_type"].upper()
                data_type = PrimitiveDataType(TYPE_STR_MAP.get(type_str, PrimitiveType.STRING))
            elif c["type"] == "NOT_NULL":
                is_optional = False

        entity = self._get_entity(entity_name, "ADD_PROPERTY") if entity_name else None
        if not entity:
            return OperationResult.skipped("add_property: precondition not met")
        entity.add_property(Property(name, data_type, False, is_optional))
        self._touch(entity_name)
        self.changes.append(f"ADD_PROP:{entity_name}.{name}")
        return OperationResult.ok()

    @register_handler(OpType.ADD_EMBEDDED)
    def _handle_add_embedded(self, params: AddEmbeddedParams) -> OperationResult:
        """ADD EMBEDDED address TO Customer WITH CARDINALITY ONE_TO_ONE"""
        name = params.name
        entity_name = params.entity
        clauses = params.clauses

        target_end_cardinality = Cardinality.ONE_TO_ONE
        for c in clauses:
            if c["type"] == "CARDINALITY":
                target_end_cardinality = CARDINALITY_MAP.get(c["value"], Cardinality.ONE_TO_ONE)

        entity = self._get_entity(entity_name, "ADD_EMBEDDED") if entity_name else None
        if entity:
            is_optional = not target_end_cardinality.is_required()
            entity.add_relationship(Embedded(aggr_name=name, aggregates=name, target_end_cardinality=target_end_cardinality, is_optional=is_optional))
            # Create the child entity so ADD_PROPERTY can target it
            if not self.database.get_entity_type(name):
                self.database.add_entity_type(EntityType(object_name=[name]))
            self._touch(entity_name, name)
            self.changes.append(f"ADD_EMBEDDED:{entity_name}.{name}")
            return OperationResult.ok()
        return OperationResult.skipped("add_embedded: precondition not met")

    @register_handler(OpType.ADD_ENTITY)
    def _handle_add_entity(self, params: AddEntityParams) -> OperationResult:
        """ADD_ENTITY Product WITH PROPERTIES (id String, name String)"""
        name = params.name
        clauses = params.clauses
        source_entity = params.source_entity
        target_entity = params.target_entity

        new_entity = EntityType(object_name=[name])

        # Process clauses for properties and key (shared by regular and EDGE entities)
        key_name = None
        for c in clauses:
            if c["type"] == "PROPERTIES":
                for attr_def in c["properties"]:
                    attr_name = attr_def["name"]
                    data_type_str = attr_def.get("data_type", "String").upper()
                    prim_type = TYPE_STR_MAP.get(data_type_str, PrimitiveType.STRING)
                    new_entity.add_property(Property(attr_name, PrimitiveDataType(prim_type), False, True))
            elif c["type"] == "KEY":
                key_name = c["key_name"]

        # EDGE entity (relationship type): set kind and source/target
        if source_entity and target_entity:
            new_entity.entity_kind = EntityKind.EDGE
            new_entity.source_entity = source_entity
            new_entity.target_entity = target_entity

            # Resolve target_end_cardinality (default: ZERO_TO_MANY)
            script_set_target_end_cardinality = bool(params.cardinality)
            target_end_cardinality = Cardinality.ZERO_TO_MANY
            if script_set_target_end_cardinality:
                target_end_cardinality = CARDINALITY_MAP.get(params.cardinality, Cardinality.ZERO_TO_MANY)

            # Recover side-aware target_end_cardinality from a recently-deleted FK; only
            # override the script's value when it was left at the default
            # (never silently contradict an explicit target_end_cardinality clause).
            # No edge_name passed: ADD_ENTITY deliberately does NOT consume
            # TRANSFORMED_EDGE traces (those are scoped to a TRANSFORM round-trip
            # of the same edge name).
            # NB: _consume_deleted_fk_for_edge returns (target_end, source_end)
            # in that order — keep the unpacking names aligned with the contract
            # so a future rename can't silently swap the two Edge ends.
            recovered_target_end, recovered_source_end = self._consume_deleted_fk_for_edge(
                source_entity, target_entity
            )
            if recovered_target_end is not None and not script_set_target_end_cardinality:
                target_end_cardinality = recovered_target_end
            recovered_source_end = self._default_source_end_cardinality(recovered_source_end)

            new_entity.edge_target_end_cardinality = target_end_cardinality
            new_entity.edge_source_end_cardinality = recovered_source_end

            # Validate source and target exist
            source_ent = self.database.get_entity_type(source_entity)
            if not source_ent:
                logger.info(f"ADD_ENTITY (EDGE) skipped: source entity '{source_entity}' not found")
                return OperationResult.skipped("add_entity: precondition not met")
            target_ent = self.database.get_entity_type(target_entity)
            if not target_ent:
                logger.info(f"ADD_ENTITY (EDGE) skipped: target entity '{target_entity}' not found")
                return OperationResult.skipped("add_entity: precondition not met")

            # Add Edge to source entity's relationships
            edge = Edge(
                rel_type_name=name,
                source_entity=source_entity,
                target_entity=target_entity,
                target_end_cardinality=target_end_cardinality,
                source_end_cardinality=recovered_source_end,
            )
            source_ent.add_relationship(edge)

            self.database.add_entity_type(new_entity)
            self._touch(name, source_entity, target_entity)
            self.changes.append(f"ADD_ENTITY:{name}({source_entity}->{target_entity})")
            return OperationResult.ok()

        # Regular entity: set primary key if specified
        if key_name:
            attr = new_entity.get_property(key_name)
            if attr:
                attr.is_key = True
                attr.is_optional = False
                constraint = UniqueConstraint(
                    is_primary_key=True,
                    is_managed=True,
                    unique_properties=[UniqueProperty(primary_key_type=PKTypeEnum.SIMPLE, property_id=attr.meta_id)]
                )
                new_entity.add_constraint(constraint)

        self.database.add_entity_type(new_entity)
        self._touch(name)
        self.changes.append(f"ADD_ENTITY:{name}")
        return OperationResult.ok()

    @register_handler(OpType.DELETE_PROPERTY)
    def _handle_delete_property(self, params: DeletePropertyParams) -> OperationResult:
        """DELETE PROPERTY Customer.email"""
        target = params.target
        entity, attr_name = self._resolve_entity_attr(target)
        if not entity:
            return OperationResult.skipped("delete_property: precondition not met")

        # Get meta_id before removal for constraint cleanup. Surface a clear
        # skip reason when the property does not exist on the resolved entity
        # — silently succeeding would let users believe their script applied.
        attr = entity.get_property(attr_name)
        if not attr:
            return OperationResult.skipped(
                f"delete_property: '{attr_name}' not found on {entity.name}"
            )
        attr_meta_id = attr.meta_id

        self._touch(entity.name)

        # If the property has an associated Reference, append a relationship
        # trace entry before removal so a later ADD_ENTITY (EDGE) can recover
        # the bidirectional target_end_cardinality. Mongo / Cass scripts use
        # DELETE_PROPERTY instead of DELETE_FOREIGN_KEY because their source
        # paradigms lack SQL FK constraints.
        for rel in entity.relationships:
            if isinstance(rel, Reference) and rel.ref_name == attr_name:
                self._remember_deleted_fk(
                    entity.name, attr_name, rel.refs_to,
                    self._fk_was_required(rel.target_end_cardinality, attr),
                    source_end_cardinality=rel.source_end_cardinality,
                )
                entity.remove_relationship(attr_name)
                break

        entity.remove_property(attr_name)

        # Clean up constraints referencing the deleted property
        if attr_meta_id:
            entity.constraints = [
                c for c in entity.constraints
                if not (c.kind == "unique" and
                        any(up.property_id == attr_meta_id for up in c.unique_properties))
            ]
            entity.remove_fk_constraint_for_property(attr_meta_id)
        # Clean up Reference relationships matching the deleted property
        for rel in list(entity.relationships):
            if isinstance(rel, Reference) and rel.ref_name == attr_name:
                entity.remove_relationship(attr_name)
                break

        self.changes.append(f"DELETE_PROP:{target}")
        return OperationResult.ok()

    @register_handler(OpType.DELETE_ENTITY)
    def _handle_delete_entity(self, params: DeleteEntityParams) -> OperationResult:
        """DELETE ENTITY Customer (also handles EDGE entities)"""
        name = params.name
        deleted_entity = self._get_entity(name, "DELETE_ENTITY")
        if not deleted_entity:
            return OperationResult.skipped("delete_entity: precondition not met")

        # If deleting an EDGE entity, clean up Edge from source entity
        if deleted_entity.entity_kind == EntityKind.EDGE and deleted_entity.source_entity:
            source_ent = self.database.get_entity_type(deleted_entity.source_entity)
            if source_ent:
                source_ent.remove_relationship(name)

        # Collect deleted entity's property meta_ids for FK cleanup
        deleted_attr_ids = set()
        for attr in deleted_entity.properties:
            deleted_attr_ids.add(attr.meta_id)
        deleted_up_ids = set()
        for c in deleted_entity.constraints:
            if c.kind == "unique":
                for up in c.unique_properties:
                    deleted_up_ids.add(up.meta_id)

        self.database.remove_entity_type(name)
        # Clean up cross-references in other entities (Reference, Embedded, and Edge);
        # collect names of touched entities so the per-op diff hint reflects them.
        modified_others: List[str] = []
        for other_entity in self.database.entity_types.values():
            before_rels = len(other_entity.relationships)
            other_entity.relationships = [
                rel for rel in other_entity.relationships
                if not (hasattr(rel, 'refs_to') and rel.refs_to == name)
                and not (hasattr(rel, 'aggregates') and rel.aggregates == name)
                and not (isinstance(rel, Edge) and (rel.source_entity == name or rel.target_entity == name))
            ]
            before_cons = len(other_entity.constraints)
            if deleted_up_ids:
                other_entity.constraints = [
                    c for c in other_entity.constraints
                    if not (c.kind == "foreign_key" and
                            any(fkp.points_to_unique_property_id in deleted_up_ids
                                for fkp in c.foreign_key_properties))
                ]
            if (len(other_entity.relationships) != before_rels
                    or len(other_entity.constraints) != before_cons):
                modified_others.append(other_entity.full_path)
        # Clean up EDGE entities that reference the deleted entity
        edges_to_remove = [
            e_name for e_name, e in self.database.entity_types.items()
            if e.entity_kind == EntityKind.EDGE and (e.source_entity == name or e.target_entity == name)
        ]
        for e_name in edges_to_remove:
            self.database.remove_entity_type(e_name)
        self._touch(name, *edges_to_remove, *modified_others)
        self.changes.append(f"DELETE_ENTITY:{name}")
        return OperationResult.ok()

    @register_handler(OpType.DELETE_EMBEDDED)
    def _handle_delete_embedded(self, params: DeleteEmbeddedParams) -> OperationResult:
        parent_name, embedded_name = self._split_path(params.embedded)
        embedded_name = embedded_name.replace("[]", "")
        parent_entity = self._get_entity(parent_name, "DELETE_EMBEDDED") if parent_name else None
        if not parent_entity:
            return OperationResult.skipped("delete_embedded: precondition not met")
        # Find the full entity path from the Embedded relationship
        full_path = f"{parent_name}.{embedded_name}"
        for rel in parent_entity.get_embedded():
            if rel.aggr_name == embedded_name:
                full_path = rel.aggregates
                break
        parent_entity.remove_relationship(embedded_name)
        self.database.remove_entity_type(full_path)
        self._touch(parent_name, full_path)
        self.changes.append(f"DELETE_EMBEDDED:{parent_name}.{embedded_name}")
        return OperationResult.ok()

    @register_handler(OpType.RENAME_PROPERTY)
    def _handle_rename_property(self, params: RenamePropertyParams) -> OperationResult:
        """RENAME_PROPERTY: Rename a property within an entity."""
        old_name = params.old_name
        new_name = params.new_name
        entity_name = params.entity

        if not entity_name:
            logger.info(f"RENAME_PROPERTY skipped: no entity specified for '{old_name}'")
            return OperationResult.skipped("rename_property: precondition not met")

        entity = self._get_entity(entity_name, "RENAME_PROPERTY")
        if not entity:
            return OperationResult.skipped("rename_property: precondition not met")

        attr = entity.get_property(old_name)
        if attr:
            attr.name = new_name
            # Update Reference.ref_name if this property is a FK
            for rel in entity.relationships:
                if isinstance(rel, Reference) and rel.ref_name == old_name:
                    rel.ref_name = new_name
                    break
            self._touch(entity_name)
            self.changes.append(f"RENAME_PROP:{entity_name}.{old_name}->{new_name}")
            return OperationResult.ok()
        return OperationResult.skipped("rename_property: precondition not met")

    @register_handler(OpType.RENAME_ENTITY)
    def _handle_rename_entity(self, params: RenameEntityParams) -> OperationResult:
        """RENAME ENTITY: Rename an entity."""
        old_name = params.old_name
        new_name = params.new_name

        entity = self._get_entity(old_name, "RENAME_ENTITY")
        if not entity:
            return OperationResult.skipped("rename_entity: precondition not met")
        # Collision check: prevent overwriting an existing entity
        if self.database.get_entity_type(new_name):
            logger.info(f"RENAME_ENTITY skipped: target '{new_name}' already exists")
            return OperationResult.skipped("rename_entity: precondition not met")

        self.database.remove_entity_type(old_name)
        # Update object_name: keep parent path, change last element
        entity.object_name = entity.parent_path + [new_name]
        self.database.add_entity_type(entity)
        # Repoint cross-references (Reference/Embedded/Edge endpoints) in other entities
        self._remap_entity_references(old_name, new_name)
        # If renaming an EDGE entity, update Edge.rel_type_name on source entity
        if entity.entity_kind == EntityKind.EDGE and entity.source_entity:
            source_ent = self.database.get_entity_type(entity.source_entity)
            if source_ent:
                for rel in source_ent.relationships:
                    if isinstance(rel, Edge) and rel.rel_type_name == old_name:
                        rel.rel_type_name = new_name
        self._touch(old_name, new_name)
        self.changes.append(f"RENAME_ENTITY:{old_name}->{new_name}")
        return OperationResult.ok()

    @register_handler(OpType.COPY_PROPERTY)
    def _handle_copy_property(self, params: CopyPropertyParams) -> OperationResult:
        """COPY_PROPERTY: Copy property from source to target."""
        source_path = params.source
        target_path = params.target

        reason = self._validate_join_conditions(
            params.join_conditions,
            [self._split_path(source_path)[0], self._split_path(target_path)[0]],
            "copy_property")
        if reason:
            logger.warning("%s", reason)
            return OperationResult.skipped(reason)

        src_entity, src_attr_name = self._resolve_entity_attr(source_path)
        tgt_entity, tgt_attr_name = self._resolve_entity_attr(target_path)

        if src_entity and tgt_entity:
            # Copy property
            src_attr = src_entity.get_property(src_attr_name)
            if src_attr:
                new_attr = Property(tgt_attr_name, src_attr.data_type, False, src_attr.is_optional)
                tgt_entity.add_property(new_attr)
                self._touch(src_entity.name, tgt_entity.name)
                self.changes.append(f"COPY_PROP:{source_path}->{target_path}")
                return OperationResult.ok()
        elif "." not in source_path and "." not in target_path:
            # Copy entity
            src_entity = self.database.get_entity_type(source_path)
            if src_entity:
                new_entity = copy.deepcopy(src_entity)
                # Update object_name with new target name
                new_entity.object_name = [target_path]
                self.database.add_entity_type(new_entity)
                self._touch(source_path, target_path)
                self.changes.append(f"COPY_PROP:{source_path}->{target_path}")
                return OperationResult.ok()
        return OperationResult.skipped("copy_property: precondition not met")

    @register_handler(OpType.COPY_ENTITY)
    def _handle_copy_entity(self, params: CopyEntityParams) -> OperationResult:
        """COPY_ENTITY: Duplicate an entire entity with all its structure."""
        source_name = params.source
        target_name = params.target
        source_entity_name = params.source_entity
        target_entity_name = params.target_entity

        src_entity = self._get_entity(source_name, "COPY_ENTITY")
        if not src_entity:
            return OperationResult.skipped("copy_entity: precondition not met")

        # EDGE requires explicit FROM...TO
        if src_entity.entity_kind == EntityKind.EDGE and not (source_entity_name and target_entity_name):
            logger.error(f"COPY_ENTITY failed: source '{source_name}' is an EDGE entity, FROM...TO is required")
            return OperationResult.skipped("copy_entity: precondition not met")

        # Non-EDGE must not use FROM...TO
        if src_entity.entity_kind != EntityKind.EDGE and (source_entity_name or target_entity_name):
            logger.error(f"COPY_ENTITY failed: source '{source_name}' is not an EDGE entity, FROM...TO is not allowed (use CAST_ENTITY to change entity kind)")
            return OperationResult.skipped("copy_entity: precondition not met")

        new_entity = copy.deepcopy(src_entity)
        new_entity.object_name = [target_name]
        # Refresh internal meta_ids on the clone so it doesn't collide with
        # the source entity's Property / UniqueProperty UUIDs. Import here
        # to avoid a circular dependency at module load.
        from core.handlers.reshape import _refresh_entity_ids
        _refresh_entity_ids(new_entity)
        # Update relationship paths that reference the old entity name
        for rel in new_entity.relationships:
            if isinstance(rel, Embedded):
                if rel.aggregates.startswith(source_name + "."):
                    rel.aggregates = target_name + rel.aggregates[len(source_name):]
                elif rel.aggregates == source_name:
                    rel.aggregates = target_name
            elif isinstance(rel, Reference):
                if rel.refs_to == source_name:
                    rel.refs_to = target_name
            elif isinstance(rel, Edge):
                if rel.source_entity == source_name:
                    rel.source_entity = target_name

        # Handle EDGE: set explicit FROM...TO and add Edge to source VERTEX
        if source_entity_name and target_entity_name:
            new_entity.source_entity = source_entity_name
            new_entity.target_entity = target_entity_name
            new_entity.entity_kind = EntityKind.EDGE
            copied_target_card = getattr(src_entity, 'edge_source_end_cardinality', None)
            if copied_target_card is not None:
                new_entity.edge_source_end_cardinality = copied_target_card
            source_ent = self.database.get_entity_type(source_entity_name)
            if source_ent:
                source_ent.add_relationship(Edge(
                    rel_type_name=target_name,
                    source_entity=source_entity_name,
                    target_entity=target_entity_name,
                    target_end_cardinality=src_entity.edge_target_end_cardinality if hasattr(src_entity, 'edge_target_end_cardinality') and src_entity.edge_target_end_cardinality else Cardinality.ZERO_TO_MANY,
                    source_end_cardinality=copied_target_card,
                ))

        self.database.add_entity_type(new_entity)
        self._touch(source_name, target_name)
        self.changes.append(f"COPY_ENTITY:{source_name}->{target_name}")
        return OperationResult.ok()

    @register_handler(OpType.MOVE_PROPERTY)
    def _handle_move_property(self, params: MovePropertyParams) -> OperationResult:
        """MOVE_PROPERTY: Move property from one entity to another."""
        source_path = params.source
        target_path = params.target

        reason = self._validate_join_conditions(
            params.join_conditions,
            [self._split_path(source_path)[0], self._split_path(target_path)[0]],
            "move_property")
        if reason:
            logger.warning("%s", reason)
            return OperationResult.skipped(reason)

        src_entity, src_attr_name = self._resolve_entity_attr(source_path)
        tgt_entity, tgt_attr_name = self._resolve_entity_attr(target_path)

        if src_entity and tgt_entity:
            src_attr = src_entity.get_property(src_attr_name)
            if src_attr:
                new_attr = Property(tgt_attr_name, src_attr.data_type, False, src_attr.is_optional)
                tgt_entity.add_property(new_attr)
                src_entity.remove_property(src_attr_name)
                self._touch(src_entity.name, tgt_entity.name)
                self.changes.append(f"MOVE_PROP:{source_path}->{target_path}")
                return OperationResult.ok()
        return OperationResult.skipped("move_property: precondition not met")
