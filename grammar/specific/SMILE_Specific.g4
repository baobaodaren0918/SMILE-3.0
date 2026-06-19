/*
 * SMILE_Specific - Schema Migration & Evolution Language (Specific Operations Version)
 * A domain-specific language for database schema migration
 *
 * This version uses specific, independent keywords for each operation.
 * Each operation has its own dedicated keyword (e.g., ADD_PROPERTY, ADD_FOREIGN_KEY)
 *
 * Comparison: This is the "Specific" version. See SMILE_Generalized.g4 for the
 * "Generalized" version that uses parameterized operations (e.g., ADD PROPERTY).
 *
 * Supported database models: RELATIONAL, DOCUMENT, GRAPH, COLUMNAR
 * Design: from AC
 *
 * Example SMILE migration script:
 *   MIGRATION customer_migration:1.0
 *   FROM DOCUMENT TO RELATIONAL
 *   USING customer_schema VERSION 1.0
 *
 * Example SMILE evolution script:
 *   EVOLUTION customer_evolution:1.0
 *   FROM DOCUMENT TO DOCUMENT
 *   USING customer_schema VERSION 1.0 TO 2.0
 *
 *   -- Extract nested object to table
 *   FLATTEN customers.address AS address
 *   ADD_PRIMARY_KEY address_id TO address
 *   ADD_FOREIGN_KEY customer_id TO address REFERENCES customers(id)
 *
 *   -- Expand array to table
 *   UNWIND customers.tags[] INTO customer_tag
 *   ADD_PRIMARY_KEY id TO customer_tag
 *   ADD_FOREIGN_KEY customer_id TO customer_tag REFERENCES customers(id)
 */
grammar SMILE_Specific;

// ============================================================================
// PARSER RULES
// ============================================================================

// Entry point: migration script = header + operations
migration: header operation* EOF;
header: (migrationDecl | evolutionDecl) fromToDecl usingDecl;        // MIGRATION|EVOLUTION name:ver FROM type TO type USING schema VERSION ver
migrationDecl: MIGRATION identifier COLON version;                  // MIGRATION payment_migration:1.0
evolutionDecl: EVOLUTION identifier COLON version;                  // EVOLUTION payment_evolution:1.0
fromToDecl: FROM databaseType TO databaseType;                      // FROM RELATIONAL TO Document
usingDecl: USING identifier VERSION_KW version (TO version)?;       // USING iso20022_schema VERSION 1.0 [TO 2.0]
databaseType: RELATIONAL | DOCUMENT | GRAPH | COLUMNAR;             // Abstract database model types
version: VERSION_NUMBER | INTEGER_LITERAL;                          // 1 | 1.0 | 1.0.0

// ============================================================================
// OPERATIONS - Each operation is a separate, specific keyword
// ============================================================================
// Structure:  NEST, UNNEST, FLATTEN, UNFLATTEN, WIND, UNWIND
// Movement:   COPY, MOVE, MERGE, SPLIT
// Type:       CAST
// CRUD:       ADD_*, DELETE_*, RENAME_*

operation: add_property | add_foreign_key | add_embedded | add_entity
         | add_primary_key | add_unique_key
         | add_partition_key | add_clustering_key
         | add_label
         | add_constraint
         | delete_property | delete_foreign_key | delete_embedded | delete_entity
         | delete_primary_key | delete_unique_key
         | delete_partition_key | delete_clustering_key
         | delete_label
         | delete_constraint
         | rename_property | rename_entity
         | flatten | unflatten | unwind | wind | nest | unnest
         | copy_property | copy_entity | move_property | merge | split | cast_property | cast_constraint | cast_entity | recard
         | transform
;

// ============================================================================
// ADD OPERATIONS - Specific keywords for each type
// ============================================================================

// ADD_PROPERTY: Add new property to entity
// Example: ADD_PROPERTY email TO Customer WITH TYPE String NOT NULL
add_property: ADD_PROPERTY identifier (TO qualifiedName)? propertyClause*;
propertyClause: withTypeClause | withDefaultClause | notNullClause;
withTypeClause: WITH TYPE dataType;
withDefaultClause: WITH DEFAULT literal;
notNullClause: NOT_NULL;

// ADD_FOREIGN_KEY: Add foreign key constraint (SQL-style)
// Single-column form (entity.field implicit):
//   Example: ADD_FOREIGN_KEY address.customer_id REFERENCES customers(customer_id)
//   Example: ADD_FOREIGN_KEY orders.customer_id REFERENCES customers(id) WITH CARDINALITY ONE_TO_MANY
// Composite form ((cols) TO source_entity, target list-of-columns):
//   Example: ADD_FOREIGN_KEY (tenant_id, item_id) TO sales REFERENCES tenants_items(tenant_id, item_id)
// Both source and target accept multiple columns; lengths must match in the handler.
add_foreign_key: ADD_FOREIGN_KEY keyColumns (TO qualifiedName)? REFERENCES qualifiedName LPAREN identifierList RPAREN constraintClause*;
constraintClause: withCardinalityClause | usingKeyClause | whereClause;

// ADD_EMBEDDED: Add embedded object relationship (MongoDB style)
// Example: ADD_EMBEDDED address TO Customer WITH CARDINALITY ONE_TO_ONE
add_embedded: ADD_EMBEDDED identifier TO qualifiedName embeddedClause*;
embeddedClause: withCardinalityClause | withStructureClause;
withStructureClause: WITH STRUCTURE LPAREN identifierList RPAREN;

// ADD_ENTITY: Add new entity/table or edge (relationship type)
// Example: ADD_ENTITY Product WITH PROPERTIES (id String, name String)
// Example: ADD_ENTITY CONTAINS FROM orders TO products WITH PROPERTIES (unitPrice Decimal, quantity Integer)
// Example: ADD_ENTITY REPORTS_TO FROM employees TO employees WITH CARDINALITY ONE_TO_MANY
add_entity: ADD_ENTITY identifier (FROM qualifiedName TO qualifiedName)? (WITH CARDINALITY cardinalityType)? entityClause*;
entityClause: withPropertiesClause | withKeyClause;
withKeyClause: WITH KEY identifier;

// ADD_PRIMARY_KEY: Add primary key constraint
// Example: ADD_PRIMARY_KEY address.address_id AS String  (new explicit entity.field syntax)
// Example: ADD_PRIMARY_KEY (id1, id2) TO Customer  (composite key)
// Example: ADD_PRIMARY_KEY id TO Customer WITH TYPE UUID (legacy TO syntax)
// Note: AS dataType is a simplified alternative to WITH TYPE dataType
// Note: keyColumns now supports qualifiedName (entity.field) for explicit entity specification
add_primary_key: ADD_PRIMARY_KEY keyColumns (AS dataType)? (TO qualifiedName)? keyClause*;

// ADD_UNIQUE_KEY: Add unique constraint
// Example: ADD_UNIQUE_KEY email TO Customer
add_unique_key: ADD_UNIQUE_KEY keyColumns (AS dataType)? (TO qualifiedName)? keyClause*;

// ADD_PARTITION_KEY: Add partition key (Cassandra - columnar)
// Example: ADD_PARTITION_KEY user_id TO UserActivity
add_partition_key: ADD_PARTITION_KEY keyColumns (AS dataType)? (TO qualifiedName)? keyClause*;

// ADD_CLUSTERING_KEY: Add clustering key (Cassandra - columnar)
// Example: ADD_CLUSTERING_KEY timestamp TO UserActivity
add_clustering_key: ADD_CLUSTERING_KEY keyColumns (AS dataType)? (TO qualifiedName)? keyClause*;

// ADD_LABEL: Add label to node (graph database)
// Example: ADD_LABEL Employee TO customers
add_label: ADD_LABEL identifier TO qualifiedName;

// Key columns - qualifiedName (entity.field) or parenthesized list for composite keys
keyColumns: qualifiedName | LPAREN identifierList RPAREN;

// Key constraint clauses
keyClause: referencesClause | withColumnsClause | withTypeClause;
referencesClause: REFERENCES qualifiedName LPAREN identifierList RPAREN;
withColumnsClause: WITH COLUMNS LPAREN identifierList RPAREN;

// ============================================================================
// DELETE OPERATIONS - Specific keywords for each type
// ============================================================================

// DELETE_PROPERTY: Remove property from entity
// Example: DELETE_PROPERTY Customer.email
delete_property: DELETE_PROPERTY qualifiedName;

// DELETE_FOREIGN_KEY: Remove foreign key constraint
// Example: DELETE_FOREIGN_KEY Customer.order_id
delete_foreign_key: DELETE_FOREIGN_KEY qualifiedName;

// DELETE_EMBEDDED: Remove embedded object relationship
// Example: DELETE_EMBEDDED Customer.address
delete_embedded: DELETE_EMBEDDED qualifiedName;

// DELETE_ENTITY: Remove entire entity/table
// Example: DELETE_ENTITY Customer
delete_entity: DELETE_ENTITY qualifiedName;

// DELETE_PRIMARY_KEY: Delete primary key constraint
// Example: DELETE_PRIMARY_KEY id FROM Customer
delete_primary_key: DELETE_PRIMARY_KEY keyColumns (FROM qualifiedName)?;

// DELETE_UNIQUE_KEY: Delete unique constraint
// Example: DELETE_UNIQUE_KEY email FROM Customer
delete_unique_key: DELETE_UNIQUE_KEY keyColumns (FROM qualifiedName)?;

// DELETE_PARTITION_KEY: Delete partition key
// Example: DELETE_PARTITION_KEY user_id FROM UserActivity
delete_partition_key: DELETE_PARTITION_KEY keyColumns (FROM qualifiedName)?;

// DELETE_CLUSTERING_KEY: Delete clustering key
// Example: DELETE_CLUSTERING_KEY timestamp FROM UserActivity
delete_clustering_key: DELETE_CLUSTERING_KEY keyColumns (FROM qualifiedName)?;

// DELETE_LABEL: Delete label from node
// Example: DELETE_LABEL Employee FROM customers
delete_label: DELETE_LABEL identifier FROM qualifiedName;

// ============================================================================
// RENAME OPERATIONS - Specific keywords for each type
// ============================================================================

// RENAME_PROPERTY: Rename property within an entity
// Example: RENAME_PROPERTY email TO contact_email IN Customer
rename_property: RENAME_PROPERTY identifier TO identifier (IN qualifiedName)?;

// RENAME_ENTITY: Rename entity/table
// Example: RENAME_ENTITY Customer TO Client
rename_entity: RENAME_ENTITY qualifiedName TO qualifiedName;

// ============================================================================
// STRUCTURE OPERATIONS
// ============================================================================

// FLATTEN - Flatten nested object fields into parent table (reduce depth by 1)
// Reference: AC - "Die Operation FLATTEN erstellt aus dem Objekt in der Spalte
//            jeweils eine Spalte für jedes Attribut dieses Objekts"
// Example: FLATTEN customers.address
//   Before: customers { name: { first_name, last_name }, age }
//   After:  customers { name_first_name, name_last_name, age }
flatten: FLATTEN qualifiedName;

// UNFLATTEN - Combine flat fields into nested object (reverse of FLATTEN)
// Example: UNFLATTEN customers:first_name, last_name AS name
//   Before: customers { first_name, last_name, age }
//   After:  customers { name: { first_name, last_name }, age }
unflatten: UNFLATTEN qualifiedName COLON identifierList AS identifier;

// UNNEST - Extract nested object to separate table (normalization)
// Example: UNNEST customers.address:street,city AS address WITH customers.customer_id TO address.customer_id
// Example with multiple carry fields:
//   UNNEST customers.employment:position AS employment
//       WITH customers.customer_id TO employment.customer_id, customers.dept_id TO employment.dept_id
//   - 'street,city' are properties to extract
//   - WITH clause: copy fields from source to new table (can carry multiple fields)
//   - WITH is optional, for cases where no parent fields need to be copied
//   Before: customers { customer_id, address: { street, city } }
//   After:  customers { customer_id }
//           address { customer_id, street, city }
// Note: Use separate ADD_PRIMARY_KEY, ADD_FOREIGN_KEY for constraints
unnest: UNNEST qualifiedName COLON unnestFieldList AS identifier (WITH unnestCarryList)?;

// Carry list for UNNEST: fields to copy from source to new table
unnestCarryList: unnestCarryField (COMMA unnestCarryField)*;
unnestCarryField: qualifiedName TO qualifiedName;

// Field list for UNNEST: supports both properties and nested objects (recursive)
// - identifier: regular property (e.g., position, name, street, city)
// - identifier{...}: nested object with its contents (e.g., company{name, address{street, city}})
unnestFieldList: unnestField (COMMA unnestField)*;
unnestField: identifier                                    # SimpleField
           | identifier LBRACE unnestFieldList RBRACE      # NestedField
           ;

// UNWIND - Expand array field into multiple rows
// Reference: AC - array expansion operation
// Supports two modes:
//   1. Expand in place: UNWIND customer_tag.tags (expands array within existing table)
//   2. Create new table: UNWIND customers.tags[] INTO customer_tag (legacy, creates new table)
// Note: Use separate ADD_PRIMARY_KEY, ADD_FOREIGN_KEY, RENAME_PROPERTY for constraints
unwind: UNWIND qualifiedName (INTO identifier)?;

// WIND - Convert scalar property back to array (reverse of UNWIND)
// Syntax: WIND customer_tag.tags
// Cross-entity movement is handled by MERGE, not WIND.
wind: WIND qualifiedName;

// NEST - Merge separate table into embedded document (PostgreSQL -> MongoDB)
// Example: NEST address:street,city IN customers.address WHERE address.customer_id = customers.customer_id
//   - 'address' is source entity
//   - ':street,city' are properties to embed
//   - 'IN customers.address' specifies target (customers entity, address field)
//   - WHERE clause specifies join condition
// Note: source entity is not removed automatically; use DELETE_ENTITY explicitly when desired.
nest: NEST qualifiedName COLON unnestFieldList IN qualifiedName WHERE equalityOnlyCondition;

// ============================================================================
// SIMPLE OPERATIONS
// ============================================================================

// COPY_PROPERTY: Duplicate a property to another entity (keeps original)
// Example: COPY_PROPERTY name FROM customers TO other WHERE other.customer_id = customers.id
copy_property: COPY_PROPERTY identifier FROM qualifiedName TO qualifiedName WHERE condition;

// COPY_ENTITY: Duplicate an entire entity with all its structure (properties, keys, constraints)
// Reference: PRISM "COPY TABLE R INTO S", CoDEL "Addtable(S, R)"
// Example: COPY_ENTITY customers AS employee
// Example: COPY_ENTITY works_at AS employed_at FROM customers TO company  (copy EDGE with explicit endpoints)
copy_entity: COPY_ENTITY qualifiedName AS identifier (FROM qualifiedName TO qualifiedName)?;

// MOVE_PROPERTY: Relocate a property to another entity (removes original)
// Example: MOVE_PROPERTY name FROM customers TO other WHERE other.customer_id = customers.id
move_property: MOVE_PROPERTY identifier FROM qualifiedName TO qualifiedName WHERE condition;

// MERGE: Combine two entities into one new entity
// Example: MERGE A, B WHERE A.id = B.id INTO C AS alias
merge: MERGE qualifiedName COMMA qualifiedName WHERE condition INTO identifier (AS identifier)?;

// SPLIT: Divide one entity into multiple separate entities (vertical partitioning)
// Reference: AC - "SPLIT Person into Person:id, firstname, lastname AND knows:id, knows"
// Example: SPLIT customers INTO customers:customer_id, first_name, last_name, age; customer_tag:customer_id, tags
//   Before: customers { customer_id, first_name, last_name, age, tags[] }
//   After:  customers { customer_id, first_name, last_name, age }
//          customer_tag { customer_id, tags[] }
// Note: Fields can be duplicated across parts (e.g., customer_id in both parts)
split: SPLIT qualifiedName INTO splitPart (SEMICOLON splitPart)+;
splitPart: identifier COLON identifierList;

// CAST_PROPERTY: Change the data type of a property
// Example: CAST_PROPERTY Entity.field TO Integer
cast_property: CAST_PROPERTY qualifiedName TO dataType;

// CAST_CONSTRAINT: Change the type of a constraint
// Reference: Orion "Cast Reference" - change the type of a constraint
// Example: CAST_CONSTRAINT customers.email TO UNIQUE KEY
// Example: CAST_CONSTRAINT customers.city TO PARTITION KEY
cast_constraint: CAST_CONSTRAINT qualifiedName TO constraintKeyType;

// ADD_CONSTRAINT: Add a constraint that is NOT covered by the narrow operators
// (i.e. ADD_PRIMARY_KEY / ADD_UNIQUE_KEY / ADD_FOREIGN_KEY / ADD_PARTITION_KEY /
//  ADD_CLUSTERING_KEY / ADD_LABEL). Three branches:
//   AS REFERENCE         -> Reference(is_enforced=False)  (Mongo cross-coll, Cass denorm)
//   AS CHECK <expr>      -> CheckConstraint with structured AST
//   AS EXISTENCE         -> ExistenceConstraint (post-hoc NOT NULL)
// Examples:
//   ADD_CONSTRAINT orders.customer_id AS REFERENCE TO customers(_id) WITH CARDINALITY ONE_TO_MANY
//   ADD_CONSTRAINT products.price AS CHECK price > 0
//   ADD_CONSTRAINT orders.shipped_date AS CHECK RAW "shipped_date IS NULL OR shipped_date >= order_date"
//   ADD_CONSTRAINT customers.contact_name AS EXISTENCE
add_constraint: ADD_CONSTRAINT qualifiedName AS constraintBody;

constraintBody
    : REFERENCE TO qualifiedName LPAREN identifierList RPAREN (WITH CARDINALITY cardinalityType)?  # ConstraintBodyReference
    | CHECK checkExpr                                                                                # ConstraintBodyCheck
    | EXISTENCE                                                                                      # ConstraintBodyExistence
    ;
// ADD_CONSTRAINT REFERENCE is always non-enforced; for SQL-traditional
// enforced foreign keys (including composite keys), use ``ADD_FOREIGN_KEY``
// directly. A previous design also exposed an ``ENFORCED`` alias here, but
// it was removed to keep one canonical, paradigm-honest entry point per
// constraint kind.

// DELETE_CONSTRAINT: Remove the constraint attached to entity.field. Handler
// inspects the entity to determine which constraint kind (logical Reference,
// CheckConstraint, ExistenceConstraint) is currently attached and removes it.
// Example: DELETE_CONSTRAINT orders.customer_id
delete_constraint: DELETE_CONSTRAINT qualifiedName;

// CHECK expression mini-grammar.
// Operator precedence (low -> high): OR < AND < NOT < atom.
// RAW gives the user a string-literal escape hatch that adapter visitors may
// pass through verbatim (PG) or wrap in $expr / description (Mongo / others).
checkExpr
    : LPAREN checkExpr RPAREN                       # CheckParenExpr
    | NOT checkExpr                                  # CheckNotExpr
    | checkExpr AND checkExpr                        # CheckAndExpr
    | checkExpr OR checkExpr                         # CheckOrExpr
    | RAW STRING_LITERAL                             # CheckRawExpr
    | checkAtom                                      # CheckAtomExpr
    ;

checkAtom
    : qualifiedName cmpOp literal                                # CmpAtom
    | qualifiedName IN LPAREN literalList RPAREN                 # InAtom
    | qualifiedName BETWEEN literal AND literal                  # BetweenAtom
    | qualifiedName MATCHES STRING_LITERAL                       # RegexAtom
    | qualifiedName IS NULL                                      # IsNullAtom
    | qualifiedName IS NOT_NULL                                  # IsNotNullAtom
    ;

cmpOp: LT | GT | LTE | GTE | EQ | NEQ;

literalList: literal (COMMA literal)*;

// CAST_ENTITY: Change the entity_kind of an entity type (cross-paradigm type conversion)
// Example: CAST_ENTITY orders TO DOCUMENT
// Example: CAST_ENTITY customers TO GRAPH
// Note: Overrides automatic entity_kind normalization for this entity
// Note: For VERTEX<->EDGE conversion, use TRANSFORM instead
cast_entity: CAST_ENTITY qualifiedName TO databaseType;

// RECARD: Change the multiplicity/cardinality of a reference
// Reference: Orion "Mult Reference" - change the multiplicity of a reference
// Example: RECARD customers.address_id TO ONE_TO_MANY
recard: RECARD qualifiedName TO cardinalityType;

// TRANSFORM: Transform entity between node and relationship (Graph database)
// Reference: Hausler et al. - "transform a node with its features into a relationship" / vice versa
// Example: TRANSFORM works_at INTO RELATIONSHIP FROM customers TO company
// Example: TRANSFORM works_at INTO RELATIONSHIP FROM customers TO company WITH CARDINALITY ZERO_TO_MANY
// Example: TRANSFORM works_at INTO ENTITY
transform: TRANSFORM qualifiedName INTO transformTarget;
transformTarget: RELATIONSHIP FROM qualifiedName TO qualifiedName (WITH CARDINALITY cardinalityType)?   # TransformToRelationship
              | ENTITY                                                                            # TransformToEntity
              ;

// ============================================================================
// SHARED CLAUSES - Reusable clause definitions
// ============================================================================

// Cardinality (relationship multiplicity)
withCardinalityClause: WITH CARDINALITY cardinalityType;
usingKeyClause: USING KEY identifier;
whereClause: WHERE condition;

// Entity clauses (for ADD_ENTITY)
// WITH PROPERTIES (name String, age Integer) - each property has name and type
withPropertiesClause: WITH PROPERTIES LPAREN propertyDefList RPAREN;
propertyDefList: propertyDef (COMMA propertyDef)*;
propertyDef: identifier dataType;

// Identifier list
identifierList: identifier (COMMA identifier)*;

// ============================================================================
// COMMON TYPES - Shared type definitions
// ============================================================================

// Cardinality notation
cardinalityType: ONE_TO_ONE | ONE_TO_MANY | ZERO_TO_ONE | ZERO_TO_MANY;

// Constraint key type (for CAST_CONSTRAINT)
constraintKeyType: PRIMARY KEY | UNIQUE KEY | PARTITION KEY | CLUSTERING KEY | NODE KEY | DOCUMENT_ID;

// Data types
dataType: STRING | TEXT | INT | INTEGER | LONG | DOUBLE | FLOAT | DECIMAL
        | BOOLEAN | DATE | DATETIME | TIMESTAMP | UUID | BINARY | identifier;

// Path and identifiers
qualifiedName: pathSegment (DOT pathSegment)*;
pathSegment: identifier (LBRACKET RBRACKET)?;
identifier: IDENTIFIER;

// Condition (simplified for schema migration)
// Two leaf forms: property equality (a = b) for relational/document/columnar,
// and an edge join (a -[:REL]-> b) for graph, where the correspondence is a
// relationship rather than a shared key.
condition: equalityCondition
         | edgeCondition
         | condition AND condition
         | LPAREN condition RPAREN;
// Equality-only condition for NEST. NEST infers embedding cardinality and the
// absorbed FK from the equality's FK-bearing side, which an edge join does not
// expose, so the edge form is excluded here at the grammar level.
equalityOnlyCondition: equalityCondition
         | equalityOnlyCondition AND equalityOnlyCondition
         | LPAREN equalityOnlyCondition RPAREN;
equalityCondition: qualifiedName EQUALS qualifiedName;
edgeCondition: qualifiedName EDGE_LEFT identifier EDGE_RIGHT qualifiedName;

// Literals
literal: STRING_LITERAL | INTEGER_LITERAL | DECIMAL_LITERAL | TRUE | FALSE | NULL;

// ============================================================================
// LEXER RULES
// ============================================================================

// ----------------------------------------------------------------------------
// KEYWORDS - Reserved words in SMILE_Specific
// ----------------------------------------------------------------------------
MIGRATION: 'MIGRATION'; EVOLUTION: 'EVOLUTION'; VERSION_KW: 'VERSION';
FROM: 'FROM'; TO: 'TO'; USING: 'USING'; AS: 'AS';
INTO: 'INTO'; WITH: 'WITH'; WHERE: 'WHERE'; IN: 'IN'; KEY: 'KEY'; AND: 'AND';
ON: 'ON';

// Database model types
RELATIONAL: 'RELATIONAL'; DOCUMENT: 'DOCUMENT'; GRAPH: 'GRAPH'; COLUMNAR: 'COLUMNAR';

// Structure operations
NEST: 'NEST'; UNNEST: 'UNNEST'; FLATTEN: 'FLATTEN'; UNFLATTEN: 'UNFLATTEN';
UNWIND: 'UNWIND'; WIND: 'WIND';

// Simple operations
COPY_PROPERTY: 'COPY_PROPERTY'; COPY_ENTITY: 'COPY_ENTITY'; MOVE_PROPERTY: 'MOVE_PROPERTY'; MERGE: 'MERGE'; SPLIT: 'SPLIT';
CAST_PROPERTY: 'CAST_PROPERTY'; CAST_CONSTRAINT: 'CAST_CONSTRAINT'; CAST_ENTITY: 'CAST_ENTITY'; RECARD: 'RECARD';
TRANSFORM: 'TRANSFORM'; RELATIONSHIP: 'RELATIONSHIP'; BETWEEN: 'BETWEEN';

// ADD operations - specific keywords
ADD_PROPERTY: 'ADD_PROPERTY';
ADD_EMBEDDED: 'ADD_EMBEDDED';
ADD_ENTITY: 'ADD_ENTITY';
ADD_PRIMARY_KEY: 'ADD_PRIMARY_KEY';
ADD_FOREIGN_KEY: 'ADD_FOREIGN_KEY';
ADD_UNIQUE_KEY: 'ADD_UNIQUE_KEY';
ADD_PARTITION_KEY: 'ADD_PARTITION_KEY';
ADD_CLUSTERING_KEY: 'ADD_CLUSTERING_KEY';
ADD_LABEL: 'ADD_LABEL';
ADD_CONSTRAINT: 'ADD_CONSTRAINT';

// DELETE operations - specific keywords
DELETE_PROPERTY: 'DELETE_PROPERTY';
DELETE_EMBEDDED: 'DELETE_EMBEDDED';
DELETE_ENTITY: 'DELETE_ENTITY';
DELETE_PRIMARY_KEY: 'DELETE_PRIMARY_KEY';
DELETE_FOREIGN_KEY: 'DELETE_FOREIGN_KEY';
DELETE_UNIQUE_KEY: 'DELETE_UNIQUE_KEY';
DELETE_PARTITION_KEY: 'DELETE_PARTITION_KEY';
DELETE_CLUSTERING_KEY: 'DELETE_CLUSTERING_KEY';
DELETE_LABEL: 'DELETE_LABEL';
DELETE_CONSTRAINT: 'DELETE_CONSTRAINT';

// RENAME operations - specific keywords
RENAME_PROPERTY: 'RENAME_PROPERTY';
RENAME_ENTITY: 'RENAME_ENTITY';


// Shared keywords
RENAME: 'RENAME';

// Structural keywords
STRUCTURE: 'STRUCTURE';

// Feature types
PROPERTY_TOKEN: 'PROPERTY'; EMBEDDED: 'EMBEDDED';
ENTITY: 'ENTITY'; VALUE: 'VALUE';
LABEL: 'LABEL';

// Entity/Variation clauses
PROPERTIES: 'PROPERTIES';

// Key types
PRIMARY: 'PRIMARY'; UNIQUE: 'UNIQUE';
PARTITION: 'PARTITION'; CLUSTERING: 'CLUSTERING';
NODE: 'NODE'; DOCUMENT_ID: 'DOCUMENT_ID';
REFERENCE: 'REFERENCE'; REFERENCES: 'REFERENCES'; COLUMNS: 'COLUMNS';

// Cardinality
CARDINALITY: 'CARDINALITY';
ONE_TO_ONE: 'ONE_TO_ONE'; ONE_TO_MANY: 'ONE_TO_MANY';
ZERO_TO_ONE: 'ZERO_TO_ONE'; ZERO_TO_MANY: 'ZERO_TO_MANY';

// Data types
STRING: 'String'; TEXT: 'Text'; INT: 'Int'; INTEGER: 'Integer'; LONG: 'Long';
DOUBLE: 'Double'; FLOAT: 'Float'; DECIMAL: 'Decimal'; BOOLEAN: 'Boolean';
DATE: 'Date'; DATETIME: 'DateTime'; TIMESTAMP: 'Timestamp'; UUID: 'UUID'; BINARY: 'Binary';
TYPE: 'TYPE'; DEFAULT: 'DEFAULT'; SERIAL: 'SERIAL'; PREFIX: 'PREFIX';

// Constraints
// NOT_NULL keeps its own multi-word literal form ('NOT NULL' as a single
// token); ANTLR's longest-match rule means "NOT NULL" is preferred over
// the shorter NOT token introduced below for CHECK expression composition.
NOT_NULL: 'NOT NULL';
NOT: 'NOT';
OR: 'OR';
IS: 'IS';
MATCHES: 'MATCHES';
RAW: 'RAW';

// ADD_CONSTRAINT body keywords
EXISTENCE: 'EXISTENCE';
CHECK: 'CHECK';

// Literals
TRUE: 'true' | 'TRUE'; FALSE: 'false' | 'FALSE'; NULL: 'null' | 'NULL';

// Symbols
EDGE_LEFT: '-[:'; EDGE_RIGHT: ']->';
COLON: ':'; SEMICOLON: ';'; COMMA: ','; DOT: '.'; LPAREN: '('; RPAREN: ')'; LBRACKET: '['; RBRACKET: ']';
LBRACE: '{'; RBRACE: '}';
EQUALS: '=';
// Comparison operators for CHECK atoms. Note: '==' must be declared before '=' so the
// lexer picks the longer match for "==".
EQ: '==';
NEQ: '!=';
LTE: '<=';
GTE: '>=';
LT: '<';
GT: '>';

// ----------------------------------------------------------------------------
// PATTERNS
// ----------------------------------------------------------------------------
VERSION_NUMBER: [0-9]+ '.' [0-9]+ ('.' [0-9]+)?;
INTEGER_LITERAL: [0-9]+;
DECIMAL_LITERAL: [0-9]+ '.' [0-9]+;
STRING_LITERAL: '\'' (~['\r\n] | '\'\'')* '\'' | '"' (~["\r\n] | '""')* '"';
IDENTIFIER: [a-zA-Z_][a-zA-Z0-9_]*;

// ----------------------------------------------------------------------------
// SKIP - Whitespace and comments
// ----------------------------------------------------------------------------
LINE_COMMENT: '--' ~[\r\n]* -> skip;
BLOCK_COMMENT: '/*' .*? '*/' -> skip;
WS: [ \t\r\n]+ -> skip;
