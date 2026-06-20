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

# PATH CONFIGURATION

# Base directory (project root)
BASE_DIR = Path(__file__).parent

# Tests directory (contains .smile migration scripts and test data)
TESTS_DIR = BASE_DIR / "tests"


# SOURCE/TARGET TYPE CONSTANTS
# Used throughout the codebase — never use raw strings for these.

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
    SOURCE_TYPE_GRAPH:      "Neo4j Cypher",
    SOURCE_TYPE_COLUMNAR:   "Cassandra CQL",
}


# Northwind source schema files keyed by product name (for web UI / inspector)
NORTHWIND_SCHEMA_FILES = {
    "postgresql": TESTS_DIR / "northwind_postgresql.sql",
    "mongodb":    TESTS_DIR / "northwind_mongodb.json",
    "neo4j":      TESTS_DIR / "northwind_neo4j.cypher",
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
    SOURCE_TYPE_GRAPH:      TESTS_DIR / "northwind_neo4j.cypher",
    SOURCE_TYPE_COLUMNAR:   TESTS_DIR / "northwind_cassandra.cql",
}

# Per-migration target schema files for two-layer validation
# Maps config_key prefix -> {target_type -> native file}
# Used when a migration direction has its own dedicated target file.
MIGRATION_TARGET_FILES = {
    # Northwind same-model evolution
    "northwind_r2r": TESTS_DIR / "northwind_r2r_target.sql",
    "northwind_d2d": TESTS_DIR / "northwind_d2d_target.json",
    "northwind_g2g": TESTS_DIR / "northwind_g2g_target.cypher",
    "northwind_c2c": TESTS_DIR / "northwind_c2c_target.cql",
}


# MIGRATION CONFIGURATIONS
# Define available migration scenarios with their source/target files.
# The literal dict below is kept for readability; the MigrationConfig
# wrapper at the bottom of this section enforces the schema.

_RAW_CONFIGS = {
    # =========================================================================
    # NORTHWIND — Same-Model Evolution (R→R, D→D, G→G, C→C)
    # =========================================================================

    # Northwind: PostgreSQL V1 -> PostgreSQL V2
    "northwind_r2r_specific": {
        "source_file": TESTS_DIR / "northwind_postgresql.sql",
        "smile_file": TESTS_DIR / "specific" / "northwind_pg1_to_pg2.smile",
        "source_type": SOURCE_TYPE_RELATIONAL,
        "target_type": SOURCE_TYPE_RELATIONAL,
        "display_name": "Northwind: PostgreSQL \u2192 PostgreSQL V2 (Specific)",
    },
    "northwind_r2r_generalized": {
        "source_file": TESTS_DIR / "northwind_postgresql.sql",
        "smile_file": TESTS_DIR / "generalized" / "northwind_pg1_to_pg2.smile_gen",
        "source_type": SOURCE_TYPE_RELATIONAL,
        "target_type": SOURCE_TYPE_RELATIONAL,
        "display_name": "Northwind: PostgreSQL \u2192 PostgreSQL V2 (Generalized)",
    },

    # Northwind: MongoDB V1 -> MongoDB V2
    "northwind_d2d_specific": {
        "source_file": TESTS_DIR / "northwind_mongodb.json",
        "smile_file": TESTS_DIR / "specific" / "northwind_mongo1_to_mongo2.smile",
        "source_type": SOURCE_TYPE_DOCUMENT,
        "target_type": SOURCE_TYPE_DOCUMENT,
        "display_name": "Northwind: MongoDB \u2192 MongoDB V2 (Specific)",
    },
    "northwind_d2d_generalized": {
        "source_file": TESTS_DIR / "northwind_mongodb.json",
        "smile_file": TESTS_DIR / "generalized" / "northwind_mongo1_to_mongo2.smile_gen",
        "source_type": SOURCE_TYPE_DOCUMENT,
        "target_type": SOURCE_TYPE_DOCUMENT,
        "display_name": "Northwind: MongoDB \u2192 MongoDB V2 (Generalized)",
    },

    # Northwind: Neo4j V1 -> Neo4j V2
    "northwind_g2g_specific": {
        "source_file": TESTS_DIR / "northwind_neo4j.cypher",
        "smile_file": TESTS_DIR / "specific" / "northwind_graph1_to_graph2.smile",
        "source_type": SOURCE_TYPE_GRAPH,
        "target_type": SOURCE_TYPE_GRAPH,
        "display_name": "Northwind: Neo4j \u2192 Neo4j V2 (Specific)",
    },
    "northwind_g2g_generalized": {
        "source_file": TESTS_DIR / "northwind_neo4j.cypher",
        "smile_file": TESTS_DIR / "generalized" / "northwind_graph1_to_graph2.smile_gen",
        "source_type": SOURCE_TYPE_GRAPH,
        "target_type": SOURCE_TYPE_GRAPH,
        "display_name": "Northwind: Neo4j \u2192 Neo4j V2 (Generalized)",
    },

    # Northwind: Cassandra V1 -> Cassandra V2
    "northwind_c2c_specific": {
        "source_file": TESTS_DIR / "northwind_cassandra.cql",
        "smile_file": TESTS_DIR / "specific" / "northwind_cass1_to_cass2.smile",
        "source_type": SOURCE_TYPE_COLUMNAR,
        "target_type": SOURCE_TYPE_COLUMNAR,
        "display_name": "Northwind: Cassandra \u2192 Cassandra V2 (Specific)",
    },
    "northwind_c2c_generalized": {
        "source_file": TESTS_DIR / "northwind_cassandra.cql",
        "smile_file": TESTS_DIR / "generalized" / "northwind_cass1_to_cass2.smile_gen",
        "source_type": SOURCE_TYPE_COLUMNAR,
        "target_type": SOURCE_TYPE_COLUMNAR,
        "display_name": "Northwind: Cassandra \u2192 Cassandra V2 (Generalized)",
    },

    # =========================================================================
    # NORTHWIND — Cross-Model Migration (grouped by source)
    # =========================================================================

    # --- From PostgreSQL ---
    "northwind_r2d_specific": {
        "source_file": TESTS_DIR / "northwind_postgresql.sql",
        "smile_file": TESTS_DIR / "specific" / "northwind_pg_to_mongo.smile",
        "source_type": SOURCE_TYPE_RELATIONAL,
        "target_type": SOURCE_TYPE_DOCUMENT,
        "display_name": "Northwind: PostgreSQL \u2192 MongoDB (Specific)",
    },
    "northwind_r2d_generalized": {
        "source_file": TESTS_DIR / "northwind_postgresql.sql",
        "smile_file": TESTS_DIR / "generalized" / "northwind_pg_to_mongo.smile_gen",
        "source_type": SOURCE_TYPE_RELATIONAL,
        "target_type": SOURCE_TYPE_DOCUMENT,
        "display_name": "Northwind: PostgreSQL \u2192 MongoDB (Generalized)",
    },
    "northwind_r2g_specific": {
        "source_file": TESTS_DIR / "northwind_postgresql.sql",
        "smile_file": TESTS_DIR / "specific" / "northwind_pg_to_neo4j.smile",
        "source_type": SOURCE_TYPE_RELATIONAL,
        "target_type": SOURCE_TYPE_GRAPH,
        "display_name": "Northwind: PostgreSQL \u2192 Neo4j (Specific)",
    },
    "northwind_r2g_generalized": {
        "source_file": TESTS_DIR / "northwind_postgresql.sql",
        "smile_file": TESTS_DIR / "generalized" / "northwind_pg_to_neo4j.smile_gen",
        "source_type": SOURCE_TYPE_RELATIONAL,
        "target_type": SOURCE_TYPE_GRAPH,
        "display_name": "Northwind: PostgreSQL \u2192 Neo4j (Generalized)",
    },
    "northwind_r2c_specific": {
        "source_file": TESTS_DIR / "northwind_postgresql.sql",
        "smile_file": TESTS_DIR / "specific" / "northwind_pg_to_cass.smile",
        "source_type": SOURCE_TYPE_RELATIONAL,
        "target_type": SOURCE_TYPE_COLUMNAR,
        "display_name": "Northwind: PostgreSQL \u2192 Cassandra (Specific)",
    },
    "northwind_r2c_generalized": {
        "source_file": TESTS_DIR / "northwind_postgresql.sql",
        "smile_file": TESTS_DIR / "generalized" / "northwind_pg_to_cass.smile_gen",
        "source_type": SOURCE_TYPE_RELATIONAL,
        "target_type": SOURCE_TYPE_COLUMNAR,
        "display_name": "Northwind: PostgreSQL \u2192 Cassandra (Generalized)",
    },

    # --- From MongoDB ---
    "northwind_d2r_specific": {
        "source_file": TESTS_DIR / "northwind_mongodb.json",
        "smile_file": TESTS_DIR / "specific" / "northwind_mongo_to_pg.smile",
        "source_type": SOURCE_TYPE_DOCUMENT,
        "target_type": SOURCE_TYPE_RELATIONAL,
        "display_name": "Northwind: MongoDB \u2192 PostgreSQL (Specific)",
    },
    "northwind_d2r_generalized": {
        "source_file": TESTS_DIR / "northwind_mongodb.json",
        "smile_file": TESTS_DIR / "generalized" / "northwind_mongo_to_pg.smile_gen",
        "source_type": SOURCE_TYPE_DOCUMENT,
        "target_type": SOURCE_TYPE_RELATIONAL,
        "display_name": "Northwind: MongoDB \u2192 PostgreSQL (Generalized)",
    },
    "northwind_d2g_specific": {
        "source_file": TESTS_DIR / "northwind_mongodb.json",
        "smile_file": TESTS_DIR / "specific" / "northwind_mongo_to_neo4j.smile",
        "source_type": SOURCE_TYPE_DOCUMENT,
        "target_type": SOURCE_TYPE_GRAPH,
        "display_name": "Northwind: MongoDB \u2192 Neo4j (Specific)",
    },
    "northwind_d2g_generalized": {
        "source_file": TESTS_DIR / "northwind_mongodb.json",
        "smile_file": TESTS_DIR / "generalized" / "northwind_mongo_to_neo4j.smile_gen",
        "source_type": SOURCE_TYPE_DOCUMENT,
        "target_type": SOURCE_TYPE_GRAPH,
        "display_name": "Northwind: MongoDB \u2192 Neo4j (Generalized)",
    },
    "northwind_d2c_specific": {
        "source_file": TESTS_DIR / "northwind_mongodb.json",
        "smile_file": TESTS_DIR / "specific" / "northwind_mongo_to_cass.smile",
        "source_type": SOURCE_TYPE_DOCUMENT,
        "target_type": SOURCE_TYPE_COLUMNAR,
        "display_name": "Northwind: MongoDB \u2192 Cassandra (Specific)",
    },
    "northwind_d2c_generalized": {
        "source_file": TESTS_DIR / "northwind_mongodb.json",
        "smile_file": TESTS_DIR / "generalized" / "northwind_mongo_to_cass.smile_gen",
        "source_type": SOURCE_TYPE_DOCUMENT,
        "target_type": SOURCE_TYPE_COLUMNAR,
        "display_name": "Northwind: MongoDB \u2192 Cassandra (Generalized)",
    },

    # --- From Neo4j ---
    "northwind_g2r_specific": {
        "source_file": TESTS_DIR / "northwind_neo4j.cypher",
        "smile_file": TESTS_DIR / "specific" / "northwind_neo4j_to_pg.smile",
        "source_type": SOURCE_TYPE_GRAPH,
        "target_type": SOURCE_TYPE_RELATIONAL,
        "display_name": "Northwind: Neo4j \u2192 PostgreSQL (Specific)",
    },
    "northwind_g2r_generalized": {
        "source_file": TESTS_DIR / "northwind_neo4j.cypher",
        "smile_file": TESTS_DIR / "generalized" / "northwind_neo4j_to_pg.smile_gen",
        "source_type": SOURCE_TYPE_GRAPH,
        "target_type": SOURCE_TYPE_RELATIONAL,
        "display_name": "Northwind: Neo4j \u2192 PostgreSQL (Generalized)",
    },
    "northwind_g2d_specific": {
        "source_file": TESTS_DIR / "northwind_neo4j.cypher",
        "smile_file": TESTS_DIR / "specific" / "northwind_neo4j_to_mongo.smile",
        "source_type": SOURCE_TYPE_GRAPH,
        "target_type": SOURCE_TYPE_DOCUMENT,
        "display_name": "Northwind: Neo4j \u2192 MongoDB (Specific)",
    },
    "northwind_g2d_generalized": {
        "source_file": TESTS_DIR / "northwind_neo4j.cypher",
        "smile_file": TESTS_DIR / "generalized" / "northwind_neo4j_to_mongo.smile_gen",
        "source_type": SOURCE_TYPE_GRAPH,
        "target_type": SOURCE_TYPE_DOCUMENT,
        "display_name": "Northwind: Neo4j \u2192 MongoDB (Generalized)",
    },
    "northwind_g2c_specific": {
        "source_file": TESTS_DIR / "northwind_neo4j.cypher",
        "smile_file": TESTS_DIR / "specific" / "northwind_neo4j_to_cass.smile",
        "source_type": SOURCE_TYPE_GRAPH,
        "target_type": SOURCE_TYPE_COLUMNAR,
        "display_name": "Northwind: Neo4j \u2192 Cassandra (Specific)",
    },
    "northwind_g2c_generalized": {
        "source_file": TESTS_DIR / "northwind_neo4j.cypher",
        "smile_file": TESTS_DIR / "generalized" / "northwind_neo4j_to_cass.smile_gen",
        "source_type": SOURCE_TYPE_GRAPH,
        "target_type": SOURCE_TYPE_COLUMNAR,
        "display_name": "Northwind: Neo4j \u2192 Cassandra (Generalized)",
    },

    # --- From Cassandra ---
    "northwind_c2r_specific": {
        "source_file": TESTS_DIR / "northwind_cassandra.cql",
        "smile_file": TESTS_DIR / "specific" / "northwind_cass_to_pg.smile",
        "source_type": SOURCE_TYPE_COLUMNAR,
        "target_type": SOURCE_TYPE_RELATIONAL,
        "display_name": "Northwind: Cassandra \u2192 PostgreSQL (Specific)",
    },
    "northwind_c2r_generalized": {
        "source_file": TESTS_DIR / "northwind_cassandra.cql",
        "smile_file": TESTS_DIR / "generalized" / "northwind_cass_to_pg.smile_gen",
        "source_type": SOURCE_TYPE_COLUMNAR,
        "target_type": SOURCE_TYPE_RELATIONAL,
        "display_name": "Northwind: Cassandra \u2192 PostgreSQL (Generalized)",
    },
    "northwind_c2d_specific": {
        "source_file": TESTS_DIR / "northwind_cassandra.cql",
        "smile_file": TESTS_DIR / "specific" / "northwind_cass_to_mongo.smile",
        "source_type": SOURCE_TYPE_COLUMNAR,
        "target_type": SOURCE_TYPE_DOCUMENT,
        "display_name": "Northwind: Cassandra \u2192 MongoDB (Specific)",
    },
    "northwind_c2d_generalized": {
        "source_file": TESTS_DIR / "northwind_cassandra.cql",
        "smile_file": TESTS_DIR / "generalized" / "northwind_cass_to_mongo.smile_gen",
        "source_type": SOURCE_TYPE_COLUMNAR,
        "target_type": SOURCE_TYPE_DOCUMENT,
        "display_name": "Northwind: Cassandra \u2192 MongoDB (Generalized)",
    },
    "northwind_c2g_specific": {
        "source_file": TESTS_DIR / "northwind_cassandra.cql",
        "smile_file": TESTS_DIR / "specific" / "northwind_cass_to_neo4j.smile",
        "source_type": SOURCE_TYPE_COLUMNAR,
        "target_type": SOURCE_TYPE_GRAPH,
        "display_name": "Northwind: Cassandra \u2192 Neo4j (Specific)",
    },
    "northwind_c2g_generalized": {
        "source_file": TESTS_DIR / "northwind_cassandra.cql",
        "smile_file": TESTS_DIR / "generalized" / "northwind_cass_to_neo4j.smile_gen",
        "source_type": SOURCE_TYPE_COLUMNAR,
        "target_type": SOURCE_TYPE_GRAPH,
        "display_name": "Northwind: Cassandra \u2192 Neo4j (Generalized)",
    },

    # ---------------------------------------------------------------------
    # Grammar-completeness suite \u2014 exercises the SMILE operations no other
    # test invokes, on a tiny synthetic schema. Pure smoke-test for handler
    # reachability (no native target file \u2192 L1/L2 validation returns N/A).
    # ---------------------------------------------------------------------
    "grammar_completeness_specific": {
        "source_file": TESTS_DIR / "grammar_completeness" / "source.sql",
        "smile_file":  TESTS_DIR / "grammar_completeness" / "test_all_unused.smile",
        "source_type": SOURCE_TYPE_RELATIONAL,
        "target_type": SOURCE_TYPE_RELATIONAL,
        "display_name": "Grammar completeness: every otherwise-untested op (specific)",
    },
    "grammar_completeness_generalized": {
        "source_file": TESTS_DIR / "grammar_completeness" / "source.sql",
        "smile_file":  TESTS_DIR / "grammar_completeness" / "test_all_unused.smile_gen",
        "source_type": SOURCE_TYPE_RELATIONAL,
        "target_type": SOURCE_TYPE_RELATIONAL,
        "display_name": "Grammar completeness: every otherwise-untested op (generalized)",
    },
}


# Wrap raw dicts in MigrationConfig — fails loudly at import time if any
# entry has a missing or extra key.
MIGRATION_CONFIGS: Dict[str, MigrationConfig] = {
    k: MigrationConfig(**v) for k, v in _RAW_CONFIGS.items()
}

