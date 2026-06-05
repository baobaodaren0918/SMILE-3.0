"""
Specific vs Generalized grammar equivalence tests.

The thesis claims: "the Specific and Generalized grammars remain distinct
at the syntax level while converging to the same internal representation"
(\\autoref{sec:smile-architecture}, paper/chapter 4.tex:481-484). This file
turns that architectural claim into an empirical one — for every Northwind
base direction (and the grammar_completeness suite), we run both grammar
variants through the full pipeline and assert the resulting Meta V2,
exported native target, and three-layer validation verdict are byte-for-byte
identical.

Without these tests, the equivalence is only enforced *transitively* — each
variant compares against the same expected target via Layer 1; if both
pass, they must agree by triangulation. That argument breaks down in two
places that this file covers explicitly:

* **The grammar_completeness suite has no target file** (Layer 1 / Layer 2
  return ``Other reasons (no target file...)``). The transitive argument
  needs both sides to anchor against a target — without one, Specific and
  Generalized can diverge silently. The direct equivalence assertion here
  is the only place this is checked.
* **Direct byte-equality is stronger evidence** for the architectural claim
  than transitive agreement. Layer 1 passing for both could in principle
  hide a divergence that ``compute_diff`` happens not to flag (e.g. two
  semantically-equivalent constraint orderings); byte-identical
  ``db_to_dict`` output rules that out.

The 17 parametrised cases cover all Northwind bases (12 cross-model + 4
same-model evolution + 1 grammar_completeness). Each base name is the
``MIGRATION_CONFIGS`` key with the ``_specific`` / ``_generalized`` suffix
stripped.
"""
import sys
from pathlib import Path

import pytest

# Make the project root importable when pytest runs from this dir.
sys.path.insert(0, str(Path(__file__).parent.parent))

from core import run_migration
from config import MIGRATION_CONFIGS


def _collect_bases():
    """Strip the ``_specific`` / ``_generalized`` suffix from every config
    key and return the unique base names. A *base* is the logical migration
    direction (e.g. ``northwind_r2d``); each base has two grammar variants
    registered under ``<base>_specific`` and ``<base>_generalized``.
    """
    bases = set()
    for key in MIGRATION_CONFIGS:
        for suffix in ("_specific", "_generalized"):
            if key.endswith(suffix):
                bases.add(key[: -len(suffix)])
                break
    return sorted(bases)


_BASES = _collect_bases()


@pytest.mark.parametrize("base", _BASES)
def test_specific_and_generalized_produce_same_result(base):
    """Both grammar variants must produce byte-identical Meta V2,
    exported target, and three-layer validation verdict.

    This is the direct empirical form of the thesis's architectural claim
    that the two grammars "converge to the same internal representation".
    Layer 1 / Layer 2's transitive enforcement (each side matches the same
    target file) does not cover the grammar_completeness suite, where both
    sides are anchorless — this test does.
    """
    spec_key = f"{base}_specific"
    gen_key = f"{base}_generalized"

    # Self-skip rather than crash if either variant is unregistered. With
    # the current 34-config set every base has both variants, so this is a
    # belt-and-suspenders guard against a future config-table edit.
    if spec_key not in MIGRATION_CONFIGS:
        pytest.skip(f"{spec_key} not registered")
    if gen_key not in MIGRATION_CONFIGS:
        pytest.skip(f"{gen_key} not registered")

    spec = run_migration(spec_key)
    gen = run_migration(gen_key)

    # Sanity: neither side should bail out before producing a result.
    assert spec.get("error") is None, (
        f"{spec_key}: run_migration errored before producing a result: "
        f"{spec.get('error')}"
    )
    assert gen.get("error") is None, (
        f"{gen_key}: run_migration errored before producing a result: "
        f"{gen.get('error')}"
    )

    # ── (1) Meta V2 byte-equality ────────────────────────────────────
    # The "same internal representation" claim measured at the canonical
    # serialisation level. ``db_to_dict`` uses path-based deterministic ids
    # (see Database.to_dict in unified_meta_schema.py) so byte-equality is
    # the right granularity here — random meta_id UUIDs have already been
    # stripped before this point.
    assert spec["result"] == gen["result"], (
        f"{base}: specific and generalized produced different Meta V2 "
        f"(this would invalidate the 'two grammars converge to the same "
        f"internal representation' claim in the thesis)."
    )

    # ── (2) Exported native target byte-equality ─────────────────────
    # Downstream consequence of (1) under deterministic adapter export,
    # but asserted independently so a hypothetical adapter-side path that
    # depends on operation history (rather than only on the final Meta V2)
    # would also be caught.
    assert spec["exported_target"] == gen["exported_target"], (
        f"{base}: specific and generalized produced different exported targets "
        f"despite identical Meta V2 — implies an adapter export path that "
        f"reads operation history rather than only the final Meta V2."
    )

    # ── (3) Three-layer validation verdict equality ──────────────────
    # The blame label and per-layer pass/fail must agree. ``details`` is
    # not asserted byte-equal because layer reports may carry innocuous
    # differences (e.g. reason strings tied to the specific keyword form
    # the listener emitted) without altering the verdict.
    assert spec["validation_blame"] == gen["validation_blame"], (
        f"{base}: blame differs — "
        f"specific={spec['validation_blame']!r}, "
        f"generalized={gen['validation_blame']!r}"
    )
    for layer in ("validation_layer0", "validation_meta", "validation_export"):
        spec_passed = spec[layer].get("passed")
        gen_passed = gen[layer].get("passed")
        assert spec_passed == gen_passed, (
            f"{base}: {layer}.passed differs — "
            f"specific={spec_passed!r}, generalized={gen_passed!r}"
        )
