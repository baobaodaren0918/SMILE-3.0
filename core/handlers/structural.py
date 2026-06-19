"""Handlers for structural reshaping ops — NEST/UNNEST, FLATTEN/UNFLATTEN, WIND/UNWIND."""

import logging

from Schema.unified_meta_schema import (
    EntityType, EntityKind, Property,
    Reference, Embedded, Cardinality, TraceOrigin,
    PrimitiveDataType, PrimitiveType, ListDataType,
)
from parser.params import (
    OperationResult,
    NestParams, UnnestParams, FlattenParams, UnflattenParams,
    WindParams, UnwindParams,
)
from parser.listeners import OpType
from core.transformer import register_handler
from config import SOURCE_TYPE_DOCUMENT

logger = logging.getLogger(__name__)



class StructuralHandlersMixin:
    """Mixin contributing one focused subset of `_handle_*` methods to ``SchemaTransformer``."""

    @register_handler(OpType.NEST)
    def _handle_nest(self, params: NestParams) -> OperationResult:
        """NEST: Embed separate table into parent as nested object (denormalization)."""
        source_name = params.source
        target_name = params.target
        alias = params.alias
        properties = params.properties

        source_entity = self._get_entity(source_name, "NEST")
        target_entity = self._get_entity(target_name, "NEST")
        if not source_entity or not target_entity:
            return OperationResult.skipped("nest: precondition not met")

        # NEST produces an embedded sub-object, a structure that exists only in
        # the document model. Restrict it to migrations whose target is a
        # document store. target_type is None outside the pipeline (unit tests),
        # in which case the guard is skipped. Entity kinds are not normalised to
        # DOCUMENT until export, so the target model is the reliable signal here
        # rather than the parent entity's kind.
        if self.target_type is not None and self.target_type != SOURCE_TYPE_DOCUMENT:
            reason = (f"nest: target model is '{self.target_type}'; NEST is only valid "
                      f"when migrating to a document store")
            logger.warning("%s", reason)
            return OperationResult.skipped(reason)

        # NEST produces a document embedding; an EDGE entity is a graph
        # relationship type and cannot be nested into or embedded. Reject it,
        # mirroring the MERGE guard.
        if source_entity.entity_kind == EntityKind.EDGE:
            reason = f"nest: source '{source_name}' is an EDGE entity; NEST does not support edges"
            logger.warning("%s", reason)
            return OperationResult.skipped(reason)
        if target_entity.entity_kind == EntityKind.EDGE:
            reason = f"nest: target '{target_name}' is an EDGE entity; NEST does not support edges"
            logger.warning("%s", reason)
            return OperationResult.skipped(reason)

        # Determine embedding target_end_cardinality based on FK direction:
        #   - target holds FK to source (e.g., orders.customer_id → customers):
        #     each target has ONE source → embed as object (1..1 or 0..1)
        #   - source holds FK to target (e.g., order_details.order_id → orders):
        #     each target has MANY sources → embed as array (1..n or 0..n)
        target_end_cardinality = Cardinality.ONE_TO_ONE
        # Check if SOURCE has FK pointing to TARGET → many-to-one → embed as array
        for rel in source_entity.relationships:
            if isinstance(rel, Reference) and rel.get_target_entity_name() == target_name:
                # Source holds FK to target: many sources per target → ONE_TO_MANY
                target_end_cardinality = Cardinality.ONE_TO_MANY if not rel.is_optional else Cardinality.ZERO_TO_MANY
                break
        # Check if TARGET has FK pointing to SOURCE → one-to-one → embed as object
        if target_end_cardinality == Cardinality.ONE_TO_ONE:
            for rel in target_entity.relationships:
                if isinstance(rel, Reference) and rel.get_target_entity_name() == source_name:
                    target_end_cardinality = Cardinality.ONE_TO_ONE if not rel.is_optional else Cardinality.ZERO_TO_ONE
                    break

        # Create embedded entity with specified properties (or all non-FK properties if not specified).
        # Use full-path naming (target_full_path + alias) so that multiple NEST
        # operations producing same-aliased children under different parents
        # become distinct entities in the database (e.g. ``customers.address``
        # vs ``orders.employee.address``). Simple-name (``[alias]``) caused
        # structural collapse when the same alias appeared in multiple
        # contexts and broke Mongo round-trip cycles.
        fk_attr_names = {rel.ref_name for rel in source_entity.get_references()}
        target_full_path = target_entity.full_path
        embedded_full_path = f"{target_full_path}.{alias}"
        embedded_entity = EntityType(
            object_name=embedded_full_path.split("."),
            # NEST always produces a sub-document; ``is_root=False`` keeps
            # this consistent with the Mongo adapter's parse-time labelling
            # of nested ``bsonType=object`` properties.
            is_root=False,
        )

        nested = params.nested

        if properties:
            # Use specified properties
            for attr_name in properties:
                attr = source_entity.get_property(attr_name)
                if attr:
                    embedded_entity.add_property(Property(attr.name, attr.data_type, False, attr.is_optional))
        else:
            # Use all non-FK properties (backward compatibility)
            for attr in source_entity.properties:
                if attr.name not in fk_attr_names:
                    embedded_entity.add_property(Property(attr.name, attr.data_type, False, attr.is_optional))

        # Copy nested embedded relationships from source entity
        # e.g., NEST company:name, address{street,city} -> copy "address" Embedded from company
        for nested_obj in nested:
            nested_name = nested_obj['name']
            for rel in source_entity.get_embedded():
                if rel.aggr_name == nested_name:
                    embedded_entity.add_relationship(
                        Embedded(aggr_name=nested_name, aggregates=rel.aggregates,
                                 target_end_cardinality=rel.target_end_cardinality, is_optional=rel.is_optional))
                    break

        # Remove FK reference from target to source
        fk_removed = False
        for rel in list(target_entity.relationships):
            if isinstance(rel, Reference) and rel.get_target_entity_name() == source_name:
                # Also remove matching ForeignKeyConstraint
                fk_attr = target_entity.get_property(rel.ref_name)
                if fk_attr:
                    target_entity.constraints = [
                        c for c in target_entity.constraints
                        if not (c.kind == "foreign_key" and
                                any(fkp.property_id == fk_attr.meta_id for fkp in c.foreign_key_properties))
                    ]
                target_entity.remove_relationship(rel.ref_name)
                target_entity.remove_property(rel.ref_name)
                fk_removed = True

        # Fallback target_end_cardinality: when no Reference objects exist (non-relational sources),
        # infer from WHERE clause direction. If source holds the FK → many sources per target → array.
        if target_end_cardinality == Cardinality.ONE_TO_ONE:
            source_fk_param = params.source_fk
            if source_fk_param and "." in source_fk_param:
                fk_entity, _ = source_fk_param.split(".", 1)
                if fk_entity == source_name:
                    # Source holds FK to target → ONE_TO_MANY (array)
                    target_end_cardinality = Cardinality.ONE_TO_MANY

        # Fallback: remove FK property from target using WHERE clause
        # (for non-relational sources that don't have Reference objects)
        if not fk_removed:
            source_fk = params.source_fk
            if source_fk and "." in source_fk:
                fk_entity, fk_attr = source_fk.split(".", 1)
                if fk_entity == target_name:
                    target_entity.remove_property(fk_attr)

        self.database.add_entity_type(embedded_entity)
        # Embedded.aggregates points to the embedded entity's full_path so that
        # database.get_entity_type() finds it deterministically without leaning
        # on the simple-name lenient fallback.
        target_entity.add_relationship(Embedded(aggr_name=alias, aggregates=embedded_full_path,
                                                target_end_cardinality=target_end_cardinality,
                                                is_optional=not target_end_cardinality.is_required()))
        self._touch(source_name, target_name, alias)
        self.changes.append(f"NEST:{target_name}.{alias}")
        return OperationResult.ok()

    @register_handler(OpType.FLATTEN)
    def _handle_flatten(self, params: FlattenParams) -> OperationResult:
        """FLATTEN: Flatten nested object fields into parent table (reduce depth by 1)."""
        source_path = params.source

        # Parse path: customers.address -> parent=customers, nested=address
        parent_path, nested_name = self._split_path(source_path)
        if not parent_path:
            return OperationResult.skipped("flatten: precondition not met")

        parent_entity = self._get_entity(parent_path, "FLATTEN")
        if not parent_entity:
            return OperationResult.skipped("flatten: precondition not met")

        # Try to find the embedded entity
        embedded_entity = None
        full_embedded_path = source_path

        # Check parent's relationships for the embedded
        for rel in parent_entity.get_embedded():
            if rel.aggr_name == nested_name:
                embedded_entity = self.database.get_entity_type(rel.aggregates)
                if embedded_entity:
                    full_embedded_path = rel.aggregates
                break

        # Fallback: try direct path lookup
        if not embedded_entity:
            embedded_entity = self.database.get_entity_type(full_embedded_path)

        if not embedded_entity:
            logger.info(f"FLATTEN skipped: embedded '{full_embedded_path}' not found")
            return OperationResult.skipped("flatten: precondition not met")

        # Flatten: copy all properties from embedded entity to parent with prefix
        prefix = nested_name + "_"
        for attr in embedded_entity.properties:
            new_attr_name = prefix + attr.name
            if not parent_entity.get_property(new_attr_name):
                parent_entity.add_property(Property(
                    new_attr_name, attr.data_type, False, attr.is_optional
                ))

        # Remove the embedded relationship from parent
        for rel in list(parent_entity.relationships):
            if isinstance(rel, Embedded) and rel.aggr_name == nested_name:
                parent_entity.remove_relationship(rel.aggr_name)
                break

        # Remove the nested entity (optional, as it's now integrated into parent)
        self.database.remove_entity_type(full_embedded_path)

        self._touch(parent_path, full_embedded_path)
        self.changes.append(f"FLATTEN:{source_path}")
        return OperationResult.ok()

    @register_handler(OpType.UNFLATTEN)
    def _handle_unflatten(self, params: UnflattenParams) -> OperationResult:
        """UNFLATTEN: Combine flat fields into nested object (reverse of FLATTEN)."""
        entity_name = params.entity
        fields = params.fields
        nested_name = params.nested_name

        entity = self._get_entity(entity_name, "UNFLATTEN")
        if not entity:
            return OperationResult.skipped("unflatten: precondition not met")

        # Create new embedded entity for the nested object. Use full-path
        # naming (parent.nested_name) — see NEST handler comment for the
        # structural-collapse rationale. Simple-name caused two
        # ``orders.employee.address`` and ``customers.address`` UNFLATTEN
        # results to merge into one shared ``address`` entity.
        nested_full_path = f"{entity.full_path}.{nested_name}"
        nested_entity = EntityType(
            object_name=nested_full_path.split("."),
            # UNFLATTEN turns previously-flat columns into a sub-document; the
            # resulting entity is by construction non-root (``is_root=False``).
            is_root=False,
        )

        # Move specified fields from parent to nested entity
        for field_name in fields:
            attr = entity.get_property(field_name)
            if attr:
                nested_entity.add_property(Property(
                    attr.name, attr.data_type, attr.is_key, attr.is_optional
                ))
                entity.remove_property(field_name)

        # Add nested entity to database
        self.database.add_entity_type(nested_entity)

        # Add embedded relationship from parent to nested. ``aggregates``
        # carries the embedded entity's full_path for deterministic lookup.
        entity.add_relationship(Embedded(
            aggr_name=nested_name,
            aggregates=nested_full_path,
            target_end_cardinality=Cardinality.ONE_TO_ONE
        ))

        self._touch(entity_name, nested_name)
        self.changes.append(f"UNFLATTEN:{entity_name}({','.join(fields)})->{nested_name}")
        return OperationResult.ok()

    @register_handler(OpType.UNNEST)
    def _handle_unnest(self, params: UnnestParams) -> OperationResult:
        """UNNEST: Extract nested object to separate table (normalization)."""
        source_path = params.source_path
        target_name = params.target
        if not source_path or not target_name:
            return OperationResult.skipped("unnest: precondition not met")

        # New parser format uses [{'name': 'company', ...}]; legacy is just ['company'].
        nested_objects = [
            item['name'] if isinstance(item, dict) else item
            for item in params.nested
        ]

        parent_path, nested_name = self._split_path(source_path)
        if not parent_path:
            return OperationResult.skipped("unnest: precondition not met")
        parent_entity = self._get_entity(parent_path, "UNNEST")
        if not parent_entity:
            return OperationResult.skipped("unnest: precondition not met")

        embedded_entity, embedded_rel, full_embedded_path = self._resolve_unnest_source(
            parent_entity, nested_name, source_path
        )

        new_entity = self._build_unnest_target_entity(
            target_name, params.carry_fields, parent_entity,
            params.properties, embedded_entity, full_embedded_path
        )

        embedded_map = self._collect_embedded_map(embedded_entity)
        self._transfer_nested_embeddeds(
            new_entity, nested_objects, embedded_map,
            old_prefix=full_embedded_path, new_prefix=target_name
        )

        if embedded_rel is not None:
            self._remember_relationship_trace(
                holder=parent_path,
                ref_name=embedded_rel.aggr_name,
                target=target_name,
                target_end_cardinality=embedded_rel.target_end_cardinality,
                origin=TraceOrigin.UNNESTED_EMBEDDED,
            )

        self.database.add_entity_type(new_entity)
        if embedded_rel:
            parent_entity.remove_relationship(embedded_rel.aggr_name)
        if embedded_entity:
            self.database.remove_entity_type(full_embedded_path)

        self._touch(parent_path, target_name, full_embedded_path)
        self.changes.append(f"UNNEST:{source_path}->{target_name}")
        return OperationResult.ok()

    def _resolve_unnest_source(self, parent_entity, nested_name, source_path):
        """Locate the embedded entity referenced by an UNNEST."""
        full_path = source_path
        for rel in parent_entity.get_embedded():
            if rel.aggr_name == nested_name:
                embedded_entity = self.database.get_entity_type(rel.aggregates)
                if embedded_entity:
                    full_path = rel.aggregates
                return embedded_entity, rel, full_path
        return self.database.get_entity_type(full_path), None, full_path

    def _build_unnest_target_entity(self, target_name, carry_fields, parent_entity,
                                    properties, embedded_entity, full_embedded_path=""):
        """Construct the new entity extracted by UNNEST."""
        new_entity = EntityType(object_name=[target_name])

        for carry in carry_fields:
            source_field = carry.get("source", "")
            field_name = carry.get("field_name", "")
            source_attr_name = source_field.split(".")[-1] if source_field else source_field
            source_attr = parent_entity.get_property(source_attr_name)
            field_type = source_attr.data_type if source_attr else PrimitiveDataType(PrimitiveType.STRING)
            new_entity.add_property(Property(field_name, field_type, False, False))

        for field_name in properties:
            attr = embedded_entity.get_property(field_name) if embedded_entity else None
            if attr:
                new_entity.add_property(Property(
                    attr.name, attr.data_type, False, attr.is_optional
                ))
            else:
                new_entity.add_property(Property(
                    field_name, PrimitiveDataType(PrimitiveType.STRING), False, True
                ))

        # Forward the target_end_cardinality of References on the embedded entity into
        # the relationship trace rather than re-attaching the References to
        # the new entity — re-attaching would pollute paradigms (like
        # Cassandra) that carry no References. Self-refs are remapped to the
        # new entity name.
        if embedded_entity:
            properties_set = set(properties)
            for rel in embedded_entity.relationships:
                if not isinstance(rel, Reference):
                    continue
                if rel.ref_name not in properties_set:
                    continue
                new_refs_to = rel.refs_to
                if full_embedded_path and (
                    rel.refs_to == full_embedded_path
                    or rel.refs_to.startswith(full_embedded_path + ".")
                ):
                    new_refs_to = target_name + rel.refs_to[len(full_embedded_path):]
                self._remember_relationship_trace(
                    holder=target_name,
                    ref_name=rel.ref_name,
                    target=new_refs_to,
                    target_end_cardinality=rel.target_end_cardinality,
                    source_end_cardinality=rel.source_end_cardinality,
                    origin=(TraceOrigin.UNNESTED_SELF_REF
                            if new_refs_to == target_name
                            else TraceOrigin.UNNESTED_EMBEDDED_REF),
                )

        return new_entity

    def _collect_embedded_map(self, entity):
        """Return {aggr_name: Embedded} for all Embedded relationships on `entity`."""
        if not entity:
            return {}
        return {rel.aggr_name: rel for rel in entity.relationships if isinstance(rel, Embedded)}

    def _transfer_nested_embeddeds(self, new_entity, nested_objects, embedded_map,
                                   old_prefix, new_prefix):
        """Relocate any embedded objects named in the UNNEST field list from"""
        specified = set(nested_objects) & set(embedded_map.keys())
        if not specified:
            return

        for emb_name in specified:
            inner_rel = embedded_map[emb_name]
            emb_old_path = inner_rel.aggregates         # e.g., "orders.customer.address"
            emb_new_path = f"{new_prefix}.{emb_name}"   # e.g., "customer.address"

            # All entities at or below the old path need to move with the embedded.
            to_update = [emb_old_path]
            for entity_name in list(self.database.entity_types.keys()):
                if entity_name.startswith(emb_old_path + "."):
                    to_update.append(entity_name)

            for old_path in to_update:
                new_path = new_prefix + old_path[len(old_prefix):]
                nested_entity = self.database.get_entity_type(old_path)
                if not nested_entity:
                    continue
                self.database.remove_entity_type(old_path)
                nested_entity.object_name = new_path.split(".")
                self.database.add_entity_type(nested_entity)
                # Inner Embedded.aggregates that still point to old prefix must follow.
                for rel in nested_entity.relationships:
                    if isinstance(rel, Embedded) and rel.aggregates.startswith(old_prefix + "."):
                        rel.aggregates = new_prefix + rel.aggregates[len(old_prefix):]

            new_entity.add_relationship(Embedded(
                aggr_name=inner_rel.aggr_name,
                aggregates=emb_new_path,
                target_end_cardinality=inner_rel.target_end_cardinality,
                is_optional=inner_rel.is_optional,
            ))

    @register_handler(OpType.UNWIND)
    def _handle_unwind(self, params: UnwindParams) -> OperationResult:
        """UNWIND: Expand array field."""
        mode = params.mode
        source_path = params.source

        if mode == "expand_in_place":
            # Mode 2: Expand in place - UNWIND customer_tag.tags
            # Transform array property to its element type (for schema transformation)
            # e.g., tags: ListDataType(STRING) -> tags: STRING
            entity, attr_name = self._resolve_entity_attr(source_path)
            if entity:
                attr = entity.get_property(attr_name)
                if attr and hasattr(attr.data_type, 'element_type'):
                    # Convert ListDataType to its element type
                    attr.data_type = attr.data_type.element_type
                    entity_name = self._split_path(source_path)[0]
                    self._touch(entity_name)
                    self.changes.append(f"UNWIND_INPLACE:{entity_name}.{attr_name}")
                    return OperationResult.ok()
            return OperationResult.skipped("unwind: precondition not met")

        # Mode 1: Create new table
        target_name = params.target
        if not target_name:
            return OperationResult.skipped("unwind: precondition not met")

        # Parse source path: customers.tags[] -> parent=customers, array_name=tags
        parent_path, array_name = self._split_path(source_path.replace("[]", ""))
        if not parent_path:
            return OperationResult.skipped("unwind: precondition not met")

        parent_entity = self._get_entity(parent_path, "UNWIND")
        if not parent_entity:
            return OperationResult.skipped("unwind: precondition not met")

        # Check if source is an array property
        attr = parent_entity.get_property(array_name)
        primitive_element_type = None
        if attr and hasattr(attr.data_type, 'element_type'):
            primitive_element_type = attr.data_type.element_type

        # Create new entity for array elements
        new_entity = EntityType(object_name=[target_name])

        # If it's a primitive array, add 'value' column
        if primitive_element_type:
            new_entity.add_property(Property("value", primitive_element_type, False, False))

        # Add new entity to database
        self.database.add_entity_type(new_entity)
        self.changes.append(f"UNWIND:{target_name}")

        # Remove the array property from parent
        if attr:
            parent_entity.remove_property(array_name)
        self._touch(parent_path, target_name)
        return OperationResult.ok()

    @register_handler(OpType.WIND)
    def _handle_wind(self, params: WindParams) -> OperationResult:
        """WIND: Convert scalar property back to array (reverse of UNWIND)."""
        source_path = params.source
        entity, attr_name = self._resolve_entity_attr(source_path)
        if entity:
            attr = entity.get_property(attr_name)
            if attr:
                # Convert scalar type to ListDataType (reverse of UNWIND which does List -> scalar)
                # Skip if already a ListDataType to avoid double-wrapping
                if not isinstance(attr.data_type, ListDataType):
                    attr.data_type = ListDataType(element_type=attr.data_type)
                entity_name = self._split_path(source_path)[0]
                self._touch(entity_name)
                self.changes.append(f"WIND:{entity_name}.{attr_name}")
                return OperationResult.ok()
        return OperationResult.skipped("wind: precondition not met")
