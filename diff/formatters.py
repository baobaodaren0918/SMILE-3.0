"""Formatters that convert a ``DatabaseDiff`` into the dict shapes expected by"""
from typing import Any, Dict, List

from diff.engine import DatabaseDiff, EntityDiff


# UI formatter (legacy shape from core._calculate_changes)

def to_ui_changes(diff: DatabaseDiff, prev: Dict, after: Dict) -> Dict[str, Any]:
    """Format a DatabaseDiff for the per-op web-UI changes panel."""
    changes: Dict[str, Any] = {
        "affected_entities": [],
        "new_entities": [],
        "deleted_entities": [],
        "modified_entities": [],
        "new_relationship_types": [],
        "deleted_relationship_types": [],
        "modified_relationship_types": [],
    }

    # --- relationship_types (graph) ---
    after_rts = after.get("__relationship_types__", {})
    prev_rts  = prev.get("__relationship_types__", {})
    for n in diff.rels_only_right:
        changes["new_relationship_types"].append(n)
        changes["affected_entities"].append({
            "name": n, "status": "new_reltype", "entity": after_rts.get(n, {}),
        })
    for n in diff.rels_only_left:
        changes["deleted_relationship_types"].append(n)
        changes["affected_entities"].append({
            "name": n, "status": "deleted_reltype", "entity": prev_rts.get(n, {}),
        })

    # --- entity-level set diff (left = prev, right = after) ---
    for n in diff.entities_only_right:
        changes["new_entities"].append(n)
        changes["affected_entities"].append({
            "name": n, "status": "new", "entity": after.get(n, {}),
        })
    for n in diff.entities_only_left:
        changes["deleted_entities"].append(n)
        changes["affected_entities"].append({
            "name": n, "status": "deleted", "entity": prev.get(n, {}),
        })

    # --- modified entities ---
    for name, ed in diff.entity_diffs.items():
        # Even an only-warnings diff counts as "modified" for UI purposes,
        # matching the legacy behavior (kind change, constraint warnings, etc.).
        type_changed = [
            {"name": pc.name, "old_type": pc.left_type, "new_type": pc.right_type}
            for pc in ed.prop_type_changes
        ]
        changes["modified_entities"].append(name)
        changes["affected_entities"].append({
            "name": name,
            "status": "modified",
            "entity": after.get(name, {}),
            "new_properties": ed.props_only_right,
            "deleted_properties": [p["name"] for p in ed.props_only_left],
            "new_embedded": ed.embedded_only_right,
            "deleted_embedded": [e["name"] for e in ed.embedded_only_left],
            "new_references": ed.refs_only_right,
            "deleted_references": [r["name"] for r in ed.refs_only_left],
            "new_edges": ed.edges_only_right,
            "deleted_edges": [e["name"] for e in ed.edges_only_left],
            "type_changed_properties": type_changed,
        })

    return changes


# Validation formatter (legacy shape from validate_meta.compare_meta_schemas)

def _pack_diff(missing: List, extra: List, hard: Dict[str, list],
               warn: Dict[str, list]) -> Dict[str, Any]:
    """Pack into the legacy {issue_count, missing, extra, ...} shape."""
    issue_count = len(missing) + len(extra) + sum(len(v) for v in hard.values())
    if issue_count == 0 and not any(warn.values()):
        return {}
    out: Dict[str, Any] = {"issue_count": issue_count}
    if missing: out["missing"] = missing
    if extra:   out["extra"]   = extra
    for k, v in hard.items():
        if v: out[k] = v
    for k, v in warn.items():
        if v: out[k] = v
    return out


def _format_entity_validation(ed: EntityDiff) -> Dict[str, Any]:
    """Convert one EntityDiff into the legacy validate_meta entity-diff shape."""
    out: Dict[str, Any] = {}
    issue_count = 0
    warnings: Dict[str, Any] = {}

    if ed.entity_kind_changed:
        warnings["entity_kind"] = {
            "actual": ed.entity_kind_left,
            "expected": ed.entity_kind_right,
        }

    # Properties
    prop_block = _pack_diff(
        missing=[p["name"] for p in ed.props_only_right],   # in expected, not actual
        extra=[p["name"] for p in ed.props_only_left],      # in actual, not expected
        hard={"type_mismatches": [
            {"attr": pc.name, "actual": pc.left_type, "expected": pc.right_type}
            for pc in ed.prop_type_changes
        ]},
        warn={
            "key_warnings": [
                {"attr": w["attr"], "field": w["field"],
                 "actual": w["left"], "expected": w["right"]}
                for w in ed.prop_key_warnings
            ],
            "optional_warnings": [
                {"attr": w["attr"], "actual": w["left"], "expected": w["right"]}
                for w in ed.prop_optional_warnings
            ],
        },
    )
    if prop_block:
        out["properties"] = prop_block
        issue_count += prop_block.get("issue_count", 0)

    # Constraints
    cd = ed.constraint_diff
    if cd is not None and not cd.is_empty():
        # Missing/extra CHECK is a hard issue (script forgot to add or wrongly
        # added a CHECK predicate); it does not belong with PK/FK warnings.
        c_issue = (len(cd.missing_pk) + len(cd.extra_pk)
                   + len(cd.check_missing) + len(cd.check_extra))
        c_block: Dict[str, Any] = {"issue_count": c_issue}
        if cd.missing_pk:        c_block["missing_pk"] = cd.missing_pk
        if cd.extra_pk:          c_block["extra_pk"]   = cd.extra_pk
        if cd.check_missing:     c_block["missing_check"] = cd.check_missing
        if cd.check_extra:       c_block["extra_check"]   = cd.check_extra
        if cd.pk_type_changes:
            c_block["pk_type_warnings"] = [
                {"columns": w["columns"], "actual": w["left"], "expected": w["right"]}
                for w in cd.pk_type_changes
            ]
        if cd.fk_missing or cd.fk_extra:
            c_block["fk_warnings"] = [{
                "missing_fks": list(cd.fk_missing),
                "extra_fks":   list(cd.fk_extra),
            }]
        if c_issue > 0:
            out["constraints"] = c_block
            issue_count += c_issue
        else:
            warnings["constraints"] = c_block

    # References
    ref_block = _pack_diff(
        missing=[r["name"] for r in ed.refs_only_right],
        extra=[r["name"] for r in ed.refs_only_left],
        hard={
            "target_mismatches": [
                {"name": tc.name, "actual_target": tc.left_target,
                 "expected_target": tc.right_target}
                for tc in ed.ref_target_changes
            ],
            "attr_mismatches": [
                {"name": ac.name, "actual": ac.left_attrs, "expected": ac.right_attrs}
                for ac in ed.ref_attr_changes
            ],
        },
        warn={"cardinality_warnings": [
            {"name": cc.name, "actual": cc.left, "expected": cc.right}
            for cc in ed.ref_cardinality_changes
        ]},
    )
    if ref_block:
        out["references"] = ref_block
        issue_count += ref_block.get("issue_count", 0)

    # Embedded
    emb_block = _pack_diff(
        missing=[e["name"] for e in ed.embedded_only_right],
        extra=[e["name"] for e in ed.embedded_only_left],
        hard={"target_mismatches": [
            {"name": tc.name, "actual_target": tc.left_target,
             "expected_target": tc.right_target}
            for tc in ed.embedded_target_changes
        ]},
        warn={"cardinality_warnings": [
            {"name": cc.name, "actual": cc.left, "expected": cc.right}
            for cc in ed.embedded_cardinality_changes
        ]},
    )
    if emb_block:
        out["embedded"] = emb_block
        issue_count += emb_block.get("issue_count", 0)

    # Edges
    edge_mismatches = []
    for ec in ed.edge_endpoint_changes:
        diffs = {}
        if ec.left_source is not None or ec.right_source is not None:
            diffs["source"] = {"actual": ec.left_source, "expected": ec.right_source}
        if ec.left_target is not None or ec.right_target is not None:
            diffs["target"] = {"actual": ec.left_target, "expected": ec.right_target}
        edge_mismatches.append({"name": ec.name, "diffs": diffs})
    edge_block = _pack_diff(
        missing=[e["name"] for e in ed.edges_only_right],
        extra=[e["name"] for e in ed.edges_only_left],
        hard={"mismatches": edge_mismatches},
        warn={"cardinality_warnings": [
            {"name": cc.name, "actual": cc.left, "expected": cc.right,
             "field": getattr(cc, "field", "target_end_cardinality")}
            for cc in ed.edge_cardinality_changes
        ]},
    )
    if edge_block:
        out["edges"] = edge_block
        issue_count += edge_block.get("issue_count", 0)

    if warnings:
        out["warnings"] = warnings
    if issue_count > 0:
        out["issue_count"] = issue_count
    return out


def to_validation_report(
    diff: DatabaseDiff, actual: Dict[str, Any], expected: Dict[str, Any]
) -> Dict[str, Any]:
    """Format a DatabaseDiff as a Layer 1 / Layer 2 validation report."""
    actual_count = sum(1 for k in actual if not k.startswith("__"))
    expected_count = sum(1 for k in expected if not k.startswith("__"))

    missing = list(diff.entities_only_right)   # in expected, missing from actual
    extra   = list(diff.entities_only_left)    # in actual, not in expected

    entity_diffs: Dict[str, Any] = {}
    entity_warnings: Dict[str, Any] = {}
    total_issues = 0
    for name, ed in diff.entity_diffs.items():
        block = _format_entity_validation(ed)
        if not block:
            continue
        ic = block.get("issue_count", 0)
        if ic > 0:
            entity_diffs[name] = block
            total_issues += ic
        else:
            entity_warnings[name] = block

    # --- relationship_types ---
    rel_diffs: Dict[str, Any] = {}
    if diff.rels_only_left or diff.rels_only_right or diff.rel_diffs:
        mismatches = []
        cardinality_warnings = []
        for n, rd in diff.rel_diffs.items():
            for ec in rd.endpoint_changes:
                fdiffs = {}
                if ec.left_source != ec.right_source:
                    fdiffs["source_entity"] = {"actual": ec.left_source, "expected": ec.right_source}
                if ec.left_target != ec.right_target:
                    fdiffs["target_entity"] = {"actual": ec.left_target, "expected": ec.right_target}
                if fdiffs:
                    mismatches.append({"name": n, "diffs": fdiffs})
            for cc in rd.cardinality_changes:
                cardinality_warnings.append({
                    "name": n, "actual": cc.left, "expected": cc.right,
                    "field": getattr(cc, "field", "target_end_cardinality"),
                })
            for ac in rd.attr_mismatches:
                mismatches.append({
                    "name": n,
                    "actual_attrs": ac.left_attrs,
                    "expected_attrs": ac.right_attrs,
                })
        rel_block = _pack_diff(
            missing=list(diff.rels_only_right),
            extra=list(diff.rels_only_left),
            hard={"mismatches": mismatches},
            warn={"cardinality_warnings": cardinality_warnings},
        )
        rel_diffs = rel_block
        total_issues += rel_block.get("issue_count", 0)

    total_issues += len(missing) + len(extra)
    passed = total_issues == 0

    if passed:
        summary = "PASS"
    else:
        parts = []
        if missing: parts.append(f"{len(missing)} missing entities")
        if extra:   parts.append(f"{len(extra)} extra entities")
        if entity_diffs: parts.append(f"{len(entity_diffs)} entity mismatches")
        if rel_diffs.get("issue_count", 0) > 0:
            parts.append("relationship type mismatches")
        summary = f"FAIL ({', '.join(parts)})"

    return {
        "passed": passed,
        "summary": summary,
        "entity_count": {"actual": actual_count, "expected": expected_count},
        "details": {
            "missing_entities": missing,
            "extra_entities": extra,
            "entity_diffs": entity_diffs,
            "entity_warnings": entity_warnings,
            "relationship_type_diffs": rel_diffs,
        },
    }
