"""DatabaseAdapter — abstract base class for the four schema adapters."""
import re
from abc import ABC, abstractmethod
from typing import List, Optional

from Schema.unified_meta_schema import Database


class DatabaseAdapter(ABC):
    """Common interface every database adapter must implement."""

    @classmethod
    @abstractmethod
    def load_from_file(cls, file_path: str, db_name: Optional[str] = None) -> Database:
        """Read a native schema file (DDL / JSON / GraphQL SDL / CQL) and return a Database."""
        ...

    @classmethod
    @abstractmethod
    def export(cls, database: Database) -> str:
        """Render a Database back to its native text form."""
        ...

    @abstractmethod
    def parse(self, content: str, db_name: str = "database") -> Database:
        """Parse in-memory native schema content into a Database."""
        ...

    @staticmethod
    def _remove_sql_comments(ddl: str) -> str:
        """Strip SQL-style ``--`` line comments and ``/* ... */`` block comments."""
        ddl = re.sub(r'--.*$', '', ddl, flags=re.MULTILINE)
        ddl = re.sub(r'/\*.*?\*/', '', ddl, flags=re.DOTALL)
        return ddl

    @staticmethod
    def _split_columns(body: str, track_angle: bool = False) -> List[str]:
        """Split a CREATE TABLE body on top-level commas, ignoring commas that
        are nested inside parentheses (``DECIMAL(15,2)``, ``PRIMARY KEY((a,b),c)``)
        or single-quoted string literals (a column ``DEFAULT 'a,b'``).

        ``track_angle`` additionally treats ``<``/``>`` as nesting so CQL
        collection types (``map<text, int>``) are not split on their inner
        comma. It is OFF by default because SQL ``CHECK`` expressions use bare
        ``<``/``>`` as comparison operators, which would corrupt the depth
        counter — only the Cassandra adapter (no CHECK constraints) enables it.
        """
        result = []
        current = ""
        depth = 0
        in_str = False
        i = 0
        while i < len(body):
            char = body[i]
            if in_str:
                current += char
                if char == "'":
                    # Escaped '' inside a string literal stays in-string.
                    if i + 1 < len(body) and body[i + 1] == "'":
                        current += body[i + 1]
                        i += 2
                        continue
                    in_str = False
            elif char == "'":
                in_str = True
                current += char
            elif char == '(' or (track_angle and char == '<'):
                depth += 1
                current += char
            elif char == ')' or (track_angle and char == '>'):
                depth -= 1
                current += char
            elif char == ',' and depth == 0:
                result.append(current.strip())
                current = ""
            else:
                current += char
            i += 1

        if current.strip():
            result.append(current.strip())

        return result

    @staticmethod
    def _scan_create_tables(text: str):
        """Quote- and paren-aware extraction of ``CREATE TABLE`` statements.

        Returns a list of ``(table_name, body, with_clause)`` tuples. Unlike a
        non-greedy ``\\((.*?)\\);`` regex, this walks the text tracking paren
        depth and skipping single-quoted string literals, so a ``)`` or ``;``
        appearing inside a column default (``DEFAULT 'see (note);'``) or nested
        parentheses no longer truncates the table body. ``with_clause`` is the
        text between the closing ``)`` and the terminating ``;`` with a leading
        ``WITH`` stripped (empty when absent).
        """
        results = []
        header_re = re.compile(
            r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:\w+\.)?(\w+)\s*\(',
            re.IGNORECASE,
        )
        for m in header_re.finditer(text):
            name = m.group(1)
            body_start = m.end()            # just past the opening '('
            i = body_start
            depth = 1
            in_str = False
            while i < len(text) and depth > 0:
                ch = text[i]
                if in_str:
                    if ch == "'":
                        if i + 1 < len(text) and text[i + 1] == "'":
                            i += 2
                            continue
                        in_str = False
                elif ch == "'":
                    in_str = True
                elif ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            if depth != 0:
                continue                    # unbalanced — skip malformed table
            body = text[body_start:i]
            # Scan from after the closing ')' to the statement terminator ';'.
            j = i + 1
            in_str = False
            while j < len(text):
                ch = text[j]
                if in_str:
                    if ch == "'":
                        if j + 1 < len(text) and text[j + 1] == "'":
                            j += 2
                            continue
                        in_str = False
                elif ch == "'":
                    in_str = True
                elif ch == ';':
                    break
                j += 1
            rest = text[i + 1:j].strip()
            wm = re.match(r'WITH\s+(.*)', rest, re.IGNORECASE | re.DOTALL)
            with_clause = wm.group(1).strip() if wm else ""
            results.append((name, body, with_clause))
        return results
