"""Cross-paradigm normalization passes — applied during ``run_export``."""
from typing import Dict, List, Optional

from Schema.unified_meta_schema import (
    Cardinality, Database, EntityKind, Embedded, PrimitiveDataType,
)
from config import (
    SOURCE_TYPE_RELATIONAL, SOURCE_TYPE_DOCUMENT,
    SOURCE_TYPE_GRAPH, SOURCE_TYPE_COLUMNAR,
)


# Default EntityKind for each database type (used by normalize_entity_kinds).
_ENTITY_KIND_DEFAULT = {
    SOURCE_TYPE_RELATIONAL: EntityKind.TABLE,
    SOURCE_TYPE_DOCUMENT:   EntityKind.DOCUMENT,
    SOURCE_TYPE_GRAPH:      EntityKind.VERTEX,
    SOURCE_TYPE_COLUMNAR:   EntityKind.WIDE_COLUMN_TABLE,
}


def _calculate_changes(prev: Dict, after: Dict, op,
                       hint_entity_names: Optional[List[str]] = None) -> Dict:
    """Calculate the changes made by an operation (web-UI shape)."""
    from diff.engine import compute_diff
    from diff.formatters import to_ui_changes
    only = set(hint_entity_names) if hint_entity_names is not None else None
    diff = compute_diff(prev, after, only_entities=only)
    return to_ui_changes(diff, prev, after)


def normalize_entity_kinds(db: Database, target_type: str) -> None:
    """Convert each entity's ``entity_kind`` to match the target paradigm."""
    target_kind = _ENTITY_KIND_DEFAULT.get(target_type, EntityKind.TABLE)

    # For Document target, identify embedded entities (those that are the
    # target of any Embedded relationship) so we can label them EMBEDDED
    # rather than DOCUMENT.
    embedded_targets = set()
    if target_type == SOURCE_TYPE_DOCUMENT:
        for entity in db.entity_types.values():
            for rel in entity.relationships:
                if isinstance(rel, Embedded):
                    embedded_targets.add(rel.aggregates)

    for name, entity in db.entity_types.items():
        if entity.kind_locked:
            continue
        if entity.entity_kind == EntityKind.EDGE:
            continue  # EDGE entities are relationship types, never normalize
        # Document target: split into DOCUMENT (root collection) vs
        # EMBEDDED (sub-document). Other paradigms have no embedded concept,
        # so every entity ends up as a top-level structure.
        if (target_type == SOURCE_TYPE_DOCUMENT
                and entity.full_path in embedded_targets):
            desired = EntityKind.EMBEDDED
            desired_is_root = False
        else:
            desired = target_kind
            desired_is_root = True
        if entity.entity_kind != desired:
            entity.entity_kind = desired
        # Keep ``is_root`` aligned with the entity_kind decision so handler
        # outputs (e.g. NEST/UNFLATTEN that produce sub-documents) and adapter
        # parses converge on the same convention.
        if entity.is_root != desired_is_root:
            entity.is_root = desired_is_root


def normalize_document_full_paths(db: Database) -> None:
    """Walk Embedded relationships from each root entity and rewrite each"""
    # Roots: any entity that is not the embedded target of another entity.
    embedded_targets = set()
    for e in db.entity_types.values():
        for rel in e.relationships:
            if isinstance(rel, Embedded):
                embedded_targets.add(rel.aggregates)
    roots = [e for e in db.entity_types.values()
             if e.full_path not in embedded_targets]

    # BFS rename map: old_full_path -> new_full_path.
    rename_map: Dict[str, str] = {}

    def _walk(parent_entity, parent_path: str) -> None:
        for rel in parent_entity.relationships:
            if not isinstance(rel, Embedded):
                continue
            child = db.get_entity_type(rel.aggregates)
            if child is None:
                continue
            target_path = f"{parent_path}.{rel.aggr_name}"
            old_path = child.full_path
            if old_path != target_path:
                rename_map[old_path] = target_path
                child.object_name = target_path.split(".")
                rel.aggregates = target_path
            else:
                # Already aligned — still update aggregates in case it
                # pointed to a stale simple name even though the entity
                # itself was renamed in an earlier walk.
                rel.aggregates = target_path
            _walk(child, target_path)

    for root in roots:
        _walk(root, root.full_path)

    # Apply dictionary key updates in one pass after the walk so we do not
    # mutate ``db.entity_types`` while iterating it.
    for old, new in rename_map.items():
        if old in db.entity_types and old != new:
            entity = db.entity_types.pop(old)
            db.entity_types[new] = entity


def normalize_property_psm(db: Database, source_type: str, target_type: str) -> None:
    """Strip source-paradigm property-level PSM that doesn't apply to the"""
    if source_type == target_type:
        return
    if target_type == SOURCE_TYPE_RELATIONAL:
        return

    # ``max_length`` (PG VARCHAR length) is a relational PSM concept.
    # Strip it when migrating into a non-relational target.
    #
    # NB: ``is_optional`` is *not* stripped here. PG NOT NULL on non-PK
    # columns is real source-side information that the Cassandra V2 ground
    # truth does not declare — when these mismatches occur Layer 1 surfaces
    # them as nullability NOTICEs. Treating them
    # as paradigm-capability diagnostics (and letting the user resolve
    # them script-side via ADD_CONSTRAINT EXISTENCE / DELETE_CONSTRAINT
    # when the column is genuinely meant to be nullable post-migration)
    # is more honest than silently rewriting the meta to hide the gap.
    for entity in db.entity_types.values():
        for prop in entity.properties:
            if isinstance(prop.data_type, PrimitiveDataType):
                prop.data_type.max_length = None


def normalize_document_cardinality(db: Database, source_type: str) -> None:
    """Promote ``Embedded`` relationships to required cardinality for D targets."""
    if source_type == SOURCE_TYPE_DOCUMENT:
        return
    for entity in db.entity_types.values():
        for rel in entity.relationships:
            if isinstance(rel, Embedded):
                if rel.target_end_cardinality == Cardinality.ZERO_TO_ONE:
                    rel.target_end_cardinality = Cardinality.ONE_TO_ONE
                elif rel.target_end_cardinality == Cardinality.ZERO_TO_MANY:
                    rel.target_end_cardinality = Cardinality.ONE_TO_MANY
