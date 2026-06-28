"""PostgreSQL Adapter - Parse SQL DDL to Unified Meta Schema."""
import re
from typing import Any, Dict, List, Optional, Tuple
from ..unified_meta_schema import (
    Database, DatabaseType, EntityType, EntityKind, Property,
    UniqueConstraint, ForeignKeyConstraint, UniqueProperty, ForeignKeyProperty, PKTypeEnum,
    CheckConstraint,
    CheckExpr, CheckCmp, CheckIn, CheckBetween, CheckIsNull,
    CheckAnd, CheckOr, CheckNot, CheckRaw,
    Reference, Cardinality, PrimitiveDataType, PrimitiveType,
    ListDataType, SetDataType, MapDataType,
    TypeMappings
)
from ._base import DatabaseAdapter


class _CheckParseError(Exception):
    """Raised internally by the CHECK expression parser to signal that the"""
    pass


class _CheckExprParser:
    """Recursive-descent parser for SQL CHECK boolean expressions."""

    def __init__(self, tokens: List[Tuple[str, Any]], original: str) -> None:
        self.tokens = tokens
        self.pos = 0
        self.original = original

    def at_end(self) -> bool:
        return self.pos >= len(self.tokens)

    def _peek(self, offset: int = 0) -> Optional[Tuple[str, Any]]:
        idx = self.pos + offset
        if idx >= len(self.tokens):
            return None
        return self.tokens[idx]

    def _advance(self) -> Tuple[str, Any]:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _match_ident(self, *names: str) -> bool:
        """Peek; if next token is an ident matching (case-insensitive) any of"""
        tok = self._peek()
        if tok is None or tok[0] != 'ident':
            return False
        if any(tok[1].upper() == n.upper() for n in names):
            self._advance()
            return True
        return False

    def parse_expr(self) -> CheckExpr:
        """Top-level entry: the OR layer (lowest precedence)."""
        left = self._parse_and()
        while self._match_ident('OR'):
            right = self._parse_and()
            left = CheckOr(left=left, right=right)
        return left

    def _parse_and(self) -> CheckExpr:
        left = self._parse_not()
        while self._match_ident('AND'):
            right = self._parse_not()
            left = CheckAnd(left=left, right=right)
        return left

    def _parse_not(self) -> CheckExpr:
        if self._match_ident('NOT'):
            return CheckNot(expr=self._parse_not())
        return self._parse_primary()

    def _parse_primary(self) -> CheckExpr:
        """Either ``( expr )`` or an atomic predicate."""
        tok = self._peek()
        if tok is None:
            raise _CheckParseError("unexpected end of input")
        if tok == ('punct', '('):
            self._advance()
            inner = self.parse_expr()
            if self._peek() != ('punct', ')'):
                raise _CheckParseError("missing closing paren")
            self._advance()
            return inner
        return self._parse_predicate()

    def _parse_predicate(self) -> CheckExpr:
        """One of: ``ident IS [NOT] NULL``, ``ident IN (...)``,"""
        tok = self._peek()
        if tok is None or tok[0] != 'ident':
            raise _CheckParseError(f"expected column identifier, got {tok!r}")
        field_name = tok[1]
        self._advance()

        # IS [NOT] NULL
        if self._match_ident('IS'):
            is_null = True
            if self._match_ident('NOT'):
                is_null = False
            if not self._match_ident('NULL'):
                raise _CheckParseError("expected NULL after IS [NOT]")
            return CheckIsNull(field_name=field_name, is_null=is_null)

        # NOT IN / NOT BETWEEN — accept both ``NOT IN`` and the SQL form
        # where NOT is at predicate-level — for our purposes wrap in CheckNot.
        negate = False
        if self._match_ident('NOT'):
            negate = True

        # IN (...)
        if self._match_ident('IN'):
            if self._peek() != ('punct', '('):
                raise _CheckParseError("expected ( after IN")
            self._advance()
            values: List[Any] = []
            if self._peek() != ('punct', ')'):
                values.append(self._parse_literal())
                while self._peek() == ('punct', ','):
                    self._advance()
                    values.append(self._parse_literal())
            if self._peek() != ('punct', ')'):
                raise _CheckParseError("missing closing paren in IN list")
            self._advance()
            node: CheckExpr = CheckIn(field_name=field_name, values=values)
            return CheckNot(expr=node) if negate else node

        # BETWEEN lo AND hi
        if self._match_ident('BETWEEN'):
            low = self._parse_literal()
            if not self._match_ident('AND'):
                raise _CheckParseError("expected AND in BETWEEN")
            high = self._parse_literal()
            node = CheckBetween(field_name=field_name, low=low, high=high)
            return CheckNot(expr=node) if negate else node

        if negate:
            # ``ident NOT <op> ...`` is not standard SQL; bail to raw.
            raise _CheckParseError("unexpected NOT after column")

        # ident op literal
        op_tok = self._peek()
        if op_tok is None or op_tok[0] != 'op':
            raise _CheckParseError(f"expected comparison op, got {op_tok!r}")
        self._advance()
        op = op_tok[1]
        # Normalise ``=`` to ``==`` so the AST matches what the SMILE grammar
        # produces from ``CHECK <field> == <lit>``. The exporter rewrites
        # both back to SQL ``=``.
        if op == '=':
            op = '=='
        if op == '<>':
            op = '!='
        literal = self._parse_literal()
        return CheckCmp(field_name=field_name, op=op, literal=literal)

    def _parse_literal(self) -> Any:
        """Parse one literal token: int / float / string / TRUE / FALSE / NULL."""
        tok = self._peek()
        if tok is None:
            raise _CheckParseError("expected literal")
        if tok[0] in ('int', 'float', 'string'):
            self._advance()
            return tok[1]
        if tok[0] == 'ident':
            up = tok[1].upper()
            if up == 'TRUE':
                self._advance()
                return True
            if up == 'FALSE':
                self._advance()
                return False
            if up == 'NULL':
                self._advance()
                return None
        raise _CheckParseError(f"expected literal, got {tok!r}")


class PostgreSQLAdapter(DatabaseAdapter):
    """Adapter to parse PostgreSQL DDL and create Unified Meta Schema."""

    TYPE_MAP = TypeMappings.POSTGRESQL_TO_PRIMITIVE

    def __init__(self):
        """Initialize adapter with empty state."""
        self.database: Optional[Database] = None
        # Pending references (column-level): (source_entity, fk_column, target_entity).
        # Stored during parsing, resolved after all tables are created.
        # Each tuple (source_entity, fk_col, target_table, target_col) becomes one
        # Reference + one single-column ForeignKeyConstraint.
        self._pending_references: List[Tuple[str, str, str, str]] = []
        # Pending table-level composite FKs: (source_entity, [src_cols], target_table, [tgt_cols]).
        # Stored separately because all columns of one FOREIGN KEY (a,b) REFERENCES t(x,y)
        # must fold into a SINGLE ForeignKeyConstraint with N ForeignKeyProperty
        # entries — distinguishing them from N independent single-column FKs.
        self._pending_table_fks: List[Tuple[str, List[str], str, List[str]]] = []

    def parse(self, ddl_content: str, db_name: str = "database") -> Database:
        """Parse SQL DDL content and return Database object."""
        self.database = Database(db_name=db_name, db_type=DatabaseType.RELATIONAL)
        self._pending_references = []
        self._pending_table_fks = []

        ddl = self._remove_sql_comments(ddl_content)
        tables = self._extract_create_tables(ddl)

        for table_name, table_body in tables:
            entity = self._parse_table(table_name, table_body)
            self.database.add_entity_type(entity)

        # FK references need the target table to exist, so resolve them only
        # after every entity has been created.
        self._resolve_references()

        return self.database

    def _extract_create_tables(self, ddl: str) -> List[Tuple[str, str]]:
        """Extract CREATE TABLE statements from DDL (quote/paren-aware)."""
        # PostgreSQL has no WITH clause we consume, so drop the third element.
        return [(name, body) for name, body, _with in self._scan_create_tables(ddl)]

    def _parse_table(self, table_name: str, table_body: str) -> EntityType:
        """Parse a single CREATE TABLE body into EntityType."""
        entity = EntityType(object_name=[table_name.lower()], entity_kind=EntityKind.TABLE)

        # Split by comma, but handle parentheses in type definitions
        # e.g., DECIMAL(15,2) should not be split
        columns = self._split_columns(table_body)

        table_level_constraints = []

        for col_def in columns:
            col_def = col_def.strip()
            if not col_def:
                continue

            upper = col_def.upper()
            if any(upper.startswith(kw) for kw in ['PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE', 'CHECK', 'CONSTRAINT']):
                table_level_constraints.append(col_def)
                continue

            attr, ref_info, check_ast = self._parse_column(col_def)
            if attr:
                entity.add_property(attr)

                if 'PRIMARY KEY' in col_def.upper():
                    constraint = UniqueConstraint(
                        is_primary_key=True,
                        is_managed=True,
                        unique_properties=[UniqueProperty(primary_key_type=PKTypeEnum.SIMPLE, property_id=attr.meta_id)]
                    )
                    entity.add_constraint(constraint)

                # Store REFERENCES for later resolution
                # e.g., "customer_id INTEGER REFERENCES customers(id)"
                if ref_info:
                    self._pending_references.append((entity.name, ref_info[0], ref_info[1], ref_info[2]))

                # Inline CHECK clause attached to this column. Anchor the
                # CheckConstraint to the column's own meta_id — for
                # column-level CHECK the anchor is unambiguous.
                if check_ast is not None:
                    entity.add_constraint(CheckConstraint(
                        expression=check_ast,
                        target_property_id=attr.meta_id,
                    ))

        # Parse table-level constraints. The four supported branches mirror
        # the keyword set collected on line 189: PRIMARY KEY, FOREIGN KEY,
        # UNIQUE, CHECK. Generic ``CONSTRAINT <name> ...`` is normalised by
        # stripping the leading ``CONSTRAINT <name>`` prefix before
        # dispatching, so user-named constraints follow the same paths.
        for constraint_def in table_level_constraints:
            stripped = constraint_def.strip()
            # Strip the optional ``CONSTRAINT <name>`` preamble so
            # ``CONSTRAINT pk_orders PRIMARY KEY (...)`` dispatches the same
            # way as a bare ``PRIMARY KEY (...)``.
            named_match = re.match(
                r'^CONSTRAINT\s+\w+\s+(.*)$', stripped, re.IGNORECASE | re.DOTALL,
            )
            if named_match:
                stripped = named_match.group(1).strip()
            upper = stripped.upper()

            if upper.startswith('PRIMARY KEY') and not entity.get_primary_key():
                # PRIMARY KEY (col1, col2, ...)
                pk_match = re.search(r'PRIMARY\s+KEY\s*\(([^)]+)\)', stripped, re.IGNORECASE)
                if pk_match:
                    pk_col_names = [c.strip() for c in pk_match.group(1).split(',')]
                    unique_props = []
                    for col_name in pk_col_names:
                        attr = entity.get_property(col_name)
                        if attr:
                            attr.is_key = True
                            unique_props.append(UniqueProperty(
                                primary_key_type=PKTypeEnum.SIMPLE,
                                property_id=attr.meta_id
                            ))
                    if unique_props:
                        entity.add_constraint(UniqueConstraint(
                            is_primary_key=True,
                            is_managed=True,
                            unique_properties=unique_props,
                        ))

            elif upper.startswith('FOREIGN KEY'):
                # FOREIGN KEY (a, b) REFERENCES target(x, y) [ON DELETE/UPDATE ...]
                # Length-1 lists express single-column FKs; longer lists are true
                # composite FKs that must fold into ONE ForeignKeyConstraint with
                # N ForeignKeyProperty entries (mirrors ADD_FOREIGN_KEY composite
                # semantics in core.handlers.keys_constraints._handle_add_foreign_key).
                fk_match = re.search(
                    r'FOREIGN\s+KEY\s*\(([^)]+)\)\s+REFERENCES\s+(?:\w+\.)?(\w+)\s*\(([^)]+)\)',
                    stripped, re.IGNORECASE,
                )
                if fk_match:
                    src_cols = [c.strip().lower() for c in fk_match.group(1).split(',')]
                    target_table = fk_match.group(2).lower()
                    tgt_cols = [c.strip().lower() for c in fk_match.group(3).split(',')]
                    # Defer to _resolve_references so target entity (which may
                    # be defined later in the DDL) can be looked up after all
                    # CREATE TABLE statements have been parsed.
                    self._pending_table_fks.append(
                        (entity.name, src_cols, target_table, tgt_cols)
                    )

            elif upper.startswith('UNIQUE'):
                # UNIQUE (a, b, ...) — table-level multi-column UNIQUE constraint.
                u_match = re.search(r'UNIQUE\s*\(([^)]+)\)', stripped, re.IGNORECASE)
                if u_match:
                    u_col_names = [c.strip().lower() for c in u_match.group(1).split(',')]
                    unique_props = []
                    for col_name in u_col_names:
                        attr = entity.get_property(col_name)
                        if attr:
                            unique_props.append(UniqueProperty(
                                primary_key_type=PKTypeEnum.SIMPLE,
                                property_id=attr.meta_id,
                            ))
                    if unique_props:
                        entity.add_constraint(UniqueConstraint(
                            is_primary_key=False,
                            is_managed=True,
                            unique_properties=unique_props,
                        ))

            elif upper.startswith('CHECK'):
                # CHECK (<expr>) — parse the SQL boolean expression into a
                # CheckExpr AST. Recognised atoms map cleanly: ``col op lit``,
                # ``col IN (...)``, ``col BETWEEN lo AND hi``, ``col IS [NOT]
                # NULL``, plus AND/OR/NOT compositions and parenthesisation.
                # Anything outside this whitelist (function calls, multi-column
                # arithmetic etc.) falls back to ``CheckRaw(<original text>)``
                # so the constraint at least round-trips intact rather than
                # being silently dropped.
                m_chk = re.search(r'CHECK\s*\((.*)\)\s*$', stripped, re.IGNORECASE | re.DOTALL)
                if m_chk:
                    expr_text = m_chk.group(1).strip()
                    expr_ast = self._parse_check_expression(expr_text)
                    # Anchor the constraint to the *first* property the
                    # expression references — gives DELETE_CONSTRAINT a
                    # qualified name to find it by. Falls back to the first
                    # entity property if expression analysis didn't yield a
                    # candidate (e.g. a CheckRaw fallback).
                    anchor_attr = self._find_check_anchor(entity, expr_ast)
                    if anchor_attr is not None:
                        entity.add_constraint(CheckConstraint(
                            expression=expr_ast,
                            target_property_id=anchor_attr.meta_id,
                        ))

        # Auto-create primary key constraint for SERIAL columns
        # (SERIAL implies PRIMARY KEY even without explicit declaration)
        if not entity.get_primary_key():
            for attr in entity.properties:
                if attr.is_key:
                    constraint = UniqueConstraint(
                        is_primary_key=True,
                        is_managed=True,
                        unique_properties=[UniqueProperty(primary_key_type=PKTypeEnum.SIMPLE, property_id=attr.meta_id)]
                    )
                    entity.add_constraint(constraint)
                    break

        return entity

    # ``_split_columns`` is inherited from DatabaseAdapter (shared with Cassandra).

    # ----------------------------------------------------------------------
    # SQL CHECK expression parsing — ``_parse_check_expression`` turns a SQL
    # boolean expression into the meta-model CheckExpr AST. Implemented as a
    # tiny recursive-descent parser over a hand-rolled tokeniser.
    #
    # Recognised atoms (mapped to specific AST nodes):
    #   ident op literal                         → CheckCmp   (=, ==, !=, <>, <, >, <=, >=)
    #   ident IN (lit, lit, ...)                 → CheckIn
    #   ident BETWEEN lit AND lit                → CheckBetween
    #   ident IS [NOT] NULL                      → CheckIsNull
    # Composition: NOT, AND, OR, parentheses.
    # Anything outside this whitelist (function calls, multi-column
    # arithmetic, string concatenation, etc.) falls back to ``CheckRaw``
    # carrying the original text so the constraint is preserved verbatim
    # rather than being silently dropped.
    # ----------------------------------------------------------------------

    @staticmethod
    def _parse_check_expression(text: str) -> CheckExpr:
        """Parse a SQL boolean expression into a CheckExpr AST."""
        try:
            tokens = PostgreSQLAdapter._tokenize_check(text)
            parser = _CheckExprParser(tokens, text)
            ast = parser.parse_expr()
            if not parser.at_end():
                # Unconsumed tokens → treat as malformed → raw fallback.
                return CheckRaw(raw_text=text.strip())
            return ast
        except _CheckParseError:
            return CheckRaw(raw_text=text.strip())

    @staticmethod
    def _tokenize_check(text: str) -> List[Tuple[str, Any]]:
        """Split a SQL CHECK expression into a stream of typed tokens."""
        tokens: List[Tuple[str, Any]] = []
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if ch.isspace():
                i += 1
                continue
            # Single-quoted string literal — '' inside is an escape for '.
            if ch == "'":
                j = i + 1
                buf = []
                while j < n:
                    if text[j] == "'":
                        if j + 1 < n and text[j + 1] == "'":
                            buf.append("'")
                            j += 2
                            continue
                        break
                    buf.append(text[j])
                    j += 1
                if j >= n:
                    raise _CheckParseError("unterminated string literal")
                tokens.append(('string', ''.join(buf)))
                i = j + 1
                continue
            # Double-quoted identifier (PG quoted name) — treat as identifier
            if ch == '"':
                j = i + 1
                buf = []
                while j < n and text[j] != '"':
                    buf.append(text[j])
                    j += 1
                if j >= n:
                    raise _CheckParseError("unterminated quoted identifier")
                tokens.append(('ident', ''.join(buf)))
                i = j + 1
                continue
            # Numeric literal (int or float)
            if ch.isdigit() or (ch == '-' and i + 1 < n and text[i + 1].isdigit()):
                j = i + 1
                while j < n and (text[j].isdigit() or text[j] == '.'):
                    j += 1
                num_str = text[i:j]
                if '.' in num_str:
                    tokens.append(('float', float(num_str)))
                else:
                    tokens.append(('int', int(num_str)))
                i = j
                continue
            # Multi-char operators first so longest-match wins
            for op in ('<=', '>=', '!=', '<>', '=='):
                if text.startswith(op, i):
                    tokens.append(('op', op))
                    i += len(op)
                    break
            else:
                if ch in '<>':
                    tokens.append(('op', ch))
                    i += 1
                    continue
                if ch == '=':
                    tokens.append(('op', '='))
                    i += 1
                    continue
                if ch in '(),':
                    tokens.append(('punct', ch))
                    i += 1
                    continue
                # Identifier (covers keywords AND, OR, NOT, IS, NULL, IN, BETWEEN, TRUE/FALSE)
                if ch.isalpha() or ch == '_':
                    j = i + 1
                    while j < n and (text[j].isalnum() or text[j] == '_'):
                        j += 1
                    tokens.append(('ident', text[i:j]))
                    i = j
                    continue
                # Anything else — bail out to raw fallback.
                raise _CheckParseError(f"unexpected character {ch!r} at offset {i}")
        return tokens

    @staticmethod
    def _check_expr_to_sql(expr: CheckExpr) -> str:
        """Render a CheckExpr AST back to a SQL boolean expression string."""
        if isinstance(expr, CheckRaw):
            return expr.raw_text
        if isinstance(expr, CheckCmp):
            return f"{expr.field_name} {PostgreSQLAdapter._cmp_op_to_sql(expr.op)} {PostgreSQLAdapter._literal_to_sql(expr.literal)}"
        if isinstance(expr, CheckIn):
            vals = ", ".join(PostgreSQLAdapter._literal_to_sql(v) for v in expr.values)
            return f"{expr.field_name} IN ({vals})"
        if isinstance(expr, CheckBetween):
            return (f"{expr.field_name} BETWEEN "
                    f"{PostgreSQLAdapter._literal_to_sql(expr.low)} AND "
                    f"{PostgreSQLAdapter._literal_to_sql(expr.high)}")
        if isinstance(expr, CheckIsNull):
            return f"{expr.field_name} IS {'NULL' if expr.is_null else 'NOT NULL'}"
        if isinstance(expr, CheckNot):
            inner = PostgreSQLAdapter._check_expr_to_sql(expr.expr) if expr.expr else ""
            return f"NOT ({inner})"
        if isinstance(expr, CheckAnd):
            l = PostgreSQLAdapter._check_expr_to_sql(expr.left) if expr.left else ""
            r = PostgreSQLAdapter._check_expr_to_sql(expr.right) if expr.right else ""
            return f"({l}) AND ({r})"
        if isinstance(expr, CheckOr):
            l = PostgreSQLAdapter._check_expr_to_sql(expr.left) if expr.left else ""
            r = PostgreSQLAdapter._check_expr_to_sql(expr.right) if expr.right else ""
            return f"({l}) OR ({r})"
        return ""

    @staticmethod
    def _cmp_op_to_sql(op: str) -> str:
        """Normalise a CheckCmp op back to a SQL comparison operator."""
        if op in ('=', '=='):
            return '='
        if op in ('!=', '<>'):
            return '<>'
        return op

    @staticmethod
    def _literal_to_sql(lit: Any) -> str:
        """Render a Python literal as SQL: strings get quoted with `` ' ``"""
        if lit is None:
            return 'NULL'
        if isinstance(lit, bool):
            return 'TRUE' if lit else 'FALSE'
        if isinstance(lit, (int, float)):
            return str(lit)
        if isinstance(lit, str):
            escaped = lit.replace("'", "''")
            return f"'{escaped}'"
        return str(lit)

    @staticmethod
    def _find_check_anchor(entity: EntityType, expr: CheckExpr) -> Optional[Property]:
        """Pick which entity property to anchor a CheckConstraint to."""
        names = PostgreSQLAdapter._collect_field_names(expr)
        for name in names:
            attr = entity.get_property(name)
            if attr is not None:
                return attr
        # No field reference visible — fall back to the first property so the
        # constraint is at least round-trippable rather than dropped.
        if entity.properties:
            return entity.properties[0]
        return None

    @staticmethod
    def _collect_field_names(expr: CheckExpr) -> List[str]:
        """Walk a CheckExpr AST and return the field names it references in"""
        out: List[str] = []
        seen = set()

        def add(name: str) -> None:
            if name and name not in seen:
                seen.add(name)
                out.append(name)

        def walk(node: CheckExpr) -> None:
            if isinstance(node, (CheckCmp, CheckIn, CheckBetween, CheckIsNull)):
                add(node.field_name)
            elif isinstance(node, CheckNot):
                if node.expr is not None:
                    walk(node.expr)
            elif isinstance(node, (CheckAnd, CheckOr)):
                if node.left is not None:
                    walk(node.left)
                if node.right is not None:
                    walk(node.right)
            # CheckRaw contributes nothing — opaque to the analyser.

        walk(expr)
        return out

    def _parse_column(self, col_def: str) -> Tuple[Optional[Property], Optional[Tuple[str, str]], Optional[CheckExpr]]:
        """Parse a single column definition."""
        col_def = ' '.join(col_def.split())

        # Pattern: column_name TYPE [constraints] [REFERENCES table(col)]
        # Handles: "id SERIAL", "name VARCHAR(100)", "price DOUBLE PRECISION"
        pattern = r'^(\w+)\s+(\w+(?:\s+PRECISION)?)\s*(?:\(([^)]+)\))?\s*(.*)?$'
        match = re.match(pattern, col_def.strip(), re.IGNORECASE)

        if not match:
            return None, None, None

        col_name = match.group(1).lower()          # "customer_id"
        col_type = match.group(2).upper()          # "INTEGER"
        type_params = match.group(3)               # "100" for VARCHAR(100)
        constraints = match.group(4) or ""         # "NOT NULL REFERENCES customers(id)"

        data_type = self._parse_data_type(col_type, type_params)

        # SERIAL is auto-increment, which implies PRIMARY KEY.
        is_key = 'PRIMARY KEY' in constraints.upper() or col_type in ('SERIAL', 'BIGSERIAL')
        is_optional = 'NOT NULL' not in constraints.upper() and not is_key
        # is_auto_generated: source said SERIAL/BIGSERIAL (PG auto-increment).
        # Carries forward into the meta model so the export side can decide
        # whether to emit ``SERIAL`` or plain ``INTEGER`` instead of guessing
        # from ``is_key + INTEGER`` — which would mis-flag any user-supplied
        # INTEGER PK (business IDs, foreign-system IDs, composite-PK members)
        # as auto-increment.
        is_auto_generated = col_type in ('SERIAL', 'BIGSERIAL')

        attr = Property(
            name=col_name,
            data_type=data_type,
            is_key=is_key,
            is_optional=is_optional,
            is_auto_generated=is_auto_generated,
        )

        ref_info = None
        ref_match = re.search(r'REFERENCES\s+(\w+)\s*\((\w+)\)', constraints, re.IGNORECASE)
        if ref_match:
            ref_info = (col_name, ref_match.group(1).lower(), ref_match.group(2))

        # Column-level CHECK clause: ``CHECK (<expr>)``. The expression is
        # parsed via the same path as table-level CHECK so the AST shape is
        # identical regardless of where the constraint was declared.
        # Re-uses the paren-balanced extractor below — naive ``)`` matching
        # would clip too early on expressions like ``CHECK (LOWER(x) = 'y')``.
        check_ast: Optional[CheckExpr] = None
        check_text = self._extract_inline_check(constraints)
        if check_text is not None:
            check_ast = self._parse_check_expression(check_text)

        return attr, ref_info, check_ast

    @staticmethod
    def _extract_inline_check(constraints: str) -> Optional[str]:
        """Pull the body of an inline ``CHECK (...)`` clause from the trailing"""
        m = re.search(r'CHECK\s*\(', constraints, re.IGNORECASE)
        if not m:
            return None
        # Walk forward from the opening paren of the CHECK clause to find
        # its matching close, ignoring parens inside string literals.
        depth = 0
        i = m.end() - 1  # index of '('
        n = len(constraints)
        in_string = False
        start_inner = m.end()
        while i < n:
            ch = constraints[i]
            if in_string:
                if ch == "'":
                    # Doubled '' is an escape, not the close.
                    if i + 1 < n and constraints[i + 1] == "'":
                        i += 2
                        continue
                    in_string = False
            else:
                if ch == "'":
                    in_string = True
                elif ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                    if depth == 0:
                        return constraints[start_inner:i].strip()
            i += 1
        # Unbalanced — bail; the caller falls back to no CHECK rather than
        # corrupting state.
        return None

    def _parse_data_type(self, type_name: str, params: Optional[str]) -> PrimitiveDataType:
        """Parse SQL type to PrimitiveDataType."""
        primitive = self.TYPE_MAP.get(type_name, PrimitiveType.STRING)

        max_length = None
        precision = None
        scale = None

        if params:
            parts = [p.strip() for p in params.split(',')]
            if primitive in (PrimitiveType.STRING, PrimitiveType.TEXT):
                # VARCHAR(100) -> max_length=100
                max_length = int(parts[0]) if parts else None
            elif primitive == PrimitiveType.DECIMAL:
                # DECIMAL(15,2) -> precision=15, scale=2
                precision = int(parts[0]) if parts else None
                scale = int(parts[1]) if len(parts) > 1 else 0

        return PrimitiveDataType(
            primitive_type=primitive,
            max_length=max_length,
            precision=precision,
            scale=scale
        )

    @staticmethod
    def _derive_fk_cardinalities(is_optional: bool, is_unique: bool):
        """Return ``(target_end_cardinality, source_end_cardinality)`` for a FK
        column. Each field stores the multiplicity at the end of the
        relationship named by the field:

            target_end = multiplicity at the target end (per FK row, how many
                         target rows)
                       = 1..1 (NOT NULL) | 0..1 (nullable)
            source_end = multiplicity at the source end (per target PK row, how
                         many FK rows)
                       = 0..1 (FK column UNIQUE) | 0..n (otherwise)
        """
        target_end = Cardinality.ZERO_TO_ONE if is_optional else Cardinality.ONE_TO_ONE
        source_end = Cardinality.ZERO_TO_ONE if is_unique else Cardinality.ZERO_TO_MANY
        return target_end, source_end

    @staticmethod
    def _is_fk_column_unique(entity, attr) -> bool:
        """A FK column counts as ``unique`` if it has a single-column UNIQUE
        constraint of its own, or if it is the sole column of the entity's PK."""
        if not attr:
            return False
        for c in entity.constraints:
            if (c.kind == "unique" and not c.is_primary_key
                    and len(c.unique_properties) == 1
                    and c.unique_properties[0].property_id == attr.meta_id):
                return True
        pk = entity.get_primary_key()
        if (pk and len(pk.unique_properties) == 1
                and pk.unique_properties[0].property_id == attr.meta_id):
            return True
        return False

    def _resolve_references(self):
        """Resolve foreign key references after all entities are created."""
        for entity_name, ref_name, target_name, target_col in self._pending_references:
            entity = self.database.get_entity_type(entity_name)
            target = self.database.get_entity_type(target_name)

            if entity and target:
                attr = entity.get_property(ref_name)
                is_optional = attr.is_optional if attr else True
                is_unique = self._is_fk_column_unique(entity, attr)
                target_end_card, source_end_card = self._derive_fk_cardinalities(is_optional, is_unique)

                reference = Reference(
                    ref_name=ref_name,
                    refs_to=target_name,
                    target_end_cardinality=target_end_card,
                    source_end_cardinality=source_end_card,
                    is_optional=is_optional,
                )
                entity.add_relationship(reference)

                # Also create ForeignKeyConstraint for consistency with SMILE ADD_FOREIGN_KEY
                if attr:
                    # Resolve to the unique property for the specifically-referenced
                    # target column (e.g. REFERENCES customers(customer_id)). Search
                    # all PK/UNIQUE constraints; fall back to the target's first PK
                    # property only if the named column can't be matched.
                    target_up_id = None
                    if target_col:
                        for c in target.constraints:
                            if c.kind == "unique":
                                for up in c.unique_properties:
                                    up_attr = target.get_property_by_id(up.property_id)
                                    if up_attr and up_attr.name == target_col:
                                        target_up_id = up.meta_id
                                        break
                            if target_up_id:
                                break
                    if target_up_id is None:
                        target_pk = target.get_primary_key()
                        if target_pk and target_pk.unique_properties:
                            target_up_id = target_pk.unique_properties[0].meta_id
                    if target_up_id is not None:
                        fk_prop = ForeignKeyProperty(
                            property_id=attr.meta_id,
                            points_to_unique_property_id=target_up_id
                        )
                        entity.add_constraint(ForeignKeyConstraint(
                            is_managed=True,
                            foreign_key_properties=[fk_prop]
                        ))

        # Resolve table-level composite/single FOREIGN KEY clauses. Unlike the
        # per-column path above (one tuple → one Reference + one single-column
        # ForeignKeyConstraint), each entry here may have N source/target
        # columns and must fold into ONE ForeignKeyConstraint with N
        # ForeignKeyProperty entries — matching the composite semantics of
        # ADD_FOREIGN_KEY in core.handlers.keys_constraints.
        for entity_name, src_cols, target_name, tgt_cols in self._pending_table_fks:
            entity = self.database.get_entity_type(entity_name)
            target = self.database.get_entity_type(target_name)
            if not entity or not target:
                continue

            # Per-column Reference relationships (one per src column).
            # Cardinality follows the same rule used above for column-level FK.
            # Map every PK/UNIQUE target column name to its UniqueProperty id so a
            # FOREIGN KEY may reference a non-PK UNIQUE column, mirroring the
            # inline-FK path above (which searches all unique constraints, not
            # only the primary key).
            target_up_lookup = {}
            for c in target.constraints:
                if c.kind == "unique":
                    for up in c.unique_properties:
                        up_attr = target.get_property_by_id(up.property_id)
                        if up_attr and up_attr.name not in target_up_lookup:
                            target_up_lookup[up_attr.name] = up.meta_id

            fk_props: List[ForeignKeyProperty] = []
            for src_col, tgt_col in zip(src_cols, tgt_cols):
                src_attr = entity.get_property(src_col)
                if not src_attr:
                    # Source column missing — skip silently; this is the same
                    # behaviour as malformed inline REFERENCES on a missing column.
                    continue
                src_optional = src_attr.is_optional
                is_unique = self._is_fk_column_unique(entity, src_attr)
                target_end_card, source_end_card = self._derive_fk_cardinalities(src_optional, is_unique)

                entity.add_relationship(Reference(
                    ref_name=src_col,
                    refs_to=target_name,
                    target_end_cardinality=target_end_card,
                    source_end_cardinality=source_end_card,
                    is_optional=src_optional,
                ))

                target_up_id = target_up_lookup.get(tgt_col, "")
                fk_props.append(ForeignKeyProperty(
                    property_id=src_attr.meta_id,
                    points_to_unique_property_id=target_up_id,
                ))

            # ONE ForeignKeyConstraint per FOREIGN KEY clause — gathers every
            # (src_col, tgt_col) pair as a ForeignKeyProperty. Length-1 lists
            # collapse to the single-column case naturally.
            if fk_props:
                entity.add_constraint(ForeignKeyConstraint(
                    is_managed=True,
                    foreign_key_properties=fk_props,
                ))

    @staticmethod
    def load_from_file(file_path: str, db_name: str = None) -> Database:
        """Load SQL DDL from file and parse to Database."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if db_name is None:
            from pathlib import Path
            db_name = Path(file_path).stem

        adapter = PostgreSQLAdapter()
        return adapter.parse(content, db_name)

    REVERSE_TYPE_MAP = TypeMappings.PRIMITIVE_TO_POSTGRESQL

    @classmethod
    def export_to_sql(cls, database: Database) -> str:
        """Export Unified Meta Schema to PostgreSQL DDL format."""
        lines = []

        # Sort so REFERENCES clauses point to already-created tables.
        sorted_entities = cls._sort_entities_by_dependency(database)

        for entity in sorted_entities:
            ddl = cls._export_entity_to_ddl(entity, database)
            lines.append(ddl)
            lines.append("")

        return "\n".join(lines)

    @classmethod
    def _sort_entities_by_dependency(cls, database: Database) -> list:
        """Sort entities so that referenced tables come before referencing tables."""
        entities = list(database.entity_types.values())

        dependencies = {}
        for entity in entities:
            deps = set()
            for rel in entity.relationships:
                if isinstance(rel, Reference):
                    target = rel.get_target_entity_name()
                    if target != entity.name:  # Avoid self-reference
                        deps.add(target)
            dependencies[entity.name] = deps

        # Topological sort (DFS)
        sorted_names = []
        visited = set()

        def visit(name):
            if name in visited:
                return
            visited.add(name)
            for dep in dependencies.get(name, []):
                if dep in dependencies:  # Only visit if entity exists
                    visit(dep)
            sorted_names.append(name)

        for name in dependencies:
            visit(name)

        return [database.get_entity_type(name) for name in sorted_names if database.get_entity_type(name)]

    @classmethod
    def _export_entity_to_ddl(cls, entity: EntityType, database: Database) -> str:
        """Export a single entity to CREATE TABLE DDL format."""
        lines = []
        lines.append(f"CREATE TABLE {entity.name} (")

        columns = []
        constraints = []

        # Build FK lookup: column_name -> Reference relationship.
        # Columns that are part of a *composite* FK (≥2 columns folded into
        # one ForeignKeyConstraint) are excluded from the column-level
        # REFERENCES emission; the composite FK is emitted as a table-level
        # FOREIGN KEY (a, b) REFERENCES ... clause further down. Inlining
        # both forms would produce a redundant duplicate FK declaration.
        composite_fk_cols = set()
        for c in entity.constraints:
            if c.kind == "foreign_key" and len(c.foreign_key_properties) >= 2:
                for fkp in c.foreign_key_properties:
                    fk_attr = entity.get_property_by_id(fkp.property_id)
                    if fk_attr:
                        composite_fk_cols.add(fk_attr.name)

        fk_refs = {}
        for rel in entity.relationships:
            if isinstance(rel, Reference) and rel.ref_name not in composite_fk_cols:
                fk_refs[rel.ref_name] = rel

        pk_constraint = entity.get_primary_key()
        pk_columns = []
        if pk_constraint and pk_constraint.unique_properties:
            for up in pk_constraint.unique_properties:
                pk_attr = entity.get_property_by_id(up.property_id)
                if pk_attr:
                    pk_columns.append(pk_attr.name)

        is_composite_pk = len(pk_columns) > 1

        for attr in entity.properties:
            col_def = cls._export_property_to_column(attr, fk_refs.get(attr.name), database, is_composite_pk, source_entity=entity)
            columns.append(f"    {col_def}")

        if is_composite_pk:
            pk_constraint_str = f"    PRIMARY KEY ({', '.join(pk_columns)})"
            columns.append(pk_constraint_str)

        # Emit non-PK UNIQUE constraints. Single-column UNIQUE could in
        # principle be inlined on the column ("col TYPE UNIQUE"), but emitting
        # them as table-level keeps the export uniform and handles composite
        # UNIQUE (a, b) the same way. Anything that round-trips through the
        # parse-side table-level UNIQUE branch comes out symmetrically.
        for c in entity.constraints:
            if c.kind != "unique" or c.is_primary_key:
                continue
            uq_cols = []
            for up in c.unique_properties:
                up_attr = entity.get_property_by_id(up.property_id)
                if up_attr:
                    uq_cols.append(up_attr.name)
            if uq_cols:
                columns.append(f"    UNIQUE ({', '.join(uq_cols)})")

        # Emit CHECK constraints. The meta-model holds a structured
        # CheckExpr AST plus an optional human-friendly name; render the AST
        # back to a SQL boolean expression via ``_check_expr_to_sql`` (which
        # is the inverse of the parse-time expression decoder above).
        for c in entity.constraints:
            if c.kind != "check" or c.expression is None:
                continue
            sql_expr = cls._check_expr_to_sql(c.expression)
            if not sql_expr:
                continue
            if c.constraint_name:
                columns.append(f"    CONSTRAINT {c.constraint_name} CHECK ({sql_expr})")
            else:
                columns.append(f"    CHECK ({sql_expr})")

        # Emit composite/multi-column FOREIGN KEYs as table-level constraints.
        # Single-column FKs continue to be inlined on the column via
        # ``_export_property_to_column``'s REFERENCES clause; this branch only
        # fires when a ForeignKeyConstraint covers ≥2 properties (true
        # composite FK), which the column-level form cannot express.
        for c in entity.constraints:
            if c.kind != "foreign_key":
                continue
            if len(c.foreign_key_properties) < 2:
                continue  # single-col FK already emitted column-level
            src_cols = []
            tgt_cols = []
            target_entity_name = ""
            for fkp in c.foreign_key_properties:
                src_attr = entity.get_property_by_id(fkp.property_id)
                if not src_attr:
                    continue
                src_cols.append(src_attr.name)
                # Locate target entity + column from any matching Reference.
                # Composite FKs always share one target table across all members.
                if not target_entity_name:
                    for rel in entity.relationships:
                        if isinstance(rel, Reference) and rel.ref_name == src_attr.name:
                            target_entity_name = rel.get_target_entity_name()
                            break
                tgt_cols.append(cls._resolve_fk_target_col(
                    fkp.points_to_unique_property_id, target_entity_name, database,
                ))
            if src_cols and target_entity_name and len(src_cols) == len(tgt_cols):
                columns.append(
                    f"    FOREIGN KEY ({', '.join(src_cols)}) "
                    f"REFERENCES {target_entity_name}({', '.join(tgt_cols)})"
                )

        lines.append(",\n".join(columns))
        lines.append(");")

        return "\n".join(lines)

    @classmethod
    def _resolve_fk_target_col(cls, target_up_id: str, target_entity_name: str,
                               database: Database) -> str:
        """Look up the property name behind a ForeignKeyProperty.points_to_unique_property_id."""
        if not target_up_id or not target_entity_name or database is None:
            return ""
        target = database.get_entity_type(target_entity_name)
        if not target:
            return ""
        for c in target.constraints:
            if c.kind != "unique":
                continue
            for up in c.unique_properties:
                if up.meta_id == target_up_id:
                    up_attr = target.get_property_by_id(up.property_id)
                    if up_attr:
                        return up_attr.name
        return ""

    @classmethod
    def _export_property_to_column(cls, attr: Property, fk_ref: Reference = None, database: Database = None, is_composite_pk: bool = False, source_entity=None) -> str:
        """Export a property to column definition."""
        parts = [attr.name]

        sql_type = cls._get_sql_type(attr)
        parts.append(sql_type)

        # Inline PRIMARY KEY only for single-column PK.
        if attr.is_key and not is_composite_pk:
            parts.append("PRIMARY KEY")
        # Composite-PK columns need NOT NULL since the PK constraint is emitted
        # separately as a table-level clause.
        elif not attr.is_optional or (attr.is_key and is_composite_pk):
            parts.append("NOT NULL")

        if fk_ref:
            target_entity_name = fk_ref.get_target_entity_name()
            # Resolve the specifically-referenced target column from this column's
            # single-column ForeignKeyConstraint (points_to_unique_property_id), so
            # a FK to a non-PK UNIQUE column exports the right column. Fall back to
            # the target PK's first column when no matching constraint is found.
            target_col_name = ""
            if source_entity is not None:
                for c in source_entity.constraints:
                    if c.kind == "foreign_key" and len(c.foreign_key_properties) == 1:
                        fkp = c.foreign_key_properties[0]
                        if fkp.property_id == attr.meta_id:
                            target_col_name = cls._resolve_fk_target_col(
                                fkp.points_to_unique_property_id, target_entity_name, database)
                            break
            if not target_col_name:
                target_col_name = cls._get_target_pk_name(target_entity_name, database)
            parts.append(f"REFERENCES {target_entity_name}({target_col_name})")

        return " ".join(parts)

    @classmethod
    def _get_sql_type(cls, attr: Property) -> str:
        """Get SQL type string from property."""
        # Complex types -> JSONB in PostgreSQL
        if isinstance(attr.data_type, ListDataType):
            return 'JSONB'
        elif isinstance(attr.data_type, SetDataType):
            return 'JSONB'
        elif isinstance(attr.data_type, MapDataType):
            return 'JSONB'
        elif not isinstance(attr.data_type, PrimitiveDataType):
            return 'VARCHAR'

        primitive = attr.data_type.primitive_type
        base_type = cls.REVERSE_TYPE_MAP.get(primitive, 'VARCHAR')

        if base_type == 'VARCHAR':
            max_len = attr.data_type.max_length or 255
            return f"VARCHAR({max_len})"

        if base_type == 'DECIMAL':
            precision = attr.data_type.precision or 13
            scale = attr.data_type.scale or 2
            return f"DECIMAL({precision},{scale})"

        # SERIAL / BIGSERIAL only when the source explicitly flagged the column
        # as auto-generated. The previous heuristic ``is_key + INTEGER`` over-
        # promoted *every* INTEGER PK to SERIAL — which corrupted the semantics
        # of business-supplied PKs (e.g. order numbers), Mongo integer ``_id``
        # values arriving via a Mongo→PG migration, and members of composite
        # PKs (each marked ``is_key=True`` but never auto-generated).
        if attr.is_auto_generated:
            if base_type == 'INTEGER':
                return 'SERIAL'
            if base_type == 'BIGINT':
                return 'BIGSERIAL'

        return base_type

    @classmethod
    def _get_target_pk_name(cls, entity_name: str, database: Database = None) -> str:
        """Get the PK column name for a target entity."""
        if database:
            target_entity = database.get_entity_type(entity_name)
            if target_entity:
                pk = target_entity.get_primary_key()
                if pk and pk.unique_properties:
                    pk_attr = target_entity.get_property_by_id(pk.unique_properties[0].property_id)
                    if pk_attr:
                        return pk_attr.name

        # Fallback when no PK metadata is available.
        return f"{entity_name}_id"

    @classmethod
    def export(cls, database: Database) -> str:
        """Convenience method that calls export_to_sql()."""
        return cls.export_to_sql(database)

    @classmethod
    def export_to_sql_file(cls, database: Database, file_path: str) -> None:
        """Export to SQL file."""
        sql = cls.export_to_sql(database)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(sql)
