"""SMILE Configuration - Centralized path and settings management."""
from dataclasses import dataclass
from pathlib import Path
from typing import Dict


@dataclass(frozen=True)
class MigrationConfig:
    """One registered migration scenario."""
    source_file: Path
    smile_file: Path
    source_type: str
    target_type: str
    display_name: str

BASE_DIR = Path(__file__).parent
TESTS_DIR = BASE_DIR / "tests"


SOURCE_TYPE_RELATIONAL = "Relational"
SOURCE_TYPE_DOCUMENT = "Document"
SOURCE_TYPE_GRAPH = "Graph"
SOURCE_TYPE_COLUMNAR = "Columnar"

# Human-readable product names for each abstract DB type
DB_TYPE_DISPLAY_NAME = {
    SOURCE_TYPE_RELATIONAL: "PostgreSQL",
    SOURCE_TYPE_DOCUMENT:   "MongoDB",
    SOURCE_TYPE_GRAPH:      "Neo4j",
    SOURCE_TYPE_COLUMNAR:   "Cassandra",
}

# Export format labels (shown when displaying generated target output)
DB_TYPE_EXPORT_LABEL = {
    SOURCE_TYPE_RELATIONAL: "PostgreSQL DDL",
    SOURCE_TYPE_DOCUMENT:   "MongoDB JSON Schema",
    SOURCE_TYPE_GRAPH:      "Neo4j GraphQL SDL",
    SOURCE_TYPE_COLUMNAR:   "Cassandra CQL",
}


# Northwind source schema files keyed by product name (for web UI / inspector)
NORTHWIND_SCHEMA_FILES = {
    "postgresql": TESTS_DIR / "northwind_postgresql.sql",
    "mongodb":    TESTS_DIR / "northwind_mongodb.json",
    "neo4j":      TESTS_DIR / "northwind_neo4j.graphql",
    "cassandra":  TESTS_DIR / "northwind_cassandra.cql",
}

# Map product name -> internal SOURCE_TYPE constant (for web UI)
PRODUCT_TO_SOURCE_TYPE = {
    "postgresql": SOURCE_TYPE_RELATIONAL,
    "mongodb":    SOURCE_TYPE_DOCUMENT,
    "neo4j":      SOURCE_TYPE_GRAPH,
    "cassandra":  SOURCE_TYPE_COLUMNAR,
}

# Northwind target schema files for cross-model validation
# Maps target_type -> native schema file (ground truth for comparison)
TARGET_SCHEMA_FILES = {
    SOURCE_TYPE_RELATIONAL: TESTS_DIR / "northwind_postgresql.sql",
    SOURCE_TYPE_DOCUMENT:   TESTS_DIR / "northwind_mongodb.json",
    SOURCE_TYPE_GRAPH:      TESTS_DIR / "northwind_neo4j.graphql",
    SOURCE_TYPE_COLUMNAR:   TESTS_DIR / "northwind_cassandra.cql",
}

# Per-migration target schema files for two-layer validation
# Maps config_key prefix -> {target_type -> native file}
# Used when a migration direction has its own dedicated target file.
MIGRATION_TARGET_FILES = {
    # Northwind same-model evolution
    "northwind_r2r": TESTS_DIR / "northwind_r2r_target.sql",
    "northwind_d2d": TESTS_DIR / "northwind_d2d_target.json",
    "northwind_g2g": TESTS_DIR / "northwind_g2g_target.graphql",
    "northwind_c2c": TESTS_DIR / "northwind_c2c_target.cql",
}


# Configs are generated from this paradigm matrix (not hand-written) so the
# 4x4 grid can never drift half-updated when a paradigm/grammar is added.
# Note the Neo4j script-file token differs by family: cross-model uses "neo4j",
# same-model evolution uses "graph".
#   key code | source file | display name | cross-model token | same-model token
_PARADIGMS = {
    SOURCE_TYPE_RELATIONAL: ("r", "northwind_postgresql.sql", "PostgreSQL", "pg",    "pg"),
    SOURCE_TYPE_DOCUMENT:   ("d", "northwind_mongodb.json",   "MongoDB",    "mongo", "mongo"),
    SOURCE_TYPE_GRAPH:      ("g", "northwind_neo4j.graphql",  "Neo4j",      "neo4j", "graph"),
    SOURCE_TYPE_COLUMNAR:   ("c", "northwind_cassandra.cql",  "Cassandra",  "cass",  "cass"),
}
# Iteration order — fixes the order entries appear in MIGRATION_CONFIGS.
_PARADIGM_ORDER = [
    SOURCE_TYPE_RELATIONAL, SOURCE_TYPE_DOCUMENT,
    SOURCE_TYPE_GRAPH, SOURCE_TYPE_COLUMNAR,
]
# grammar key suffix | script subdir | script extension | display label
_GRAMMARS = [
    ("specific",    "specific",    ".smile",     "Specific"),
    ("generalized", "generalized", ".smile_gen", "Generalized"),
]


def _build_raw_configs():
    """Build the scenario dict from the paradigm matrix. Order: 4 same-model
    evolutions, then 12 cross-model migrations grouped by source, then the 2
    grammar-completeness smoke configs — each direction in both grammars."""
    cfgs = {}

    # --- Same-model evolution (R->R, D->D, G->G, C->C) ---
    for p in _PARADIGM_ORDER:
        code, src, disp, _xtok, stok = _PARADIGMS[p]
        for gsuf, gdir, ext, glabel in _GRAMMARS:
            cfgs[f"northwind_{code}2{code}_{gsuf}"] = {
                "source_file": TESTS_DIR / src,
                "smile_file": TESTS_DIR / gdir / f"northwind_{stok}1_to_{stok}2{ext}",
                "source_type": p,
                "target_type": p,
                "display_name": f"Northwind: {disp} → {disp} V2 ({glabel})",
            }

    # --- Cross-model migration (grouped by source) ---
    for s in _PARADIGM_ORDER:
        scode, ssrc, sdisp, sxtok, _sstok = _PARADIGMS[s]
        for t in _PARADIGM_ORDER:
            if t == s:
                continue
            tcode, _tsrc, tdisp, txtok, _tstok = _PARADIGMS[t]
            for gsuf, gdir, ext, glabel in _GRAMMARS:
                cfgs[f"northwind_{scode}2{tcode}_{gsuf}"] = {
                    "source_file": TESTS_DIR / ssrc,
                    "smile_file": TESTS_DIR / gdir / f"northwind_{sxtok}_to_{txtok}{ext}",
                    "source_type": s,
                    "target_type": t,
                    "display_name": f"Northwind: {sdisp} → {tdisp} ({glabel})",
                }

    # --- Grammar-completeness suite (exercises every otherwise-untested op
    # on a tiny synthetic schema; no native target -> L1/L2 validation N/A) ---
    for gsuf, _gdir, ext, glabel in _GRAMMARS:
        cfgs[f"grammar_completeness_{gsuf}"] = {
            "source_file": TESTS_DIR / "grammar_completeness" / "source.sql",
            "smile_file": TESTS_DIR / "grammar_completeness" / f"test_all_unused{ext}",
            "source_type": SOURCE_TYPE_RELATIONAL,
            "target_type": SOURCE_TYPE_RELATIONAL,
            "display_name": f"Grammar completeness: every otherwise-untested op ({glabel.lower()})",
        }

    return cfgs


_RAW_CONFIGS = _build_raw_configs()

# Wrap raw dicts in MigrationConfig — fails loudly at import time if any
# entry has a missing or extra key.
MIGRATION_CONFIGS: Dict[str, MigrationConfig] = {
    k: MigrationConfig(**v) for k, v in _RAW_CONFIGS.items()
}

