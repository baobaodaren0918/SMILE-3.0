"""Automated consistency guard across the four operation registries.

The audit of 2026-06-28 verified by hand that the SMILE operation set is kept
in sync across: the ``OpType`` enum, the handler registry, both ANTLR grammars,
and ``grammar/smile_operations.json`` (the autocomplete source of truth). This
test encodes that cross-check so future drift — e.g. adding a grammar keyword
without a handler, or a JSON entry without a grammar token — fails immediately
instead of slipping through.
"""
import json
import re
from pathlib import Path

import pytest

from parser.listeners import OpType
from core.transformer import _HANDLER_REGISTRY

ROOT = Path(__file__).resolve().parent.parent
OPS_JSON = ROOT / "grammar" / "smile_operations.json"
G_SPECIFIC = ROOT / "grammar" / "specific" / "SMILE_Specific.g4"
G_GENERALIZED = ROOT / "grammar" / "generalized" / "SMILE_Generalized.g4"

# The 8 paradigm-specific key keywords collapse onto 2 OpTypes; the concrete
# kind is carried in the parameter record (see parser/listeners.py). Every
# other JSON keyword maps onto the OpType of the same name.
_KEY_COLLAPSE = {
    "ADD_PRIMARY_KEY": "ADD_KEY", "ADD_UNIQUE_KEY": "ADD_KEY",
    "ADD_PARTITION_KEY": "ADD_KEY", "ADD_CLUSTERING_KEY": "ADD_KEY",
    "DELETE_PRIMARY_KEY": "DELETE_KEY", "DELETE_UNIQUE_KEY": "DELETE_KEY",
    "DELETE_PARTITION_KEY": "DELETE_KEY", "DELETE_CLUSTERING_KEY": "DELETE_KEY",
}


def _load_ops():
    return json.loads(OPS_JSON.read_text(encoding="utf-8"))["operations"]


def _has_literal(grammar_text: str, token: str) -> bool:
    """True if ``token`` appears as a single-quoted literal in the grammar."""
    return re.search(r"'" + re.escape(token) + r"'", grammar_text) is not None


def test_optype_and_handler_registry_are_in_bijection():
    """Every OpType has exactly one handler and vice versa."""
    op_types = set(OpType)
    handlers = set(_HANDLER_REGISTRY.keys())
    assert op_types == handlers, (
        f"OpType without handler: {op_types - handlers}; "
        f"handler without OpType: {handlers - op_types}"
    )


def test_json_operations_cover_exactly_the_optypes():
    """Each JSON op maps to a real OpType (after key collapse), and every
    OpType is covered by at least one JSON op."""
    ops = _load_ops()
    optype_names = {ot.name for ot in OpType}
    mapped = {_KEY_COLLAPSE.get(key, key) for key in ops}
    assert mapped == optype_names, (
        f"JSON ops mapping to no OpType: {mapped - optype_names}; "
        f"OpTypes missing from JSON: {optype_names - mapped}"
    )


def test_json_entries_are_well_formed():
    """Each JSON entry's key equals its specific keyword and carries the
    fields the autocomplete UI relies on."""
    ops = _load_ops()
    for key, entry in ops.items():
        assert entry.get("specific") == key, f"{key}: specific != key"
        for field in ("generalized", "syntax_specific", "syntax_generalized"):
            assert entry.get(field), f"{key}: missing/empty '{field}'"


def test_specific_keywords_exist_in_specific_grammar():
    """Every JSON specific keyword is a literal token in the specific grammar."""
    grammar = G_SPECIFIC.read_text(encoding="utf-8")
    missing = [e["specific"] for e in _load_ops().values()
               if not _has_literal(grammar, e["specific"])]
    assert not missing, f"specific keywords absent from grammar: {missing}"


def test_generalized_words_exist_in_generalized_grammar():
    """Every word of each JSON generalized phrase is a literal token in the
    generalized grammar (the phrase itself is assembled from word tokens)."""
    grammar = G_GENERALIZED.read_text(encoding="utf-8")
    missing = []
    for entry in _load_ops().values():
        for word in entry["generalized"].split():
            if not _has_literal(grammar, word):
                missing.append((entry["generalized"], word))
    assert not missing, f"generalized words absent from grammar: {missing}"