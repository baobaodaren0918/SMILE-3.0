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

    # ----------------------------------------------------------------------
    # Shared SQL-style helpers (used by PostgreSQL and Cassandra adapters).
    # MongoDB uses JSON parsing and Neo4j a custom comment-driven format,
    # so they don't need these.
    # ----------------------------------------------------------------------

    @staticmethod
    def _remove_sql_comments(ddl: str) -> str:
        """Strip SQL-style ``--`` line comments and ``/* ... */`` block comments."""
        # Remove single-line comments (-- ...)
        ddl = re.sub(r'--.*$', '', ddl, flags=re.MULTILINE)
        # Remove multi-line comments (/* ... */)
        ddl = re.sub(r'/\*.*?\*/', '', ddl, flags=re.DOTALL)
        return ddl

    @staticmethod
    def _split_columns(body: str) -> List[str]:
        """Split a CREATE TABLE body on top-level commas, ignoring those"""
        result = []
        current = ""
        depth = 0

        for char in body:
            if char == '(':
                depth += 1
                current += char
            elif char == ')':
                depth -= 1
                current += char
            elif char == ',' and depth == 0:
                result.append(current.strip())
                current = ""
            else:
                current += char

        if current.strip():
            result.append(current.strip())

        return result
