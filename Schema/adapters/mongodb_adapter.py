"""MongoDB Adapter - Parse MongoDB JSON Schema to Unified Meta Schema."""
import json
import re
from typing import Dict, Any, Optional, List, Tuple, Union
from ..unified_meta_schema import (
    Database, DatabaseType, EntityType, EntityKind, Property,
    UniqueConstraint, UniqueProperty, PKTypeEnum,
    Embedded, Reference, Cardinality, PrimitiveDataType, PrimitiveType,
    ListDataType, SetDataType, MapDataType,
    TypeMappings
)
from ._base import DatabaseAdapter


# Canonical SMILE marker for a logical (non-enforced) reference, used for both
# cross-collection refs *and* self-references. Self-reference is encoded by
# ``refs_to`` matching the owning entity's own ``full_path``; the parser
# distinguishes the two cases on that condition. Shape:
#   "_smile_logical_ref": {"refs_to": "<entity_full_path>", "column": "<field>"}
# The exporter always writes this canonical form; the parser still accepts the
# legacy description regex forms below for backward compatibility.
_SMILE_LOGICAL_REF_KEY = "_smile_logical_ref"

# Legacy: descriptive text MongoDB sources used to mark a column as a logical
# cross-collection reference. Kept as a fallback for externally-authored
# schemas without the structured ``_smile_logical_ref`` marker.
#
# The regex is anchored to the START of the description (``\A\s*``) so a
# longer human-readable description that just *mentions* the phrase mid-string
# (e.g. ``"This field is *not* a cross-collection reference to legacy data"``)
# does not get misinterpreted as a real logical reference. New schemas should
# use the structured marker instead — this fallback is for back-compat only.
_CROSS_COLLECTION_REF_RE = re.compile(
    r"\A\s*Cross-collection reference to ([\w]+)\.(\w+)",
    re.IGNORECASE,
)

# Legacy: descriptive text marking a self-reference. Same start-of-string
# anchor as above — only descriptions that *begin* with "Self-reference" are
# treated as the marker; the phrase in the middle of a longer text is ignored.
_SELF_REFERENCE_RE = re.compile(r"\A\s*Self-reference", re.IGNORECASE)


class MongoDBAdapter(DatabaseAdapter):
    """Adapter to parse MongoDB JSON Schema and create Unified Meta Schema."""

    # BSON type to PrimitiveType mapping (from centralized TypeMappings)
    TYPE_MAP = TypeMappings.MONGODB_TO_PRIMITIVE

    def __init__(self):
        self.database: Optional[Database] = None

    def parse(self, schema: Union[Dict[str, Any], str], db_name: str = "database") -> Database:
        """Parse MongoDB JSON Schema and return Database object."""
        if isinstance(schema, str):
            schema = json.loads(schema)
        self.database = Database(db_name=db_name, db_type=DatabaseType.DOCUMENT)

        collections = schema.get('collections')
        if isinstance(collections, dict) and collections:
            # Multi-root: each top-level entry is an independent root document.
            for coll_name, coll_schema in collections.items():
                # Prefer the collection key as the canonical name; fall back to
                # the inner ``title`` if present, then to the key.
                inner_title = coll_schema.get('title') if isinstance(coll_schema, dict) else None
                root_name = (inner_title or coll_name).lower().replace(' ', '_')
                root_entity = self._parse_object_schema(
                    coll_schema, root_name, parent_path=[], is_root=True
                )
                self.database.add_entity_type(root_entity)
        else:
            # Single-root (legacy): the top-level object IS the root document.
            root_name = schema.get('title', 'root_document').lower().replace(' ', '_')
            root_entity = self._parse_object_schema(
                schema, root_name, parent_path=[], is_root=True
            )
            self.database.add_entity_type(root_entity)

        return self.database

    def _parse_object_schema(self, schema: Dict[str, Any], name: str, parent_path: List[str] = None, is_root: bool = False) -> EntityType:
        """Parse an object schema into EntityType."""
        if parent_path is None:
            parent_path = []
        # Build full object_name path (from AC)
        # Example: parent_path=["customers"], name="address" -> ["customers", "address"]
        object_name = parent_path + [name]
        entity = EntityType(
            object_name=object_name,
            entity_kind=EntityKind.DOCUMENT if is_root else EntityKind.EMBEDDED,
            # Carry the structural is_root distinction onto the EntityType so
            # downstream tools can tell a root collection apart from an
            # embedded sub-document without re-deriving it from entity_kind.
            is_root=is_root,
        )

        properties = schema.get('properties', {})
        required = set(schema.get('required', []))

        for prop_name, prop_schema in properties.items():
            prop_name_lower = prop_name.lower()
            is_required = prop_name in required

            # Handle different property types
            bson_type = prop_schema.get('bsonType') or prop_schema.get('type', 'string')

            if bson_type == 'object':
                # Embedded object - pass current entity's object_name as parent_path
                # Example: { "address": { "bsonType": "object", "properties": {...} } }
                #   -> Creates EntityType(object_name=["customers", "address"])
                #   -> Creates Embedded relationship with Cardinality.ONE_TO_ONE
                embedded_entity = self._parse_object_schema(prop_schema, prop_name_lower, parent_path=object_name)
                self.database.add_entity_type(embedded_entity)

                embedded = Embedded(
                    aggr_name=prop_name_lower,
                    aggregates=embedded_entity.full_path,  # Use full path for reference
                    target_end_cardinality=Cardinality.ONE_TO_ONE if is_required else Cardinality.ZERO_TO_ONE,
                    is_optional=not is_required
                )
                entity.add_relationship(embedded)

            elif bson_type == 'array':
                # Array - check if array of objects or primitives
                # Example 1 (object array): { "items": [{"name": "a"}, {"name": "b"}] }
                #   -> Creates Embedded with Cardinality.ONE_TO_MANY
                # Example 2 (primitive array): { "tags": ["tag1", "tag2"] }
                #   -> Creates Property with ListDataType
                items = prop_schema.get('items', {})
                items_type = items.get('bsonType') or items.get('type', 'string')

                if items_type == 'object':
                    # Array of embedded objects - pass current entity's object_name as parent_path
                    # Example: { "items": { "bsonType": "array", "items": { "bsonType": "object" } } }
                    #   -> Creates EntityType for the embedded object
                    #   -> Creates Embedded with Cardinality.ONE_TO_MANY (or ZERO_TO_MANY)
                    embedded_entity = self._parse_object_schema(items, prop_name_lower, parent_path=object_name)
                    self.database.add_entity_type(embedded_entity)

                    embedded = Embedded(
                        aggr_name=prop_name_lower,
                        aggregates=embedded_entity.full_path,  # Use full path for reference
                        target_end_cardinality=Cardinality.ONE_TO_MANY if is_required else Cardinality.ZERO_TO_MANY,
                        is_optional=not is_required
                    )
                    entity.add_relationship(embedded)
                else:
                    # Array of primitives - use ListDataType to preserve array semantics
                    # Example: { "tags": { "bsonType": "array", "items": { "bsonType": "string" } } }
                    #   -> Property("tags", ListDataType(element_type=PrimitiveDataType(STRING)))
                    element_type = self._parse_primitive_type(items_type, items)
                    attr = Property(
                        name=prop_name_lower,
                        data_type=ListDataType(element_type=element_type),
                        is_key=False,
                        is_optional=not is_required
                    )
                    entity.add_property(attr)

            else:
                # Primitive type
                is_key = prop_name == '_id'
                attr = Property(
                    name=prop_name_lower,
                    data_type=self._parse_primitive_type(bson_type, prop_schema),
                    is_key=is_key,
                    is_optional=not is_required and not is_key
                )
                entity.add_property(attr)

                # Add primary key if _id
                if is_key:
                    constraint = UniqueConstraint(
                        is_primary_key=True,
                        is_managed=True,
                        unique_properties=[UniqueProperty(primary_key_type=PKTypeEnum.DOCUMENT_ID, property_id=attr.meta_id)]
                    )
                    entity.add_constraint(constraint)

                # Logical Reference recognition. Single unified path through
                # ``_extract_logical_ref_target``, which recognises either
                # the canonical structured marker or one of two legacy
                # description regexes (cross-collection or self-reference).
                # The returned ``target_table`` distinguishes the two flavours:
                #   * target == owning entity's full_path -> self-reference
                #     (target_end_cardinality follows the 0..1 / 1..1 convention because
                #     the column points at *another instance* of the same
                #     entity, not at a multi-row collection)
                #   * target != owner -> cross-collection reference
                #     (target_end_cardinality follows Mongo's array/non-array convention)
                if not is_key:
                    target_table, _target_column = \
                        self._extract_logical_ref_target(
                            prop_schema, owner_entity=entity)
                    if target_table:
                        is_self_ref = (target_table == entity.full_path)
                        # Multiplicity at the target end: per source document,
                        # how many target documents are referenced by this scalar
                        # field. A scalar reference is always 1..1 (NOT NULL) or 0..1.
                        target_end_cardinality = Cardinality.ONE_TO_ONE \
                            if is_required else Cardinality.ZERO_TO_ONE
                        # Multiplicity at the source end: cross-collection
                        # references default to ZERO_TO_MANY (many docs may carry
                        # the same FK value); self-refs are typically 0..n as well
                        # (an employee can have many direct reports).
                        source_end_cardinality = Cardinality.ZERO_TO_MANY
                        entity.add_relationship(Reference(
                            ref_name=prop_name_lower,
                            refs_to=target_table,
                            target_end_cardinality=target_end_cardinality,
                            source_end_cardinality=source_end_cardinality,
                            is_optional=not is_required,
                            is_enforced=False,
                            description=prop_schema.get('description') or None,
                        ))

        return entity

    @staticmethod
    def _extract_logical_ref_target(prop_schema: Dict[str, Any],
                                    owner_entity: EntityType) -> Tuple[Optional[str], Optional[str]]:
        """Identify the target of a logical reference (cross-collection *or*"""
        marker = prop_schema.get(_SMILE_LOGICAL_REF_KEY)
        if isinstance(marker, dict):
            refs_to = marker.get("refs_to")
            column = marker.get("column", "")
            if refs_to:
                return refs_to, column

        description = prop_schema.get('description', '') or ''
        m = _CROSS_COLLECTION_REF_RE.search(description)
        if m:
            return m.group(1), m.group(2)

        # Legacy self-reference: target is implicit (the owning entity).
        if _SELF_REFERENCE_RE.search(description):
            return owner_entity.full_path, "_id"

        return None, None

    def _parse_primitive_type(self, bson_type: str, schema: Dict[str, Any]) -> PrimitiveDataType:
        """Parse BSON type to PrimitiveDataType."""
        primitive = self.TYPE_MAP.get(bson_type, PrimitiveType.STRING)

        max_length = schema.get('maxLength')
        # MongoDB doesn't have precision/scale in JSON Schema, but we can infer from description

        return PrimitiveDataType(
            primitive_type=primitive,
            max_length=max_length
        )

    @staticmethod
    def load_from_file(file_path: str, db_name: str = None) -> Database:
        """Load MongoDB JSON Schema from file and parse to Database."""
        with open(file_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)

        if db_name is None:
            db_name = schema.get('title', 'mongodb_schema')

        adapter = MongoDBAdapter()
        return adapter.parse(schema, db_name)

    # ========== Export Methods ==========
    # These methods convert Unified Meta Schema back to MongoDB JSON Schema

    # Reverse mapping (from centralized TypeMappings)
    # Used when exporting back to MongoDB format
    REVERSE_TYPE_MAP = TypeMappings.PRIMITIVE_TO_MONGODB

    @classmethod
    def export_to_json(cls, database: Database, root_entity_name: str = None) -> Dict[str, Any]:
        """Export Unified Meta Schema to MongoDB JSON Schema format."""
        if not database.entity_types:
            return {"bsonType": "object", "properties": {}}

        # Caller pinned a specific root → single-root export, no auto-detect.
        if root_entity_name is not None:
            return cls._build_single_collection_schema(database, root_entity_name, is_top_level=True)

        roots = cls._find_root_entities(database)
        if len(roots) <= 1:
            # Zero/one root: keep the legacy flat shape so existing single-root
            # consumers (and the round-trip validator) see no behavior change.
            chosen = roots[0] if roots else next(iter(database.entity_types.keys()), None)
            return cls._build_single_collection_schema(database, chosen, is_top_level=True)

        # Multi-root: emit ``collections`` envelope. Each entry is itself a
        # full collection schema, but with the document-level ``$schema`` /
        # ``title`` stripped (the envelope owns those).
        envelope: Dict[str, Any] = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": database.db_name,
            "collections": {},
        }
        for root_name in roots:
            envelope["collections"][root_name] = cls._build_single_collection_schema(
                database, root_name, is_top_level=False
            )
        return envelope

    @classmethod
    def _build_single_collection_schema(cls, database: Database, root_name: str,
                                        *, is_top_level: bool) -> Dict[str, Any]:
        """Render one collection (root + its embedded subtree) as a JSON Schema dict."""
        root_entity = database.get_entity_type(root_name) if root_name else None
        if not root_entity:
            raise ValueError(f"Root entity '{root_name}' not found")

        # Pass ``is_root=True`` regardless of envelope shape: each collection
        # in a multi-root schema still owns the ``_id`` primary-key convention
        # and the same document-level metadata. The envelope-vs-flat decision
        # is just about WHERE that metadata lives, not whether to compute it.
        schema = cls._export_entity_to_schema(database, root_entity, is_root=True)

        # Strip the document-level keys when this collection is being placed
        # inside a multi-root envelope — the envelope owns them.
        if not is_top_level:
            for k in ("$schema", "title", "description"):
                schema.pop(k, None)

        # Relationship-type metadata is a database-level concern, so it only
        # rides along with the top-level shape (single-root export).
        if is_top_level and database.relationship_types:
            rel_types_meta = {}
            for rt_name, rt in database.relationship_types.items():
                rt_dict = {
                    "source": rt.source_entity,
                    "target": rt.target_entity,
                    "target_end_cardinality": rt.target_end_cardinality.value if rt.target_end_cardinality else "0..n",
                }
                if rt.properties:
                    rt_dict["properties"] = [attr.name for attr in rt.properties]
                rel_types_meta[rt_name] = rt_dict
            schema["_relationship_types"] = rel_types_meta

        return schema

    @classmethod
    def _find_root_entities(cls, database: Database) -> List[str]:
        """Return all root collection names, in declaration order."""
        from ..unified_meta_schema import Embedded, EntityKind

        embedded_targets = set()
        for entity in database.entity_types.values():
            for rel in entity.relationships:
                if isinstance(rel, Embedded):
                    embedded_targets.add(rel.get_target_entity_name())

        roots: List[str] = []
        for name, entity in database.entity_types.items():
            # EDGE entities are graph-paradigm artifacts — never a Mongo root.
            if entity.entity_kind == EntityKind.EDGE:
                continue
            if name in embedded_targets:
                continue
            roots.append(name)
        return roots

    @classmethod
    def _export_entity_to_schema(cls, database: Database, entity: EntityType, is_root: bool = False) -> Dict[str, Any]:
        """Export a single entity to MongoDB JSON Schema format."""
        from ..unified_meta_schema import Embedded, Cardinality

        schema = {
            "bsonType": "object",
            "required": [],
            "properties": {}
        }

        if is_root:
            schema["$schema"] = "http://json-schema.org/draft-07/schema#"
            schema["title"] = entity.name.replace('_', ' ')
            schema["description"] = f"MongoDB document schema for {entity.name}"

        # Build a lookup from property name -> matching logical Reference,
        # used to write the cross-collection reference description back into
        # the JSON Schema. The description is the round-trip signal for the
        # parse-end recognition; without it the meta-model relationship is
        # invisible in the exported document.
        logical_ref_by_prop = {
            rel.ref_name: rel
            for rel in entity.relationships
            if isinstance(rel, Reference) and rel.is_enforced is False
        }

        # Process properties
        for attr in entity.properties:
            prop_name = attr.name
            # Convert _id for root document
            if is_root and attr.is_key and prop_name != '_id':
                prop_name = '_id'

            prop_schema = cls._export_property_to_bson_type(attr)
            ref = logical_ref_by_prop.get(attr.name)
            if ref is not None:
                # Single canonical marker for both cross-collection and
                # self-references. ``refs_to`` matching the owning entity's
                # full_path is what flags it as a self-reference on the
                # parse side.
                prop_schema[_SMILE_LOGICAL_REF_KEY] = {
                    "refs_to": ref.refs_to,
                    "column": "_id",
                }
                # Human-readable description — distinguishes the two cases
                # for human readers but is not the parser's primary signal.
                if "description" not in prop_schema:
                    if ref.refs_to == entity.full_path:
                        prop_schema["description"] = (
                            f"Self-reference to another {entity.name}"
                        )
                    else:
                        prop_schema["description"] = (
                            f"Cross-collection reference to {ref.refs_to}._id"
                        )
            schema["properties"][prop_name] = prop_schema

            if not attr.is_optional:
                schema["required"].append(prop_name)

        # Process embedded relationships
        for rel in entity.relationships:
            if isinstance(rel, Embedded):
                embedded_entity = database.get_entity_type(rel.get_target_entity_name())
                if not embedded_entity:
                    continue

                embedded_schema = cls._export_entity_to_schema(database, embedded_entity, is_root=False)

                # Check if it's an array (ONE_TO_MANY, ZERO_TO_MANY)
                if rel.target_end_cardinality in (Cardinality.ONE_TO_MANY, Cardinality.ZERO_TO_MANY):
                    schema["properties"][rel.aggr_name] = {
                        "bsonType": "array",
                        "description": f"{rel.aggr_name} array",
                        "items": embedded_schema
                    }
                else:
                    schema["properties"][rel.aggr_name] = embedded_schema

                if rel.target_end_cardinality.is_required():
                    schema["required"].append(rel.aggr_name)

        # Clean up empty required list
        if not schema["required"]:
            del schema["required"]

        return schema

    @classmethod
    def _export_property_to_bson_type(cls, attr: Property) -> Dict[str, Any]:
        """Export a property to MongoDB BSON type schema."""
        data_type = attr.data_type

        # Handle ListDataType (arrays)
        # Example: ListDataType(STRING) -> {"bsonType": "array", "items": {"bsonType": "string"}}
        if isinstance(data_type, ListDataType):
            element_type = data_type.element_type
            if isinstance(element_type, PrimitiveDataType):
                element_bson_type = cls.REVERSE_TYPE_MAP.get(element_type.primitive_type, 'string')
                return {
                    "bsonType": "array",
                    "items": {"bsonType": element_bson_type}
                }
            else:
                return {
                    "bsonType": "array",
                    "items": {"bsonType": "string"}
                }

        # Handle SetDataType (unique arrays)
        # Example: SetDataType(STRING) -> {"bsonType": "array", "uniqueItems": true}
        if isinstance(data_type, SetDataType):
            element_type = data_type.element_type
            if isinstance(element_type, PrimitiveDataType):
                element_bson_type = cls.REVERSE_TYPE_MAP.get(element_type.primitive_type, 'string')
                return {
                    "bsonType": "array",
                    "uniqueItems": True,
                    "items": {"bsonType": element_bson_type}
                }
            else:
                return {
                    "bsonType": "array",
                    "uniqueItems": True,
                    "items": {"bsonType": "string"}
                }

        # Handle MapDataType (key-value objects)
        # Example: MapDataType(STRING, INTEGER) -> {"bsonType": "object"}
        if isinstance(data_type, MapDataType):
            return {"bsonType": "object"}

        # Handle PrimitiveDataType
        if isinstance(data_type, PrimitiveDataType):
            bson_type = cls.REVERSE_TYPE_MAP.get(data_type.primitive_type, 'string')
            prop = {"bsonType": bson_type}

            # Add maxLength for strings
            if data_type.max_length and bson_type == 'string':
                prop["maxLength"] = data_type.max_length

            return prop

        # Default fallback
        return {"bsonType": "string"}

    @classmethod
    def export_to_json_string(cls, database: Database, root_entity_name: str = None, indent: int = 2) -> str:
        """Export to formatted JSON string."""
        schema = cls.export_to_json(database, root_entity_name)
        return json.dumps(schema, indent=indent, ensure_ascii=False)

    @classmethod
    def export(cls, database: Database) -> str:
        """Convenience method that calls export_to_json_string()."""
        return cls.export_to_json_string(database)
