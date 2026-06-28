"""Pipeline orchestration — the four-step flow that turns a source schema into a target one."""
import copy
import logging
import dataclasses
from typing import Any, Dict

from Schema.unified_meta_schema import DatabaseType
from Schema.adapters import ADAPTER_REGISTRY
from config import (
    MIGRATION_CONFIGS,
    SOURCE_TYPE_RELATIONAL, SOURCE_TYPE_DOCUMENT,
    SOURCE_TYPE_GRAPH, SOURCE_TYPE_COLUMNAR,
)

from core.transformer import SchemaTransformerBase
from core.handlers.structural import StructuralHandlersMixin
from core.handlers.crud import CRUDHandlersMixin
from core.handlers.keys_constraints import KeysConstraintsHandlersMixin
from core.handlers.reshape import ReshapeHandlersMixin
from core.serialization import (
    db_to_dict, db_to_source_dict, parse_original_source,
)
from core.normalization import (
    _calculate_changes,
    normalize_entity_kinds,
    normalize_document_cardinality,
    normalize_document_full_paths,
    normalize_property_psm,
)

logger = logging.getLogger(__name__)


# SMILE syntax highlighting data for web_server.py frontend.
# Derived at import time from grammar/smile_operations.json (the canonical
# operations catalogue used by autocomplete) plus a small static set of
# header / structural / clause keywords that do not have operation entries.
# This eliminates the previous drift risk where a hand-maintained list here
# could diverge from operations.json (CAST_ENTITY was previously missing).
def _build_smile_syntax():
    """Compose SMILE_SYNTAX["keywords"] from operations.json + static keywords."""
    import json
    from pathlib import Path

    # Header / structural / clause keywords not represented as ops in the JSON
    static_keywords = {
        # Header keywords
        'MIGRATION', 'EVOLUTION', 'FROM', 'TO', 'USING', 'VERSION',
        'AS', 'INTO', 'WITH', 'WHERE', 'IN', 'KEY', 'AND', 'ON',
        # Type parameters that appear standalone in clauses
        'PROPERTY', 'ATTRIBUTE', 'ATTRIBUTES', 'CONSTRAINT', 'EMBEDDED',
        'ENTITY', 'LABEL', 'RELATIONSHIP',
        # Key kind modifiers (used in CAST_CONSTRAINT, key clauses)
        'PRIMARY', 'UNIQUE', 'FOREIGN', 'PARTITION', 'CLUSTERING',
        'REFERENCE', 'REFERENCES', 'COLUMNS', 'STRUCTURE',
        'NODE', 'DOCUMENT_ID',
        # CARDINALITY clause + values
        'CARDINALITY', 'ONE_TO_ONE', 'ONE_TO_MANY',
        'ZERO_TO_ONE', 'ZERO_TO_MANY',
        # CRUD/structural verb tokens (generalized grammar uses these
        # standalone; the compound forms come from operations.json below)
        'ADD', 'DELETE', 'REMOVE', 'RENAME', 'COPY', 'MOVE',
        'MERGE', 'SPLIT', 'CAST', 'RECARD', 'TRANSFORM',
        'NEST', 'UNNEST', 'FLATTEN', 'UNFLATTEN', 'UNWIND', 'WIND',
        # ADD_CONSTRAINT body keywords (REFERENCE/CHECK/EXISTENCE branches)
        'LOGICAL', 'EXISTENCE', 'CHECK', 'MATCHES', 'RAW',
        'NOT', 'OR', 'IS',
    }

    keywords = set(static_keywords)
    types: list = []

    json_path = Path(__file__).resolve().parent.parent / "grammar" / "smile_operations.json"
    try:
        with json_path.open(encoding="utf-8") as f:
            spec = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(
            "Failed to load %s for SMILE_SYNTAX derivation: %s. "
            "Falling back to static keyword set only.", json_path, e)
        return {"keywords": sorted(keywords), "types": []}

    # Every operation's specific keyword (e.g. ADD_PROPERTY) and the tokens of
    # its generalized form (e.g. ADD PROPERTY → ADD, PROPERTY) join the set.
    for op_meta in spec.get("operations", {}).values():
        spec_kw = op_meta.get("specific")
        if spec_kw:
            keywords.add(spec_kw)
        gen_kw = op_meta.get("generalized")
        if gen_kw:
            for tok in gen_kw.split():
                keywords.add(tok)

    # Enums: databaseType + cardinalityType go into keywords;
    # dataType becomes the types list.
    for v in spec.get("enums", {}).get("databaseType", []):
        keywords.add(v)
    for v in spec.get("enums", {}).get("cardinalityType", []):
        keywords.add(v)
    types = list(spec.get("enums", {}).get("dataType", []))

    return {"keywords": sorted(keywords), "types": types}


SMILE_SYNTAX = _build_smile_syntax()


# Module-level constant: maps SOURCE_TYPE string -> DatabaseType enum.
# Used by run_export to set the result Database's db_type before passing
# it to the target adapter.
_DB_TYPE_MAP = {
    SOURCE_TYPE_RELATIONAL: DatabaseType.RELATIONAL,
    SOURCE_TYPE_DOCUMENT: DatabaseType.DOCUMENT,
    SOURCE_TYPE_GRAPH: DatabaseType.GRAPH,
    SOURCE_TYPE_COLUMNAR: DatabaseType.COLUMNAR,
}


class SchemaTransformer(
    StructuralHandlersMixin,
    CRUDHandlersMixin,
    KeysConstraintsHandlersMixin,
    ReshapeHandlersMixin,
    SchemaTransformerBase,
):
    """Transform a schema based on parsed SMILE operations."""
    pass



def run_load(source_file, smile_file, source_type: str):
    """Step 1 — Resolve adapters, read source schema + SMILE script, parse the"""
    from parser.factory import detect_grammar_type, parse_smile_text

    source_adapter = ADAPTER_REGISTRY.get(source_type)
    if not source_adapter:
        raise ValueError(f"No adapter for source type: {source_type}. Available: {list(ADAPTER_REGISTRY.keys())}")

    raw_source = source_file.read_text(encoding='utf-8') if hasattr(source_file, 'read_text') else open(source_file, encoding='utf-8').read()
    smile_content = smile_file.read_text(encoding='utf-8') if hasattr(smile_file, 'read_text') else open(smile_file, encoding='utf-8').read()

    # Source DDL → Meta V1 (Database)
    source_db = source_adapter.load_from_file(str(source_file), "source")
    meta_v1_db = copy.deepcopy(source_db)

    # Parse the already-read SMILE text (grammar picked by extension) instead of
    # re-reading the file inside parse_smile_auto.
    context, operations, errors = parse_smile_text(
        smile_content, detect_grammar_type(str(smile_file)))
    return source_adapter, source_db, meta_v1_db, smile_content, raw_source, operations, errors


def run_apply(transformer: 'SchemaTransformer', operations) -> tuple:
    """Step 2 — Apply parsed operations to a transformer's database, tracking"""
    operations_detail = []
    success_count = 0
    skipped_count = 0
    error_count = 0

    # One snapshot before the first op; reuse the "after" of step N as the "before"
    # of step N+1 so we only serialize the database once per op (not twice).
    prev_snapshot = db_to_dict(transformer.database)

    for i, op in enumerate(operations):
        prev_count = len(transformer.database.entity_types)
        transformer._touched = []           # reset per-op hint

        handler = transformer._handlers.get(op.op_type)
        reason = None
        if handler:
            try:
                result = handler(op.params)
                if result:
                    status = "success"
                    success_count += 1
                else:
                    status = "skipped"
                    skipped_count += 1
                    reason = result.reason if hasattr(result, "reason") else None
            except Exception as e:
                # Bugs in handlers should never be conflated with deliberate
                # skips. logger.exception() includes the full traceback so the
                # underlying defect is visible without re-running. The op is
                # recorded as status="error" and counted separately so that
                # CI / callers can fail loud rather than swallow real bugs.
                logger.exception(
                    "Step %d: Operation %s raised %s — handler bug",
                    i + 1, op.op_type.name, type(e).__name__,
                )
                status = "error"
                reason = f"{type(e).__name__}: {e}"
                error_count += 1
        else:
            logger.info(f"Unknown operation type: {op.op_type.name}")
            status = "skipped"
            reason = f"unknown op_type: {op.op_type.name}"
            skipped_count += 1

        new_count = len(transformer.database.entity_types)
        if status == "skipped":
            # CONTRACT: a handler that returns a falsy/skipped result MUST NOT
            # have mutated transformer.database. We reuse prev_snapshot here to
            # avoid a redundant db_to_dict serialization, which is only correct
            # under that invariant. If a future handler mutates and then skips,
            # this snapshot — and every subsequent op's diff — goes stale. Any
            # handler with a precondition must validate BEFORE mutating (see
            # ADD_KEY's validate-then-apply ordering for the canonical example).
            after_snapshot = prev_snapshot
        else:
            after_snapshot = db_to_dict(transformer.database)
        # Pass the hint when the handler reported what it touched; else None
        # (full-DB diff, legacy behavior).
        hint = list(transformer._touched) if transformer._touched else None
        changes_detail = _calculate_changes(prev_snapshot, after_snapshot, op, hint)

        detail = {
            "step": i + 1,
            "type": op.op_type.name,
            "original_keyword": op.original_keyword if op.original_keyword else op.op_type.name,
            "params": dataclasses.asdict(op.params),
            "entity_count_before": prev_count,
            "entity_count_after": new_count,
            "changes": changes_detail,
            "status": status,
        }
        if reason:
            detail["reason"] = reason
        operations_detail.append(detail)
        # roll forward — current "after" becomes next "before"
        prev_snapshot = after_snapshot

    transformer._touched = None
    return operations_detail, success_count, skipped_count, error_count


def run_export(transformer: 'SchemaTransformer', source_type: str, target_type: str) -> tuple:
    """Step 3 — Set target db_type, normalize entity_kind, and export Meta V2"""
    target_adapter = ADAPTER_REGISTRY.get(target_type)
    if not target_adapter:
        raise ValueError(f"No adapter for target type: {target_type}. Available: {list(ADAPTER_REGISTRY.keys())}")

    result_db = transformer.database
    if target_type not in _DB_TYPE_MAP:
        raise ValueError(f"Unknown target_type: {target_type}")
    result_db.db_type = _DB_TYPE_MAP[target_type]

    # Skip-list now lives on each EntityType.kind_locked (set by CAST_ENTITY).
    # Two passes with a single responsibility each — the previous combined
    # function silently mixed entity-kind translation with Document-specific
    # cardinality promotion, which made the call site read ambiguously.
    normalize_entity_kinds(result_db, target_type)
    normalize_document_cardinality(result_db, source_type)
    normalize_property_psm(result_db, source_type, target_type)
    # Document-specific: promote any simple-name embedded entities (left
    # behind by NEST / UNFLATTEN when source-side embedded chains were
    # carried forward) to canonical ``parent.child`` full paths. This is
    # the structural counterpart of the Mongo adapter's parse-time
    # ``parent_path=object_name`` recursion and closes the round-trip
    # cycle ``Mongo -> X -> Mongo'`` that previously diverged on entity
    # full_path naming.
    if target_type == SOURCE_TYPE_DOCUMENT:
        normalize_document_full_paths(result_db)
    exported_target = target_adapter.export(result_db)
    return result_db, exported_target, target_adapter


def _early_exit(reason: str) -> Dict[str, Any]:
    """Build an early-exit response that still carries the full set of
    ``validation_*`` keys. All layers are reported as ``unverifiable`` so
    callers (web UI, CLI, tests) can read the validation payload without
    branching on whether the pipeline reached the validation stage."""
    skipped = {"passed": None, "summary": f"Other reasons ({reason})",
               "details": {}}
    return {
        "error": reason,
        "validation_layer0": skipped,
        "validation_meta": skipped,
        "validation_export": skipped,
        "validation_text_diff": skipped,
        "validation_blame": "unverifiable",
        "validation_summary": reason,
    }


def run_migration(direction: str) -> Dict[str, Any]:
    """Run a complete migration and return results."""
    if direction not in MIGRATION_CONFIGS:
        return _early_exit(f"Unknown direction: {direction}. "
                           f"Available: {list(MIGRATION_CONFIGS.keys())}")

    config = MIGRATION_CONFIGS[direction]
    source_file = config.source_file
    smile_file = config.smile_file
    source_type = config.source_type
    target_type = config.target_type

    for f in [source_file, smile_file]:
        if not f.exists():
            return _early_exit(f"File not found: {f}")

    try:
        (source_adapter, source_db, meta_v1_db, smile_content, raw_source,
         operations, errors) = run_load(source_file, smile_file, source_type)
    except ValueError as e:
        return _early_exit(str(e))
    if errors:
        return _early_exit(f"SMILE parse errors: {errors}")

    transformer = SchemaTransformer(source_db, target_type=target_type)
    operations_detail, success_count, skipped_count, error_count = run_apply(transformer, operations)

    try:
        result_db, exported_target, _ = run_export(transformer, source_type, target_type)
    except ValueError as e:
        return _early_exit(str(e))

    result_dict = {
        "source_type": source_type,
        "target_type": target_type,
        "raw_source": raw_source,
        "exported_target": exported_target,
        "smile_content": smile_content,
        "smile_file": smile_file.name,
        "operations_detail": operations_detail,
        "original_source": parse_original_source(raw_source, source_type),
        "target_nested": parse_original_source(exported_target, target_type),
        "source": db_to_source_dict(meta_v1_db, source_type),
        "meta_v1": db_to_dict(meta_v1_db),
        "result": db_to_dict(result_db),
        "target_with_db_types": db_to_source_dict(result_db, target_type),
        "changes": transformer.changes,
        "key_registry": transformer.source_key_snapshot,
        "operations_count": len(operations),
        "stats": {
            "source_count": len(meta_v1_db.entity_types),
            "result_count": len(result_db.entity_types)
        },
        "execution_stats": {
            "total": len(operations),
            "success": success_count,
            "skipped": skipped_count,
            "error": error_count,
        },
        "smile_syntax": SMILE_SYNTAX,
        # Live Database object for integrity check (Layer-0.5). Not serialised
        # into JSON responses by db_to_dict — consumed only by validate_pipeline.
        "__result_db": result_db,
    }

    # Unified validation: Layer Preparation I (script execution) + Layer
    # Preparation II (metamodel integrity) + Layer 1/2/3 (meta-compare,
    # round-trip, text-fidelity) + blame attribution.
    # Top-level keys validation_layer0 / validation_meta / validation_export
    # are kept for backwards compatibility with existing front-end code that
    # reads them by their pre-rename names; the conceptual mapping is
    # documented in validation/pipeline.py.
    try:
        from validation.pipeline import validate_pipeline
        v = validate_pipeline(result_dict, target_type, direction)
        result_dict["validation_layer0"] = v["layer0"]
        result_dict["validation_meta"] = v["layer1"]
        result_dict["validation_export"] = v["layer2"]
        result_dict["validation_text_diff"] = v["layer3"]
        result_dict["validation_integrity"] = v["integrity"]
        result_dict["validation_blame"] = v["blame"]
        result_dict["validation_summary"] = v["summary"]
    except Exception as e:
        err = {"passed": None, "summary": f"Error: {e}", "details": {}}
        # Integrity uses ``violations`` rather than ``details`` so the field
        # shape matches the success path; consumers can rely on .violations.
        err_integrity = {"passed": None, "summary": f"Error: {e}", "violations": []}
        result_dict["validation_layer0"] = err
        result_dict["validation_meta"] = err
        result_dict["validation_export"] = err
        result_dict["validation_text_diff"] = err
        result_dict["validation_integrity"] = err_integrity
        result_dict["validation_blame"] = "unverifiable"
        result_dict["validation_summary"] = f"validation crashed: {e}"
    finally:
        # Don't leak the live Database object to JSON responses.
        result_dict.pop("__result_db", None)

    return result_dict
