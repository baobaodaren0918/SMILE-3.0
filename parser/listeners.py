"""SMILE Listeners - Parsers for the two SMILE grammar variants."""
import sys
from enum import Enum
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

sys.path.insert(0, str(Path(__file__).parent))

from grammar.specific.SMILE_SpecificListener import SMILE_SpecificListener
from grammar.specific.SMILE_SpecificParser import SMILE_SpecificParser
from grammar.generalized.SMILE_GeneralizedListener import SMILE_GeneralizedListener
from grammar.generalized.SMILE_GeneralizedParser import SMILE_GeneralizedParser
from parser.params import (
    OpParams, KeyType,
    NestParams, UnnestParams, FlattenParams, UnflattenParams,
    WindParams, UnwindParams,
    AddEntityParams, DeleteEntityParams, RenameEntityParams, CopyEntityParams,
    AddPropertyParams, DeletePropertyParams, RenamePropertyParams,
    CopyPropertyParams, MovePropertyParams,
    AddKeyParams, DeleteKeyParams,
    AddForeignKeyParams, DeleteForeignKeyParams, CastConstraintParams,
    AddConstraintParams, DeleteConstraintParams, ConstraintBodyKind,
    CastEntityParams,
    AddEmbeddedParams, DeleteEmbeddedParams,
    AddLabelParams, DeleteLabelParams,
    CastPropertyParams, MergeParams, SplitParams,
    RecardParams, TransformParams,
)
from Schema.unified_meta_schema import (
    CheckExpr, CheckCmp, CheckIn, CheckBetween, CheckRegex, CheckIsNull,
    CheckAnd, CheckOr, CheckNot, CheckRaw,
)


class OpType(str, Enum):
    """Operation types for SMILE schema migration operations."""
    # Structure operations
    NEST = "nest"
    UNNEST = "unnest"
    FLATTEN = "flatten"
    UNFLATTEN = "unflatten"
    WIND = "wind"
    UNWIND = "unwind"
    # Entity operations
    ADD_ENTITY = "add_entity"
    DELETE_ENTITY = "delete_entity"
    RENAME_ENTITY = "rename_entity"
    COPY_ENTITY = "copy_entity"
    # Property operations
    ADD_PROPERTY = "add_property"
    DELETE_PROPERTY = "delete_property"
    RENAME_PROPERTY = "rename_property"
    COPY_PROPERTY = "copy_property"
    MOVE_PROPERTY = "move_property"
    # Key/Constraint operations
    ADD_KEY = "add_key"
    DELETE_KEY = "delete_key"
    ADD_FOREIGN_KEY = "add_foreign_key"
    DELETE_FOREIGN_KEY = "delete_foreign_key"
    CAST_CONSTRAINT = "cast_constraint"
    # ADD_CONSTRAINT / DELETE_CONSTRAINT cover constraint kinds the narrow
    # operators above don't address: logical references (Mongo cross-collection,
    # Cass denormalised columns, PG soft references), CHECK predicates, and
    # post-hoc EXISTENCE (NOT NULL applied after property creation).
    ADD_CONSTRAINT = "add_constraint"
    DELETE_CONSTRAINT = "delete_constraint"
    CAST_ENTITY = "cast_entity"
    # Embedded operations
    ADD_EMBEDDED = "add_embedded"
    DELETE_EMBEDDED = "delete_embedded"
    # Label operations (Graph)
    ADD_LABEL = "add_label"
    DELETE_LABEL = "delete_label"
    # Schema transformation
    TRANSFORM = "transform"
    MERGE = "merge"
    SPLIT = "split"
    CAST_PROPERTY = "cast_property"
    RECARD = "recard"


@dataclass
class MigrationContext:
    """Context information from SMILE script declaration."""
    name: str = ""
    version: str = ""
    is_evolution: bool = False
    source_db_type: str = ""
    target_db_type: str = ""
    schema_name: str = ""
    schema_version: str = ""
    target_schema_version: str = ""  # only for evolution: VERSION x TO y


@dataclass
class Operation:
    """Represents a single SMILE operation."""
    op_type: OpType
    params: OpParams  # typed payload; see operation_params.py for one dataclass per OpType
    original_keyword: str = ""  # Original keyword from source (e.g., "FLATTEN", "RENAME_PROPERTY")


class BaseSMILEListener:
    """Base class with shared parsing logic for all SMILE variants."""

    def __init__(self):
        self.context = MigrationContext()
        self.operations: List[Operation] = []

    # ========== Helper methods for parsing clauses ==========

    def _parse_condition_pairs(self, condition_ctx):
        """Recursively parse a condition tree into a list of typed join entries.

        Equality leaf  (a = b)         -> {"type": "eq",   "left", "right"}
        Edge leaf      (a -[:REL]-> b) -> {"type": "edge",  "from", "rel", "to"}
        AND / (cond)                   -> recurse and concatenate.
        ``None`` (no WHERE present) -> [].
        """
        if condition_ctx is None:
            return []

        # Equality leaf: qualifiedName EQUALS qualifiedName. Guard the operand
        # count so a tree recovered from a syntax error (e.g. an edge form fed
        # to NEST's equality-only condition) is skipped rather than crashing.
        eq = condition_ctx.equalityCondition() if hasattr(condition_ctx, "equalityCondition") else None
        if eq is not None:
            qns = eq.qualifiedName()
            if len(qns) >= 2:
                return [{
                    "type": "eq",
                    "left": qns[0].getText(),
                    "right": qns[1].getText(),
                }]
            return []

        # Edge leaf: qualifiedName -[:REL]-> qualifiedName  (graph relationship join)
        edge = condition_ctx.edgeCondition() if hasattr(condition_ctx, "edgeCondition") else None
        if edge is not None:
            qns = edge.qualifiedName()
            if len(qns) >= 2 and edge.identifier() is not None:
                return [{
                    "type": "edge",
                    "from": qns[0].getText(),
                    "rel": edge.identifier().getText(),
                    "to": qns[1].getText(),
                }]
            return []

        # Recursive: AND / parenthesised group. The node may be a full
        # ``condition`` (MERGE/MOVE/COPY) or an equality-only ``condition`` used
        # by NEST (``equalityOnlyCondition``); recurse on whichever child
        # accessor the context exposes.
        subs = []
        if hasattr(condition_ctx, "condition") and condition_ctx.condition():
            subs = condition_ctx.condition()
        elif hasattr(condition_ctx, "equalityOnlyCondition") and condition_ctx.equalityOnlyCondition():
            subs = condition_ctx.equalityOnlyCondition()
        pairs = []
        for sub in subs:
            pairs.extend(self._parse_condition_pairs(sub))
        return pairs

    def _parse_property_clauses(self, clause_list):
        """Parse property clauses: WITH TYPE, WITH DEFAULT, NOT NULL."""
        result = []
        for clause in clause_list:
            if hasattr(clause, 'withTypeClause') and clause.withTypeClause():
                result.append({'type': 'TYPE', 'data_type': clause.withTypeClause().dataType().getText()})
            elif hasattr(clause, 'withDefaultClause') and clause.withDefaultClause():
                result.append({'type': 'DEFAULT', 'value': clause.withDefaultClause().literal().getText()})
            elif hasattr(clause, 'notNullClause') and clause.notNullClause():
                result.append({'type': 'NOT_NULL'})
        return result

    def _parse_reference_clauses(self, clause_list):
        """Parse reference clauses"""
        result = {}
        for clause in clause_list:
            if hasattr(clause, 'withCardinalityClause') and clause.withCardinalityClause():
                result['cardinality'] = clause.withCardinalityClause().cardinalityType().getText()
            elif hasattr(clause, 'usingKeyClause') and clause.usingKeyClause():
                result['key'] = clause.usingKeyClause().identifier().getText()
            elif hasattr(clause, 'whereClause') and clause.whereClause():
                result['where'] = clause.whereClause().condition().getText()
        return result

    def _parse_embedded_clauses(self, clause_list):
        """Parse embedded clauses."""
        result = []
        for clause in clause_list:
            if hasattr(clause, 'withCardinalityClause') and clause.withCardinalityClause():
                result.append({'type': 'CARDINALITY', 'value': clause.withCardinalityClause().cardinalityType().getText()})
            elif hasattr(clause, 'withStructureClause') and clause.withStructureClause():
                ids = clause.withStructureClause().identifierList()
                result.append({'type': 'STRUCTURE', 'fields': [id.getText() for id in ids.identifier()]})
        return result

    def _parse_entity_clauses(self, clause_list):
        """Parse entity clauses."""
        result = []
        for clause in clause_list:
            if hasattr(clause, 'withPropertiesClause') and clause.withPropertiesClause():
                prop_def_list = clause.withPropertiesClause().propertyDefList()
                props = []
                for prop_def in prop_def_list.propertyDef():
                    props.append({
                        'name': prop_def.identifier().getText(),
                        'data_type': prop_def.dataType().getText()
                    })
                result.append({'type': 'PROPERTIES', 'properties': props})
            elif hasattr(clause, 'withKeyClause') and clause.withKeyClause():
                result.append({'type': 'KEY', 'key_name': clause.withKeyClause().identifier().getText()})
        return result

    def _parse_key_columns(self, key_columns_ctx):
        """Parse key columns - supports qualifiedName (entity.field) or composite keys."""
        if key_columns_ctx.qualifiedName():
            # New: qualifiedName supports entity.field syntax
            full_path = key_columns_ctx.qualifiedName().getText()
            parts = full_path.split(".")
            if len(parts) == 2:
                # Explicit entity.field syntax: address.address_id -> (["address_id"], "address")
                entity_name = parts[0]
                field_name = parts[1]
                return [field_name], entity_name
            else:
                # Single identifier (no dot): just field name
                return [full_path], None
        elif key_columns_ctx.identifierList():
            # Composite key (id1, id2, id3)
            return [id.getText() for id in key_columns_ctx.identifierList().identifier()], None
        return [], None

    def _parse_key_clauses(self, clause_list):
        """Parse key clauses"""
        result = {}
        for clause in clause_list:
            if hasattr(clause, 'referencesClause') and clause.referencesClause():
                ref = clause.referencesClause()
                result['references'] = {
                    'table': ref.qualifiedName().getText(),
                    'columns': [id.getText() for id in ref.identifierList().identifier()]
                }
            elif hasattr(clause, 'withColumnsClause') and clause.withColumnsClause():
                ids = clause.withColumnsClause().identifierList()
                result['columns'] = [id.getText() for id in ids.identifier()]
        return result

    def _parse_unnest_field_list(self, field_list_ctx, parser_module):
        """Recursively parse UNNEST field list to separate properties and nested objects."""
        properties = []
        nested = []

        for field_ctx in field_list_ctx.unnestField():
            if isinstance(field_ctx, parser_module.SimpleFieldContext):
                # Simple property: position, name, street, city
                properties.append(field_ctx.identifier().getText())
            elif isinstance(field_ctx, parser_module.NestedFieldContext):
                # Nested object: company{name, address{street, city}}
                nested_name = field_ctx.identifier().getText()
                # Recursively parse nested field list
                nested_field_list = field_ctx.unnestFieldList()
                child_props, child_nested = self._parse_unnest_field_list(nested_field_list, parser_module)
                nested.append({
                    'name': nested_name,
                    'properties': child_props,
                    'nested': child_nested
                })

        return properties, nested

    # ========================================================================
    # ADD_CONSTRAINT helpers — parse the constraintBody / checkExpr / checkAtom
    # subtree into a CheckExpr AST and an AddConstraintParams payload. Both
    # specific and generalized grammars produce identically-named labelled
    # alternatives for these rules, so the helpers dispatch on the parser
    # context's class name (e.g. "CmpAtomContext") and work for both grammars.
    # ========================================================================

    @staticmethod
    def _strip_string_literal(text: str) -> str:
        """Strip the outer quotes from an ANTLR STRING_LITERAL token. The"""
        if len(text) >= 2 and text[0] in ("'", '"') and text[-1] == text[0]:
            return text[1:-1]
        return text

    def _parse_literal_value(self, lit_ctx):
        """Convert a ``literal`` parse-tree node into a Python value."""
        if lit_ctx.STRING_LITERAL():
            return self._strip_string_literal(lit_ctx.STRING_LITERAL().getText())
        if lit_ctx.INTEGER_LITERAL():
            return int(lit_ctx.INTEGER_LITERAL().getText())
        if lit_ctx.DECIMAL_LITERAL():
            return float(lit_ctx.DECIMAL_LITERAL().getText())
        if lit_ctx.TRUE():
            return True
        if lit_ctx.FALSE():
            return False
        if lit_ctx.NULL():
            return None
        return lit_ctx.getText()

    def _build_check_expr(self, ctx):
        """Recursively build a CheckExpr AST from a ``checkExpr`` /"""
        cls_name = type(ctx).__name__

        # Composite expression nodes. ANTLR accessor convention: a sub-rule
        # invoked once -> ``ctx.checkExpr()`` (no args, single context).
        # A sub-rule invoked multiple times -> ``ctx.checkExpr(i)`` (indexed).
        if cls_name == "CheckParenExprContext":
            return self._build_check_expr(ctx.checkExpr())
        if cls_name == "CheckNotExprContext":
            return CheckNot(expr=self._build_check_expr(ctx.checkExpr()))
        if cls_name == "CheckAndExprContext":
            return CheckAnd(
                left=self._build_check_expr(ctx.checkExpr(0)),
                right=self._build_check_expr(ctx.checkExpr(1)),
            )
        if cls_name == "CheckOrExprContext":
            return CheckOr(
                left=self._build_check_expr(ctx.checkExpr(0)),
                right=self._build_check_expr(ctx.checkExpr(1)),
            )
        if cls_name == "CheckRawExprContext":
            return CheckRaw(raw_text=self._strip_string_literal(
                ctx.STRING_LITERAL().getText()))
        if cls_name == "CheckAtomExprContext":
            return self._build_check_expr(ctx.checkAtom())

        # Atomic predicates.
        if cls_name == "CmpAtomContext":
            return CheckCmp(
                field_name=ctx.qualifiedName().getText(),
                op=ctx.cmpOp().getText(),
                literal=self._parse_literal_value(ctx.literal()),
            )
        if cls_name == "InAtomContext":
            return CheckIn(
                field_name=ctx.qualifiedName().getText(),
                values=[self._parse_literal_value(lit)
                        for lit in ctx.literalList().literal()],
            )
        if cls_name == "BetweenAtomContext":
            literals = ctx.literal()
            return CheckBetween(
                field_name=ctx.qualifiedName().getText(),
                low=self._parse_literal_value(literals[0]),
                high=self._parse_literal_value(literals[1]),
            )
        if cls_name == "RegexAtomContext":
            return CheckRegex(
                field_name=ctx.qualifiedName().getText(),
                pattern=self._strip_string_literal(
                    ctx.STRING_LITERAL().getText()),
            )
        if cls_name == "IsNullAtomContext":
            return CheckIsNull(field_name=ctx.qualifiedName().getText(),
                               is_null=True)
        if cls_name == "IsNotNullAtomContext":
            return CheckIsNull(field_name=ctx.qualifiedName().getText(),
                               is_null=False)

        raise ValueError(f"Unknown CheckExpr context: {cls_name}")

    def _build_add_constraint_params(self, target: str, body_ctx):
        """Construct AddConstraintParams from a constraintBody parse tree."""
        cls_name = type(body_ctx).__name__

        if cls_name == "ConstraintBodyReferenceContext":
            # ADD_CONSTRAINT REFERENCE is always non-enforced (the grammar no
            # longer admits ENFORCED — that case is handled by ADD_FOREIGN_KEY).
            target_table = body_ctx.qualifiedName().getText()
            target_columns = [i.getText()
                              for i in body_ctx.identifierList().identifier()]
            cardinality = (body_ctx.cardinalityType().getText()
                           if body_ctx.cardinalityType() else None)
            return AddConstraintParams(
                target=target,
                body_kind=ConstraintBodyKind.REFERENCE,
                ref_target_table=target_table,
                ref_target_columns=target_columns,
                ref_cardinality=cardinality,
            )

        if cls_name == "ConstraintBodyCheckContext":
            return AddConstraintParams(
                target=target,
                body_kind=ConstraintBodyKind.CHECK,
                check_expression=self._build_check_expr(body_ctx.checkExpr()),
            )

        if cls_name == "ConstraintBodyExistenceContext":
            return AddConstraintParams(
                target=target,
                body_kind=ConstraintBodyKind.EXISTENCE,
            )

        raise ValueError(f"Unknown constraintBody context: {cls_name}")


# SMILE_Specific Listener - For SMILE_Specific.g4

class SMILESpecificListener(SMILE_SpecificListener, BaseSMILEListener):
    """Listener for SMILE_Specific.g4 grammar."""

    def __init__(self):
        BaseSMILEListener.__init__(self)

    # Header parsing (same for all versions)
    def enterMigrationDecl(self, ctx):
        self.context.is_evolution = False
        self.context.name = ctx.identifier().getText()
        self.context.version = ctx.version().getText()

    def enterEvolutionDecl(self, ctx):
        self.context.is_evolution = True
        self.context.name = ctx.identifier().getText()
        self.context.version = ctx.version().getText()

    def enterUsingDecl(self, ctx):
        self.context.schema_name = ctx.identifier().getText()
        self.context.schema_version = ctx.version(0).getText()
        if len(ctx.version()) > 1:
            self.context.target_schema_version = ctx.version(1).getText()

    def enterFromToDecl(self, ctx):
        self.context.source_db_type = ctx.databaseType(0).getText()
        self.context.target_db_type = ctx.databaseType(1).getText()

    # Structure operations
    def enterFlatten(self, ctx):
        # New syntax: FLATTEN qualifiedName
        # Flattens nested object fields into parent table (reduce depth by 1)
        # Example: FLATTEN customers.address
        #   Before: customers { name: { first_name, last_name }, age }
        #   After:  customers { name_first_name, name_last_name, age }
        self.operations.append(Operation(OpType.FLATTEN, FlattenParams(
            source=ctx.qualifiedName().getText()
        ), original_keyword="FLATTEN"))

    def enterUnflatten(self, ctx):
        # UNFLATTEN - Combine flat fields into nested object (reverse of FLATTEN)
        # New: source accepts qualifiedName so embedded entities (e.g. orders.customer)
        # can be addressed by full path, not just by leaf name.
        entity = ctx.qualifiedName().getText()                                   # customers OR orders.customer
        fields = [id.getText() for id in ctx.identifierList().identifier()]      # [first_name, last_name]
        nested_name = ctx.identifier().getText()                                 # name (the AS identifier)
        self.operations.append(Operation(OpType.UNFLATTEN, UnflattenParams(
            entity=entity,
            fields=fields,
            nested_name=nested_name,
        ), original_keyword="UNFLATTEN"))

    def enterUnwind(self, ctx):
        source = ctx.qualifiedName().getText()
        target = ctx.identifier().getText() if ctx.identifier() else None

        if target:
            # Mode 1: Create new table - UNWIND customers.tags[] INTO customer_tag
            self.operations.append(Operation(OpType.UNWIND, UnwindParams(
                mode="create_table",
                source=source,
                target=target,
            ), original_keyword="UNWIND"))
        else:
            # Mode 2: Expand in place - UNWIND customer_tag.value
            self.operations.append(Operation(OpType.UNWIND, UnwindParams(
                mode="expand_in_place",
                source=source,
            ), original_keyword="UNWIND"))

    def enterWind(self, ctx):
        # WIND - Convert scalar property back to array (reverse of UNWIND)
        # Syntax: WIND customer_tag.tags
        # Cross-entity movement is handled by MERGE, not WIND.
        source = ctx.qualifiedName().getText()  # customer_tag.tags
        self.operations.append(Operation(OpType.WIND, WindParams(
            source=source,
        ), original_keyword="WIND"))

    def enterNest(self, ctx):
        # Syntax: NEST qualifiedName COLON unnestFieldList IN qualifiedName WHERE condition
        # Source now accepts qualifiedName too — supports nesting an embedded entity
        # like orders.customer into another container.
        source_entity = ctx.qualifiedName(0).getText()      # address OR orders.customer
        target_location = ctx.qualifiedName(1).getText()    # customers.address

        # Parse WHERE condition(s): supports single or AND-chained conditions
        join_conditions = self._parse_condition_pairs(ctx.equalityOnlyCondition())
        first_eq = next((c for c in join_conditions if c.get("type") == "eq"), None)
        source_fk = first_eq["left"] if first_eq else ""
        target_pk = first_eq["right"] if first_eq else ""

        # Parse target location: customers.address -> target_entity=customers, embedded_name=address
        target_parts = target_location.split(".")
        target_entity = target_parts[0] if target_parts else target_location
        embedded_name = target_parts[1] if len(target_parts) > 1 else source_entity

        # Parse field list: properties to embed
        properties, nested = self._parse_unnest_field_list(
            ctx.unnestFieldList(), SMILE_SpecificParser)

        self.operations.append(Operation(OpType.NEST, NestParams(
            source=source_entity,       # source entity to embed (address)
            target=target_entity,       # target entity (customers)
            alias=embedded_name,        # embedded field name (address)
            properties=properties,      # properties to embed (street, city)
            nested=nested,              # nested objects
            source_fk=source_fk,        # first join condition left (address.customer_id)
            target_pk=target_pk,        # first join condition right (customers.customer_id)
            join_conditions=join_conditions,  # all join conditions
        ), original_keyword="NEST"))

    def enterUnnest(self, ctx):
        # New syntax: UNNEST qualifiedName COLON unnestFieldList AS identifier (WITH unnestCarryList)?
        # Example: UNNEST customers.address:street,city AS address WITH customers.customer_id TO address.customer_id
        # Example with multiple carry fields:
        #   UNNEST customers.employment:position AS employment
        #       WITH customers.customer_id TO employment.customer_id, customers.dept_id TO employment.dept_id
        #   - WITH clause: copy fields from source to new table (can carry multiple fields)
        source_path = ctx.qualifiedName().getText()  # customers.address (single qualifiedName in unnest rule)
        target_name = ctx.identifier().getText()  # address (identifier after AS)

        # Parse carry fields (WITH clause is optional)
        carry_fields = []
        if ctx.unnestCarryList():
            for carry_field in ctx.unnestCarryList().unnestCarryField():
                # unnestCarryField has two qualifiedName: source AS target
                source_field = carry_field.qualifiedName(0).getText()  # customers.customer_id
                target_field = carry_field.qualifiedName(1).getText()  # address.customer_id
                # Extract just the field name from target path
                target_parts = target_field.split(".")
                field_name = target_parts[-1] if target_parts else target_field
                carry_fields.append({
                    "source": source_field,      # customers.customer_id
                    "target": target_field,      # address.customer_id
                    "field_name": field_name     # customer_id
                })

        # Parse field list: recursively separate properties and nested objects
        properties, nested = self._parse_unnest_field_list(
            ctx.unnestFieldList(), SMILE_SpecificParser)

        self.operations.append(Operation(OpType.UNNEST, UnnestParams(
            source_path=source_path,
            properties=properties,  # Regular properties ['street', 'city']
            nested=nested,          # Nested objects [{'name': 'company', 'properties': [...], 'nested': [...]}]
            target=target_name,
            carry_fields=carry_fields,  # List of fields to copy from source to new table
        ), original_keyword="UNNEST"))

    # ADD operations - each has its own method
    def enterAdd_property(self, ctx):
        # Rule: ADD_PROPERTY identifier (TO qualifiedName)? propertyClause*
        self.operations.append(Operation(OpType.ADD_PROPERTY, AddPropertyParams(
            name=ctx.identifier().getText(),
            entity=ctx.qualifiedName().getText() if ctx.qualifiedName() else None,
            clauses=self._parse_property_clauses(ctx.propertyClause()),
        ), original_keyword="ADD_PROPERTY"))

    def enterAdd_foreign_key(self, ctx):
        # Two grammar shapes share this rule:
        #   single-column: ADD_FOREIGN_KEY orders.customer_id REFERENCES customers(customer_id)
        #     -> keyColumns is a qualifiedName, target list has one identifier
        #   composite:     ADD_FOREIGN_KEY (a, b) TO sales REFERENCES tenants_items(a, b)
        #     -> keyColumns is "(identifierList)", explicit TO names the source entity,
        #        target identifierList has the matching columns.
        entity_name, field_names = self._extract_fk_source(ctx)
        target_table, target_columns = self._extract_fk_target(ctx)
        self.operations.append(Operation(OpType.ADD_FOREIGN_KEY, AddForeignKeyParams(
            entity=entity_name,
            field_names=field_names,
            target_table=target_table,
            target_columns=target_columns,
            clauses=self._parse_reference_clauses(ctx.constraintClause()),
        ), original_keyword="ADD_FOREIGN_KEY"))

    def _extract_fk_source(self, ctx):
        """Pull (entity_name, [column, ...]) out of an ADD_FOREIGN_KEY ctx."""
        kc = ctx.keyColumns()
        if kc.qualifiedName():
            # Single-column form: keyColumns is a dotted qualifiedName (entity.field).
            qualified_name = kc.qualifiedName().getText()
            parts = qualified_name.split(".")
            if len(parts) == 2:
                return parts[0], [parts[1]]
            return None, [qualified_name]
        # Composite form: (col1, col2, ...) plus an explicit TO entity.
        cols = [i.getText() for i in kc.identifierList().identifier()]
        top_qns = ctx.qualifiedName()
        if len(top_qns) >= 2:
            # [TO, REFERENCES] — first qualifiedName is the source entity (path-capable).
            return top_qns[0].getText(), cols
        # No TO clause but composite source — fall back to None and let the
        # handler skip with a clear reason.
        return None, cols

    def _extract_fk_target(self, ctx):
        """Return (target_table, [target_column, ...]) from the REFERENCES side."""
        top_qns = ctx.qualifiedName()
        target_table = top_qns[-1].getText()
        target_columns = [i.getText() for i in ctx.identifierList().identifier()]
        return target_table, target_columns

    def enterAdd_embedded(self, ctx):
        # Rule: ADD_EMBEDDED identifier TO qualifiedName embeddedClause*
        self.operations.append(Operation(OpType.ADD_EMBEDDED, AddEmbeddedParams(
            name=ctx.identifier().getText(),
            entity=ctx.qualifiedName().getText(),
            clauses=self._parse_embedded_clauses(ctx.embeddedClause()),
        ), original_keyword="ADD_EMBEDDED"))

    def enterAdd_entity(self, ctx):
        # Rule: ADD_ENTITY identifier (FROM qualifiedName TO qualifiedName)? ...
        # Edge endpoints are now qualifiedName so they can target nested entities.
        params = AddEntityParams(
            name=ctx.identifier().getText(),
            clauses=self._parse_entity_clauses(ctx.entityClause()),
        )
        edge_qns = ctx.qualifiedName()
        if len(edge_qns) >= 2:
            params.source_entity = edge_qns[0].getText()
            params.target_entity = edge_qns[1].getText()
        if ctx.cardinalityType():
            params.cardinality = ctx.cardinalityType().getText()
        self.operations.append(Operation(OpType.ADD_ENTITY, params, original_keyword="ADD_ENTITY"))

    def _resolve_add_key_entity(self, ctx, entity_from_path):
        """TO qualifiedName at top level, falling back to the entity inferred"""
        if ctx.qualifiedName():
            return ctx.qualifiedName().getText()
        return entity_from_path

    def enterAdd_primary_key(self, ctx):
        # Rule: ADD_PRIMARY_KEY keyColumns (AS dataType)? (TO qualifiedName)? keyClause*
        data_type = ctx.dataType().getText() if ctx.dataType() else None
        key_columns, entity_from_path = self._parse_key_columns(ctx.keyColumns())
        entity_name = self._resolve_add_key_entity(ctx, entity_from_path)
        self.operations.append(Operation(OpType.ADD_KEY, AddKeyParams(
            key_type=KeyType.PRIMARY,
            key_columns=key_columns,
            data_type=data_type,
            entity=entity_name,
            clauses=self._parse_key_clauses(ctx.keyClause()),
        ), original_keyword="ADD_PRIMARY_KEY"))

    def enterAdd_unique_key(self, ctx):
        data_type = ctx.dataType().getText() if ctx.dataType() else None
        key_columns, entity_from_path = self._parse_key_columns(ctx.keyColumns())
        entity_name = self._resolve_add_key_entity(ctx, entity_from_path)
        self.operations.append(Operation(OpType.ADD_KEY, AddKeyParams(
            key_type=KeyType.UNIQUE,
            key_columns=key_columns,
            data_type=data_type,
            entity=entity_name,
            clauses=self._parse_key_clauses(ctx.keyClause()),
        ), original_keyword="ADD_UNIQUE_KEY"))

    def enterAdd_partition_key(self, ctx):
        data_type = ctx.dataType().getText() if ctx.dataType() else None
        key_columns, entity_from_path = self._parse_key_columns(ctx.keyColumns())
        entity_name = self._resolve_add_key_entity(ctx, entity_from_path)
        self.operations.append(Operation(OpType.ADD_KEY, AddKeyParams(
            key_type=KeyType.PARTITION,
            key_columns=key_columns,
            data_type=data_type,
            entity=entity_name,
            clauses=self._parse_key_clauses(ctx.keyClause()),
        ), original_keyword="ADD_PARTITION_KEY"))

    def enterAdd_clustering_key(self, ctx):
        data_type = ctx.dataType().getText() if ctx.dataType() else None
        key_columns, entity_from_path = self._parse_key_columns(ctx.keyColumns())
        entity_name = self._resolve_add_key_entity(ctx, entity_from_path)
        self.operations.append(Operation(OpType.ADD_KEY, AddKeyParams(
            key_type=KeyType.CLUSTERING,
            key_columns=key_columns,
            data_type=data_type,
            entity=entity_name,
            clauses=self._parse_key_clauses(ctx.keyClause()),
        ), original_keyword="ADD_CLUSTERING_KEY"))

    def enterAdd_label(self, ctx):
        # Rule: ADD_LABEL identifier TO qualifiedName
        self.operations.append(Operation(OpType.ADD_LABEL, AddLabelParams(
            label=ctx.identifier().getText(),
            entity=ctx.qualifiedName().getText(),
        ), original_keyword="ADD_LABEL"))

    def enterAdd_constraint(self, ctx):
        # Rule: ADD_CONSTRAINT qualifiedName AS constraintBody
        target = ctx.qualifiedName().getText()
        params = self._build_add_constraint_params(target, ctx.constraintBody())
        self.operations.append(Operation(
            OpType.ADD_CONSTRAINT, params, original_keyword="ADD_CONSTRAINT"))

    # DELETE operations
    def enterDelete_property(self, ctx):
        self.operations.append(Operation(OpType.DELETE_PROPERTY, DeletePropertyParams(
            target=ctx.qualifiedName().getText(),
        ), original_keyword="DELETE_PROPERTY"))

    def enterDelete_foreign_key(self, ctx):
        self.operations.append(Operation(OpType.DELETE_FOREIGN_KEY, DeleteForeignKeyParams(
            reference=ctx.qualifiedName().getText(),
        ), original_keyword="DELETE_FOREIGN_KEY"))

    def enterDelete_constraint(self, ctx):
        # Rule: DELETE_CONSTRAINT qualifiedName
        self.operations.append(Operation(
            OpType.DELETE_CONSTRAINT,
            DeleteConstraintParams(target=ctx.qualifiedName().getText()),
            original_keyword="DELETE_CONSTRAINT",
        ))

    def enterDelete_embedded(self, ctx):
        self.operations.append(Operation(OpType.DELETE_EMBEDDED, DeleteEmbeddedParams(
            embedded=ctx.qualifiedName().getText(),
        ), original_keyword="DELETE_EMBEDDED"))

    def enterDelete_entity(self, ctx):
        # Rule: DELETE_ENTITY qualifiedName
        self.operations.append(Operation(OpType.DELETE_ENTITY, DeleteEntityParams(
            name=ctx.qualifiedName().getText(),
        ), original_keyword="DELETE_ENTITY"))

    def _resolve_delete_key_entity(self, ctx, entity_from_path):
        """FROM qualifiedName at top level, falling back to entity from"""
        if ctx.qualifiedName():
            return ctx.qualifiedName().getText()
        return entity_from_path

    def enterDelete_primary_key(self, ctx):
        # Rule: DELETE_PRIMARY_KEY keyColumns (FROM qualifiedName)?
        key_columns, entity_from_path = self._parse_key_columns(ctx.keyColumns())
        entity_name = self._resolve_delete_key_entity(ctx, entity_from_path)
        self.operations.append(Operation(OpType.DELETE_KEY, DeleteKeyParams(
            key_type=KeyType.PRIMARY,
            key_columns=key_columns,
            entity=entity_name,
        ), original_keyword="DELETE_PRIMARY_KEY"))

    def enterDelete_unique_key(self, ctx):
        key_columns, entity_from_path = self._parse_key_columns(ctx.keyColumns())
        entity_name = self._resolve_delete_key_entity(ctx, entity_from_path)
        self.operations.append(Operation(OpType.DELETE_KEY, DeleteKeyParams(
            key_type=KeyType.UNIQUE,
            key_columns=key_columns,
            entity=entity_name,
        ), original_keyword="DELETE_UNIQUE_KEY"))

    def enterDelete_partition_key(self, ctx):
        key_columns, entity_from_path = self._parse_key_columns(ctx.keyColumns())
        entity_name = self._resolve_delete_key_entity(ctx, entity_from_path)
        self.operations.append(Operation(OpType.DELETE_KEY, DeleteKeyParams(
            key_type=KeyType.PARTITION,
            key_columns=key_columns,
            entity=entity_name,
        ), original_keyword="DELETE_PARTITION_KEY"))

    def enterDelete_clustering_key(self, ctx):
        key_columns, entity_from_path = self._parse_key_columns(ctx.keyColumns())
        entity_name = self._resolve_delete_key_entity(ctx, entity_from_path)
        self.operations.append(Operation(OpType.DELETE_KEY, DeleteKeyParams(
            key_type=KeyType.CLUSTERING,
            key_columns=key_columns,
            entity=entity_name,
        ), original_keyword="DELETE_CLUSTERING_KEY"))

    def enterDelete_label(self, ctx):
        # Rule: DELETE_LABEL identifier FROM qualifiedName
        self.operations.append(Operation(OpType.DELETE_LABEL, DeleteLabelParams(
            label=ctx.identifier().getText(),
            entity=ctx.qualifiedName().getText(),
        ), original_keyword="DELETE_LABEL"))

    # RENAME operations
    def enterRename_property(self, ctx):
        # Rule: RENAME_PROPERTY identifier TO identifier (IN qualifiedName)?
        identifiers = ctx.identifier()
        self.operations.append(Operation(OpType.RENAME_PROPERTY, RenamePropertyParams(
            old_name=identifiers[0].getText(),
            new_name=identifiers[1].getText() if len(identifiers) > 1 else None,
            entity=ctx.qualifiedName().getText() if ctx.qualifiedName() else None,
        ), original_keyword="RENAME_PROPERTY"))

    def enterRename_entity(self, ctx):
        # Rule: RENAME_ENTITY qualifiedName TO qualifiedName
        qns = ctx.qualifiedName()
        self.operations.append(Operation(OpType.RENAME_ENTITY, RenameEntityParams(
            old_name=qns[0].getText(),
            new_name=qns[1].getText() if len(qns) > 1 else None,
        ), original_keyword="RENAME_ENTITY"))

    # Simple operations
    def enterCopy_property(self, ctx):
        # Rule: COPY_PROPERTY identifier FROM qualifiedName TO qualifiedName
        property_name = ctx.identifier().getText()
        qns = ctx.qualifiedName()
        source_entity = qns[0].getText()
        target_entity = qns[1].getText()
        self.operations.append(Operation(OpType.COPY_PROPERTY, CopyPropertyParams(
            source=f"{source_entity}.{property_name}",
            target=f"{target_entity}.{property_name}",
            join_conditions=self._parse_condition_pairs(ctx.condition()),
        ), original_keyword="COPY_PROPERTY"))

    def enterCopy_entity(self, ctx):
        # Rule: COPY_ENTITY qualifiedName AS identifier (FROM qualifiedName TO qualifiedName)?
        qns = ctx.qualifiedName()
        params = CopyEntityParams(
            source=qns[0].getText(),
            target=ctx.identifier().getText(),
        )
        if len(qns) >= 3:
            params.source_entity = qns[1].getText()
            params.target_entity = qns[2].getText()
        self.operations.append(Operation(OpType.COPY_ENTITY, params, original_keyword="COPY_ENTITY"))

    def enterMove_property(self, ctx):
        # Rule: MOVE_PROPERTY identifier FROM qualifiedName TO qualifiedName
        property_name = ctx.identifier().getText()
        qns = ctx.qualifiedName()
        source_entity = qns[0].getText()
        target_entity = qns[1].getText()
        self.operations.append(Operation(OpType.MOVE_PROPERTY, MovePropertyParams(
            source=f"{source_entity}.{property_name}",
            target=f"{target_entity}.{property_name}",
            join_conditions=self._parse_condition_pairs(ctx.condition()),
        ), original_keyword="MOVE_PROPERTY"))

    def enterMerge(self, ctx):
        # Rule: MERGE qualifiedName COMMA qualifiedName INTO identifier (AS identifier)?
        qns = ctx.qualifiedName()
        ids = ctx.identifier()
        if len(qns) < 2 or not ids:
            return  # malformed MERGE (e.g. missing required WHERE); syntax error already reported
        self.operations.append(Operation(OpType.MERGE, MergeParams(
            source1=qns[0].getText(),
            source2=qns[1].getText(),
            target=ids[0].getText(),
            alias=ids[1].getText() if len(ids) > 1 else None,
            join_conditions=self._parse_condition_pairs(ctx.condition()),
        ), original_keyword="MERGE"))

    def enterSplit(self, ctx):
        # Rule: SPLIT qualifiedName INTO splitPart (SEMICOLON splitPart)+
        # source accepts a fully-qualified path so an embedded entity can be split.
        source_entity = ctx.qualifiedName().getText()
        split_parts = ctx.splitPart() if isinstance(ctx.splitPart(), list) else [ctx.splitPart()]

        parts = []
        for part in split_parts:
            part_name = part.identifier().getText()
            part_fields = [id.getText() for id in part.identifierList().identifier()]
            parts.append({
                "name": part_name,
                "fields": part_fields
            })

        self.operations.append(Operation(OpType.SPLIT, SplitParams(
            source=source_entity,
            parts=parts,
        ), original_keyword="SPLIT"))

    def enterCast_property(self, ctx):
        self.operations.append(Operation(OpType.CAST_PROPERTY, CastPropertyParams(
            target=ctx.qualifiedName().getText(),
            type=ctx.dataType().getText(),
        ), original_keyword="CAST_PROPERTY"))

    def enterCast_constraint(self, ctx):
        ct = ctx.constraintKeyType()
        if ct.PRIMARY():
            constraint_type = "PRIMARY_KEY"
        elif ct.UNIQUE():
            constraint_type = "UNIQUE_KEY"
        elif ct.PARTITION():
            constraint_type = "PARTITION_KEY"
        elif ct.NODE():
            constraint_type = "NODE_KEY"
        elif ct.DOCUMENT_ID():
            constraint_type = "DOCUMENT_ID"
        elif ct.CLUSTERING():
            constraint_type = "CLUSTERING_KEY"
        else:
            raise ValueError(f"Unknown constraint type in CAST_CONSTRAINT: {ct.getText()}")
        self.operations.append(Operation(OpType.CAST_CONSTRAINT, CastConstraintParams(
            target=ctx.qualifiedName().getText(),
            constraint_type=constraint_type,
        ), original_keyword="CAST_CONSTRAINT"))

    def enterCast_entity(self, ctx):
        # Rule: CAST_ENTITY qualifiedName TO databaseType
        self.operations.append(Operation(OpType.CAST_ENTITY, CastEntityParams(
            target=ctx.qualifiedName().getText(),
            entity_kind=ctx.databaseType().getText().upper(),
        ), original_keyword="CAST_ENTITY"))

    def enterRecard(self, ctx):
        self.operations.append(Operation(OpType.RECARD, RecardParams(
            target=ctx.qualifiedName().getText(),
            cardinality=ctx.cardinalityType().getText(),
        ), original_keyword="RECARD"))

    def enterTransform(self, ctx):
        # Rule: TRANSFORM qualifiedName INTO transformTarget
        # transformTarget RELATIONSHIP variant: FROM qualifiedName TO qualifiedName ...
        name = ctx.qualifiedName().getText()
        target_ctx = ctx.transformTarget()

        if isinstance(target_ctx, SMILE_SpecificParser.TransformToRelationshipContext):
            qns = target_ctx.qualifiedName()
            params = TransformParams(
                name=name,
                target_type="RELATIONSHIP",
                source_entity=qns[0].getText(),
                target_entity=qns[1].getText(),
            )
            if target_ctx.cardinalityType():
                params.cardinality = target_ctx.cardinalityType().getText()
            self.operations.append(Operation(OpType.TRANSFORM, params, original_keyword="TRANSFORM"))
        else:
            self.operations.append(Operation(OpType.TRANSFORM, TransformParams(
                name=name,
                target_type="ENTITY",
            ), original_keyword="TRANSFORM"))




# SMILE_Generalized Listener - For SMILE_Generalized.g4

class SMILEGeneralizedListener(SMILE_GeneralizedListener, BaseSMILEListener):
    """Listener for SMILE_Generalized.g4 grammar."""

    def __init__(self):
        BaseSMILEListener.__init__(self)

    # Header parsing (same for all versions)
    def enterMigrationDecl(self, ctx):
        self.context.is_evolution = False
        self.context.name = ctx.identifier().getText()
        self.context.version = ctx.version().getText()

    def enterEvolutionDecl(self, ctx):
        self.context.is_evolution = True
        self.context.name = ctx.identifier().getText()
        self.context.version = ctx.version().getText()

    def enterUsingDecl(self, ctx):
        self.context.schema_name = ctx.identifier().getText()
        self.context.schema_version = ctx.version(0).getText()
        if len(ctx.version()) > 1:
            self.context.target_schema_version = ctx.version(1).getText()

    def enterFromToDecl(self, ctx):
        self.context.source_db_type = ctx.databaseType(0).getText()
        self.context.target_db_type = ctx.databaseType(1).getText()

    # Structure operations
    def enterFlatten_gen(self, ctx):
        # New syntax: FLATTEN qualifiedName
        # Flattens nested object fields into parent table (reduce depth by 1)
        # Example: FLATTEN customers.address
        #   Before: customers { name: { first_name, last_name }, age }
        #   After:  customers { name_first_name, name_last_name, age }
        self.operations.append(Operation(OpType.FLATTEN, FlattenParams(
            source=ctx.qualifiedName().getText(),
        ), original_keyword="FLATTEN"))

    def enterUnflatten_gen(self, ctx):
        # Rule: UNFLATTEN qualifiedName COLON identifierList AS identifier
        entity = ctx.qualifiedName().getText()                                   # customers OR orders.customer
        fields = [id.getText() for id in ctx.identifierList().identifier()]      # [first_name, last_name]
        nested_name = ctx.identifier().getText()                                 # name (the AS identifier)
        self.operations.append(Operation(OpType.UNFLATTEN, UnflattenParams(
            entity=entity,
            fields=fields,
            nested_name=nested_name,
        ), original_keyword="UNFLATTEN"))

    def enterUnwind_gen(self, ctx):
        source = ctx.qualifiedName().getText()
        target = ctx.identifier().getText() if ctx.identifier() else None

        if target:
            # Mode 1: Create new table - UNWIND customers.tags[] INTO customer_tag
            self.operations.append(Operation(OpType.UNWIND, UnwindParams(
                mode="create_table",
                source=source,
                target=target,
            ), original_keyword="UNWIND"))
        else:
            # Mode 2: Expand in place - UNWIND customer_tag.value
            self.operations.append(Operation(OpType.UNWIND, UnwindParams(
                mode="expand_in_place",
                source=source,
            ), original_keyword="UNWIND"))

    def enterWind_gen(self, ctx):
        # WIND - Convert scalar property back to array (reverse of UNWIND)
        # Syntax: WIND customer_tag.tags
        # Cross-entity movement is handled by MERGE, not WIND.
        source = ctx.qualifiedName().getText()  # customer_tag.tags
        self.operations.append(Operation(OpType.WIND, WindParams(
            source=source,
        ), original_keyword="WIND"))

    def enterNest_gen(self, ctx):
        # Rule: NEST qualifiedName COLON unnestFieldList IN qualifiedName WHERE condition
        source_entity = ctx.qualifiedName(0).getText()      # address OR orders.customer
        target_location = ctx.qualifiedName(1).getText()    # customers.address

        # Parse WHERE condition(s): supports single or AND-chained conditions
        join_conditions = self._parse_condition_pairs(ctx.equalityOnlyCondition())
        first_eq = next((c for c in join_conditions if c.get("type") == "eq"), None)
        source_fk = first_eq["left"] if first_eq else ""
        target_pk = first_eq["right"] if first_eq else ""

        # Parse target location: customers.address -> target_entity=customers, embedded_name=address
        target_parts = target_location.split(".")
        target_entity = target_parts[0] if target_parts else target_location
        embedded_name = target_parts[1] if len(target_parts) > 1 else source_entity

        # Parse field list: properties to embed
        properties, nested = self._parse_unnest_field_list(
            ctx.unnestFieldList(), SMILE_GeneralizedParser)

        self.operations.append(Operation(OpType.NEST, NestParams(
            source=source_entity,       # source entity to embed (address)
            target=target_entity,       # target entity (customers)
            alias=embedded_name,        # embedded field name (address)
            properties=properties,      # properties to embed (street, city)
            nested=nested,              # nested objects
            source_fk=source_fk,        # first join condition left (address.customer_id)
            target_pk=target_pk,        # first join condition right (customers.customer_id)
            join_conditions=join_conditions,  # all join conditions
        ), original_keyword="NEST"))

    def enterUnnest_gen(self, ctx):
        # New syntax: UNNEST qualifiedName COLON unnestFieldList AS identifier (WITH unnestCarryList)?
        # Example: UNNEST customers.address:street,city AS address WITH customers.customer_id TO address.customer_id
        # Example with multiple carry fields:
        #   UNNEST customers.employment:position AS employment
        #       WITH customers.customer_id TO employment.customer_id, customers.dept_id TO employment.dept_id
        #   - WITH clause: copy fields from source to new table (can carry multiple fields)
        source_path = ctx.qualifiedName().getText()  # customers.address (single qualifiedName in unnest_gen rule)
        target_name = ctx.identifier().getText()  # address (identifier after AS)

        # Parse carry fields (WITH clause is optional)
        carry_fields = []
        if ctx.unnestCarryList():
            for carry_field in ctx.unnestCarryList().unnestCarryField():
                # unnestCarryField has two qualifiedName: source AS target
                source_field = carry_field.qualifiedName(0).getText()  # customers.customer_id
                target_field = carry_field.qualifiedName(1).getText()  # address.customer_id
                # Extract just the field name from target path
                target_parts = target_field.split(".")
                field_name = target_parts[-1] if target_parts else target_field
                carry_fields.append({
                    "source": source_field,      # customers.customer_id
                    "target": target_field,      # address.customer_id
                    "field_name": field_name     # customer_id
                })

        # Parse field list: recursively separate properties and nested objects
        properties, nested = self._parse_unnest_field_list(
            ctx.unnestFieldList(), SMILE_GeneralizedParser)

        self.operations.append(Operation(OpType.UNNEST, UnnestParams(
            source_path=source_path,
            properties=properties,  # Regular properties ['street', 'city']
            nested=nested,          # Nested objects [{'name': 'company', 'properties': [...], 'nested': [...]}]
            target=target_name,
            carry_fields=carry_fields,  # List of fields to copy from source to new table
        ), original_keyword="UNNEST"))

    # ADD operations - same internal structure as original SMILE
    def enterPropertyAdd(self, ctx):
        # Rule: PROPERTY identifier (TO qualifiedName)? propertyClause*
        self.operations.append(Operation(OpType.ADD_PROPERTY, AddPropertyParams(
            name=ctx.identifier().getText(),
            entity=ctx.qualifiedName().getText() if ctx.qualifiedName() else None,
            clauses=self._parse_property_clauses(ctx.propertyClause()),
        ), original_keyword="ADD PROPERTY"))

    def enterForeignKeyAdd(self, ctx):
        # Generalized variant of ADD_FOREIGN_KEY — same two grammar shapes
        # (single-column qualifiedName vs composite "(cols) TO entity") share
        # this rule. The Specific listener defines the shape-extraction
        # helpers; reuse them so both grammars normalise to the same params.
        entity_name, field_names = SMILESpecificListener._extract_fk_source(self, ctx)
        target_table, target_columns = SMILESpecificListener._extract_fk_target(self, ctx)
        self.operations.append(Operation(OpType.ADD_FOREIGN_KEY, AddForeignKeyParams(
            entity=entity_name,
            field_names=field_names,
            target_table=target_table,
            target_columns=target_columns,
            clauses=self._parse_reference_clauses(ctx.constraintClause()),
        ), original_keyword="ADD FOREIGN KEY"))

    def enterEmbeddedAdd(self, ctx):
        # Rule: EMBEDDED identifier TO qualifiedName embeddedClause*
        self.operations.append(Operation(OpType.ADD_EMBEDDED, AddEmbeddedParams(
            name=ctx.identifier().getText(),
            entity=ctx.qualifiedName().getText(),
            clauses=self._parse_embedded_clauses(ctx.embeddedClause()),
        ), original_keyword="ADD EMBEDDED"))

    def enterEntityAdd(self, ctx):
        # Rule: ENTITY identifier (FROM qualifiedName TO qualifiedName)? ...
        params = AddEntityParams(
            name=ctx.identifier().getText(),
            clauses=self._parse_entity_clauses(ctx.entityClause()),
        )
        edge_qns = ctx.qualifiedName()
        if len(edge_qns) >= 2:
            params.source_entity = edge_qns[0].getText()
            params.target_entity = edge_qns[1].getText()
        if ctx.cardinalityType():
            params.cardinality = ctx.cardinalityType().getText()
        self.operations.append(Operation(OpType.ADD_ENTITY, params, original_keyword="ADD ENTITY"))

    def enterKeyAdd(self, ctx):
        # Rule: keyType? KEY keyColumns (AS dataType)? (TO qualifiedName)? keyClause*
        key_type = ctx.keyType().getText() if ctx.keyType() else "PRIMARY"
        data_type = ctx.dataType().getText() if ctx.dataType() else None
        key_columns, entity_from_path = self._parse_key_columns(ctx.keyColumns())
        # Entity priority: explicit TO qualifiedName > entity from dotted keyColumns
        if ctx.qualifiedName():
            entity_name = ctx.qualifiedName().getText()
        else:
            entity_name = entity_from_path
        original_kw = "ADD " + (key_type + " " if key_type != "PRIMARY" else "") + "KEY"
        self.operations.append(Operation(OpType.ADD_KEY, AddKeyParams(
            key_type=key_type,
            key_columns=key_columns,
            data_type=data_type,
            entity=entity_name,
            clauses=self._parse_key_clauses(ctx.keyClause()),
        ), original_keyword=original_kw))

    def enterLabelAdd(self, ctx):
        # Rule: LABEL identifier TO qualifiedName
        self.operations.append(Operation(OpType.ADD_LABEL, AddLabelParams(
            label=ctx.identifier().getText(),
            entity=ctx.qualifiedName().getText(),
        ), original_keyword="ADD LABEL"))

    def enterConstraintAdd(self, ctx):
        # Rule: CONSTRAINT qualifiedName AS constraintBody
        target = ctx.qualifiedName().getText()
        params = self._build_add_constraint_params(target, ctx.constraintBody())
        self.operations.append(Operation(
            OpType.ADD_CONSTRAINT, params, original_keyword="ADD CONSTRAINT"))

    # DELETE operations
    def enterPropertyDelete(self, ctx):
        self.operations.append(Operation(OpType.DELETE_PROPERTY, DeletePropertyParams(
            target=ctx.qualifiedName().getText(),
        ), original_keyword="DELETE PROPERTY"))

    def enterConstraintDelete(self, ctx):
        # Rule: CONSTRAINT qualifiedName
        self.operations.append(Operation(
            OpType.DELETE_CONSTRAINT,
            DeleteConstraintParams(target=ctx.qualifiedName().getText()),
            original_keyword="DELETE CONSTRAINT",
        ))

    def enterForeignKeyDelete(self, ctx):
        self.operations.append(Operation(OpType.DELETE_FOREIGN_KEY, DeleteForeignKeyParams(
            reference=ctx.qualifiedName().getText(),
        ), original_keyword="DELETE FOREIGN KEY"))

    def enterEmbeddedDelete(self, ctx):
        self.operations.append(Operation(OpType.DELETE_EMBEDDED, DeleteEmbeddedParams(
            embedded=ctx.qualifiedName().getText(),
        ), original_keyword="DELETE EMBEDDED"))

    def enterEntityDelete(self, ctx):
        # Rule: ENTITY qualifiedName
        self.operations.append(Operation(OpType.DELETE_ENTITY, DeleteEntityParams(
            name=ctx.qualifiedName().getText(),
        ), original_keyword="DELETE ENTITY"))

    def enterKeyDelete(self, ctx):
        # Rule: keyType KEY keyColumns (FROM qualifiedName)?
        key_columns, entity_from_path = self._parse_key_columns(ctx.keyColumns())
        if ctx.qualifiedName():
            entity_name = ctx.qualifiedName().getText()
        else:
            entity_name = entity_from_path
        key_type = ctx.keyType().getText()
        self.operations.append(Operation(OpType.DELETE_KEY, DeleteKeyParams(
            key_type=key_type,
            key_columns=key_columns,
            entity=entity_name,
        ), original_keyword="DELETE " + key_type + " KEY"))

    def enterLabelDelete(self, ctx):
        # Rule: LABEL identifier FROM qualifiedName
        self.operations.append(Operation(OpType.DELETE_LABEL, DeleteLabelParams(
            label=ctx.identifier().getText(),
            entity=ctx.qualifiedName().getText(),
        ), original_keyword="DELETE LABEL"))

    # RENAME operations
    def enterPropertyRename(self, ctx):
        # Rule: PROPERTY identifier TO identifier (IN qualifiedName)?
        identifiers = ctx.identifier()
        self.operations.append(Operation(OpType.RENAME_PROPERTY, RenamePropertyParams(
            old_name=identifiers[0].getText(),
            new_name=identifiers[1].getText() if len(identifiers) > 1 else None,
            entity=ctx.qualifiedName().getText() if ctx.qualifiedName() else None,
        ), original_keyword="RENAME PROPERTY"))

    def enterEntityRename(self, ctx):
        # Rule: ENTITY qualifiedName TO qualifiedName
        qns = ctx.qualifiedName()
        self.operations.append(Operation(OpType.RENAME_ENTITY, RenameEntityParams(
            old_name=qns[0].getText(),
            new_name=qns[1].getText() if len(qns) > 1 else None,
        ), original_keyword="RENAME ENTITY"))

    # Simple operations
    def enterCopy_gen(self, ctx):
        if ctx.entityCopy():
            # Rule: ENTITY qualifiedName AS identifier (FROM qualifiedName TO qualifiedName)?
            ec = ctx.entityCopy()
            qns = ec.qualifiedName()
            params = CopyEntityParams(
                source=qns[0].getText(),
                target=ec.identifier().getText(),
            )
            if len(qns) >= 3:
                params.source_entity = qns[1].getText()
                params.target_entity = qns[2].getText()
            self.operations.append(Operation(OpType.COPY_ENTITY, params, original_keyword="COPY ENTITY"))
        else:
            # Rule: PROPERTY identifier FROM qualifiedName TO qualifiedName
            pc = ctx.propertyCopy()
            property_name = pc.identifier().getText()
            qns = pc.qualifiedName()
            source_entity = qns[0].getText()
            target_entity = qns[1].getText()
            self.operations.append(Operation(OpType.COPY_PROPERTY, CopyPropertyParams(
                source=f"{source_entity}.{property_name}",
                target=f"{target_entity}.{property_name}",
                join_conditions=self._parse_condition_pairs(pc.condition()),
            ), original_keyword="COPY PROPERTY"))

    def enterMove_gen(self, ctx):
        # Rule: MOVE PROPERTY identifier FROM qualifiedName TO qualifiedName
        property_name = ctx.identifier().getText()
        qns = ctx.qualifiedName()
        source_entity = qns[0].getText()
        target_entity = qns[1].getText()
        self.operations.append(Operation(OpType.MOVE_PROPERTY, MovePropertyParams(
            source=f"{source_entity}.{property_name}",
            target=f"{target_entity}.{property_name}",
            join_conditions=self._parse_condition_pairs(ctx.condition()),
        ), original_keyword="MOVE PROPERTY"))

    def enterMerge_gen(self, ctx):
        # Rule: MERGE qualifiedName COMMA qualifiedName INTO identifier (AS identifier)?
        qns = ctx.qualifiedName()
        ids = ctx.identifier()
        if len(qns) < 2 or not ids:
            return  # malformed MERGE (e.g. missing required WHERE); syntax error already reported
        self.operations.append(Operation(OpType.MERGE, MergeParams(
            source1=qns[0].getText(),
            source2=qns[1].getText(),
            target=ids[0].getText(),
            alias=ids[1].getText() if len(ids) > 1 else None,
            join_conditions=self._parse_condition_pairs(ctx.condition()),
        ), original_keyword="MERGE"))

    def enterSplit_gen(self, ctx):
        # Rule: SPLIT qualifiedName INTO splitPartGen (SEMICOLON splitPartGen)+
        source_entity = ctx.qualifiedName().getText()
        split_parts = ctx.splitPartGen() if isinstance(ctx.splitPartGen(), list) else [ctx.splitPartGen()]

        parts = []
        for part in split_parts:
            part_name = part.identifier().getText()
            part_fields = [id.getText() for id in part.identifierList().identifier()]
            parts.append({
                "name": part_name,
                "fields": part_fields
            })

        self.operations.append(Operation(OpType.SPLIT, SplitParams(
            source=source_entity,
            parts=parts,
        ), original_keyword="SPLIT"))

    def enterCast_gen(self, ctx):
        if ctx.constraintCast():
            cc = ctx.constraintCast()
            ct = cc.constraintKeyType()
            if ct.PRIMARY():
                constraint_type = "PRIMARY_KEY"
            elif ct.UNIQUE():
                constraint_type = "UNIQUE_KEY"
            elif ct.PARTITION():
                constraint_type = "PARTITION_KEY"
            elif ct.NODE():
                constraint_type = "NODE_KEY"
            elif ct.DOCUMENT_ID():
                constraint_type = "DOCUMENT_ID"
            elif ct.CLUSTERING():
                constraint_type = "CLUSTERING_KEY"
            else:
                raise ValueError(f"Unknown constraint type in CAST CONSTRAINT: {ct.getText()}")
            self.operations.append(Operation(OpType.CAST_CONSTRAINT, CastConstraintParams(
                target=cc.qualifiedName().getText(),
                constraint_type=constraint_type,
            ), original_keyword="CAST CONSTRAINT"))
        elif ctx.entityCast():
            ec = ctx.entityCast()
            # Rule: ENTITY qualifiedName TO databaseType
            self.operations.append(Operation(OpType.CAST_ENTITY, CastEntityParams(
                target=ec.qualifiedName().getText(),
                entity_kind=ec.databaseType().getText().upper(),
            ), original_keyword="CAST ENTITY"))
        else:
            pc = ctx.propertyCast()
            self.operations.append(Operation(OpType.CAST_PROPERTY, CastPropertyParams(
                target=pc.qualifiedName().getText(),
                type=pc.dataType().getText(),
            ), original_keyword="CAST PROPERTY"))

    def enterRecard_gen(self, ctx):
        self.operations.append(Operation(OpType.RECARD, RecardParams(
            target=ctx.qualifiedName().getText(),
            cardinality=ctx.cardinalityType().getText(),
        ), original_keyword="RECARD"))

    def enterTransform_gen(self, ctx):
        # Rule: TRANSFORM qualifiedName INTO transformTarget
        name = ctx.qualifiedName().getText()
        target_ctx = ctx.transformTarget()

        if isinstance(target_ctx, SMILE_GeneralizedParser.TransformToRelationshipContext):
            qns = target_ctx.qualifiedName()
            params = TransformParams(
                name=name,
                target_type="RELATIONSHIP",
                source_entity=qns[0].getText(),
                target_entity=qns[1].getText(),
            )
            if target_ctx.cardinalityType():
                params.cardinality = target_ctx.cardinalityType().getText()
            self.operations.append(Operation(OpType.TRANSFORM, params, original_keyword="TRANSFORM"))
        else:
            self.operations.append(Operation(OpType.TRANSFORM, TransformParams(
                name=name,
                target_type="ENTITY",
            ), original_keyword="TRANSFORM"))


