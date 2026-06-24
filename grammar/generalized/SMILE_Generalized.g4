/*
 * SMILE_Generalized - Schema Migration & Evolution Language (Generalized Operations Version)
 * A domain-specific language for database schema migration
 *
 * This version uses generalized, parameterized operations.
 * Operations use a base keyword with parameters (e.g., ADD PROPERTY, ADD FOREIGN KEY)
 *
 * Comparison: This is the "Generalized" version. See SMILE_Specific.g4
 * for the "Specific" version that uses independent keywords for each operation.
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
 *   ADD PRIMARY KEY address_id TO address
 *   ADD FOREIGN KEY customer_id TO address REFERENCES customers(id)
 *
 *   -- Expand array to table
 *   UNWIND customers.tags[] INTO customer_tag
 *   ADD PRIMARY KEY id TO customer_tag
 *   ADD FOREIGN KEY customer_id TO customer_tag REFERENCES customers(id)
 */
grammar SMILE_Generalized;

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
// OPERATIONS - Generalized operations with parameters
// ============================================================================
// Structure:  NEST, UNNEST, FLATTEN, UNFLATTEN, WIND, UNWIND
// Movement:   COPY, MOVE, MERGE, SPLIT
// Type:       CAST
// CRUD:       ADD, DELETE, RENAME

operation: nest_gen | unnest_gen | flatten_gen | unflatten_gen | unwind_gen | wind_gen
         | copy_gen | move_gen | merge_gen | split_gen | cast_gen | recard_gen
         | transform_gen
         | add_gen | delete_gen | rename_gen;

// ============================================================================
// ADD - Generalized ADD operation with type parameter
// ============================================================================
// Supports adding:
//   - PROPERTY:     Add new property to entity
//   - FOREIGN KEY:  Add foreign key constraint (SQL-style REFERENCES syntax)
//   - EMBEDDED:     Add embedded object relationship (MongoDB style)
//   - ENTITY:       Add new entity/table
//   - KEY:          Add primary/unique/partition/clustering key
//
// Example: ADD PROPERTY email TO Customer WITH TYPE String NOT NULL
// Example: ADD PRIMARY KEY id TO Customer
// Example: ADD FOREIGN KEY order.customer_id REFERENCES customer(id)
// Example: ADD ENTITY CONTAINS FROM orders TO products WITH PROPERTIES (unitPrice Decimal)

add_gen: ADD (propertyAdd | foreignKeyAdd | embeddedAdd | entityAdd
        | keyAdd | labelAdd | constraintAdd);

// Add property: ADD PROPERTY email TO Customer WITH TYPE String NOT NULL
propertyAdd: PROPERTY identifier (TO qualifiedName)? propertyClause*;
propertyClause: withTypeClause | withDefaultClause | notNullClause;
withTypeClause: WITH TYPE dataType;
withDefaultClause: WITH DEFAULT literal;
notNullClause: NOT_NULL;

// Add foreign key: ADD FOREIGN KEY <columns> [TO entity] REFERENCES target_table(<columns>)
// Single-column form (entity.field implicit):
//   Example: ADD FOREIGN KEY address.customer_id REFERENCES customers(customer_id)
//   Example: ADD FOREIGN KEY orders.customer_id REFERENCES customers(id) WITH CARDINALITY ONE_TO_MANY
// Composite form ((cols) TO source_entity, target list-of-columns):
//   Example: ADD FOREIGN KEY (tenant_id, item_id) TO sales REFERENCES tenants_items(tenant_id, item_id)
foreignKeyAdd: FOREIGN KEY keyColumns (TO qualifiedName)? REFERENCES qualifiedName LPAREN identifierList RPAREN constraintClause*;
constraintClause: withCardinalityClause | usingKeyClause | whereClause;

// Add embedded: ADD EMBEDDED address TO Customer WITH CARDINALITY ONE_TO_ONE
embeddedAdd: EMBEDDED identifier TO qualifiedName embeddedClause*;
embeddedClause: withCardinalityClause | withStructureClause;
withStructureClause: WITH STRUCTURE LPAREN identifierList RPAREN;

// Add entity: ADD ENTITY Product WITH PROPERTIES (id String, name String)
// Add edge:   ADD ENTITY CONTAINS FROM orders TO products WITH PROPERTIES (unitPrice Decimal)
// Add edge:   ADD ENTITY REPORTS_TO FROM employees TO employees WITH CARDINALITY ONE_TO_MANY
entityAdd: ENTITY identifier (FROM qualifiedName TO qualifiedName)? (WITH CARDINALITY cardinalityType)? entityClause*;
entityClause: withPropertiesClause | withKeyClause;
withKeyClause: WITH KEY identifier;

// Add key: ADD KEY entity.field AS String (explicit entity.field syntax)
// Or full form: ADD PRIMARY KEY id TO Customer WITH TYPE UUID (legacy TO syntax)
// Example: ADD KEY address.address_id AS String  (new explicit syntax)
// Example: ADD PRIMARY KEY (id1, id2) TO Customer (composite key)
keyAdd: keyType? KEY keyColumns (AS dataType)? (TO qualifiedName)? keyClause*;
// Note: keyType is optional, defaults to PRIMARY KEY when omitted
// Note: AS dataType is a simplified alternative to WITH TYPE dataType
// Note: keyColumns now supports qualifiedName (entity.field) for explicit entity specification

// Key columns - qualifiedName (entity.field) or parenthesized list for composite keys
keyColumns: qualifiedName | LPAREN identifierList RPAREN;

// Add label (Graph): ADD LABEL Employee TO customers
labelAdd: LABEL identifier TO qualifiedName;

// Add constraint: covers constraint kinds NOT addressed by the narrow operators
// (PRIMARY KEY / UNIQUE KEY / FOREIGN KEY / PARTITION KEY / CLUSTERING KEY / LABEL).
//   ADD CONSTRAINT orders.customer_id AS REFERENCE TO customers(_id) WITH CARDINALITY ONE_TO_MANY
//   ADD CONSTRAINT products.price AS CHECK price > 0
//   ADD CONSTRAINT orders.shipped_date AS CHECK RAW "shipped_date IS NULL OR shipped_date >= order_date"
//   ADD CONSTRAINT customers.contact_name AS EXISTENCE
constraintAdd: CONSTRAINT qualifiedName AS constraintBody;

constraintBody
    : REFERENCE TO qualifiedName LPAREN identifierList RPAREN (WITH CARDINALITY cardinalityType)?  # ConstraintBodyReference
    | CHECK checkExpr                                                                                # ConstraintBodyCheck
    | EXISTENCE                                                                                      # ConstraintBodyExistence
    ;
// ADD CONSTRAINT REFERENCE is always non-enforced — see specific-grammar
// counterpart for the rationale (enforced FKs go through ADD FOREIGN KEY).

// CHECK expression mini-grammar — operator precedence (low -> high): OR < AND < NOT < atom.
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

// ============================================================================
// DELETE - Generalized DELETE operation with type parameter
// ============================================================================
// Supports deleting:
//   - PROPERTY:    Remove property from entity
//   - FOREIGN KEY: Remove foreign key constraint
//   - EMBEDDED:    Remove embedded object relationship
//   - ENTITY:      Remove entire entity/table
//   - KEY:         Remove key constraints (PRIMARY, UNIQUE, PARTITION, CLUSTERING)
//   - LABEL:       Remove label
//
// Example: DELETE PROPERTY Customer.email
// Example: DELETE PRIMARY KEY id FROM Customer

delete_gen: DELETE (propertyDelete | foreignKeyDelete | embeddedDelete | entityDelete
          | keyDelete | labelDelete | constraintDelete);

// Delete property: DELETE PROPERTY Customer.email
propertyDelete: PROPERTY qualifiedName;

// Delete foreign key: DELETE FOREIGN KEY Customer.order_id
foreignKeyDelete: FOREIGN KEY qualifiedName;

// Delete embedded: DELETE EMBEDDED Customer.address
embeddedDelete: EMBEDDED qualifiedName;

// Delete entity: DELETE ENTITY Customer
entityDelete: ENTITY qualifiedName;

// Delete key: DELETE PRIMARY KEY id FROM Customer
keyDelete: keyType KEY keyColumns (FROM qualifiedName)?;

// Delete label: DELETE LABEL Employee FROM customers
labelDelete: LABEL identifier FROM qualifiedName;

// Delete constraint: DELETE CONSTRAINT entity.field
//   Handler inspects the entity to determine which constraint kind
//   (logical Reference / CheckConstraint / ExistenceConstraint) is currently
//   attached and removes it.
// Example: DELETE CONSTRAINT orders.customer_id
constraintDelete: CONSTRAINT qualifiedName;

// ============================================================================
// RENAME - Generalized RENAME operation with type parameter
// ============================================================================
// Supports renaming:
//   - Property: RENAME PROPERTY oldName TO newName IN Entity
//   - Entity:   RENAME ENTITY OldName TO NewName
//
// Example: RENAME PROPERTY email TO contact_email IN Customer

rename_gen: RENAME (propertyRename | entityRename);

// Rename property: RENAME PROPERTY oldName TO newName IN Entity
propertyRename: PROPERTY identifier TO identifier (IN qualifiedName)?;

// Rename entity: RENAME ENTITY OldName TO NewName
entityRename: ENTITY qualifiedName TO qualifiedName;

// ----------------------------------------------------------------------------
// KEY TYPES - Constraint types for different database models
// ----------------------------------------------------------------------------
// Matches PKTypeEnum in unified_meta_schema.py (from AC)
//
//   PRIMARY:    Standard primary key (all databases)
//   UNIQUE:     Unique constraint (all databases)
//   PARTITION:  Partition key (Cassandra - columnar)
//   CLUSTERING: Clustering key (Cassandra - columnar)
// Note: FOREIGN KEY uses its own rule (foreignKeyAdd / foreignKeyDelete) with REFERENCES clause.
//
keyType: PRIMARY | UNIQUE | PARTITION | CLUSTERING;
keyClause: referencesClause | withColumnsClause | withTypeClause;
referencesClause: REFERENCES qualifiedName LPAREN identifierList RPAREN;
withColumnsClause: WITH COLUMNS LPAREN identifierList RPAREN;
identifierList: identifier (COMMA identifier)*;

// ============================================================================
// STRUCTURE OPERATIONS
// ============================================================================

// FLATTEN - Flatten nested object fields into parent table (reduce depth by 1)
// Reference: AC - "Die Operation FLATTEN erstellt aus dem Objekt in der Spalte
//            jeweils eine Spalte für jedes Attribut dieses Objekts"
// Example: FLATTEN customers.address
//   Before: customers { name: { first_name, last_name }, age }
//   After:  customers { name_first_name, name_last_name, age }
flatten_gen: FLATTEN qualifiedName;

// UNFLATTEN - Combine flat fields into nested object (reverse of FLATTEN)
// Example: UNFLATTEN customers:first_name, last_name AS name
//   Before: customers { first_name, last_name, age }
//   After:  customers { name: { first_name, last_name }, age }
unflatten_gen: UNFLATTEN qualifiedName COLON identifierList AS identifier;

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
// Note: Use separate ADD KEY, ADD FOREIGN KEY for constraints
unnest_gen: UNNEST qualifiedName COLON unnestFieldList AS identifier (WITH unnestCarryList)?;

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
// Note: Use separate ADD KEY, ADD FOREIGN KEY, RENAME PROPERTY for constraints
unwind_gen: UNWIND qualifiedName (INTO identifier)?;

// WIND - Convert scalar property back to array (reverse of UNWIND)
// Syntax: WIND customer_tag.tags
// Cross-entity movement is handled by MERGE, not WIND.
wind_gen: WIND qualifiedName;

// NEST - Merge separate table into embedded document (PostgreSQL -> MongoDB)
// Example: NEST address:street,city IN customers.address WHERE address.customer_id = customers.customer_id
//   - 'address' is source entity
//   - ':street,city' are properties to embed
//   - 'IN customers.address' specifies target (customers entity, address field)
//   - WHERE clause specifies join condition
// Note: source entity is not removed automatically; use DELETE ENTITY explicitly when desired.
nest_gen: NEST qualifiedName COLON unnestFieldList IN qualifiedName WHERE equalityOnlyCondition;

// ============================================================================
// SIMPLE OPERATIONS
// ============================================================================

// COPY: Duplicate a property or entity
// Example: COPY PROPERTY email FROM customers TO employee WHERE employee.customer_id = customers.id
// Example: COPY ENTITY customers AS employee
// Example: COPY ENTITY works_at AS employed_at FROM customers TO company  (copy EDGE with explicit endpoints)
copy_gen: COPY (entityCopy | propertyCopy);
propertyCopy: PROPERTY identifier FROM qualifiedName TO qualifiedName WHERE condition;
entityCopy: ENTITY qualifiedName AS identifier (FROM qualifiedName TO qualifiedName)?;

// MOVE: Relocate a property to another entity (removes original)
// Example: MOVE PROPERTY email FROM customers TO employee WHERE employee.customer_id = customers.id
move_gen: MOVE PROPERTY identifier FROM qualifiedName TO qualifiedName WHERE condition;

// MERGE: Combine two entities into one new entity
// Example: MERGE A, B WHERE A.id = B.id INTO C AS alias
merge_gen: MERGE qualifiedName COMMA qualifiedName WHERE condition INTO identifier (AS identifier)?;

// SPLIT: Divide one entity into multiple separate entities (vertical partitioning)
// Reference: AC - "SPLIT Person into Person:id, firstname, lastname AND knows:id, knows"
// Example: SPLIT customers INTO customers:customer_id, first_name, last_name, age; customer_tag:customer_id, tags
//   Before: customers { customer_id, first_name, last_name, age, tags[] }
//   After:  customers { customer_id, first_name, last_name, age }
//          customer_tag { customer_id, tags[] }
// Note: Fields can be duplicated across parts (e.g., customer_id in both parts)
split_gen: SPLIT qualifiedName INTO splitPartGen (SEMICOLON splitPartGen)+;
splitPartGen: identifier COLON identifierList;

// CAST: Change the data type of a property, the type of a constraint, or the kind of an entity
// Example: CAST PROPERTY Entity.field TO Integer
// Example: CAST CONSTRAINT Entity.field TO UNIQUE KEY
// Example: CAST ENTITY orders TO DOCUMENT
cast_gen: CAST (constraintCast | entityCast | propertyCast);
propertyCast: PROPERTY qualifiedName TO dataType;
constraintCast: CONSTRAINT qualifiedName TO constraintKeyType;
entityCast: ENTITY qualifiedName TO databaseType;

// RECARD: Change the multiplicity/cardinality of a reference
// Example: RECARD customers.address_id TO ONE_TO_MANY
recard_gen: RECARD qualifiedName TO cardinalityType;

// TRANSFORM: Transform entity between node and relationship (Graph database)
// Reference: Hausler et al. - "transform a node with its features into a relationship" / vice versa
// Example: TRANSFORM works_at INTO RELATIONSHIP FROM customers TO company
// Example: TRANSFORM works_at INTO RELATIONSHIP FROM customers TO company WITH CARDINALITY ZERO_TO_MANY
// Example: TRANSFORM works_at INTO ENTITY
transform_gen: TRANSFORM qualifiedName INTO transformTarget;
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

// Entity clauses (for ADD ENTITY)
// WITH PROPERTIES (name String, age Integer) - each property has name and type
withPropertiesClause: WITH PROPERTIES LPAREN propertyDefList RPAREN;
propertyDefList: propertyDef (COMMA propertyDef)*;
propertyDef: identifier dataType;

// ============================================================================
// COMMON TYPES - Shared type definitions
// ============================================================================

// Cardinality notation
cardinalityType: ONE_TO_ONE | ONE_TO_MANY | ZERO_TO_ONE | ZERO_TO_MANY | MANY_TO_MANY;

// Constraint key type (for CAST CONSTRAINT)
constraintKeyType: PRIMARY KEY | UNIQUE KEY | PARTITION KEY | CLUSTERING KEY | NODE KEY | DOCUMENT_ID;

// Data types
dataType: STRING | TEXT | INT | INTEGER | LONG | DOUBLE | FLOAT | DECIMAL
        | BOOLEAN | DATE | DATETIME | TIMESTAMP | UUID | BINARY | identifier;

// Path and identifiers
qualifiedName: pathSegment (DOT pathSegment)*;
pathSegment: identifier (LBRACKET RBRACKET)?;
identifier: IDENTIFIER;

// Condition (simplified for schema migration)
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
// KEYWORDS - Reserved words in SMILE_Generalized
// ----------------------------------------------------------------------------
MIGRATION: 'MIGRATION'; EVOLUTION: 'EVOLUTION'; VERSION_KW: 'VERSION';
FROM: 'FROM'; TO: 'TO'; USING: 'USING'; AS: 'AS';
INTO: 'INTO'; WITH: 'WITH'; WHERE: 'WHERE'; IN: 'IN'; KEY: 'KEY'; AND: 'AND';
ON: 'ON';

// Database model types
RELATIONAL: 'RELATIONAL'; DOCUMENT: 'DOCUMENT'; GRAPH: 'GRAPH'; COLUMNAR: 'COLUMNAR';

// Generalized operations (no suffix)
NEST: 'NEST'; UNNEST: 'UNNEST'; FLATTEN: 'FLATTEN'; UNFLATTEN: 'UNFLATTEN';
UNWIND: 'UNWIND'; WIND: 'WIND';
ADD: 'ADD'; DELETE: 'DELETE'; RENAME: 'RENAME';
COPY: 'COPY'; MOVE: 'MOVE'; MERGE: 'MERGE'; SPLIT: 'SPLIT';
CAST: 'CAST'; RECARD: 'RECARD'; TRANSFORM: 'TRANSFORM';
RELATIONSHIP: 'RELATIONSHIP'; BETWEEN: 'BETWEEN';

// Type parameters for generalized operations
PROPERTY: 'PROPERTY'; CONSTRAINT: 'CONSTRAINT'; EMBEDDED: 'EMBEDDED'; ENTITY: 'ENTITY';
LABEL: 'LABEL';

// Entity/Variation clauses
PROPERTIES: 'PROPERTIES';

// Key types
PRIMARY: 'PRIMARY'; UNIQUE: 'UNIQUE'; FOREIGN: 'FOREIGN';
PARTITION: 'PARTITION'; CLUSTERING: 'CLUSTERING';
NODE: 'NODE'; DOCUMENT_ID: 'DOCUMENT_ID';
REFERENCE: 'REFERENCE'; REFERENCES: 'REFERENCES'; COLUMNS: 'COLUMNS';

// Structural keywords
STRUCTURE: 'STRUCTURE';

// Cardinality
CARDINALITY: 'CARDINALITY';
ONE_TO_ONE: 'ONE_TO_ONE'; ONE_TO_MANY: 'ONE_TO_MANY';
ZERO_TO_ONE: 'ZERO_TO_ONE'; ZERO_TO_MANY: 'ZERO_TO_MANY'; MANY_TO_MANY: 'MANY_TO_MANY';

// Data types
STRING: 'String'; TEXT: 'Text'; INT: 'Int'; INTEGER: 'Integer'; LONG: 'Long';
DOUBLE: 'Double'; FLOAT: 'Float'; DECIMAL: 'Decimal'; BOOLEAN: 'Boolean';
DATE: 'Date'; DATETIME: 'DateTime'; TIMESTAMP: 'Timestamp'; UUID: 'UUID'; BINARY: 'Binary';
TYPE: 'TYPE'; DEFAULT: 'DEFAULT'; SERIAL: 'SERIAL'; PREFIX: 'PREFIX';

// Constraints
// NOT_NULL keeps its own multi-word literal form ('NOT NULL' as a single token);
// ANTLR's longest-match rule means "NOT NULL" is preferred over the shorter NOT
// token introduced below for CHECK expression composition.
NOT_NULL: 'NOT NULL';
NOT: 'NOT';
OR: 'OR';
IS: 'IS';
MATCHES: 'MATCHES';
RAW: 'RAW';

// ADD CONSTRAINT body keywords
EXISTENCE: 'EXISTENCE';
CHECK: 'CHECK';

// Literals
TRUE: 'true' | 'TRUE'; FALSE: 'false' | 'FALSE'; NULL: 'null' | 'NULL';

// Symbols
EDGE_LEFT: '-[:'; EDGE_RIGHT: ']->';
COLON: ':'; SEMICOLON: ';'; COMMA: ','; DOT: '.'; LPAREN: '('; RPAREN: ')'; LBRACKET: '['; RBRACKET: ']';
LBRACE: '{'; RBRACE: '}';
EQUALS: '=';
// Comparison operators for CHECK atoms. '==' must come before '=' so longest-match wins.
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
