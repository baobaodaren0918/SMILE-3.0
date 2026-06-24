"""
Unit tests for the relationship trace mechanism on the SchemaTransformer
base class. These are deliberately small and bypass the full parse/migrate
pipeline so the trace's edge cases can be exercised in isolation.

The key invariant under test: when multiple trace entries match the same
Edge endpoint pair, ``_consume_deleted_fk_for_edge`` must NOT silently
pick one — it must log a warning and return (None, None), leaving the
caller to fall back to the default. This protects against the multi-FK
footgun (e.g. an entity with both ``billing_customer_id`` and
``shipping_customer_id`` pointing at the same target).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core import SchemaTransformer
from Schema.unified_meta_schema import (
    Cardinality,
    Database,
    DatabaseType,
    Edge,
    EntityKind,
    EntityType,
    RelationshipTrace,
    TraceOrigin,
)
from parser.params import TransformParams


def _new_transformer():
    return SchemaTransformer(Database(db_name="t", db_type=DatabaseType.RELATIONAL))


def test_single_trace_opp_dir_returns_swapped_values():
    """One trace entry, opposite-direction lookup: source/target swap per Path C convention."""
    t = _new_transformer()
    t._relationship_trace.append(RelationshipTrace(
        holder="orders", ref_name="customer_id", target="customers",
        target_end_cardinality=Cardinality.ONE_TO_ONE,
        source_end_cardinality=Cardinality.ZERO_TO_MANY,
        origin=TraceOrigin.DELETED_REFERENCE,
    ))
    # ADD_ENTITY PURCHASED FROM customers TO orders → opp_dir match
    target_end_card, source_end_card = t._consume_deleted_fk_for_edge("customers", "orders")
    assert target_end_card == Cardinality.ZERO_TO_MANY  # was trace.source_end_cardinality
    assert source_end_card == Cardinality.ONE_TO_ONE    # was trace.target_end_cardinality
    assert t._relationship_trace == []              # consumed


def test_single_trace_same_dir_returns_direct_values():
    """One trace entry, same-direction lookup: no swap."""
    t = _new_transformer()
    t._relationship_trace.append(RelationshipTrace(
        holder="products", ref_name="category_id", target="categories",
        target_end_cardinality=Cardinality.ONE_TO_ONE,
        source_end_cardinality=Cardinality.ZERO_TO_MANY,
        origin=TraceOrigin.DELETED_REFERENCE,
    ))
    # ADD_ENTITY PART_OF FROM products TO categories → same_dir match
    target_end_card, source_end_card = t._consume_deleted_fk_for_edge("products", "categories")
    assert target_end_card == Cardinality.ONE_TO_ONE
    assert source_end_card == Cardinality.ZERO_TO_MANY
    assert t._relationship_trace == []


def test_multi_fk_same_endpoint_pair_refuses_to_guess():
    """Multi-FK footgun: two References from orders to customers
    (billing_customer_id + shipping_customer_id) produce two trace entries
    on the same (orders, customers) endpoint pair. ADD_ENTITY must NOT
    silently pick one; it must log a warning and return (None, None) so
    the caller falls back to the default target_end_cardinality."""
    t = _new_transformer()
    t._relationship_trace.append(RelationshipTrace(
        holder="orders", ref_name="billing_customer_id", target="customers",
        target_end_cardinality=Cardinality.ONE_TO_ONE,
        source_end_cardinality=Cardinality.ZERO_TO_MANY,
        origin=TraceOrigin.DELETED_REFERENCE,
    ))
    t._relationship_trace.append(RelationshipTrace(
        holder="orders", ref_name="shipping_customer_id", target="customers",
        target_end_cardinality=Cardinality.ZERO_TO_ONE,
        source_end_cardinality=Cardinality.ZERO_TO_MANY,
        origin=TraceOrigin.DELETED_REFERENCE,
    ))
    # ADD_ENTITY CUSTOMER_LINK FROM customers TO orders → opp_dir would
    # find 2 candidates → refuse to guess.
    target_end_card, source_end_card = t._consume_deleted_fk_for_edge("customers", "orders")
    assert target_end_card is None
    assert source_end_card is None
    # Both traces remain — neither was silently consumed.
    assert len(t._relationship_trace) == 2


def test_self_ref_multi_trace_also_refuses_to_guess():
    """Self-reference variant: multiple traces with holder == target.
    Same protection applies."""
    t = _new_transformer()
    t._relationship_trace.append(RelationshipTrace(
        holder="employees", ref_name="manager_id", target="employees",
        target_end_cardinality=Cardinality.ZERO_TO_ONE,
        origin=TraceOrigin.DELETED_REFERENCE,
    ))
    t._relationship_trace.append(RelationshipTrace(
        holder="employees", ref_name="mentor_id", target="employees",
        target_end_cardinality=Cardinality.ZERO_TO_ONE,
        origin=TraceOrigin.DELETED_REFERENCE,
    ))
    # ADD_ENTITY REPORTS_TO FROM employees TO employees — self-ref edge.
    target_end_card, source_end_card = t._consume_deleted_fk_for_edge("employees", "employees")
    assert target_end_card is None
    assert source_end_card is None
    assert len(t._relationship_trace) == 2


def test_fallback_default_applied_after_ambiguous_lookup():
    """After ambiguous lookup returns None, _default_source_end_cardinality
    fills 0..n. The handler thus emits an explicit default rather than
    silently propagating a guessed value."""
    t = _new_transformer()
    t._relationship_trace.append(RelationshipTrace(
        holder="orders", ref_name="billing_customer_id", target="customers",
        target_end_cardinality=Cardinality.ONE_TO_ONE,
        origin=TraceOrigin.DELETED_REFERENCE,
    ))
    t._relationship_trace.append(RelationshipTrace(
        holder="orders", ref_name="shipping_customer_id", target="customers",
        target_end_cardinality=Cardinality.ONE_TO_ONE,
        origin=TraceOrigin.DELETED_REFERENCE,
    ))
    _, source_end_card = t._consume_deleted_fk_for_edge("customers", "orders")
    # default_source_end_cardinality returns ZERO_TO_MANY when given None
    assert t._default_source_end_cardinality(source_end_card) == Cardinality.ZERO_TO_MANY


# ---------------------------------------------------------------------------
# TRANSFORMED_EDGE scoping (edge -> vertex -> edge round-trip)
# ---------------------------------------------------------------------------

def test_transformed_edge_trace_requires_matching_edge_name():
    """A TRANSFORMED_EDGE trace is scoped to its edge name: only a caller that
    passes the matching ``edge_name`` may consume it. ADD_ENTITY (no edge_name)
    and a TRANSFORM of a differently-named edge must NOT claim it."""
    t = _new_transformer()
    t._relationship_trace.append(RelationshipTrace(
        holder="orders", ref_name="CONTAINS", target="products",
        target_end_cardinality=Cardinality.ONE_TO_ONE,
        source_end_cardinality=Cardinality.ONE_TO_MANY,
        origin=TraceOrigin.TRANSFORMED_EDGE,
    ))

    # ADD_ENTITY path: no edge_name -> not eligible, trace untouched.
    assert t._consume_deleted_fk_for_edge("orders", "products") == (None, None)
    assert len(t._relationship_trace) == 1

    # TRANSFORM of a different edge name -> not eligible, trace untouched.
    assert t._consume_deleted_fk_for_edge(
        "orders", "products", edge_name="SUPPLIES") == (None, None)
    assert len(t._relationship_trace) == 1

    # TRANSFORM of the matching edge name -> consumed, values recovered.
    assert t._consume_deleted_fk_for_edge(
        "orders", "products", edge_name="CONTAINS") == (
            Cardinality.ONE_TO_ONE, Cardinality.ONE_TO_MANY)
    assert t._relationship_trace == []


def test_transform_edge_vertex_edge_round_trip_is_lossless():
    """End-to-end: TRANSFORM <edge> INTO ENTITY then back INTO RELATIONSHIP
    (no WITH CARDINALITY) recovers the original bidirectional cardinality via
    the scoped TRANSFORMED_EDGE trace."""
    db = Database(db_name="g", db_type=DatabaseType.GRAPH)
    orders = EntityType(object_name=["orders"], entity_kind=EntityKind.VERTEX)
    products = EntityType(object_name=["products"], entity_kind=EntityKind.VERTEX)
    contains = EntityType(object_name=["CONTAINS"], entity_kind=EntityKind.EDGE)
    contains.source_entity = "orders"
    contains.target_entity = "products"
    contains.edge_target_end_cardinality = Cardinality.ONE_TO_ONE
    contains.edge_source_end_cardinality = Cardinality.ONE_TO_MANY
    for e in (orders, products, contains):
        db.add_entity_type(e)
    orders.add_relationship(Edge(
        rel_type_name="CONTAINS", source_entity="orders", target_entity="products",
        target_end_cardinality=Cardinality.ONE_TO_ONE,
        source_end_cardinality=Cardinality.ONE_TO_MANY,
    ))

    t = SchemaTransformer(db)

    # EDGE -> VERTEX
    r1 = t._handle_transform(TransformParams(name="CONTAINS", target_type="ENTITY"))
    assert r1.success
    live = t.database.get_entity_type("CONTAINS")
    assert live.entity_kind == EntityKind.VERTEX
    assert live.edge_target_end_cardinality is None

    # VERTEX -> EDGE (same direction, no explicit cardinality)
    r2 = t._handle_transform(TransformParams(
        name="CONTAINS", target_type="RELATIONSHIP",
        source_entity="orders", target_entity="products"))
    assert r2.success
    live = t.database.get_entity_type("CONTAINS")
    assert live.entity_kind == EntityKind.EDGE
    assert live.edge_target_end_cardinality == Cardinality.ONE_TO_ONE
    assert live.edge_source_end_cardinality == Cardinality.ONE_TO_MANY
    # The scoped trace was consumed exactly once.
    assert t._relationship_trace == []


def test_transform_round_trip_reversed_direction_swaps_ends():
    """Round-trip back with the endpoints reversed (FROM products TO orders)
    swaps the two ends, matching the opp-dir convention."""
    db = Database(db_name="g", db_type=DatabaseType.GRAPH)
    orders = EntityType(object_name=["orders"], entity_kind=EntityKind.VERTEX)
    products = EntityType(object_name=["products"], entity_kind=EntityKind.VERTEX)
    contains = EntityType(object_name=["CONTAINS"], entity_kind=EntityKind.EDGE)
    contains.source_entity = "orders"
    contains.target_entity = "products"
    contains.edge_target_end_cardinality = Cardinality.ONE_TO_ONE
    contains.edge_source_end_cardinality = Cardinality.ONE_TO_MANY
    for e in (orders, products, contains):
        db.add_entity_type(e)
    orders.add_relationship(Edge(
        rel_type_name="CONTAINS", source_entity="orders", target_entity="products",
        target_end_cardinality=Cardinality.ONE_TO_ONE,
        source_end_cardinality=Cardinality.ONE_TO_MANY,
    ))

    t = SchemaTransformer(db)
    t._handle_transform(TransformParams(name="CONTAINS", target_type="ENTITY"))
    t._handle_transform(TransformParams(
        name="CONTAINS", target_type="RELATIONSHIP",
        source_entity="products", target_entity="orders"))  # reversed

    live = t.database.get_entity_type("CONTAINS")
    # opp-dir: trace's (target=1..1, source=1..n) swap to (1..n, 1..1)
    assert live.edge_target_end_cardinality == Cardinality.ONE_TO_MANY
    assert live.edge_source_end_cardinality == Cardinality.ONE_TO_ONE


def _graph_with_self_ref_edge():
    """employees --REPORTS_TO--> employees (self-referential edge)."""
    db = Database(db_name="g", db_type=DatabaseType.GRAPH)
    employees = EntityType(object_name=["employees"], entity_kind=EntityKind.VERTEX)
    reports_to = EntityType(object_name=["REPORTS_TO"], entity_kind=EntityKind.EDGE)
    reports_to.source_entity = "employees"
    reports_to.target_entity = "employees"
    reports_to.edge_target_end_cardinality = Cardinality.ZERO_TO_ONE
    reports_to.edge_source_end_cardinality = Cardinality.ZERO_TO_MANY
    for e in (employees, reports_to):
        db.add_entity_type(e)
    employees.add_relationship(Edge(
        rel_type_name="REPORTS_TO", source_entity="employees", target_entity="employees",
        target_end_cardinality=Cardinality.ZERO_TO_ONE,
        source_end_cardinality=Cardinality.ZERO_TO_MANY,
    ))
    return db


def test_self_ref_edge_round_trip_is_lossless():
    """Self-referential edge (source == target) survives EDGE->VERTEX->EDGE."""
    t = SchemaTransformer(_graph_with_self_ref_edge())
    t._handle_transform(TransformParams(name="REPORTS_TO", target_type="ENTITY"))
    t._handle_transform(TransformParams(
        name="REPORTS_TO", target_type="RELATIONSHIP",
        source_entity="employees", target_entity="employees"))

    live = t.database.get_entity_type("REPORTS_TO")
    assert live.entity_kind == EntityKind.EDGE
    assert live.edge_target_end_cardinality == Cardinality.ZERO_TO_ONE
    assert live.edge_source_end_cardinality == Cardinality.ZERO_TO_MANY
    assert t._relationship_trace == []


def test_two_transformed_edges_same_endpoints_disambiguated_by_name():
    """Two edges between the SAME endpoint pair, transformed to vertices, then
    each round-tripped: name-scoping keeps their cardinalities from crossing."""
    db = Database(db_name="g", db_type=DatabaseType.GRAPH)
    a = EntityType(object_name=["a"], entity_kind=EntityKind.VERTEX)
    b = EntityType(object_name=["b"], entity_kind=EntityKind.VERTEX)
    e1 = EntityType(object_name=["E1"], entity_kind=EntityKind.EDGE)
    e1.source_entity, e1.target_entity = "a", "b"
    e1.edge_target_end_cardinality = Cardinality.ONE_TO_ONE
    e1.edge_source_end_cardinality = Cardinality.ONE_TO_MANY
    e2 = EntityType(object_name=["E2"], entity_kind=EntityKind.EDGE)
    e2.source_entity, e2.target_entity = "a", "b"
    e2.edge_target_end_cardinality = Cardinality.ZERO_TO_ONE
    e2.edge_source_end_cardinality = Cardinality.ZERO_TO_MANY
    for e in (a, b, e1, e2):
        db.add_entity_type(e)
    a.add_relationship(Edge(rel_type_name="E1", source_entity="a", target_entity="b",
                            target_end_cardinality=Cardinality.ONE_TO_ONE,
                            source_end_cardinality=Cardinality.ONE_TO_MANY))
    a.add_relationship(Edge(rel_type_name="E2", source_entity="a", target_entity="b",
                            target_end_cardinality=Cardinality.ZERO_TO_ONE,
                            source_end_cardinality=Cardinality.ZERO_TO_MANY))

    t = SchemaTransformer(db)
    # Transform both edges to vertices (two traces on the same (a, b) pair).
    t._handle_transform(TransformParams(name="E1", target_type="ENTITY"))
    t._handle_transform(TransformParams(name="E2", target_type="ENTITY"))
    assert len(t._relationship_trace) == 2

    # Round-trip each back; each must recover ITS OWN cardinality.
    t._handle_transform(TransformParams(name="E2", target_type="RELATIONSHIP",
                                        source_entity="a", target_entity="b"))
    t._handle_transform(TransformParams(name="E1", target_type="RELATIONSHIP",
                                        source_entity="a", target_entity="b"))

    live1 = t.database.get_entity_type("E1")
    live2 = t.database.get_entity_type("E2")
    assert (live1.edge_target_end_cardinality, live1.edge_source_end_cardinality) == (
        Cardinality.ONE_TO_ONE, Cardinality.ONE_TO_MANY)
    assert (live2.edge_target_end_cardinality, live2.edge_source_end_cardinality) == (
        Cardinality.ZERO_TO_ONE, Cardinality.ZERO_TO_MANY)
    assert t._relationship_trace == []
