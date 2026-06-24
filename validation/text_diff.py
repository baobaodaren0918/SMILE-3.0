"""Layer 3 Validation: Text-level diff between FE-exported native and the"""
from typing import Any, Dict, List
import difflib
import json
import re

from config import (
    SOURCE_TYPE_RELATIONAL, SOURCE_TYPE_DOCUMENT,
    SOURCE_TYPE_GRAPH, SOURCE_TYPE_COLUMNAR,
)


# Per-paradigm normalizers

# Mongo / JSON Schema: title and description are descriptive metadata not
# part of the schema's structural content; sort_keys handles object member
# order, the ``required`` array order, and collection order.
_JSON_NOISE_KEYS = ("title", "description", "$schema", "version")


def _normalize_json(text: str) -> str:
    obj = json.loads(text)

    def walk(o: Any) -> None:
        if isinstance(o, dict):
            for k in _JSON_NOISE_KEYS:
                o.pop(k, None)
            # JSON Schema ``required`` is a set (spec 6.5.3: elements MUST be
            # unique), so its element order carries no semantics. ``sort_keys``
            # only sorts dict keys, not array contents -- we sort it here.
            req = o.get("required")
            if isinstance(req, list) and all(isinstance(x, str) for x in req):
                o["required"] = sorted(req)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(obj)
    return json.dumps(obj, sort_keys=True, indent=2)


def _split_top_level(s: str) -> List[str]:
    """Split a comma-separated string but ignore commas inside parentheses"""
    parts: List[str] = []
    depth = 0
    cur: List[str] = []
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur))
    return parts


def _normalize_sql_like(text: str, comment_prefix: str) -> str:
    """SQL / CQL: idempotent normalization to a canonical string."""
    # 1. Strip line comments + blank lines, collapse whitespace.
    cleaned: List[str] = []
    for raw in text.splitlines():
        i = raw.find(comment_prefix)
        if i >= 0:
            raw = raw[:i]
        s = raw.strip()
        if s:
            cleaned.append(s)
    flat = " ".join(cleaned)
    flat = re.sub(r"\s+", " ", flat)

    # 2. Split into statements by ``CREATE TABLE`` keyword rather than by
    #    the trailing ``;``. The first normalization pass drops ``;``, so a
    #    ``;``-based splitter would collapse every CREATE TABLE into one
    #    blob on the second pass — breaking idempotency.
    stmt_pattern = re.compile(r"\bcreate\s+table\b", re.IGNORECASE)
    positions = [m.start() for m in stmt_pattern.finditer(flat)]
    raw_statements: List[str] = []
    if positions:
        for idx, start in enumerate(positions):
            end = positions[idx + 1] if idx + 1 < len(positions) else len(flat)
            raw_statements.append(flat[start:end].strip().rstrip(";").strip())
    elif flat.strip():
        raw_statements.append(flat.strip().rstrip(";").strip())

    statements: List[str] = []
    for s in raw_statements:
        # Lowercase keywords (rough but sufficient for diff).
        s = re.sub(
            r"\b(CREATE|TABLE|PRIMARY|KEY|FOREIGN|REFERENCES|NOT|NULL|"
            r"VARCHAR|INT|INTEGER|TEXT|DATE|TIMESTAMP|BOOLEAN|NUMERIC|"
            r"DECIMAL|SERIAL|BIGINT|UNIQUE|CHECK|DEFAULT|WITH|ON|"
            r"DELETE|UPDATE|CASCADE|CONSTRAINT|INDEX|DOUBLE|PRECISION|"
            r"PARTITION|CLUSTERING|ORDER|BY|ASC|DESC)\b",
            lambda m: m.group(0).lower(),
            s,
            flags=re.IGNORECASE,
        )
        # For CREATE TABLE statements: parse out (name, body) and sort body.
        m = re.match(r"create\s+table\s+(\w+)\s*\((.*)\)\s*$", s, re.DOTALL)
        if m:
            name = m.group(1)
            body = m.group(2)
            cols = [c.strip() for c in _split_top_level(body) if c.strip()]
            cols_sorted = sorted(cols)
            s = f"create table {name} ({', '.join(cols_sorted)})"
        statements.append(s)

    # Sort statements (tables) alphabetically.
    return "\n".join(sorted(statements))


def _normalize_graph_schema(text: str) -> str:
    """Graph schema: compare parsed structure, independent of SDL field order."""
    from Schema.adapters import Neo4jAdapter
    from core import db_to_dict

    db = Neo4jAdapter().parse(text, "text_diff")
    meta = db_to_dict(db)
    meta.get("__db_meta__", {}).pop("db_name", None)

    def sort_dict_lists(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: sort_dict_lists(v) for k, v in value.items()}
        if isinstance(value, list):
            items = [sort_dict_lists(v) for v in value]
            if all(isinstance(v, dict) for v in items):
                return sorted(items, key=lambda v: json.dumps(v, sort_keys=True))
            return items
        return value

    return json.dumps(sort_dict_lists(meta), sort_keys=True, indent=2)


_NORMALIZERS = {
    SOURCE_TYPE_DOCUMENT:   _normalize_json,
    SOURCE_TYPE_RELATIONAL: lambda t: _normalize_sql_like(t, "--"),
    SOURCE_TYPE_COLUMNAR:   lambda t: _normalize_sql_like(t, "--"),
    SOURCE_TYPE_GRAPH:      _normalize_graph_schema,
}


# Main entry

def validate_text_diff(result_dict: Dict[str, Any], target_type: str,
                       config_key: str = "") -> Dict[str, Any]:
    """Layer 3: Compare FE-exported native text against the project's"""
    from validation.meta import _resolve_target_file

    exported = result_dict.get("exported_target", "")
    if not exported:
        return {"passed": False, "summary": "FAIL (no exported target)", "details": {}}

    target_file = _resolve_target_file(config_key, target_type)
    if not target_file:
        return {"passed": None,
                "summary": f"Other reasons (no target file for {config_key})",
                "details": {}}

    normalizer = _NORMALIZERS.get(target_type)
    if normalizer is None:
        return {"passed": None,
                "summary": f"Other reasons (no Layer 3 normalizer for {target_type})",
                "details": {}}

    try:
        with open(target_file, "r", encoding="utf-8") as f:
            native = f.read()
    except OSError as e:
        return {"passed": False, "summary": f"FAIL (cannot read {target_file}: {e})",
                "details": {}}

    try:
        n_exported = normalizer(exported)
        n_native = normalizer(native)
    except Exception as e:
        return {"passed": False,
                "summary": f"FAIL (normalization error: {type(e).__name__}: {e})",
                "details": {}}

    if n_exported == n_native:
        return {
            "passed": True,
            "summary": "PASS (text matches under set-based normalization)",
            "details": {
                "target_file": str(target_file),
                "normalized_lines": len(n_exported.splitlines()),
            },
        }

    diff = list(difflib.unified_diff(
        n_native.splitlines(), n_exported.splitlines(),
        "native(norm)", "exported(norm)", lineterm=""))
    minus = [l for l in diff if l.startswith("-") and not l.startswith("---")]
    plus = [l for l in diff if l.startswith("+") and not l.startswith("+++")]

    return {
        "passed": False,
        "summary": f"FAIL ({len(minus)} only-in-native, {len(plus)} only-in-export "
                   f"lines after normalization)",
        "details": {
            "target_file": str(target_file),
            "diff_preview": diff[:60],
            "native_norm_lines": len(n_native.splitlines()),
            "exported_norm_lines": len(n_exported.splitlines()),
        },
    }


# Standalone runner: report on the 4 cross-paradigm directions

def _report(directions: List[str]) -> int:
    """Run validate_text_diff over the given config keys and print a table."""
    from core import run_migration

    print("=" * 76)
    print("Layer 3: Text-level diff against project ground-truth (set-based)")
    print("=" * 76)
    print(f"{'direction':<36} {'verdict':<10} {'summary'}")
    print("-" * 76)

    failed = 0
    for key in directions:
        result = run_migration(key)
        if result.get("error"):
            print(f"{key:<36} {'ERROR':<10} {result['error']}")
            failed += 1
            continue
        report = validate_text_diff(
            result_dict=result,
            target_type=result["target_type"],
            config_key=key,
        )
        verdict = ("PASS" if report["passed"]
                   else "SKIP" if report["passed"] is None
                   else "FAIL")
        if verdict == "FAIL":
            failed += 1
        print(f"{key:<36} {verdict:<10} {report['summary']}")
    print("-" * 76)
    print(f"{len(directions)} directions, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    # The 4 cross-paradigm directions the thesis discusses (specific grammar).
    # Add more keys here to extend coverage (e.g. all 12 cross-paradigm or
    # all 32 Northwind configs).
    DEFAULT_DIRECTIONS = [
        "northwind_r2d_specific",  # PG -> Mongo
        "northwind_d2r_specific",  # Mongo -> PG
        "northwind_r2g_specific",  # PG -> Neo4j
        "northwind_r2c_specific",  # PG -> Cass
    ]
    raise SystemExit(_report(DEFAULT_DIRECTIONS))
