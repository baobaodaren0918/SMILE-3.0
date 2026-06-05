"""
SMILE Full Flow Verification - Two-Layer Validation

Tests all 34 migration configurations (8 Same-Model + 24 Cross-Model Northwind
+ 2 grammar-completeness) with a unified validation framework.

Pipeline:
  Source Schema -> [RE] -> Meta V1 -> [SMILE] -> Meta V2 -> [FE] -> Target Schema

Validation Layers:
  Layer 0: Execution check (no errors, no skipped ops)
  Layer 1: Meta V2 vs Expected Meta (SMILE script correctness)
  Layer 2: Exported Target -> RE -> Round-trip Meta vs Expected Meta (Adapter correctness)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core import run_migration
from config import MIGRATION_CONFIGS


# Notice classification: helps distinguish DB-technical limitations from bugs
NOTICE_REASONS = {
    "cardinality": "Adapter representation difference (e.g. 1..1 vs 0..N default)",
    "entity_kind": "Target type normalization (e.g. table vs document vs vertex)",
    "key_type":    "PK type representation (e.g. SERIAL vs string in different DBs)",
    "optional":    "Nullability difference across DB types (e.g. MongoDB optional vs Cassandra NOT NULL)",
    "fk":          "FK constraint detail (adapter-level representation difference)",
}


def _print_validation_warnings(validation_result: dict):
    """Print detailed warnings from a validation result."""
    details = validation_result.get("details", {})
    warning_count = 0

    # Entity-level warnings (from both entity_warnings and entity_diffs)
    for source_key in ("entity_warnings", "entity_diffs"):
        for entity_name, entity_diff in details.get(source_key, {}).items():
            # General warnings (entity_kind, etc.)
            warns = entity_diff.get("warnings", {})
            for warn_type, warn_data in warns.items():
                if warn_type == "constraints":
                    for fw in warn_data.get("fk_warnings", []):
                        reason = NOTICE_REASONS.get("fk", "Unknown")
                        missing = fw.get("missing_fks", [])
                        extra = fw.get("extra_fks", [])
                        if missing or extra:
                            print(f"      [NOTICE] {entity_name}.FK: "
                                  f"missing={missing} extra={extra}")
                            print(f"                Reason: {reason}")
                            warning_count += 1
                    for pw in warn_data.get("pk_type_warnings", []):
                        print(f"      [NOTICE] {entity_name}.PK({pw['columns']}).primary_key_types: "
                              f"actual={pw['actual']} expected={pw['expected']}")
                        print(f"                Reason: Cassandra PARTITION/CLUSTERING key distinction")
                        warning_count += 1
                else:
                    reason = NOTICE_REASONS.get(warn_type, "Unknown")
                    print(f"      [NOTICE] {entity_name}.{warn_type}: "
                          f"actual={warn_data.get('actual')} expected={warn_data.get('expected')}")
                    print(f"                Reason: {reason}")
                    warning_count += 1

            # Property key warnings
            attr_diff = entity_diff.get("properties", {})
            for kw in attr_diff.get("key_warnings", []):
                reason = NOTICE_REASONS.get("key_type", "Unknown")
                print(f"      [NOTICE] {entity_name}.{kw['attr']}.{kw['field']}: "
                      f"actual={kw['actual']} expected={kw['expected']}")
                print(f"                Reason: {reason}")
                warning_count += 1

            # Property optional (nullability) warnings
            for ow in attr_diff.get("optional_warnings", []):
                reason = NOTICE_REASONS.get("optional", "Unknown")
                print(f"      [NOTICE] {entity_name}.{ow['attr']}.is_optional: "
                      f"actual={ow['actual']} expected={ow['expected']}")
                print(f"                Reason: {reason}")
                warning_count += 1

            # Reference cardinality warnings
            ref_diff = entity_diff.get("references", {})
            for cw in ref_diff.get("cardinality_warnings", []):
                reason = NOTICE_REASONS.get("cardinality", "Unknown")
                print(f"      [NOTICE] {entity_name}.ref({cw['name']}): "
                      f"actual={cw['actual']} expected={cw['expected']}")
                print(f"                Reason: {reason}")
                warning_count += 1

            # Embedded cardinality warnings
            emb_diff = entity_diff.get("embedded", {})
            for cw in emb_diff.get("cardinality_warnings", []):
                reason = NOTICE_REASONS.get("cardinality", "Unknown")
                print(f"      [NOTICE] {entity_name}.embedded({cw['name']}): "
                      f"actual={cw['actual']} expected={cw['expected']}")
                print(f"                Reason: {reason}")
                warning_count += 1

            # Constraint FK/PK-type warnings (from entity_diffs with hard issues)
            cons_diff = entity_diff.get("constraints", {})
            for fw in cons_diff.get("fk_warnings", []):
                reason = NOTICE_REASONS.get("fk", "Unknown")
                missing = fw.get("missing_fks", [])
                extra = fw.get("extra_fks", [])
                if missing or extra:
                    print(f"      [NOTICE] {entity_name}.FK: "
                          f"missing={missing} extra={extra}")
                    print(f"                Reason: {reason}")
                    warning_count += 1
            for pw in cons_diff.get("pk_type_warnings", []):
                print(f"      [NOTICE] {entity_name}.PK({pw['columns']}).primary_key_types: "
                      f"actual={pw['actual']} expected={pw['expected']}")
                print(f"                Reason: Cassandra PARTITION/CLUSTERING key distinction")
                warning_count += 1

            # Edge cardinality warnings
            edge_diff = entity_diff.get("edges", {})
            for cw in edge_diff.get("cardinality_warnings", []):
                reason = NOTICE_REASONS.get("cardinality", "Unknown")
                print(f"      [NOTICE] {entity_name}.edge({cw['name']}): "
                      f"actual={cw['actual']} expected={cw['expected']}")
                print(f"                Reason: {reason}")
                warning_count += 1

    # Relationship type diffs (graph schemas)
    rel_diffs = details.get("relationship_type_diffs", {})
    if rel_diffs:
        # Cardinality warnings (always printed, regardless of issue_count)
        for cw in rel_diffs.get("cardinality_warnings", []):
            reason = NOTICE_REASONS.get("cardinality", "Unknown")
            print(f"      [NOTICE] RelType({cw['name']}).cardinality: "
                  f"actual={cw['actual']} expected={cw['expected']}")
            print(f"                Reason: {reason}")
            warning_count += 1

    return warning_count


def _print_validation_errors(validation_result: dict):
    """Print detailed errors (hard issues) from a validation result."""
    details = validation_result.get("details", {})

    # Missing/extra entities
    for name in details.get("missing_entities", []):
        print(f"      [ERROR] Missing entity: {name}")
    for name in details.get("extra_entities", []):
        print(f"      [ERROR] Extra entity: {name}")

    # Entity-level diffs
    for entity_name, entity_diff in details.get("entity_diffs", {}).items():
        # Property issues
        attr_diff = entity_diff.get("properties", {})
        for name in attr_diff.get("missing", []):
            print(f"      [ERROR] {entity_name}: missing property '{name}'")
        for name in attr_diff.get("extra", []):
            print(f"      [ERROR] {entity_name}: extra property '{name}'")
        for tm in attr_diff.get("type_mismatches", []):
            print(f"      [ERROR] {entity_name}.{tm['attr']}: "
                  f"type actual={tm['actual']} expected={tm['expected']}")

        # Reference issues
        ref_diff = entity_diff.get("references", {})
        for name in ref_diff.get("missing", []):
            print(f"      [ERROR] {entity_name}: missing reference '{name}'")
        for name in ref_diff.get("extra", []):
            print(f"      [ERROR] {entity_name}: extra reference '{name}'")
        for tm in ref_diff.get("target_mismatches", []):
            print(f"      [ERROR] {entity_name}.ref({tm['name']}): "
                  f"target actual={tm['actual_target']} expected={tm['expected_target']}")
        for am in ref_diff.get("attr_mismatches", []):
            print(f"      [ERROR] {entity_name}.ref({am['name']}).edge_properties: "
                  f"actual={am['actual']} expected={am['expected']}")

        # Embedded issues
        emb_diff = entity_diff.get("embedded", {})
        for name in emb_diff.get("missing", []):
            print(f"      [ERROR] {entity_name}: missing embedded '{name}'")
        for name in emb_diff.get("extra", []):
            print(f"      [ERROR] {entity_name}: extra embedded '{name}'")
        for tm in emb_diff.get("target_mismatches", []):
            print(f"      [ERROR] {entity_name}.embedded({tm['name']}): "
                  f"target actual={tm['actual_target']} expected={tm['expected_target']}")

        # Edge issues
        edge_diff = entity_diff.get("edges", {})
        for name in edge_diff.get("missing", []):
            print(f"      [ERROR] {entity_name}: missing edge '{name}'")
        for name in edge_diff.get("extra", []):
            print(f"      [ERROR] {entity_name}: extra edge '{name}'")
        for tm in edge_diff.get("mismatches", []):
            print(f"      [ERROR] {entity_name}.edge({tm['name']}): {tm.get('diffs', {})}")

        # Constraint PK issues
        cons_diff = entity_diff.get("constraints", {})
        for pk in cons_diff.get("missing_pk", []):
            print(f"      [ERROR] {entity_name}: missing PK {pk.get('columns', [])}")
        for pk in cons_diff.get("extra_pk", []):
            print(f"      [ERROR] {entity_name}: extra PK {pk.get('columns', [])}")

    # Relationship type issues (graph schemas)
    rel_diffs = details.get("relationship_type_diffs", {})
    if rel_diffs and rel_diffs.get("issue_count", 0) > 0:
        for name in rel_diffs.get("missing", []):
            print(f"      [ERROR] Missing relationship type: {name}")
        for name in rel_diffs.get("extra", []):
            print(f"      [ERROR] Extra relationship type: {name}")
        for m in rel_diffs.get("mismatches", []):
            print(f"      [ERROR] RelType({m['name']}): {m.get('diffs', {})}")


def run_test(direction: str, verbose: bool = False) -> dict:
    """
    Run a single migration test with unified validation.

    Returns:
        {
            "passed": bool,
            "layer0": bool,          # Execution check
            "layer1": bool or None,  # Meta validation (None = N/A)
            "layer2": bool or None,  # Export validation (None = N/A)
            "warnings": int,
            "stats": {...},
        }
    """
    r = run_migration(direction)

    if "error" in r:
        print(f"  [FAIL] {direction}")
        print(f"         Error: {r['error']}")
        return {"passed": False, "layer0": False, "layer1": None, "layer2": None, "warnings": 0}

    stats = r.get("execution_stats", {})
    total_ops = stats.get("total", 0)
    success_ops = stats.get("success", 0)
    skipped_ops = stats.get("skipped", 0)
    error_ops = stats.get("error", 0)

    is_cross_model = r["source_type"] != r["target_type"]
    is_northwind = direction.startswith("northwind_")

    # ── Layer 0: Execution check ──
    # A passing migration must apply *every* op without falling back to a
    # deliberate skip AND without a single handler bug. ``error_ops`` lives
    # in its own bucket since 2026-04-29 — previously handler exceptions
    # were folded into ``skipped_ops`` and the fact that the count went up
    # for the wrong reason was hidden from the layer-0 verdict.
    layer0 = (skipped_ops == 0 and error_ops == 0 and total_ops > 0)
    result_entities = {k for k in r.get("result", {}) if not k.startswith("__")}
    if len(result_entities) == 0:
        layer0 = False

    # ── Layer 1 & 2: Two-layer validation (all tests with target files) ──
    layer1 = None
    layer2 = None
    layer3 = None
    total_warnings = 0

    v_meta = r.get("validation_meta", {})
    v_export = r.get("validation_export", {})
    v_text_diff = r.get("validation_text_diff", {})
    v_integrity = r.get("validation_integrity", {})

    # Layer Preparation II (integrity) must run AND pass for every config.
    # Tightening to ``is True`` (vs ``is not False``) catches two regression
    # classes: (a) real metamodel violations (dangling UUID / duplicate UP
    # meta_id from un-relinked FK or copy.deepcopy clones), and (b) the
    # integrity check silently failing to wire up (e.g. ``__result_db``
    # missing in the result dict → ``passed=None``). Both should be hard
    # test failures, not silent passes.
    assert v_integrity.get("passed") is True, (
        f"{direction}: integrity check did not pass — "
        f"passed={v_integrity.get('passed')} "
        f"summary={v_integrity.get('summary')} "
        f"violations={v_integrity.get('violations')}"
    )

    # Use validation results if available (not N/A)
    if v_meta.get("passed") is not None:
        layer1 = v_meta.get("passed")
    if v_export.get("passed") is not None:
        layer2 = v_export.get("passed")
    if v_text_diff.get("passed") is not None:
        layer3 = v_text_diff.get("passed")

    overall_passed = layer0
    if layer1 is not None:
        overall_passed = overall_passed and layer1
    if layer2 is not None:
        overall_passed = overall_passed and layer2
    if layer3 is not None:
        overall_passed = overall_passed and layer3

    # ── Print results ──
    status = "PASS" if overall_passed else "FAIL"
    print(f"  [{status}] {direction}")
    print(f"         Layer 0: {'PASS' if layer0 else 'FAIL'} "
          f"({total_ops} ops, {success_ops} success, {skipped_ops} skipped, "
          f"{error_ops} error, {len(result_entities)} entities)")

    l1_summary = v_meta.get("summary", "N/A")
    l2_summary = v_export.get("summary", "N/A")
    l1_counts = v_meta.get("entity_count", {})
    l2_counts = v_export.get("entity_count", {})
    print(f"         Layer 1: {l1_summary} "
          f"(actual={l1_counts.get('actual', '?')}, expected={l1_counts.get('expected', '?')})")
    print(f"         Layer 2: {l2_summary} "
          f"(actual={l2_counts.get('actual', '?')}, expected={l2_counts.get('expected', '?')})")
    l3_summary = v_text_diff.get("summary", "N/A")
    print(f"         Layer 3: {l3_summary}")

    # Print errors if any layer failed
    if layer1 is False:
        _print_validation_errors(v_meta)
    if layer2 is False:
        _print_validation_errors(v_export)
    if layer3 is False:
        for ln in (v_text_diff.get("details") or {}).get("diff_preview", []) or []:
            print(f"         {ln}")

    # Print warnings (always, even on PASS)
    if layer1 is not None:
        total_warnings += _print_validation_warnings(v_meta)
    if layer2 is not None:
        total_warnings += _print_validation_warnings(v_export)

    # Verbose: print full schema details
    if verbose:
        _print_verbose(r)

    return {
        "passed": overall_passed,
        "layer0": layer0,
        "layer1": layer1,
        "layer2": layer2,
        "layer3": layer3,
        "warnings": total_warnings,
        "stats": stats,
    }


def _print_verbose(r: dict):
    """Print detailed schema information (for debugging)."""
    def filter_entities(d):
        return {k: v for k, v in d.items() if not k.startswith('__')}

    print("\n         --- Source Schema ---")
    source_filtered = filter_entities(r.get('source', {}))
    for name, entity in source_filtered.items():
        attrs = [a['name'] + (' [PK]' if a.get('is_key') else '') for a in entity.get('properties', [])]
        print(f"         {name}: {attrs}")

    print("\n         --- Meta V2 (Result) ---")
    result_filtered = filter_entities(r.get('result', {}))
    for name, entity in result_filtered.items():
        attrs = [a['name'] + (' [PK]' if a.get('is_key') else '') for a in entity.get('properties', [])]
        embedded = [e['name'] for e in entity.get('embedded', [])]
        refs = [f"{ref['name']}->{ref['target']}" for ref in entity.get('references', [])]
        line = f"         {name}: {attrs}"
        if embedded:
            line += f" embedded={embedded}"
        if refs:
            line += f" refs={refs}"
        print(line)


# pytest-compatible test functions
import pytest

_northwind_same_keys = sorted(
    k for k in MIGRATION_CONFIGS
    if k.startswith("northwind_") and
    MIGRATION_CONFIGS[k].source_type == MIGRATION_CONFIGS[k].target_type
)

_northwind_cross_keys = sorted(
    k for k in MIGRATION_CONFIGS
    if k.startswith("northwind_") and
    MIGRATION_CONFIGS[k].source_type != MIGRATION_CONFIGS[k].target_type
)


@pytest.mark.parametrize("direction", _northwind_same_keys)
def test_northwind_same_model(direction):
    """Test same-model evolution (R2R, D2D, G2G, C2C)."""
    result = run_test(direction)
    assert result["passed"], f"{direction} failed"


@pytest.mark.parametrize("direction", _northwind_cross_keys)
def test_northwind_cross_model(direction):
    """Test cross-model migration (all 12 directions x 2 grammars)."""
    result = run_test(direction)
    assert result["passed"], f"{direction} failed"


_grammar_completeness_keys = sorted(
    k for k in MIGRATION_CONFIGS if k.startswith("grammar_completeness_")
)


@pytest.mark.parametrize("direction", _grammar_completeness_keys)
def test_grammar_completeness_handlers_execute(direction):
    """Smoke-test the otherwise-untested operations.

    The Northwind suite never invokes WIND, UNWIND, CAST_PROPERTY, RECARD,
    COPY_ENTITY, etc. Without this test those handlers ship with zero
    execution coverage — they could regress and the rest of the suite
    would not notice. ``test_all_unused.{smile,smile_gen}`` exercises every
    such op end-to-end against a synthetic 3-table source schema.

    Validation is N/A here (no native target file to compare against), so
    we don't assert blame; we assert no handler raised and no op was
    silently skipped.
    """
    from core import run_migration
    r = run_migration(direction)
    assert "error" not in r, f"{direction} crashed: {r.get('error')}"
    stats = r.get("execution_stats") or {}
    assert stats.get("error", 0) == 0, (
        f"{direction}: {stats.get('error')} handler exception(s) — "
        f"see operations_detail for traceback context"
    )
    assert stats.get("skipped", 0) == 0, (
        f"{direction}: {stats.get('skipped')} op(s) skipped — every op in "
        f"test_all_unused must reach its handler successfully"
    )
    assert stats.get("success", 0) == stats.get("total", 0)


# Standalone execution (python tests/test_full_flow.py)
def main():
    import argparse
    parser = argparse.ArgumentParser(description="SMILE Full Flow Verification")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed schema info")
    parser.add_argument("--only", type=str, help="Run only tests matching this prefix (e.g. 'northwind_r2d')")
    args = parser.parse_args()

    print("=" * 70)
    print("SMILE FULL FLOW VERIFICATION")
    print("=" * 70)

    same_keys = list(_northwind_same_keys)
    cross_keys = list(_northwind_cross_keys)

    # Apply --only filter
    if args.only:
        same_keys = [k for k in same_keys if args.only in k]
        cross_keys = [k for k in cross_keys if args.only in k]

    all_results = {}
    total_warnings = 0

    # ── Northwind Same-Model ──
    if same_keys:
        print(f"\n{'=' * 70}")
        print(f"NORTHWIND SAME-MODEL EVOLUTION ({len(same_keys)} tests)")
        print("=" * 70)
        for direction in same_keys:
            all_results[direction] = run_test(direction, verbose=args.verbose)
            total_warnings += all_results[direction]["warnings"]

    # ── Northwind Cross-Model ──
    if cross_keys:
        print(f"\n{'=' * 70}")
        print(f"NORTHWIND CROSS-MODEL MIGRATION ({len(cross_keys)} tests)")
        print("=" * 70)
        for direction in cross_keys:
            all_results[direction] = run_test(direction, verbose=args.verbose)
            total_warnings += all_results[direction]["warnings"]

    # ── Summary ──
    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print("=" * 70)

    categories = {
        "Northwind Same": [k for k in all_results if k.startswith("northwind_") and
                           MIGRATION_CONFIGS[k].source_type == MIGRATION_CONFIGS[k].target_type],
        "Northwind Cross": [k for k in all_results if k.startswith("northwind_") and
                            MIGRATION_CONFIGS[k].source_type != MIGRATION_CONFIGS[k].target_type],
    }

    grand_total = 0
    grand_passed = 0

    for cat_name, keys in categories.items():
        if not keys:
            continue
        cat_passed = sum(1 for k in keys if all_results[k]["passed"])
        cat_total = len(keys)
        grand_total += cat_total
        grand_passed += cat_passed
        status = "PASS" if cat_passed == cat_total else "FAIL"
        print(f"  {cat_name:20s}: {cat_passed}/{cat_total} passed  [{status}]")

    print("-" * 70)
    print(f"  {'TOTAL':20s}: {grand_passed}/{grand_total} passed")
    if total_warnings > 0:
        print(f"  {'Notices':20s}: {total_warnings} (see details above)")
    print("=" * 70)

    overall = "ALL PASSED" if grand_passed == grand_total else "SOME FAILED"
    print(f"OVERALL: {overall} ({grand_passed}/{grand_total})")
    print("=" * 70)

    sys.exit(0 if grand_passed == grand_total else 1)


if __name__ == "__main__":
    main()
