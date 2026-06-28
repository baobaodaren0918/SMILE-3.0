"""Handlers for entity-level reshaping ops — MERGE, SPLIT, CAST_PROPERTY, CAST_ENTITY."""

import copy
import logging
import uuid
from typing import Dict

from Schema.unified_meta_schema import (
    EntityType, EntityKind, Property,
    Reference, Embedded, Edge,
    PrimitiveDataType, PrimitiveType,
    TYPE_STR_MAP,
)
from parser.params import (
    OperationResult,
    CastEntityParams,
    CastPropertyParams, MergeParams, SplitParams,
)
from parser.listeners import OpType
from core.transformer import register_handler

logger = logging.getLogger(__name__)


def _refresh_entity_ids(entity):
    """Generate fresh meta_ids for every Property and UniqueProperty inside
    ``entity`` and remap internal pointers (UP.property_id, FKP.property_id,
    self-ref FKP.points_to_unique_property_id) accordingly. Cross-entity FK
    targets (FKP.points_to_unique_property_id pointing at OTHER entities'
    UPs) are intentionally left unchanged. Used after ``copy.deepcopy`` in
    SPLIT / COPY_ENTITY to prevent UniqueProperty.meta_id collisions across
    the original entity and its clone."""
    prop_remap = {}
    for prop in entity.properties:
        new_id = str(uuid.uuid4())
        prop_remap[prop.meta_id] = new_id
        prop.meta_id = new_id
    up_remap = {}
    for c in entity.constraints:
        if c.kind == "unique":
            for up in c.unique_properties:
                new_up_id = str(uuid.uuid4())
                up_remap[up.meta_id] = new_up_id
                up.meta_id = new_up_id
                if up.property_id in prop_remap:
                    up.property_id = prop_remap[up.property_id]
        elif c.kind == "foreign_key":
            for fkp in c.foreign_key_properties:
                if fkp.property_id in prop_remap:
                    fkp.property_id = prop_remap[fkp.property_id]
                if fkp.points_to_unique_property_id in up_remap:
                    fkp.points_to_unique_property_id = up_remap[
                        fkp.points_to_unique_property_id]
        elif c.kind == "check" and getattr(c, "target_property_id", None) in prop_remap:
            c.target_property_id = prop_remap[c.target_property_id]
        elif c.kind == "existence" and getattr(c, "target_property_id", None) in prop_remap:
            c.target_property_id = prop_remap[c.target_property_id]



class ReshapeHandlersMixin:
    """Mixin contributing one focused subset of `_handle_*` methods to ``SchemaTransformer``."""

    @register_handler(OpType.MERGE)
    def _handle_merge(self, params: MergeParams) -> OperationResult:
        """MERGE: Merge two entities into one."""
        source1_name = params.source1
        source2_name = params.source2
        target_name = params.target

        source1 = self._get_entity(source1_name, "MERGE")
        source2 = self._get_entity(source2_name, "MERGE")
        if not source1 or not source2:
            return OperationResult.skipped("merge: precondition not met")

        # EDGE entities cannot be merged
        if source1.entity_kind == EntityKind.EDGE:
            logger.error(f"MERGE failed: entity '{source1_name}' is an EDGE entity, MERGE does not support EDGE")
            return OperationResult.skipped("merge: precondition not met")
        if source2.entity_kind == EntityKind.EDGE:
            logger.error(f"MERGE failed: entity '{source2_name}' is an EDGE entity, MERGE does not support EDGE")
            return OperationResult.skipped("merge: precondition not met")

        # The WHERE clause states how the two entities correspond. Validate that
        # it references only the two merge operands; the condition itself does
        # not change how properties are combined.
        reason = self._validate_join_conditions(
            params.join_conditions, [source1_name, source2_name], "merge")
        if reason:
            logger.warning("%s", reason)
            return OperationResult.skipped(reason)

        # Snapshot the UniqueProperty meta_ids of both sources before any
        # mutation, paired with their property names. After we build the
        # merged entity and refresh its IDs (below), we walk every FK in the
        # database and relink ``points_to_unique_property_id`` from these old
        # source UPs to the new UPs (matched by property name). Without this,
        # any incoming FK that pointed at a removed source's PK would orphan.
        merged_up_map: Dict[str, str] = {}
        for src in (source1, source2):
            for c in src.constraints:
                if c.kind == "unique":
                    for up in c.unique_properties:
                        attr = src.get_property_by_id(up.property_id)
                        if attr:
                            merged_up_map[up.meta_id] = attr.name

        # Create new entity with combined properties
        new_entity = EntityType(object_name=[target_name])

        # Track old->new meta_id mapping for constraint property_id remap
        meta_id_map = {}

        # Add properties from source1
        for attr in source1.properties:
            new_attr = Property(attr.name, attr.data_type, attr.is_key, attr.is_optional)
            meta_id_map[attr.meta_id] = new_attr.meta_id
            new_entity.add_property(new_attr)

        # Add properties from source2 (avoid duplicates)
        existing_names = {a.name for a in new_entity.properties}
        for attr in source2.properties:
            if attr.name not in existing_names:
                new_attr = Property(attr.name, attr.data_type, attr.is_key, attr.is_optional)
                meta_id_map[attr.meta_id] = new_attr.meta_id
                new_entity.add_property(new_attr)

        # Copy constraints from source1 with remapped property_ids
        has_pk = False
        for constraint in source1.constraints:
            new_c = copy.deepcopy(constraint)
            if new_c.kind == "unique":
                if new_c.is_primary_key:
                    has_pk = True
                for up in new_c.unique_properties:
                    if up.property_id in meta_id_map:
                        up.property_id = meta_id_map[up.property_id]
            elif new_c.kind == "foreign_key":
                for fkp in new_c.foreign_key_properties:
                    if fkp.property_id in meta_id_map:
                        fkp.property_id = meta_id_map[fkp.property_id]
            new_entity.add_constraint(new_c)

        # Copy constraints from source2 (skip duplicate PK)
        for constraint in source2.constraints:
            new_c = copy.deepcopy(constraint)
            if new_c.kind == "unique":
                if new_c.is_primary_key and has_pk:
                    continue  # Skip duplicate primary key
                for up in new_c.unique_properties:
                    if up.property_id in meta_id_map:
                        up.property_id = meta_id_map[up.property_id]
            elif new_c.kind == "foreign_key":
                for fkp in new_c.foreign_key_properties:
                    if fkp.property_id in meta_id_map:
                        fkp.property_id = meta_id_map[fkp.property_id]
            new_entity.add_constraint(new_c)

        # Helper to get relationship identifier
        def _rel_id(r):
            if isinstance(r, Reference): return ('ref', r.ref_name)
            if isinstance(r, Embedded): return ('emb', r.aggr_name)
            if isinstance(r, Edge): return ('edge', r.rel_type_name)
            return ('other', id(r))

        # Copy relationships from source1 (Embedded, Reference, etc.)
        for rel in source1.relationships:
            new_entity.add_relationship(copy.deepcopy(rel))

        # Copy relationships from source2 (avoid duplicates by type+name)
        existing_rel_ids = {_rel_id(r) for r in new_entity.relationships}
        for rel in source2.relationships:
            if _rel_id(rel) not in existing_rel_ids:
                new_entity.add_relationship(copy.deepcopy(rel))

        self.database.add_entity_type(new_entity)

        # Refresh all internal meta_ids on the merged entity. Without this, the
        # deep-copied constraints (above) silently preserve UPs whose meta_ids
        # collide with source1/source2 UPs — an invariant violation the
        # integrity check would flag. After refreshing, build a name->new_id
        # map so the FK relink loop below can rewrite incoming pointers.
        _refresh_entity_ids(new_entity)
        new_up_by_name: Dict[str, str] = {}
        for c in new_entity.constraints:
            if c.kind == "unique":
                for up in c.unique_properties:
                    attr = new_entity.get_property_by_id(up.property_id)
                    if attr and attr.name not in new_up_by_name:
                        new_up_by_name[attr.name] = up.meta_id

        # Remove source entities if different from target
        removed_sources = []
        if source1_name != target_name:
            self.database.remove_entity_type(source1_name)
            removed_sources.append(source1_name)
        if source2_name != target_name:
            self.database.remove_entity_type(source2_name)
            removed_sources.append(source2_name)

        # Walk all FKs and relink ``points_to_unique_property_id`` from old
        # source UPs to the merged entity's new UPs (matched by property name).
        if removed_sources:
            for entity in self.database.entity_types.values():
                for c in entity.constraints:
                    if c.kind != "foreign_key":
                        continue
                    for fkp in c.foreign_key_properties:
                        old_up = fkp.points_to_unique_property_id
                        if old_up in merged_up_map:
                            prop_name = merged_up_map[old_up]
                            new_up = new_up_by_name.get(prop_name)
                            if new_up:
                                fkp.points_to_unique_property_id = new_up

        # Repoint cross-references in other entities from each removed source
        # onto the surviving merge target.
        for old_name in removed_sources:
            self._remap_entity_references(old_name, target_name)

        self._touch(source1_name, source2_name, target_name)
        self.changes.append(f"MERGE:{source1_name},{source2_name}->{target_name}")
        return OperationResult.ok()

    @register_handler(OpType.SPLIT)
    def _handle_split(self, params: SplitParams) -> OperationResult:
        """SPLIT: Divide one entity into multiple separate entities (vertical partitioning)."""
        source_name = params.source
        parts = params.parts

        source = self.database.get_entity_type(source_name)
        if not source or not parts:
            return OperationResult.skipped("split: precondition not met")

        # EDGE entities cannot be split
        if source.entity_kind == EntityKind.EDGE:
            logger.error(f"SPLIT failed: entity '{source_name}' is an EDGE entity, SPLIT does not support EDGE")
            return OperationResult.skipped("split: precondition not met")

        pk = source.get_primary_key()
        created_entities = []

        # First pass: create NEW entities (parts with different name than source).
        # Must happen before modifying source, so property copying works.
        source_part_fields = None  # track fields for in-place source modification

        for i, part in enumerate(parts):
            part_name = part["name"]
            part_fields = part.get("fields", [])

            # When part_name == source_name, defer in-place modification to second pass
            if part_name == source_name:
                source_part_fields = part_fields
                created_entities.append(part_name)
                continue

            new_entity = EntityType(object_name=[part_name])

            # Track old->new meta_id mapping for constraint updates
            meta_id_map = {}

            # If fields are explicitly specified, use them
            if part_fields:
                for field_name in part_fields:
                    attr = source.get_property(field_name)
                    if attr:
                        # Create new property with is_key preserved from source
                        new_attr = Property(
                            attr.name, attr.data_type, attr.is_key, attr.is_optional
                        )
                        meta_id_map[attr.meta_id] = new_attr.meta_id
                        new_entity.add_property(new_attr)
            else:
                # Fallback: split properties evenly (old behavior)
                attrs = list(source.properties)
                mid = len(attrs) // 2
                if i == 0:
                    selected_attrs = attrs[:mid] if mid > 0 else attrs[:1]
                else:
                    selected_attrs = attrs[mid:] if mid > 0 else attrs[1:]

                for attr in selected_attrs:
                    new_attr = Property(
                        attr.name, attr.data_type, attr.is_key, attr.is_optional
                    )
                    meta_id_map[attr.meta_id] = new_attr.meta_id
                    new_entity.add_property(new_attr)

            # Each part reuses the source primary key (only if ALL PK attrs are in this part)
            if pk:
                all_pk_in_part = all(up.property_id in meta_id_map for up in pk.unique_properties)
                if all_pk_in_part:
                    new_pk = copy.deepcopy(pk)
                    for up in new_pk.unique_properties:
                        up.property_id = meta_id_map[up.property_id]
                        # Fresh UniqueProperty.meta_id to avoid UUID collision
                        # with the source's preserved PK (when source survives
                        # this SPLIT via in-place modification below).
                        up.meta_id = str(uuid.uuid4())
                    new_entity.add_constraint(new_pk)

            self.database.add_entity_type(new_entity)
            created_entities.append(part_name)

        # Second pass: modify source in-place (preserves edges, embedded, references)
        if source_part_fields is not None:
            keep_fields = set(source_part_fields)
            attrs_to_remove = [a.name for a in source.properties
                               if a.name not in keep_fields]
            for attr_name in attrs_to_remove:
                source.remove_property(attr_name)

        # Remove source if different from all targets
        if source_name not in [p["name"] for p in parts]:
            self.database.remove_entity_type(source_name)

        parts_str = ",".join(created_entities)
        self._touch(source_name, *created_entities)
        self.changes.append(f"SPLIT:{source_name}->{parts_str}")
        return OperationResult.ok()

    @register_handler(OpType.CAST_PROPERTY)
    def _handle_cast_property(self, params: CastPropertyParams) -> OperationResult:
        """CAST_PROPERTY: Change property data type."""
        target = params.target
        new_type_str = (params.data_type or params.type or "STRING").upper()

        entity, attr_name = self._resolve_entity_attr(target, "CAST_PROPERTY")
        if not entity:
            return OperationResult.skipped("cast_property: precondition not met")

        attr = entity.get_property(attr_name)
        if not attr:
            logger.info(f"CAST_PROPERTY skipped: property '{attr_name}' not found")
            return OperationResult.skipped("cast_property: precondition not met")

        new_type = TYPE_STR_MAP.get(new_type_str, PrimitiveType.STRING)
        attr.data_type = PrimitiveDataType(new_type)
        self._touch(entity.name)
        self.changes.append(f"CAST_PROP:{target}->{new_type_str}")
        return OperationResult.ok()

    @register_handler(OpType.CAST_ENTITY)
    def _handle_cast_entity(self, params: CastEntityParams) -> OperationResult:
        """CAST_ENTITY: Change the entity_kind of an entity type (cross-paradigm type conversion)."""
        target = params.target
        entity_kind_str = params.entity_kind

        entity = self._get_entity(target, "CAST_ENTITY")
        if not entity:
            return OperationResult.skipped("cast_entity: precondition not met")

        # EDGE entities must use TRANSFORM, not CAST_ENTITY
        if entity.entity_kind == EntityKind.EDGE:
            logger.error(f"CAST_ENTITY failed: entity '{target}' is an EDGE entity, use TRANSFORM INTO ENTITY first")
            return OperationResult.skipped("cast_entity: precondition not met")

        kind_map = {
            "RELATIONAL": EntityKind.TABLE,
            "DOCUMENT": EntityKind.DOCUMENT,
            "GRAPH": EntityKind.VERTEX,
            "COLUMNAR": EntityKind.WIDE_COLUMN_TABLE,
        }

        new_kind = kind_map.get(entity_kind_str)
        if not new_kind:
            return OperationResult.skipped("cast_entity: precondition not met")
        entity.entity_kind = new_kind
        entity.kind_locked = True   # tell normalize_entity_kinds() to skip
        self._touch(target)
        self.changes.append(f"CAST_ENTITY:{target}->{entity_kind_str}")
        return OperationResult.ok()
