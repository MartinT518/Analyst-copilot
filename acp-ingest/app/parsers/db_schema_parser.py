"""Database schema parser for extracting structured information from databases."""

import asyncio
from typing import Dict, List, Any, Optional
import psycopg2
import psycopg2.extras
from sqlalchemy import create_engine, text, MetaData, Table, Column, ForeignKey
from sqlalchemy.engine import Engine
import logging

logger = logging.getLogger(__name__)


class DatabaseSchemaParser:
    """Parser for extracting database schema information."""

    def __init__(self):
        """Initialize the database schema parser."""
        self.supported_databases = ["postgresql", "mysql", "sqlite", "oracle", "mssql"]

    async def parse(
        self, content: str, metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Parse database schema and extract structured information.

        Args:
            content: Database connection string or schema content
            metadata: Additional metadata

        Returns:
            List of parsed schema documents
        """
        try:
            # Check if content is a connection string
            if self._is_connection_string(content):
                return await self._parse_database_schema(content, metadata)
            else:
                return await self._parse_schema_content(content, metadata)

        except Exception as e:
            logger.error(f"Database schema parsing failed: {e}")
            return []

    def _is_connection_string(self, content: str) -> bool:
        """Check if content is a database connection string."""
        return any(
            db in content.lower()
            for db in [
                "postgresql://",
                "mysql://",
                "sqlite://",
                "oracle://",
                "mssql://",
            ]
        )

    async def _parse_database_schema(
        self, connection_string: str, metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Parse database schema from live database.

        Args:
            connection_string: Database connection string
            metadata: Additional metadata

        Returns:
            List of parsed schema documents
        """
        try:
            # Create database engine
            engine = create_engine(connection_string)

            # Extract schema information
            schema_info = await self._extract_schema_info(engine)

            # Generate documents
            documents = []

            # Create overall schema document
            schema_doc = {
                "id": "database_schema_overview",
                "title": "Database Schema Overview",
                "content": self._generate_schema_overview(schema_info),
                "metadata": {
                    **metadata,
                    "source_type": "database_schema",
                    "database_type": self._get_database_type(connection_string),
                    "table_count": len(schema_info["tables"]),
                    "view_count": len(schema_info["views"]),
                    "procedure_count": len(schema_info["procedures"]),
                },
            }
            documents.append(schema_doc)

            # Create individual table documents
            for table in schema_info["tables"]:
                table_doc = {
                    "id": f"table_{table['name']}",
                    "title": f"Table: {table['name']}",
                    "content": self._generate_table_description(table),
                    "metadata": {
                        **metadata,
                        "source_type": "database_table",
                        "table_name": table["name"],
                        "column_count": len(table["columns"]),
                        "foreign_keys": table["foreign_keys"],
                        "indexes": table["indexes"],
                    },
                }
                documents.append(table_doc)

            # Create relationship documents
            for relationship in schema_info["relationships"]:
                rel_doc = {
                    "id": f"relationship_{relationship['id']}",
                    "title": f"Relationship: {relationship['from_table']} -> {relationship['to_table']}",
                    "content": self._generate_relationship_description(relationship),
                    "metadata": {
                        **metadata,
                        "source_type": "database_relationship",
                        "from_table": relationship["from_table"],
                        "to_table": relationship["to_table"],
                        "relationship_type": relationship["type"],
                    },
                }
                documents.append(rel_doc)

            return documents

        except Exception as e:
            logger.error(f"Database schema parsing failed: {e}")
            return []

    async def _extract_schema_info(self, engine: Engine) -> Dict[str, Any]:
        """Extract comprehensive schema information from database.

        Args:
            engine: SQLAlchemy engine

        Returns:
            Dictionary containing schema information
        """
        schema_info = {"tables": [], "views": [], "procedures": [], "relationships": []}

        try:
            with engine.connect() as conn:
                # Get database type
                db_type = engine.dialect.name

                if db_type == "postgresql":
                    schema_info = await self._extract_postgresql_schema(conn)
                elif db_type == "mysql":
                    schema_info = await self._extract_mysql_schema(conn)
                elif db_type == "sqlite":
                    schema_info = await self._extract_sqlite_schema(conn)
                else:
                    # Generic extraction
                    schema_info = await self._extract_generic_schema(conn)

        except Exception as e:
            logger.error(f"Schema extraction failed: {e}")

        return schema_info

    async def _extract_postgresql_schema(self, conn) -> Dict[str, Any]:
        """Extract schema from PostgreSQL database."""
        schema_info = {"tables": [], "views": [], "procedures": [], "relationships": []}

        try:
            # Get tables
            tables_query = """
            SELECT 
                t.table_name,
                t.table_type,
                obj_description(c.oid) as table_comment
            FROM information_schema.tables t
            LEFT JOIN pg_class c ON c.relname = t.table_name
            WHERE t.table_schema = 'public'
            ORDER BY t.table_name
            """

            tables_result = conn.execute(text(tables_query))
            for row in tables_result:
                table_name = row[0]
                table_type = row[1]
                table_comment = row[2] or ""

                # Get columns for this table
                columns_query = """
                SELECT 
                    c.column_name,
                    c.data_type,
                    c.is_nullable,
                    c.column_default,
                    c.character_maximum_length,
                    c.numeric_precision,
                    c.numeric_scale,
                    col_description(pgc.oid, c.ordinal_position) as column_comment
                FROM information_schema.columns c
                LEFT JOIN pg_class pgc ON pgc.relname = c.table_name
                WHERE c.table_name = :table_name
                ORDER BY c.ordinal_position
                """

                columns_result = conn.execute(
                    text(columns_query), {"table_name": table_name}
                )
                columns = []
                for col_row in columns_result:
                    columns.append(
                        {
                            "name": col_row[0],
                            "type": col_row[1],
                            "nullable": col_row[2] == "YES",
                            "default": col_row[3],
                            "max_length": col_row[4],
                            "precision": col_row[5],
                            "scale": col_row[6],
                            "comment": col_row[7] or "",
                        }
                    )

                # Get foreign keys
                fk_query = """
                SELECT 
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name,
                    tc.constraint_name
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY' 
                    AND tc.table_name = :table_name
                """

                fk_result = conn.execute(text(fk_query), {"table_name": table_name})
                foreign_keys = []
                for fk_row in fk_result:
                    foreign_keys.append(
                        {
                            "column": fk_row[0],
                            "references_table": fk_row[1],
                            "references_column": fk_row[2],
                            "constraint_name": fk_row[3],
                        }
                    )

                # Get indexes
                index_query = """
                SELECT 
                    i.relname as index_name,
                    a.attname as column_name,
                    ix.indisunique as is_unique,
                    ix.indisprimary as is_primary
                FROM pg_class t
                JOIN pg_index ix ON t.oid = ix.indrelid
                JOIN pg_class i ON i.oid = ix.indexrelid
                JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
                WHERE t.relname = :table_name
                ORDER BY i.relname, a.attnum
                """

                index_result = conn.execute(
                    text(index_query), {"table_name": table_name}
                )
                indexes = []
                for idx_row in index_result:
                    indexes.append(
                        {
                            "name": idx_row[0],
                            "column": idx_row[1],
                            "unique": idx_row[2],
                            "primary": idx_row[3],
                        }
                    )

                table_info = {
                    "name": table_name,
                    "type": table_type,
                    "comment": table_comment,
                    "columns": columns,
                    "foreign_keys": foreign_keys,
                    "indexes": indexes,
                }

                if table_type == "BASE TABLE":
                    schema_info["tables"].append(table_info)
                elif table_type == "VIEW":
                    schema_info["views"].append(table_info)

            # Extract relationships
            for table in schema_info["tables"]:
                for fk in table["foreign_keys"]:
                    relationship = {
                        "id": f"{table['name']}_{fk['column']}_to_{fk['references_table']}_{fk['references_column']}",
                        "from_table": table["name"],
                        "from_column": fk["column"],
                        "to_table": fk["references_table"],
                        "to_column": fk["references_column"],
                        "type": "foreign_key",
                    }
                    schema_info["relationships"].append(relationship)

        except Exception as e:
            logger.error(f"PostgreSQL schema extraction failed: {e}")

        return schema_info

    async def _extract_mysql_schema(self, conn) -> Dict[str, Any]:
        """Extract schema from MySQL database."""
        # Similar implementation for MySQL
        return {"tables": [], "views": [], "procedures": [], "relationships": []}

    async def _extract_sqlite_schema(self, conn) -> Dict[str, Any]:
        """Extract schema from SQLite database."""
        # Similar implementation for SQLite
        return {"tables": [], "views": [], "procedures": [], "relationships": []}

    async def _extract_generic_schema(self, conn) -> Dict[str, Any]:
        """Extract schema using generic SQLAlchemy metadata."""
        try:
            metadata = MetaData()
            metadata.reflect(bind=conn)

            schema_info = {
                "tables": [],
                "views": [],
                "procedures": [],
                "relationships": [],
            }

            for table_name, table in metadata.tables.items():
                columns = []
                for column in table.columns:
                    columns.append(
                        {
                            "name": column.name,
                            "type": str(column.type),
                            "nullable": column.nullable,
                            "default": str(column.default) if column.default else None,
                            "primary_key": column.primary_key,
                        }
                    )

                foreign_keys = []
                for fk in table.foreign_keys:
                    foreign_keys.append(
                        {
                            "column": fk.parent.name,
                            "references_table": fk.column.table.name,
                            "references_column": fk.column.name,
                        }
                    )

                table_info = {
                    "name": table_name,
                    "type": "BASE TABLE",
                    "comment": "",
                    "columns": columns,
                    "foreign_keys": foreign_keys,
                    "indexes": [],
                }

                schema_info["tables"].append(table_info)

            return schema_info

        except Exception as e:
            logger.error(f"Generic schema extraction failed: {e}")
            return {"tables": [], "views": [], "procedures": [], "relationships": []}

    def _generate_schema_overview(self, schema_info: Dict[str, Any]) -> str:
        """Generate natural language overview of database schema."""
        overview_parts = []

        table_count = len(schema_info["tables"])
        view_count = len(schema_info["views"])
        relationship_count = len(schema_info["relationships"])

        overview_parts.append(
            f"Database schema contains {table_count} table(s) and {view_count} view(s)."
        )

        if schema_info["tables"]:
            table_names = [
                table["name"] for table in schema_info["tables"][:10]
            ]  # First 10 tables
            overview_parts.append(f"Main tables include: {', '.join(table_names)}.")

        if relationship_count > 0:
            overview_parts.append(
                f"Schema defines {relationship_count} relationship(s) between tables."
            )

        # Add key relationships
        if schema_info["relationships"]:
            key_relationships = schema_info["relationships"][
                :5
            ]  # First 5 relationships
            rel_descriptions = []
            for rel in key_relationships:
                rel_descriptions.append(f"{rel['from_table']} -> {rel['to_table']}")
            overview_parts.append(f"Key relationships: {', '.join(rel_descriptions)}.")

        return " ".join(overview_parts)

    def _generate_table_description(self, table: Dict[str, Any]) -> str:
        """Generate natural language description of a table."""
        desc_parts = [
            f"Table '{table['name']}' contains {len(table['columns'])} column(s)."
        ]

        # Describe columns
        column_descriptions = []
        for col in table["columns"][:5]:  # First 5 columns
            col_desc = f"{col['name']} ({col['type']})"
            if col.get("primary_key"):
                col_desc += " [PRIMARY KEY]"
            if not col.get("nullable"):
                col_desc += " [NOT NULL]"
            column_descriptions.append(col_desc)

        desc_parts.append(f"Columns include: {', '.join(column_descriptions)}.")

        # Describe foreign keys
        if table["foreign_keys"]:
            fk_descriptions = []
            for fk in table["foreign_keys"]:
                fk_descriptions.append(
                    f"{fk['column']} -> {fk['references_table']}.{fk['references_column']}"
                )
            desc_parts.append(
                f"Foreign key relationships: {', '.join(fk_descriptions)}."
            )

        return " ".join(desc_parts)

    def _generate_relationship_description(self, relationship: Dict[str, Any]) -> str:
        """Generate natural language description of a relationship."""
        return f"Foreign key relationship: {relationship['from_table']}.{relationship['from_column']} references {relationship['to_table']}.{relationship['to_column']}."

    def _get_database_type(self, connection_string: str) -> str:
        """Extract database type from connection string."""
        if "postgresql://" in connection_string:
            return "postgresql"
        elif "mysql://" in connection_string:
            return "mysql"
        elif "sqlite://" in connection_string:
            return "sqlite"
        elif "oracle://" in connection_string:
            return "oracle"
        elif "mssql://" in connection_string:
            return "mssql"
        else:
            return "unknown"

    async def _parse_schema_content(
        self, content: str, metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Parse schema content directly (SQL DDL)."""
        # For direct schema content, we'll do basic parsing
        doc = {
            "id": "schema_ddl",
            "title": "Database Schema DDL",
            "content": f"Database schema definition containing {content.count('CREATE TABLE')} table(s) and {content.count('CREATE VIEW')} view(s).",
            "metadata": {
                **metadata,
                "source_type": "database_schema",
                "ddl_content": content[:1000],  # First 1000 chars
            },
        }

        return [doc]
