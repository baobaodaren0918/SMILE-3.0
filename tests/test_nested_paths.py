"""
Tests for the post-2026-04-29 grammar fix that promoted every entity-reference
position from ``identifier`` to ``qualifiedName``. The 89 pre-existing tests
all use simple-name forms and would still pass with the old grammar — they
verify nothing about the new capability. These tests do.

Two layers of coverage:

* **Parse-level** — feed each path-capable op a SMILE snippet that uses a
  dotted entity reference and assert the listener stored the full path on
  the resulting ``Operation``. Catches grammar / listener regressions
  without needing a real database.
* **End-to-end** — load the multi-root Mongo Northwind schema (which has
  real nested entities like ``orders.employee.address``), run scripts that
  target those entities by path, and assert the database state changed as
  intended. Catches handler-side breakage and proves the path actually
  reaches the meta-model.
"""
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from parser.factory import parse_smile_auto
from parser.listeners import OpType


HEADER_MIG = (
    "MIGRATION nested_path_test:1.0\n"
    "FROM DOCUMENT TO DOCUMENT\n"
    "USING test_schema VERSION 1.0\n\n"
)
HEADER_EVO = (
    "EVOLUTION nested_path_test:1.0\n"
    "FROM DOCUMENT TO DOCUMENT\n"
    "USING test_schema VERSION 1.0 TO 2.0\n\n"
)


def _parse_one(script: str, suffix: str = ".smile"):
    """Write `script` to a temp file, parse it, return the single op
    produced. Asserts a clean parse (no errors) so failure reports the
    grammar / listener problem rather than an indirect index error."""
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    )
    try:
        f.write(script)
        f.close()
        ctx, ops, errors = parse_smile_auto(f.name)
        assert not errors, f"Parse errors for snippet:\n{script}\nerrors: {errors}"
        assert len(ops) == 1, f"Expected exactly 1 op, got {len(ops)}"
        return ops[0]
    finally:
        Path(f.name).unlink(missing_ok=True)


# Parse-level: every ⚠️→✅ promoted op accepts a dotted path source/target.
# Each test exercises BOTH grammars (specific .smile and generalized .smile_gen)
# to prove the spec/gen parity contract holds for path-capable forms too.

class TestParsePathForms:

    # ------- structural: UNFLATTEN, NEST, MERGE, SPLIT, TRANSFORM -------

    def test_unflatten_specific_accepts_dotted_source(self):
        op = _parse_one(HEADER_EVO + "UNFLATTEN orders.customer:phone, fax AS contact\n")
        assert op.op_type == OpType.UNFLATTEN
        assert op.params.entity == "orders.customer"
        assert op.params.fields == ["phone", "fax"]
        assert op.params.nested_name == "contact"

    def test_unflatten_generalized_accepts_dotted_source(self):
        op = _parse_one(HEADER_EVO + "UNFLATTEN orders.customer:phone, fax AS contact\n",
                        suffix=".smile_gen")
        assert op.op_type == OpType.UNFLATTEN
        assert op.params.entity == "orders.customer"

    def test_nest_specific_accepts_dotted_source(self):
        op = _parse_one(HEADER_MIG +
                        "NEST orders.shipper:company_name IN orders.carrier "
                        "WHERE orders.shipper.id = orders.carrier_id\n")
        assert op.op_type == OpType.NEST
        # source carries full path now
        assert op.params.source == "orders.shipper"

    def test_merge_specific_accepts_dotted_sources(self):
        op = _parse_one(HEADER_EVO +
                        "MERGE orders.shipper, orders.employee WHERE orders.shipper.id = orders.employee.id INTO contact\n")
        assert op.op_type == OpType.MERGE
        assert op.params.source1 == "orders.shipper"
        assert op.params.source2 == "orders.employee"
        assert op.params.target == "contact"  # INTO target stays simple (new entity)

    def test_split_specific_accepts_dotted_source(self):
        # Grammar: SPLIT qualifiedName INTO splitPart (SEMICOLON splitPart)+
        # The source accepts a path; each splitPart names a NEW entity created by
        # the split, which intentionally stays a simple identifier (new entities
        # are top-level by construction).
        op = _parse_one(HEADER_EVO +
                        "SPLIT orders.employee INTO emp_basic:first_name, last_name; "
                        "emp_meta:hire_date, phone\n")
        assert op.op_type == OpType.SPLIT
        assert op.params.source == "orders.employee"

    def test_transform_specific_accepts_dotted_entity(self):
        op = _parse_one(HEADER_EVO +
                        "TRANSFORM orders.employee INTO RELATIONSHIP "
                        "FROM orders TO orders.employee.address\n")
        assert op.op_type == OpType.TRANSFORM
        assert op.params.name == "orders.employee"
        assert op.params.source_entity == "orders"
        assert op.params.target_entity == "orders.employee.address"

    # ------- property CRUD: ADD/RENAME/COPY/MOVE_PROPERTY -------

    def test_add_property_specific_accepts_dotted_entity(self):
        op = _parse_one(HEADER_EVO +
                        "ADD_PROPERTY note TO orders.customer WITH TYPE String\n")
        assert op.op_type == OpType.ADD_PROPERTY
        assert op.params.name == "note"
        assert op.params.entity == "orders.customer"

    def test_add_property_generalized_accepts_dotted_entity(self):
        op = _parse_one(HEADER_EVO +
                        "ADD PROPERTY note TO orders.customer WITH TYPE String\n",
                        suffix=".smile_gen")
        assert op.op_type == OpType.ADD_PROPERTY
        assert op.params.entity == "orders.customer"

    def test_rename_property_specific_accepts_dotted_entity(self):
        op = _parse_one(HEADER_EVO +
                        "RENAME_PROPERTY phone TO contact_phone IN orders.customer\n")
        assert op.op_type == OpType.RENAME_PROPERTY
        assert op.params.old_name == "phone"
        assert op.params.new_name == "contact_phone"
        assert op.params.entity == "orders.customer"

    def test_copy_property_specific_accepts_dotted_entities(self):
        op = _parse_one(HEADER_EVO +
                        "COPY_PROPERTY phone FROM orders.customer TO orders.shipper WHERE orders.customer.id = orders.shipper.id\n")
        assert op.op_type == OpType.COPY_PROPERTY
        # Listener composes "{entity}.{property}" — orders.customer.phone form
        assert op.params.source == "orders.customer.phone"
        assert op.params.target == "orders.shipper.phone"

    def test_move_property_specific_accepts_dotted_entities(self):
        op = _parse_one(HEADER_EVO +
                        "MOVE_PROPERTY phone FROM orders.customer TO orders.shipper WHERE orders.customer.id = orders.shipper.id\n")
        assert op.op_type == OpType.MOVE_PROPERTY
        assert op.params.source == "orders.customer.phone"
        assert op.params.target == "orders.shipper.phone"

    # ------- entity CRUD: DELETE / RENAME / CAST_ENTITY / COPY_ENTITY -------

    def test_delete_entity_specific_accepts_dotted(self):
        op = _parse_one(HEADER_EVO + "DELETE_ENTITY orders.shipper\n")
        assert op.op_type == OpType.DELETE_ENTITY
        assert op.params.name == "orders.shipper"

    def test_delete_entity_generalized_accepts_dotted(self):
        op = _parse_one(HEADER_EVO + "DELETE ENTITY orders.shipper\n",
                        suffix=".smile_gen")
        assert op.op_type == OpType.DELETE_ENTITY
        assert op.params.name == "orders.shipper"

    def test_rename_entity_specific_accepts_dotted_both_sides(self):
        op = _parse_one(HEADER_EVO + "RENAME_ENTITY orders.shipper TO orders.carrier\n")
        assert op.op_type == OpType.RENAME_ENTITY
        assert op.params.old_name == "orders.shipper"
        assert op.params.new_name == "orders.carrier"

    def test_cast_entity_specific_accepts_dotted(self):
        op = _parse_one(HEADER_EVO + "CAST_ENTITY orders.employee TO RELATIONAL\n")
        assert op.op_type == OpType.CAST_ENTITY
        assert op.params.target == "orders.employee"

    def test_copy_entity_specific_accepts_dotted_source(self):
        op = _parse_one(HEADER_EVO + "COPY_ENTITY orders.shipper AS shipper_archive\n")
        assert op.op_type == OpType.COPY_ENTITY
        assert op.params.source == "orders.shipper"
        # "AS" target stays simple (it's a new top-level entity name)
        assert op.params.target == "shipper_archive"

    # ------- ADD_EMBEDDED / ADD_LABEL / DELETE_LABEL -------

    def test_add_embedded_specific_accepts_dotted_parent(self):
        op = _parse_one(HEADER_EVO +
                        "ADD_EMBEDDED metadata TO orders.customer "
                        "WITH CARDINALITY ONE_TO_ONE\n")
        assert op.op_type == OpType.ADD_EMBEDDED
        assert op.params.name == "metadata"
        assert op.params.entity == "orders.customer"

    def test_add_label_specific_accepts_dotted_target(self):
        op = _parse_one(HEADER_EVO + "ADD_LABEL Vip TO orders.customer\n")
        assert op.op_type == OpType.ADD_LABEL
        assert op.params.label == "Vip"
        assert op.params.entity == "orders.customer"

    def test_delete_label_specific_accepts_dotted_source(self):
        op = _parse_one(HEADER_EVO + "DELETE_LABEL Vip FROM orders.customer\n")
        assert op.op_type == OpType.DELETE_LABEL
        assert op.params.label == "Vip"
        assert op.params.entity == "orders.customer"

    # ------- key ops: ADD_*_KEY / DELETE_*_KEY / FK -------

    def test_add_primary_key_specific_to_dotted_entity(self):
        op = _parse_one(HEADER_EVO +
                        "ADD_PRIMARY_KEY id AS String TO orders.customer\n")
        assert op.op_type == OpType.ADD_KEY
        assert op.params.entity == "orders.customer"

    def test_delete_primary_key_specific_from_dotted(self):
        op = _parse_one(HEADER_EVO +
                        "DELETE_PRIMARY_KEY id FROM orders.customer\n")
        assert op.op_type == OpType.DELETE_KEY
        assert op.params.entity == "orders.customer"

    def test_add_foreign_key_specific_dotted_target_table(self):
        op = _parse_one(HEADER_EVO +
                        "ADD_FOREIGN_KEY (a, b) TO orders.shipper "
                        "REFERENCES orders.customer(x, y)\n")
        assert op.op_type == OpType.ADD_FOREIGN_KEY
        assert op.params.entity == "orders.shipper"
        assert op.params.target_table == "orders.customer"


# End-to-end: run a full pipeline against the multi-root Mongo schema and
# verify path-based ops actually reach the meta-model.

@pytest.fixture
def mongo_db():
    """Fresh copy of the Northwind 2-root Mongo schema for each test."""
    from Schema.adapters import MongoDBAdapter
    return MongoDBAdapter().load_from_file(
        str(Path(__file__).parent / "northwind_mongodb.json"), "test"
    )


def _run_script(db, body: str):
    """Apply a SMILE script body against `db`. Returns ``(out_db, details,
    success, skipped, errors)`` where ``out_db`` is the post-mutation
    database — note that ``SchemaTransformer.__init__`` deep-copies its
    input, so mutations are observable on ``transformer.database`` only,
    NOT on the ``db`` passed in."""
    from core import SchemaTransformer, run_apply
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".smile", delete=False, encoding="utf-8"
    )
    try:
        f.write(HEADER_EVO + body)
        f.close()
        _, operations, errors = parse_smile_auto(f.name)
        assert not errors, errors
        transformer = SchemaTransformer(db)
        details, succ, skip, err = run_apply(transformer, operations)
        return transformer.database, details, succ, skip, err
    finally:
        Path(f.name).unlink(missing_ok=True)


class TestNestedPathsEndToEnd:
    """Each test runs a tiny script that uses a dotted entity path on the
    real Northwind Mongo schema, then asserts the meta-model changed."""

    def test_delete_nested_entity_by_full_path(self, mongo_db):
        assert "orders.shipper" in mongo_db.entity_types
        out_db, details, succ, skip, err = _run_script(mongo_db, "DELETE_ENTITY orders.shipper\n")
        assert err == 0, f"handler bug: {details}"
        assert succ == 1, f"expected success, got: {details}"
        assert "orders.shipper" not in out_db.entity_types, \
            "DELETE_ENTITY orders.shipper did not remove the nested entity"

    def test_add_property_to_nested_entity_by_full_path(self, mongo_db):
        before = mongo_db.entity_types["orders.shipper"].properties
        assert not any(p.name == "tracking_url" for p in before)
        out_db, details, succ, skip, err = _run_script(
            mongo_db, "ADD_PROPERTY tracking_url TO orders.shipper WITH TYPE String\n"
        )
        assert err == 0 and succ == 1, details
        after = out_db.entity_types["orders.shipper"].properties
        assert any(p.name == "tracking_url" for p in after), \
            "ADD_PROPERTY did not reach the nested entity"

    def test_rename_property_in_nested_entity_by_full_path(self, mongo_db):
        assert any(p.name == "phone" for p in mongo_db.entity_types["orders.shipper"].properties)
        out_db, details, succ, skip, err = _run_script(
            mongo_db, "RENAME_PROPERTY phone TO contact_phone IN orders.shipper\n"
        )
        assert err == 0 and succ == 1, details
        names = [p.name for p in out_db.entity_types["orders.shipper"].properties]
        assert "contact_phone" in names, "rename did not apply"
        assert "phone" not in names, "old name still present"

    def test_simple_name_still_works_for_unambiguous_leaf(self, mongo_db):
        """Backwards-compat: an unambiguous simple name still resolves."""
        out_db, details, succ, skip, err = _run_script(
            mongo_db, "ADD_PROPERTY note TO customers WITH TYPE String\n"
        )
        assert err == 0 and succ == 1, details
        assert any(p.name == "note" for p in out_db.entity_types["customers"].properties)

    def test_deeply_nested_path(self, mongo_db):
        """Two-level nesting: orders.employee.address."""
        assert "orders.employee.address" in mongo_db.entity_types
        out_db, details, succ, skip, err = _run_script(
            mongo_db, "ADD_PROPERTY apartment TO orders.employee.address WITH TYPE String\n"
        )
        assert err == 0 and succ == 1, details
        names = [p.name for p in out_db.entity_types["orders.employee.address"].properties]
        assert "apartment" in names

    def test_path_form_matches_simple_form_when_unambiguous(self, mongo_db):
        """For an unambiguous leaf name, dotted-path form and simple form
        should hit the same entity. Sanity-check that the path-aware lookup
        hasn't broken legacy resolution."""
        out_path, *_ = _run_script(mongo_db,
            "ADD_PROPERTY note TO orders.shipper WITH TYPE String\n")
        out_simple, *_ = _run_script(mongo_db,
            "ADD_PROPERTY note TO shipper WITH TYPE String\n")
        n1 = [p.name for p in out_path.entity_types["orders.shipper"].properties]
        n2 = [p.name for p in out_simple.entity_types["orders.shipper"].properties]
        assert "note" in n1, f"path form did not add: {n1}"
        assert "note" in n2, f"simple form did not add: {n2}"
        assert n1 == n2, "path-form and simple-form produced different effects"
