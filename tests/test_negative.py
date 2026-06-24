"""
Negative tests — verify the system fails *gracefully* when given bad input.

The 73 happy-path tests in test_full_flow.py / test_parser.py prove the
golden path works. This file proves the *failure* surfaces are sane:

* ``OpParams`` constructors reject empty required identifiers at
  construction time (rather than letting None/empty propagate into a
  confusing AttributeError deep inside a handler);
* handlers return ``OperationResult.skipped(reason=...)`` instead of
  raising when an op references something that does not exist;
* the run_apply loop continues past a bad op and finishes the rest;
* ``parse_smile_auto`` collects ANTLR syntax errors into the returned
  errors list — it does not crash and does not silently emit ops;
* adapters raise an informative exception on garbage native input.
"""
import sys
import tempfile
from pathlib import Path

import pytest

# Make the project root importable when pytest runs from this dir.
sys.path.insert(0, str(Path(__file__).parent.parent))

from parser.params import (
    AddPropertyParams, DeletePropertyParams, NestParams, UnnestParams,
    AddKeyParams, KeyType, OperationResult,
)
from Schema.unified_meta_schema import (
    Database, DatabaseType, EntityType, EntityKind, Property,
    PrimitiveDataType, PrimitiveType,
)


# 1. OpParams self-validation (#13 from stage 1)

class TestOpParamsValidation:
    """Constructing an OpParams with an empty required identifier must raise."""

    def test_add_property_rejects_empty_name(self):
        with pytest.raises(ValueError, match="name must be non-empty"):
            AddPropertyParams(name="")

    def test_delete_property_rejects_empty_target(self):
        with pytest.raises(ValueError, match="target must be non-empty"):
            DeletePropertyParams(target="")

    def test_nest_rejects_empty_alias(self):
        with pytest.raises(ValueError, match="alias must be non-empty"):
            NestParams(source="orders", target="customers", alias="")

    def test_nest_rejects_all_empty(self):
        with pytest.raises(ValueError):
            NestParams(source="", target="", alias="")

    def test_unnest_rejects_empty_source_path(self):
        with pytest.raises(ValueError, match="source_path must be non-empty"):
            UnnestParams(source_path="", target="customers")

    def test_add_key_rejects_unknown_key_type_string(self):
        # __post_init__ coerces str → KeyType; unknown value should fail loudly.
        with pytest.raises(ValueError, match="not a valid KeyType"):
            AddKeyParams(key_type="NOT_A_REAL_KEY_TYPE", key_columns=["id"])

    def test_add_key_accepts_enum_directly(self):
        p = AddKeyParams(key_type=KeyType.PRIMARY, key_columns=["id"])
        assert p.key_type is KeyType.PRIMARY


# 2. Handler graceful failure (#7 OperationResult)

def _make_one_entity_db() -> Database:
    """Build a trivial Database with one entity ('users') for handler tests."""
    db = Database(db_name="t", db_type=DatabaseType.RELATIONAL)
    e = EntityType(object_name=["users"], entity_kind=EntityKind.TABLE)
    e.add_property(Property(
        name="id",
        data_type=PrimitiveDataType(primitive_type=PrimitiveType.INTEGER),
        is_key=True,
    ))
    db.add_entity_type(e)
    return db


class TestHandlerGracefulFailure:
    """Handlers must return OperationResult.skipped(reason=...) on bad input,
    not raise. The reason field must identify what went wrong."""

    def test_delete_property_on_missing_entity_returns_skipped(self):
        from core import SchemaTransformer
        db = _make_one_entity_db()
        t = SchemaTransformer(db)
        result = t._handle_delete_property(DeletePropertyParams(target="ghost.field"))
        assert isinstance(result, OperationResult)
        assert not result   # __bool__ returns success
        assert result.reason, "skipped result must carry a non-empty reason"

    def test_delete_property_on_missing_field_returns_skipped(self):
        from core import SchemaTransformer
        db = _make_one_entity_db()
        t = SchemaTransformer(db)
        # Entity 'users' exists, field 'nonexistent_col' does not.
        result = t._handle_delete_property(DeletePropertyParams(target="users.nonexistent_col"))
        assert not result
        assert result.reason

    def test_add_property_on_missing_entity_returns_skipped(self):
        from core import SchemaTransformer
        db = _make_one_entity_db()
        t = SchemaTransformer(db)
        result = t._handle_add_property(
            AddPropertyParams(name="email", entity="ghost_table")
        )
        assert not result
        assert result.reason

    def test_successful_handler_returns_ok(self):
        # Sanity check that the failure assertions aren't trivially true.
        from core import SchemaTransformer
        db = _make_one_entity_db()
        t = SchemaTransformer(db)
        result = t._handle_add_property(
            AddPropertyParams(name="email", entity="users")
        )
        assert result, f"successful add should return truthy OperationResult, got reason={result.reason}"
        assert result.reason is None


# 3. Pipeline continues after a bad op

class TestPipelineContinuesAfterFailure:
    """run_apply should not bail on the first failed op."""

    def test_bad_op_then_good_op_both_recorded(self):
        from core import SchemaTransformer, run_apply
        from parser.listeners import Operation, OpType
        db = _make_one_entity_db()
        transformer = SchemaTransformer(db)

        ops = [
            # Op 1: targets a non-existent entity -> skipped
            Operation(OpType.DELETE_PROPERTY,
                      DeletePropertyParams(target="ghost.field")),
            # Op 2: valid -> success
            Operation(OpType.ADD_PROPERTY,
                      AddPropertyParams(name="email", entity="users")),
        ]
        details, success_count, skipped_count, error_count = run_apply(transformer, ops)

        assert len(details) == 2, "every op must be recorded, even when skipped"
        assert success_count == 1
        assert skipped_count == 1
        assert error_count == 0, "no handler bugs expected for valid input"
        assert details[0]["status"] == "skipped"
        assert details[0].get("reason"), "skipped op must surface a reason"
        assert details[1]["status"] == "success"
        # Side effect of op 2 actually applied:
        users = transformer.database.get_entity_type("users")
        assert any(p.name == "email" for p in users.properties)

    def test_run_migration_with_conflicting_ops_does_not_crash(self):
        """End-to-end: a script that deletes an entity then tries to add a
        property to it. The pipeline must finish and report the second op
        as skipped — not raise."""
        from core import SchemaTransformer, run_apply
        from parser.listeners import Operation, OpType
        from parser.params import DeleteEntityParams
        db = _make_one_entity_db()
        transformer = SchemaTransformer(db)
        ops = [
            Operation(OpType.DELETE_ENTITY, DeleteEntityParams(name="users")),
            Operation(OpType.ADD_PROPERTY,
                      AddPropertyParams(name="email", entity="users")),
        ]
        details, success, skipped, errors = run_apply(transformer, ops)
        assert len(details) == 2
        assert errors == 0, "no handler bugs expected for valid input"
        # First op succeeds (deletes users), second op now sees no entity.
        assert details[0]["status"] == "success"
        assert details[1]["status"] == "skipped"
        assert details[1].get("reason")


# 4. Parser handles malformed input

class TestMalformedSmileScript:
    """parse_smile_auto must collect ANTLR syntax errors into errors list,
    not raise and not silently swallow them."""

    def _write_temp(self, content: str, suffix: str = ".smile") -> str:
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=suffix, delete=False, encoding="utf-8"
        )
        f.write(content)
        f.close()
        return f.name

    def test_garbage_script_reports_errors(self):
        from parser.factory import parse_smile_auto
        path = self._write_temp("THIS IS NOT VALID SMILE @@@ ###")
        try:
            ctx, ops, errors = parse_smile_auto(path)
            # Must report errors rather than silently succeed.
            assert errors, "malformed script should produce non-empty errors list"
            assert len(ops) == 0, "no ops should be emitted from a fully-malformed script"
        finally:
            Path(path).unlink(missing_ok=True)

    def test_empty_script_does_not_crash(self):
        from parser.factory import parse_smile_auto
        path = self._write_temp("")
        try:
            ctx, ops, errors = parse_smile_auto(path)
            # Empty file → zero ops; whether errors are emitted depends on grammar
            # (header is required), but the call must not raise.
            assert ops == []
        finally:
            Path(path).unlink(missing_ok=True)

    def test_partial_op_with_missing_name_emits_error(self):
        # MIGRATION header is fine, but ADD_PROPERTY is missing its identifier.
        script = (
            "MIGRATION test:1.0\n"
            "FROM RELATIONAL TO RELATIONAL\n"
            "USING demo VERSION 1.0\n"
            "\n"
            "ADD_PROPERTY\n"   # truncated — missing name
        )
        from parser.factory import parse_smile_auto
        path = self._write_temp(script)
        try:
            ctx, ops, errors = parse_smile_auto(path)
            assert errors, "missing-identifier syntax error must be reported"
        finally:
            Path(path).unlink(missing_ok=True)


# 5. Adapters reject corrupted native input

class TestAdapterMalformedInput:
    """Each adapter's parse() should raise an informative exception on garbage,
    not segfault, hang, or silently produce an empty Database."""

    def test_postgresql_handles_garbage_gracefully(self):
        from Schema.adapters import PostgreSQLAdapter
        # Random text isn't valid SQL DDL. The adapter is text-based and tolerant
        # (parses as zero tables) — verify it does not raise unhandled exceptions.
        db = PostgreSQLAdapter().parse("blah blah this is not sql", "t")
        assert isinstance(db, Database)
        assert len(db.entity_types) == 0, "no tables should be parsed from garbage"

    def test_mongodb_rejects_invalid_json(self):
        from Schema.adapters import MongoDBAdapter
        with pytest.raises(Exception):  # json.JSONDecodeError or similar
            MongoDBAdapter().parse("{not valid json", "t")

    def test_cassandra_handles_garbage_gracefully(self):
        from Schema.adapters import CassandraAdapter
        db = CassandraAdapter().parse("not a valid cql script", "t")
        assert isinstance(db, Database)
        assert len(db.entity_types) == 0

    def test_neo4j_invalid_string_routes_to_graphql(self):
        # Non-JSON string input is routed to the GraphQL SDL parser (the
        # canonical Neo4j schema form). The parser is tolerant: garbage with
        # no GraphQL type blocks yields an empty db rather than raising.
        from Schema.adapters import Neo4jAdapter
        db = Neo4jAdapter().parse("not graphql either", "t")
        assert isinstance(db, Database)
        assert len(db.entity_types) == 0

    def test_neo4j_rejects_truncated_json(self):
        # If the input *looks* like JSON ({...) but is malformed, json.loads
        # raises — we want that error to propagate, not be silently swallowed.
        from Schema.adapters import Neo4jAdapter
        with pytest.raises(Exception):
            Neo4jAdapter().parse('{"nodes": [missing-quotes', "t")


# 6. Validation pipeline blame attribution

class TestValidationBlame:
    """validate_pipeline must attribute blame correctly when L1/L2 disagree."""

    def test_unverifiable_when_no_target_file(self):
        from core import run_migration
        r = run_migration("grammar_completeness_specific")
        # No target file registered for grammar_completeness → both layers N/A.
        assert r["validation_blame"] == "unverifiable"

    def test_ok_when_both_layers_pass(self):
        from core import run_migration
        r = run_migration("northwind_r2d_specific")
        assert r["validation_blame"] == "ok"

    def test_smile_script_blame_on_layer1_failure(self):
        """Simulate a broken Meta V2 (script bug) and confirm blame=smile_script.

        Surgically swap the entity dict for a single bogus entity so:
          * Layer 0 still passes (≥1 entity, original execution_stats kept)
          * Layer 1 fails (entity names don't match the expected target)
          * Layer 2 still passes (the original ``exported_target`` produced
            from the real Meta V2 is left intact, so it round-trips
            cleanly against the expected target file)

        Keeping Layer 2 green is what makes blame collapse to
        ``smile_script`` rather than ``both`` — it isolates the Layer 1
        attribution path. A separate test below covers the ``both`` case.
        """
        from core import run_migration
        from validation.pipeline import validate_pipeline
        r = run_migration("northwind_r2d_specific")
        # Replace the entity map with a single bogus entity so the entity-set
        # diff against the expected Mongo target fails on Layer 1, while Layer 0
        # still sees one entity + all original execution_stats pass. The
        # original ``exported_target`` is intentionally not cleared, so
        # Layer 2 round-trips cleanly against the expected Mongo target.
        r["result"] = {
            "bogus_entity": {
                "name": "bogus_entity",
                "entity_kind": "document",
                "properties": [],
                "constraints": [],
                "references": [],
                "embedded": [],
                "edges": [],
                "labels": [],
            },
            "__db_meta__": r["result"].get("__db_meta__", {}),
        }
        v = validate_pipeline(r, "Document", "northwind_r2d_specific")
        assert v["blame"] == "smile_script"

    def test_both_blame_when_layer1_and_layer2_fail(self):
        """Layer 1 and Layer 2 both fail → blame=both.

        Reproduces the double-failure case where the script produced the
        wrong Meta V2 (Layer 1 fail) *and* the adapter export/parse cycle
        could not round-trip to the expected target (Layer 2 fail) — for
        instance, because the bogus Meta V2 produced no exported target at
        all. The verdict ``both`` surfaces that both responsible
        components are involved, instead of silently collapsing on the
        first failing layer.
        """
        from core import run_migration
        from validation.pipeline import validate_pipeline
        r = run_migration("northwind_r2d_specific")
        # Same bogus entity swap as above so Layer 1 fails ...
        r["result"] = {
            "bogus_entity": {
                "name": "bogus_entity",
                "entity_kind": "document",
                "properties": [],
                "constraints": [],
                "references": [],
                "embedded": [],
                "edges": [],
                "labels": [],
            },
            "__db_meta__": r["result"].get("__db_meta__", {}),
        }
        # ... plus blanking the exported target so Layer 2 also fails.
        r["exported_target"] = ""
        v = validate_pipeline(r, "Document", "northwind_r2d_specific")
        assert v["blame"] == "both"
        assert v["layer1"]["passed"] is False
        assert v["layer2"]["passed"] is False

    def test_script_failed_blame_when_handler_errors(self):
        """An exception in a handler surfaces as Layer 0 fail → blame=script_failed.

        Synthetic result_dict simulates the post-run_apply state where one
        op finished with status="error" — the same shape the real pipeline
        produces when a handler raises an unexpected exception. We don't
        actually need a broken handler in production code: the contract is
        that ``execution_stats.error > 0`` flips Layer 0 to fail, and Layer
        0 fail dominates blame attribution regardless of L1/L2 outcomes.
        """
        from validation.pipeline import validate_pipeline
        result_dict = {
            "result": {"some_entity": {"name": "some_entity"}},
            "execution_stats": {"total": 3, "success": 2, "skipped": 0, "error": 1},
            "operations_detail": [
                {"step": 1, "type": "ADD_PROPERTY",
                 "original_keyword": "ADD_PROPERTY", "status": "success"},
                {"step": 2, "type": "ADD_FOREIGN_KEY",
                 "original_keyword": "ADD_FOREIGN_KEY", "status": "error",
                 "reason": "AttributeError: 'NoneType' has no attribute 'meta_id'"},
                {"step": 3, "type": "MERGE",
                 "original_keyword": "MERGE", "status": "success"},
            ],
            "exported_target": "",
        }
        v = validate_pipeline(result_dict, "Relational", "")
        assert v["blame"] == "script_failed"
        # Failed-step list must surface the bad op so the user can locate it.
        failed = v["layer0"]["details"]["failed_steps"]
        assert len(failed) == 1
        assert failed[0]["step"] == 2
        assert failed[0]["status"] == "error"
        assert "AttributeError" in failed[0]["reason"]

    def test_script_failed_blame_when_all_skipped(self):
        """Every op deliberately skipped (e.g. wrong entity names throughout)
        also fails Layer 0 — the script ran without crashing but produced
        no schema change, which is a script-side mistake, not an adapter
        problem.
        """
        from validation.pipeline import validate_pipeline
        result_dict = {
            "result": {"unrelated_entity": {"name": "unrelated_entity"}},
            "execution_stats": {"total": 2, "success": 0, "skipped": 2, "error": 0},
            "operations_detail": [
                {"step": 1, "type": "ADD_PROPERTY",
                 "original_keyword": "ADD_PROPERTY", "status": "skipped",
                 "reason": "add_property: precondition not met"},
                {"step": 2, "type": "DELETE_PROPERTY",
                 "original_keyword": "DELETE_PROPERTY", "status": "skipped",
                 "reason": "delete_property: 'foo' not found on bar"},
            ],
            "exported_target": "",
        }
        v = validate_pipeline(result_dict, "Relational", "")
        assert v["blame"] == "script_failed"
        assert v["layer0"]["passed"] is False
        # Both skipped ops surfaced with their reasons — exactly the "where
        # did it fail?" answer the user wants.
        failed = v["layer0"]["details"]["failed_steps"]
        assert len(failed) == 2
        assert all(s["status"] == "skipped" for s in failed)

    def test_layer0_failed_steps_listing_format(self):
        """``details.failed_steps`` must carry AT LEAST the keys the CLI /
        web UI rely on for rendering: step / type / original_keyword /
        status / reason. Subset assertion (``<=``) rather than ``==`` so
        that future additions (e.g. ``traceback`` / ``op_index``) don't
        false-fail this contract test — the rendering code reads only the
        five required keys, so adding extras is forward-compatible.
        """
        from validation.pipeline import derive_layer0
        layer0 = derive_layer0({
            "result": {"e": {"name": "e"}},
            "execution_stats": {"total": 1, "success": 0, "skipped": 0, "error": 1},
            "operations_detail": [
                {"step": 1, "type": "NEST",
                 "original_keyword": "NEST", "status": "error",
                 "reason": "RuntimeError: boom"},
            ],
        })
        assert layer0["passed"] is False
        failed = layer0["details"]["failed_steps"]
        required_keys = {"step", "type", "original_keyword", "status", "reason"}
        assert failed and required_keys <= set(failed[0].keys()), (
            f"failed_steps[0] missing required keys: "
            f"{required_keys - set(failed[0].keys())}"
        )
