# SMILE - Schema Migration and Evolution Language

A formally defined DSL for schema migration and evolution between heterogeneous database systems, supporting 4 data models with a full 4×4 migration matrix, three-layer automated validation, and a metamodel integrity check.

## Supported Database Models

| Model | Representative DB | Schema Format | Entity Kind |
|-------|-------------------|---------------|-------------|
| **Relational** | PostgreSQL | SQL DDL (`.sql`) | TABLE |
| **Document** | MongoDB | JSON Schema (`.json`) | DOCUMENT |
| **Graph** | Neo4j | GraphQL SDL (`.graphql`) | VERTEX / EDGE |
| **Columnar** | Cassandra | CQL (`.cql`) | WIDE_COLUMN_TABLE |

## Installation

### Prerequisites
- Python 3.10+
- ANTLR 4.13.2

### Setup
```bash
git clone <anonymized-repository-url>
cd SMILE-3.0

python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
```

## Usage

### Web Interface
```bash
python web_server.py
# Opens at http://localhost:5601
```

The web interface provides five tabs:
- **Source Schemas** — inspect any of the 4 native schemas (SQL, JSON, GraphQL SDL, CQL) and the resulting Meta V1
- **User Transformation** — point at a source DDL, pick a target DB, generate a SMILE header, edit the script in the in-browser Ace editor (autocomplete + syntax highlighting), validate, then run; the resulting Meta V2 and Target Schema panels are rendered read-only
- **Schema Comparison** — side-by-side card view of Meta V1 vs Meta V2 with structural diff highlighting
- **SMILE Script** — script rendering and syntax-highlighted preview for any registered migration config
- **Migration / Evolution Process** — full pipeline run (parse → transform → export → validate) with step-by-step operation log and Layer 1 / Layer 2 / Layer 3 validation results

### CLI
```bash
set PYTHONIOENCODING=utf-8  # Windows (for Unicode arrows in display)
python main.py
```

### Programmatic Usage
```python
from core import run_migration

# Cross-model migration (Northwind)
result = run_migration('northwind_r2d_specific')    # Relational -> Document
result = run_migration('northwind_d2g_generalized') # Document -> Graph
result = run_migration('northwind_g2c_specific')    # Graph -> Columnar

# Same-model evolution (Northwind)
result = run_migration('northwind_r2r_specific')    # Relational V1 -> V2

print(result['exported_target'])       # Generated target schema
print(result['validation_layer0'])     # Layer Preparation I: script execution
print(result['validation_integrity'])  # Layer Preparation II: metamodel integrity check
print(result['validation_meta'])       # Layer 1 validation result
print(result['validation_export'])     # Layer 2 validation result
print(result['validation_text_diff'])  # Layer 3 validation result
print(result['validation_blame'])      # Verdict: ok / smile_script / adapter / text_diff / ...
```

### Run Tests
```bash
python -m pytest tests/ -q
# 151 tests:
#   * test_full_flow.py                       — 34 (32 Northwind + 2 grammar-completeness)
#   * test_parser.py                          — 34 (specific + generalized)
#   * test_negative.py                        — 28 (graceful-failure surfaces)
#   * test_nested_paths.py                    — 28 (nested-path resolution)
#   * test_specific_generalized_equivalence.py — 17 (cross-grammar IR equivalence)
#   * test_diff_and_invariants.py              — 5  (diff engine + invariants)
#   * test_relationship_trace.py               — 5  (FK -> edge cardinality trace)

python -m pytest tests/test_full_flow.py -k r2d -q
# Run only tests matching a keyword
```

## Migration Matrix

### Full 4×4 Matrix (16 directions)

|  | → Relational | → Document | → Graph | → Columnar |
|--|:---:|:---:|:---:|:---:|
| **Relational →** | R2R | R2D | R2G | R2C |
| **Document →** | D2R | D2D | D2G | D2C |
| **Graph →** | G2R | G2D | G2G | G2C |
| **Columnar →** | C2R | C2D | C2G | C2C |

- Diagonal (R2R, D2D, G2G, C2C) = **same-model evolution**
- Off-diagonal = **cross-model migration**
- Each direction has both **Specific** (`.smile`) and **Generalized** (`.smile_gen`) grammar variants = **32 Northwind configs**

In addition to the 32 Northwind configs, the registry includes a **grammar-completeness** pair (specific + generalized) that exercises the operations not naturally hit by the Northwind matrix — **34 configs in total**.

### Test Dataset: Northwind

The Northwind dataset (8 entities: orders, products, customers, employees, categories, suppliers, shippers, order\_details) exists as 4 independent native schema files:

| Native File | Model |
|-------------|-------|
| `tests/northwind_postgresql.sql` | Relational |
| `tests/northwind_mongodb.json` | Document |
| `tests/northwind_neo4j.graphql` | Graph |
| `tests/northwind_cassandra.cql` | Columnar |

## Project Structure

```
SMILE/
├── grammar/
│   ├── specific/                      # Specific grammar (dedicated underscore-form keywords)
│   │   ├── SMILE_Specific.g4
│   │   └── generate_parser.bat
│   ├── generalized/                   # Generalized grammar (verb + object composition)
│   │   ├── SMILE_Generalized.g4
│   │   └── generate_parser.bat
│   ├── smile_operations.json          # Single source of truth for all 38 ops
│   │                                  #   (used by editor autocomplete)
│   └── antlr-4.13.2-complete.jar
├── Schema/
│   ├── unified_meta_schema.py         # M-Model+ Meta Schema
│   └── adapters/
│       ├── __init__.py                # ADAPTER_REGISTRY
│       ├── postgresql_adapter.py      # PostgreSQL RE/FE
│       ├── mongodb_adapter.py         # MongoDB RE/FE
│       ├── neo4j_adapter.py           # Neo4j RE/FE
│       └── cassandra_adapter.py       # Cassandra RE/FE
├── static/
│   └── smile-app.js                   # Web UI app code (extracted from web_server.py)
├── tests/
│   ├── northwind_*.sql/json/graphql/cql # 4 source schemas (Northwind, all 4 paradigms)
│   ├── northwind_*_target.*             # Same-model evolution targets (V2)
│   ├── specific/                        # 16 Specific scripts (.smile)
│   ├── generalized/                     # 16 Generalized scripts (.smile_gen)
│   ├── grammar_completeness/            # source.sql + test_all_unused.smile
│   │                                    #   (exercises the ops not hit by the matrix)
│   ├── test_full_flow.py                # 34 end-to-end tests (32 Northwind + 2 grammar-completeness)
│   ├── test_parser.py                   # 34 parser tests (specific + generalized)
│   └── test_negative.py                 # 28 graceful-failure tests
│                                        #   (OpParams validation, handler skip
│                                        #    reasons, malformed scripts, etc.)
├── core/                              # SchemaTransformer + pipeline orchestration
│   ├── __init__.py                    #   public re-exports (run_migration, ...)
│   ├── transformer.py                 #   SchemaTransformerBase + @register_handler
│   ├── pipeline.py                    #   run_load / run_apply / run_export / run_migration
│   ├── normalization.py               #   _calculate_changes + entity-kind / cardinality passes
│   ├── serialization.py               #   db_to_dict / parse_original_source helpers
│   └── handlers/                      #   32 handlers split into 4 mixin files
│       ├── structural.py              #     NEST/UNNEST/FLATTEN/UNFLATTEN/WIND/UNWIND
│       ├── crud.py                    #     ADD/DELETE/RENAME × {PROPERTY,ENTITY,EMBEDDED} + COPY/MOVE
│       ├── keys_constraints.py        #     FK/KEY/LABEL/CAST_CONSTRAINT/RECARD/TRANSFORM
│       └── reshape.py                 #     MERGE/SPLIT/CAST_PROPERTY/CAST_ENTITY
├── parser/                            # SMILE script parsing
│   ├── factory.py                     #   parse_smile_auto (grammar auto-detect by extension)
│   ├── listeners.py                   #   ANTLR listeners (Specific + Generalized)
│   └── params.py                      #   Per-op param dataclasses (NestParams, ...)
├── validation/                        # Preparation I/II + three-layer + blame-attribution validators
│   ├── integrity.py                   #   Layer Preparation II: metamodel integrity (dangling UUIDs, UP uniqueness)
│   ├── meta.py                        #   Layer 1: Meta V2 vs expected schema (PIM)
│   ├── export.py                      #   Layer 2: Export → re-parse round-trip (PSM round-trip)
│   ├── text_diff.py                   #   Layer 3: Exported text vs target file (set-based)
│   └── pipeline.py                    #   Wraps Preparation I/II + L1/L2/L3; assigns blame
│                                      #     (ok | smile_script | adapter | text_diff | both | script_failed | unverifiable)
├── diff/                              # Unified diff engine + two formatter shapes
│   ├── engine.py                      #   compute_diff (single source of truth)
│   ├── formatters.py                  #   to_ui_changes (per-op panel)
│   │                                  #   to_validation_report (Layer 1 report)
│   └── __init__.py
├── schema_inspector.py                # Reverse-engineer any source DDL → Meta V1 (web UI only)
├── script_renderer.py                 # Emits SMILE header for /api/generate_script (body left to user)
├── config.py                          # Migration registry (34 configs: 32 Northwind + 2 grammar-completeness)
├── main.py                            # CLI entry point
└── web_server.py                      # Web interface (http.server, port 5601)
```

## Architecture

### Five-Phase Pipeline

```
 Source Schema        SMILE Script (.smile/.smile_gen)         Target Schema
 (SQL/JSON/                      │                          (SQL/JSON/
 GraphQL/CQL)                    │                          GraphQL/CQL)
      │                          ▼                                ▲
      │                   ┌──────────────┐                        │
      │                   │   Phase 2    │                        │
      │                   │ SMILE Parsing │                        │
      │                   │  (ANTLR 4)   │                        │
      │                   └──────┬───────┘                        │
      ▼                     Operations                            │
 ┌──────────┐  Meta V1  ┌──────────────┐  Meta V2  ┌──────────┐  │
 │ Phase 1  │──────────►│   Phase 3    │──────────►│ Phase 4  │──┘
 │ Reverse  │           │SchemaTransf. │           │ Forward  │
 │ Engineer │           │ (32 handlers)│           │ Engineer │
 └──────────┘           └──────────────┘           └──────────┘
                               │                        │
                               ▼                        ▼
          ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
          │   Phase 5   │ │   Phase 5   │ │   Phase 5   │
          │  Layer 1    │ │  Layer 2    │ │  Layer 3    │
          │ Meta V2 vs  │ │ Round-trip  │ │ Text-level  │
          │  expected   │ │ vs expected │ │ vs target   │
          └─────────────┘ └─────────────┘ └─────────────┘
```

| Phase | Component | Input → Output |
|-------|-----------|---------------|
| 1. Reverse Engineering | `ADAPTER_REGISTRY[source_type]` (driven by `core.run_load`) | Native DDL → Meta V1 (M-Model+) |
| 2. SMILE Parsing | `parser.factory.parse_smile_auto()` | `.smile` / `.smile_gen` → `Operation` list |
| 3. Transformation | `SchemaTransformer` (32 handlers, called via `core.run_apply`) | Meta V1 + Operations → Meta V2 |
| 4. Forward Engineering | `ADAPTER_REGISTRY[target_type]` (driven by `core.run_export`) | Meta V2 → Target DDL |
| 5. Validation | `validation.integrity` + `validation.meta` + `validation.export` + `validation.text_diff` (composed by `validation.pipeline`) | Layer Preparation II (integrity) + three-layer correctness check + blame attribution |

`core.run_migration()` is a thin orchestrator on top of the three pipeline helpers (`run_load`, `run_apply`, `run_export`) so each phase can also be invoked independently from the web UI's User Transformation flow.

### Validation Pipeline (Preparation I/II + Layer 1/2/3)

Two preparation steps run before the three thesis-documented correctness layers. Preparation I gates script execution; Preparation II asserts metamodel internal consistency. Layer 1/2/3 are the authoritative correctness gates and are the layers referenced in the thesis.

| Layer | File | What it proves | How |
|-------|------|---------------|-----|
| **Preparation I** | `validation/pipeline.py` (`derive_layer0`) | SMILE script executed cleanly | No `error` or `skipped` ops, ≥1 entity in result |
| **Preparation II** | `validation/integrity.py` | Metamodel is internally consistent (no dangling UUID pointers, UP.meta_id unique across DB) | Scan FK/UP/CHECK/EXISTENCE pointers + UP meta_id uniqueness |
| **Layer 1** | `validation/meta.py` | SMILE script correctness (PIM equivalence) | Meta V2 vs parsed expected target |
| **Layer 2** | `validation/export.py` | Adapter forward-engineering correctness (PSM round-trip, Foster PUT-GET law) | `parse(export(Meta V2))` vs parsed expected target |
| **Layer 3** | `validation/text_diff.py` | Adapter output alignment with hand-written native (PSM style) | Exported text vs target file text under set-based normalization |
| **Blame**   | `validation/pipeline.py` | Which side failed | `ok` / `smile_script` (L1) / `adapter` (L2) / `text_diff` (L3) / `both` / `script_failed` / `unverifiable` |

Preparation II is a non-blocking diagnostic: integrity violations are surfaced but do not influence the `blame` verdict, because Layer 1/2 are the authoritative correctness gates. If integrity ever fails while L1/L2 pass, the metamodel is "right by chance" and the test suite asserts `passed is True` to catch this regression class.

#### Dual-Role Validation Diagram

The 4 native files form a closed validation loop: each file plays both the **source role** (outgoing migrations) and the **target / ground-truth role** (incoming migrations). The diagram below shows the forward (PG → Mongo) and reverse (Mongo → PG) cases side-by-side.

```
  ╔══════════════════════════════════════════════════════════════════╗
  ║ (a) Direction A:  PG  →  Mongo                                   ║
  ╚══════════════════════════════════════════════════════════════════╝

  source role          target / ground truth
  ┌─────────────┐      ┌─────────────┐ ◄·············┐
  │ northwind_  │      │ northwind_  │               ┊
  │postgresql.  │      │  mongodb.   │               ┊
  │    sql      │      │    json     │               ┊
  └──────┬──────┘      └──────┬──────┘               ┊
         │ parse(PG)          │ parse(Mongo)         ┊
         ▼                    ▼                      ┊
    ┌─────────┐          ┌─────────┐                 ┊
    │   M₁    │          │    X    │                 ┊
    └────┬────┘          └────┬────┘                 ┊
         │ Apply               │                     ┊
         │pg_to_mongo.smile    │                     ┊
         ▼                     │                     ┊
    ┌─────────┐ ···· L1 ·····► │                     ┊  L3 (text)
    │   M₂    │   (PIM)        │                     ┊  E vs target
    └────┬────┘                │                     ┊  file
         │ export(Mongo)       │                     ┊
         ▼                     │                     ┊
    ┌─────────┐                                      ┊
    │    E    │·····································┘
    │ (file)  │
    └────┬────┘
         │ parse(Mongo)
         ▼
    ┌─────────┐ ···· L2 ·····► X (reused)
    │    R    │  (round-trip)
    └─────────┘


  ╔══════════════════════════════════════════════════════════════════╗
  ║ (b) Direction B:  Mongo  →  PG                                   ║
  ╚══════════════════════════════════════════════════════════════════╝

  source role          target / ground truth
  ┌─────────────┐      ┌─────────────┐ ◄·············┐
  │ northwind_  │      │ northwind_  │               ┊
  │  mongodb.   │      │postgresql.  │               ┊
  │    json     │      │    sql      │               ┊
  └──────┬──────┘      └──────┬──────┘               ┊
         │ parse(Mongo)       │ parse(PG)            ┊
         ▼                    ▼                      ┊
    ┌─────────┐          ┌─────────┐                 ┊
    │   M₁    │          │    X    │                 ┊
    └────┬────┘          └────┬────┘                 ┊
         │ Apply               │                     ┊
         │mongo_to_pg.smile    │                     ┊
         ▼                     │                     ┊
    ┌─────────┐ ···· L1 ·····► │                     ┊  L3 (text)
    │   M₂    │   (PIM)        │                     ┊  E vs target
    └────┬────┘                │                     ┊  file
         │ export(PG)          │                     ┊
         ▼                     │                     ┊
    ┌─────────┐                                      ┊
    │    E    │·····································┘
    │ (file)  │
    └────┬────┘
         │ parse(PG)
         ▼
    ┌─────────┐ ···· L2 ·····► X (reused)
    │    R    │  (round-trip)
    └─────────┘
```

In direction (a), `northwind_mongodb.json` serves as the target / ground truth. In direction (b), the same file serves as the source. No manually written ground truth is needed for any of the 12 cross-paradigm scenarios.

For **same-model** evolution (e.g., r2r), dedicated V2 target files (`northwind_r2r_target.sql`, etc.) serve as expected output.

#### Why Layer 2 and Layer 3 are both kept

Layer 3 is logically stronger than Layer 2 (text equivalence implies meta equivalence under deterministic parsing), but Layer 2 is retained because it (a) directly instantiates Foster (2007)'s PUT-GET law for bidirectional transformations, (b) serves as an independent cross-check against bugs in Layer 3's per-paradigm normalizers, and (c) is paradigm-independent — a new adapter automatically gets Layer 2 coverage without writing a new Layer 3 normalizer.

### M-Model+ Meta Schema

The hub representation (`Schema/unified_meta_schema.py`) that makes cross-model migration possible:

```
Database
  └── EntityType (TABLE / DOCUMENT / EMBEDDED / VERTEX / EDGE / WIDE_COLUMN_TABLE)
        ├── Property (name, data_type, is_key, is_optional)
        ├── Constraint
        │     ├── UniqueConstraint (PK: simple / partition / clustering)
        │     └── ForeignKeyConstraint
        └── Relationship (ABC)
              ├── Reference (FK → target entity)
              ├── Embedded (nested object / array)
              └── Edge (graph relationship)
```

## SMILE Operations (38 surface ops)

The grammar exposes 38 named operations grouped as **9 structural + 6 property + 4 entity + 13 key/constraint + 2 type/cardinality + 4 embedded/label**. Many of them collapse at the IR level — e.g. `ADD_PRIMARY_KEY` / `ADD_UNIQUE_KEY` / `ADD_PARTITION_KEY` / `ADD_CLUSTERING_KEY` all dispatch through a single `_handle_add_key` — so the four mixin files in `core/handlers/` (`structural.py`, `crud.py`, `keys_constraints.py`, `reshape.py`) jointly register the unique handler methods via the `@register_handler` decorator. The single source of truth for the surface op set is `grammar/smile_operations.json` (also consumed by the web-UI Ace autocomplete).

### Structural Operations (9)

| Operation | Description | Typical Use |
|-----------|-------------|-------------|
| `NEST` | Embed entity as nested object | R→D: table → embedded document |
| `UNNEST` | Extract nested object to entity | D→R: embedded → table |
| `FLATTEN` | Merge child fields into parent | D→R: flatten nested address |
| `UNFLATTEN` | Group flat fields into nested object | R→D: columns → sub-object |
| `WIND` | Convert scalar to array | R→D: column → array |
| `UNWIND` | Expand array to rows/entity | D→R: array → table |
| `MERGE` | Combine two entities | R2R: denormalize |
| `SPLIT` | Partition entity vertically | R2R: split table |
| `TRANSFORM` | Entity ↔ Relationship conversion | R↔G: table ↔ edge |

### Property Operations (6)

| Operation | Description |
|-----------|-------------|
| `ADD_PROPERTY` | Add field to entity |
| `DELETE_PROPERTY` | Remove field from entity |
| `RENAME_PROPERTY` | Rename field |
| `COPY_PROPERTY` | Copy field to another entity |
| `MOVE_PROPERTY` | Move field to another entity |
| `CAST_PROPERTY` | Change property data type |

### Entity Operations (4)

| Operation | Description |
|-----------|-------------|
| `ADD_ENTITY` | Create new entity (supports EDGE with FROM...TO) |
| `DELETE_ENTITY` | Remove entity (cleans up cross-references) |
| `RENAME_ENTITY` | Rename entity (updates all references) |
| `COPY_ENTITY` | Deep-copy entity structure |

### Key & Constraint Operations (13)

| Operation | Description |
|-----------|-------------|
| `ADD_PRIMARY_KEY` / `DELETE_PRIMARY_KEY` | Add or remove a primary key |
| `ADD_UNIQUE_KEY` / `DELETE_UNIQUE_KEY` | Add or remove a unique constraint |
| `ADD_FOREIGN_KEY` / `DELETE_FOREIGN_KEY` | Add (with `REFERENCES` + cardinality) or remove an FK |
| `ADD_PARTITION_KEY` / `DELETE_PARTITION_KEY` | Cassandra-specific partition key |
| `ADD_CLUSTERING_KEY` / `DELETE_CLUSTERING_KEY` | Cassandra-specific clustering key |
| `CAST_CONSTRAINT` | Change constraint type (e.g., `UNIQUE` → `PARTITION`) |
| `ADD_CONSTRAINT` | Generic constraint creator covering the kinds the narrow operators don't address. Three `AS` branches: `REFERENCE TO <target>(<col>)` for non-enforced cross-entity refs (Mongo cross-collection, Cassandra denormalised columns, self-references — enforced FKs use `ADD_FOREIGN_KEY` instead), `CHECK <expr>` for value-domain predicates with structured atoms (`>`, `<`, `==`, `!=`, `IN`, `BETWEEN`, `MATCHES`, `IS [NOT] NULL`) plus `AND` / `OR` / `NOT` composition and a `RAW "..."` escape hatch, and `EXISTENCE` for post-hoc `NOT NULL`. |
| `DELETE_CONSTRAINT` | Remove the `ADD_CONSTRAINT`-produced object (logical Reference, CheckConstraint, ExistenceConstraint) anchored at `<entity.field>`. Narrow-operator constraints (`PK`/`FK`/`UNIQUE`/`PARTITION`/`CLUSTERING`/`LABEL`) are managed by their own `DELETE_*` siblings. |

### Type & Cardinality Operations (2)

| Operation | Description |
|-----------|-------------|
| `CAST_ENTITY` | Change entity kind (e.g., TABLE → DOCUMENT) |
| `RECARD` | Change the **target-end** cardinality of a relationship (`source_end_cardinality` is preserved; SMILE has no source-end grammar clause) |

### Embedded & Label Operations (4)

| Operation | Description |
|-----------|-------------|
| `ADD_EMBEDDED` / `DELETE_EMBEDDED` | Add/remove embedded relationship |
| `ADD_LABEL` / `DELETE_LABEL` | Add/remove graph node label |

## Grammar Variants

Two functionally equivalent grammars — same abstract syntax, different concrete syntax:

| Grammar | Extension | Keywords | Example |
|---------|-----------|----------|---------|
| **Specific** | `.smile` | 38 dedicated | `ADD_PROPERTY email TO customers WITH TYPE String` |
| **Generalized** | `.smile_gen` | 27 composable | `ADD PROPERTY email TO customers WITH TYPE String` |

The Generalized grammar reduces keyword count by ~29% through verb+object composition (6 verbs × 5 object types + modifiers). Structural operations (`NEST`, `UNNEST`, `FLATTEN`, `UNFLATTEN`, `WIND`, `UNWIND`, `MERGE`, `SPLIT`, `TRANSFORM`) are identical in both variants.

## Canonical Script Style for Key Operations

The grammar accepts several syntactic forms for the same semantic key operation (e.g. `AS Type` versus `WITH TYPE Type`, dotted `entity.field` versus `field TO entity`). The 32 Northwind scripts shipped with this project follow a single self-consistent convention based on **whether the column already exists** at the point the key is declared. New scripts are recommended to follow the same convention; the alternative forms remain valid for backward compatibility but are not used in canonical examples.

### Primary Key

| Situation | Specific | Generalized |
|-----------|----------|-------------|
| New entity / column does not yet exist | `ADD_PRIMARY_KEY entity.field AS Type` | `ADD KEY entity.field AS Type` |
| Existing entity, existing column (promote to PK) | `ADD_PRIMARY_KEY field TO entity` | `ADD KEY field TO entity` |
| Composite primary key | `ADD_PRIMARY_KEY (col1, col2) TO entity` | `ADD KEY (col1, col2) TO entity` |

The `AS Type` form auto-creates the property when the named column is absent, using the supplied data type. The `TO entity` form attaches a primary-key constraint to columns that already exist on the entity (typically added earlier in the script via `ADD_PROPERTY`, `SPLIT`, or `WITH PROPERTIES` on `ADD_ENTITY`).

### Cassandra Partition / Clustering Keys

The same column-existence rule applies. `AS Type` is omitted in current scripts because Cassandra key columns are always pre-declared:

```smile
ADD_PARTITION_KEY field TO entity
ADD_PARTITION_KEY (col1, col2) TO entity
ADD_CLUSTERING_KEY field TO entity
```

Generalized form replaces the underscore prefix with a space: `ADD PARTITION KEY ...`, `ADD CLUSTERING KEY ...`.

### Foreign Key

```smile
ADD_FOREIGN_KEY entity.field REFERENCES target(col)                    -- single column
ADD_FOREIGN_KEY (col1, col2) TO entity REFERENCES target(c1, c2)       -- composite
```

The composite form requires the explicit `TO entity` because the parenthesised column list is not dotted. Single-column FKs use the dotted `entity.field` form and need no `TO` clause. Add `WITH CARDINALITY <ZERO|ONE>_TO_<ONE|MANY>` after the `REFERENCES(...)` clause to make the target-end (referenced-side) multiplicity explicit.

## SMILE Script Examples

Cross-paradigm scripts open with the `MIGRATION` keyword; same-paradigm V1→V2 evolution scripts open with `EVOLUTION`. Both forms parse to the same `Operation` list internally and share every operator.

### Cross-Model: Relational → Document (R2D)

```smile
MIGRATION northwind_pg_to_mongo:1.0
FROM RELATIONAL TO DOCUMENT
USING adapted_northwind_schema VERSION 1

-- Embed tables as nested objects (deepest first)
NEST categories:category_name, description IN products.category
  WHERE products.category_id = categories.category_id
NEST suppliers:company_name, contact_name, ... IN products.supplier
  WHERE products.supplier_id = suppliers.supplier_id

-- Group flat shipping fields into nested object
UNFLATTEN orders:ship_address, ship_city, ship_region, ship_postal_code, ship_country
  AS ship_destination

-- Rename PK for MongoDB convention
RENAME_PROPERTY order_id TO _id IN orders
```

### Same-Model Evolution: Relational V1 → V2 (R2R)

```smile
EVOLUTION northwind_r2r:1.0
FROM RELATIONAL TO RELATIONAL
USING adapted_northwind_schema VERSION 1 TO 2

-- Denormalize: merge categories into products
DELETE_FOREIGN_KEY products.category_id
DELETE_PRIMARY_KEY category_id FROM categories
MERGE categories, products WHERE products.category_id = categories.category_id INTO products
DELETE_PROPERTY products.category_id

-- Vertical partition: split customer contacts
SPLIT customers INTO customers:customer_id, company_name, street, city, region,
  postal_code, country; customer_contacts:customer_id, contact_name, contact_title,
  phone, fax

-- Add new entities for territory management
-- (Named sales_region to disambiguate from the address.region column
--  that already exists in customers/employees/suppliers.)
ADD_ENTITY sales_region WITH PROPERTIES (region_id String, region_description String)
ADD_ENTITY territories WITH PROPERTIES (territory_id String, territory_description String, region_id String)
```

## Regenerating Parsers

After modifying `.g4` grammar files:

```bash
cd grammar/specific
java -jar ..\antlr-4.13.2-complete.jar -Dlanguage=Python3 -visitor SMILE_Specific.g4

cd grammar/generalized
java -jar ..\antlr-4.13.2-complete.jar -Dlanguage=Python3 -visitor SMILE_Generalized.g4
```

## License

MIT License
