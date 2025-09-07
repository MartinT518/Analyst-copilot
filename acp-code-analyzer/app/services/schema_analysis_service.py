"""Database schema analysis service for extracting structured information from databases."""

import asyncio
from typing import Dict, List, Any, Optional, Tuple
import structlog
import sqlalchemy as sa
from sqlalchemy import create_engine, MetaData, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
import psycopg2
from psycopg2.extras import RealDictCursor

from ..config import get_settings

logger = structlog.get_logger(__name__)


class SchemaAnalysisService:
    """Service for analyzing database schemas and extracting structured information."""

    def __init__(self):
        """Initialize the schema analysis service."""
        self.settings = get_settings()
        self.logger = logger.bind(service="schema_analysis")

        # Analysis statistics
        self.schemas_analyzed = 0
        self.tables_analyzed = 0
        self.errors_encountered = 0

    async def analyze_database_schema(
        self,
        connection_string: str,
        schema_names: Optional[List[str]] = None,
        include_system_tables: bool = False,
    ) -> Dict[str, Any]:
        """Analyze database schema and extract structured information.

        Args:
            connection_string: Database connection string
            schema_names: Specific schemas to analyze (None for all)
            include_system_tables: Whether to include system tables

        Returns:
            Schema analysis results
        """
        self.logger.info(
            "Starting database schema analysis",
            connection_string=connection_string[:50] + "...",
        )

        try:
            # Create database engine
            engine = create_engine(
                connection_string,
                pool_timeout=self.settings.db_connection_timeout,
                pool_recycle=3600,
            )

            # Test connection
            with engine.connect() as conn:
                conn.execute(sa.text("SELECT 1"))

            # Get database metadata
            db_info = await self._get_database_info(engine)

            # Get schema information
            schemas = await self._get_schemas(
                engine, schema_names, include_system_tables
            )

            # Analyze each schema
            schema_analyses = []
            for schema_name in schemas:
                try:
                    schema_analysis = await self._analyze_schema(
                        engine, schema_name, include_system_tables
                    )
                    schema_analyses.append(schema_analysis)
                    self.schemas_analyzed += 1
                except Exception as e:
                    self.errors_encountered += 1
                    self.logger.warning(
                        "Schema analysis failed", schema=schema_name, error=str(e)
                    )
                    schema_analyses.append(
                        {
                            "schema_name": schema_name,
                            "error": str(e),
                            "tables": [],
                            "views": [],
                            "functions": [],
                            "procedures": [],
                        }
                    )

            # Extract insights
            insights = await self._extract_schema_insights(schema_analyses, db_info)

            # Create final analysis result
            final_result = {
                "database_info": db_info,
                "schemas_analyzed": len(schema_analyses),
                "schema_analyses": schema_analyses,
                "insights": insights,
                "statistics": {
                    "schemas_analyzed": self.schemas_analyzed,
                    "tables_analyzed": self.tables_analyzed,
                    "errors_encountered": self.errors_encountered,
                    "total_objects": sum(
                        len(s.get("tables", []))
                        + len(s.get("views", []))
                        + len(s.get("functions", []))
                        + len(s.get("procedures", []))
                        for s in schema_analyses
                    ),
                },
            }

            self.logger.info(
                "Database schema analysis completed",
                schemas_count=len(schema_analyses),
                tables_count=self.tables_analyzed,
            )

            return final_result

        except Exception as e:
            self.logger.error("Database schema analysis failed", error=str(e))
            raise
        finally:
            if "engine" in locals():
                engine.dispose()

    async def _get_database_info(self, engine: Engine) -> Dict[str, Any]:
        """Get basic database information.

        Args:
            engine: SQLAlchemy engine

        Returns:
            Database metadata
        """
        info = {
            "database_type": engine.dialect.name,
            "database_version": "unknown",
            "server_version": "unknown",
            "connection_info": {},
        }

        try:
            with engine.connect() as conn:
                # Get database version
                if engine.dialect.name == "postgresql":
                    result = conn.execute(sa.text("SELECT version()"))
                    info["database_version"] = result.scalar()

                    # Get server info
                    result = conn.execute(
                        sa.text(
                            "SELECT current_database(), current_user, inet_server_addr(), inet_server_port()"
                        )
                    )
                    row = result.fetchone()
                    if row:
                        info["connection_info"] = {
                            "database_name": row[0],
                            "current_user": row[1],
                            "server_address": row[2],
                            "server_port": row[3],
                        }

                elif engine.dialect.name == "mysql":
                    result = conn.execute(sa.text("SELECT VERSION()"))
                    info["database_version"] = result.scalar()

                elif engine.dialect.name == "sqlite":
                    result = conn.execute(sa.text("SELECT sqlite_version()"))
                    info["database_version"] = result.scalar()

        except Exception as e:
            self.logger.warning("Failed to get database info", error=str(e))
            info["error"] = str(e)

        return info

    async def _get_schemas(
        self,
        engine: Engine,
        schema_names: Optional[List[str]],
        include_system_tables: bool,
    ) -> List[str]:
        """Get list of schemas to analyze.

        Args:
            engine: SQLAlchemy engine
            schema_names: Specific schemas to include
            include_system_tables: Whether to include system schemas

        Returns:
            List of schema names
        """
        try:
            inspector = inspect(engine)
            all_schemas = inspector.get_schema_names()

            if schema_names:
                # Use specified schemas
                schemas = [s for s in schema_names if s in all_schemas]
            else:
                # Use all schemas, optionally filtering system schemas
                schemas = all_schemas

                if not include_system_tables and engine.dialect.name == "postgresql":
                    # Filter out PostgreSQL system schemas
                    system_schemas = {
                        "information_schema",
                        "pg_catalog",
                        "pg_toast",
                        "pg_temp_1",
                        "pg_toast_temp_1",
                    }
                    schemas = [
                        s
                        for s in schemas
                        if s not in system_schemas and not s.startswith("pg_")
                    ]

            return schemas

        except Exception as e:
            self.logger.warning("Failed to get schemas", error=str(e))
            return ["public"]  # Default schema

    async def _analyze_schema(
        self, engine: Engine, schema_name: str, include_system_tables: bool
    ) -> Dict[str, Any]:
        """Analyze a specific database schema.

        Args:
            engine: SQLAlchemy engine
            schema_name: Schema name to analyze
            include_system_tables: Whether to include system tables

        Returns:
            Schema analysis results
        """
        self.logger.info("Analyzing schema", schema=schema_name)

        analysis = {
            "schema_name": schema_name,
            "tables": [],
            "views": [],
            "functions": [],
            "procedures": [],
            "sequences": [],
            "indexes": [],
            "constraints": [],
        }

        try:
            inspector = inspect(engine)

            # Analyze tables
            table_names = inspector.get_table_names(schema=schema_name)
            for table_name in table_names[: self.settings.max_tables_per_analysis]:
                try:
                    table_analysis = await self._analyze_table(
                        inspector, schema_name, table_name
                    )
                    analysis["tables"].append(table_analysis)
                    self.tables_analyzed += 1
                except Exception as e:
                    self.logger.warning(
                        "Table analysis failed", table=table_name, error=str(e)
                    )
                    analysis["tables"].append(
                        {"table_name": table_name, "error": str(e)}
                    )

            # Analyze views
            try:
                view_names = inspector.get_view_names(schema=schema_name)
                for view_name in view_names:
                    view_analysis = await self._analyze_view(
                        inspector, schema_name, view_name
                    )
                    analysis["views"].append(view_analysis)
            except Exception as e:
                self.logger.warning(
                    "View analysis failed", schema=schema_name, error=str(e)
                )

            # Database-specific analysis
            if engine.dialect.name == "postgresql":
                analysis.update(
                    await self._analyze_postgresql_schema(engine, schema_name)
                )

        except Exception as e:
            self.logger.error(
                "Schema analysis failed", schema=schema_name, error=str(e)
            )
            analysis["error"] = str(e)

        return analysis

    async def _analyze_table(
        self, inspector, schema_name: str, table_name: str
    ) -> Dict[str, Any]:
        """Analyze a database table.

        Args:
            inspector: SQLAlchemy inspector
            schema_name: Schema name
            table_name: Table name

        Returns:
            Table analysis results
        """
        analysis = {
            "table_name": table_name,
            "schema_name": schema_name,
            "columns": [],
            "primary_keys": [],
            "foreign_keys": [],
            "indexes": [],
            "constraints": [],
            "table_comment": None,
        }

        try:
            # Get columns
            columns = inspector.get_columns(table_name, schema=schema_name)
            for column in columns:
                column_info = {
                    "column_name": column["name"],
                    "data_type": str(column["type"]),
                    "nullable": column.get("nullable", True),
                    "default": str(column.get("default"))
                    if column.get("default") is not None
                    else None,
                    "comment": column.get("comment"),
                    "autoincrement": column.get("autoincrement", False),
                }
                analysis["columns"].append(column_info)

            # Get primary keys
            pk_constraint = inspector.get_pk_constraint(table_name, schema=schema_name)
            if pk_constraint:
                analysis["primary_keys"] = pk_constraint.get("constrained_columns", [])

            # Get foreign keys
            foreign_keys = inspector.get_foreign_keys(table_name, schema=schema_name)
            for fk in foreign_keys:
                fk_info = {
                    "constraint_name": fk.get("name"),
                    "constrained_columns": fk.get("constrained_columns", []),
                    "referred_table": fk.get("referred_table"),
                    "referred_schema": fk.get("referred_schema"),
                    "referred_columns": fk.get("referred_columns", []),
                }
                analysis["foreign_keys"].append(fk_info)

            # Get indexes
            indexes = inspector.get_indexes(table_name, schema=schema_name)
            for index in indexes:
                index_info = {
                    "index_name": index.get("name"),
                    "column_names": index.get("column_names", []),
                    "unique": index.get("unique", False),
                }
                analysis["indexes"].append(index_info)

            # Get check constraints
            try:
                check_constraints = inspector.get_check_constraints(
                    table_name, schema=schema_name
                )
                for constraint in check_constraints:
                    constraint_info = {
                        "constraint_name": constraint.get("name"),
                        "constraint_text": constraint.get("sqltext"),
                    }
                    analysis["constraints"].append(constraint_info)
            except Exception:
                # Not all databases support check constraints inspection
                pass

            # Get table comment
            try:
                table_comment = inspector.get_table_comment(
                    table_name, schema=schema_name
                )
                analysis["table_comment"] = (
                    table_comment.get("text") if table_comment else None
                )
            except Exception:
                pass

        except Exception as e:
            analysis["error"] = str(e)

        return analysis

    async def _analyze_view(
        self, inspector, schema_name: str, view_name: str
    ) -> Dict[str, Any]:
        """Analyze a database view.

        Args:
            inspector: SQLAlchemy inspector
            schema_name: Schema name
            view_name: View name

        Returns:
            View analysis results
        """
        analysis = {
            "view_name": view_name,
            "schema_name": schema_name,
            "columns": [],
            "view_definition": None,
        }

        try:
            # Get view columns
            columns = inspector.get_columns(view_name, schema=schema_name)
            for column in columns:
                column_info = {
                    "column_name": column["name"],
                    "data_type": str(column["type"]),
                    "nullable": column.get("nullable", True),
                }
                analysis["columns"].append(column_info)

            # Try to get view definition
            try:
                view_definition = inspector.get_view_definition(
                    view_name, schema=schema_name
                )
                analysis["view_definition"] = view_definition
            except Exception:
                # Not all databases support view definition inspection
                pass

        except Exception as e:
            analysis["error"] = str(e)

        return analysis

    async def _analyze_postgresql_schema(
        self, engine: Engine, schema_name: str
    ) -> Dict[str, Any]:
        """Perform PostgreSQL-specific schema analysis.

        Args:
            engine: SQLAlchemy engine
            schema_name: Schema name

        Returns:
            PostgreSQL-specific analysis results
        """
        analysis = {
            "functions": [],
            "procedures": [],
            "sequences": [],
            "types": [],
            "triggers": [],
        }

        try:
            with engine.connect() as conn:
                # Get functions and procedures
                functions_query = sa.text(
                    """
                    SELECT
                        p.proname as name,
                        pg_get_function_result(p.oid) as return_type,
                        pg_get_function_arguments(p.oid) as arguments,
                        p.prokind as kind,
                        obj_description(p.oid) as description
                    FROM pg_proc p
                    JOIN pg_namespace n ON p.pronamespace = n.oid
                    WHERE n.nspname = :schema_name
                    ORDER BY p.proname
                """
                )

                result = conn.execute(functions_query, {"schema_name": schema_name})
                for row in result:
                    func_info = {
                        "name": row.name,
                        "return_type": row.return_type,
                        "arguments": row.arguments,
                        "kind": row.kind,  # 'f' = function, 'p' = procedure
                        "description": row.description,
                    }

                    if row.kind == "f":
                        analysis["functions"].append(func_info)
                    elif row.kind == "p":
                        analysis["procedures"].append(func_info)

                # Get sequences
                sequences_query = sa.text(
                    """
                    SELECT
                        c.relname as sequence_name,
                        obj_description(c.oid) as description
                    FROM pg_class c
                    JOIN pg_namespace n ON c.relnamespace = n.oid
                    WHERE c.relkind = 'S' AND n.nspname = :schema_name
                    ORDER BY c.relname
                """
                )

                result = conn.execute(sequences_query, {"schema_name": schema_name})
                for row in result:
                    seq_info = {
                        "sequence_name": row.sequence_name,
                        "description": row.description,
                    }
                    analysis["sequences"].append(seq_info)

                # Get custom types
                types_query = sa.text(
                    """
                    SELECT
                        t.typname as type_name,
                        t.typtype as type_type,
                        obj_description(t.oid) as description
                    FROM pg_type t
                    JOIN pg_namespace n ON t.typnamespace = n.oid
                    WHERE n.nspname = :schema_name AND t.typtype IN ('c', 'e', 'd')
                    ORDER BY t.typname
                """
                )

                result = conn.execute(types_query, {"schema_name": schema_name})
                for row in result:
                    type_info = {
                        "type_name": row.type_name,
                        "type_type": row.type_type,  # 'c' = composite, 'e' = enum, 'd' = domain
                        "description": row.description,
                    }
                    analysis["types"].append(type_info)

        except Exception as e:
            self.logger.warning(
                "PostgreSQL-specific analysis failed", schema=schema_name, error=str(e)
            )
            analysis["error"] = str(e)

        return analysis

    async def _extract_schema_insights(
        self, schema_analyses: List[Dict[str, Any]], db_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract high-level insights from schema analyses.

        Args:
            schema_analyses: List of schema analysis results
            db_info: Database information

        Returns:
            High-level insights
        """
        insights = {
            "database_summary": {},
            "table_statistics": {},
            "relationship_analysis": {},
            "data_type_distribution": {},
            "naming_conventions": {},
            "complexity_metrics": {},
        }

        # Database summary
        total_tables = sum(len(s.get("tables", [])) for s in schema_analyses)
        total_views = sum(len(s.get("views", [])) for s in schema_analyses)
        total_functions = sum(len(s.get("functions", [])) for s in schema_analyses)

        insights["database_summary"] = {
            "database_type": db_info.get("database_type", "unknown"),
            "total_schemas": len(schema_analyses),
            "total_tables": total_tables,
            "total_views": total_views,
            "total_functions": total_functions,
            "total_objects": total_tables + total_views + total_functions,
        }

        # Table statistics
        all_tables = []
        for schema in schema_analyses:
            all_tables.extend(schema.get("tables", []))

        if all_tables:
            column_counts = [len(table.get("columns", [])) for table in all_tables]
            insights["table_statistics"] = {
                "average_columns_per_table": sum(column_counts) / len(column_counts),
                "max_columns_in_table": max(column_counts) if column_counts else 0,
                "min_columns_in_table": min(column_counts) if column_counts else 0,
                "tables_with_primary_keys": sum(
                    1 for table in all_tables if table.get("primary_keys")
                ),
                "tables_with_foreign_keys": sum(
                    1 for table in all_tables if table.get("foreign_keys")
                ),
            }

        # Relationship analysis
        total_foreign_keys = sum(
            len(table.get("foreign_keys", []))
            for schema in schema_analyses
            for table in schema.get("tables", [])
        )

        insights["relationship_analysis"] = {
            "total_foreign_keys": total_foreign_keys,
            "referential_integrity_coverage": (
                insights["table_statistics"].get("tables_with_foreign_keys", 0)
                / total_tables
                if total_tables > 0
                else 0
            ),
        }

        # Data type distribution
        data_types = {}
        for schema in schema_analyses:
            for table in schema.get("tables", []):
                for column in table.get("columns", []):
                    data_type = column.get("data_type", "unknown")
                    data_types[data_type] = data_types.get(data_type, 0) + 1

        insights["data_type_distribution"] = dict(
            sorted(data_types.items(), key=lambda x: x[1], reverse=True)[:10]
        )

        # Naming conventions analysis
        table_names = [
            table.get("table_name", "")
            for schema in schema_analyses
            for table in schema.get("tables", [])
        ]

        if table_names:
            snake_case_count = sum(
                1 for name in table_names if "_" in name and name.islower()
            )
            camel_case_count = sum(
                1 for name in table_names if any(c.isupper() for c in name[1:])
            )

            insights["naming_conventions"] = {
                "snake_case_tables": snake_case_count,
                "camel_case_tables": camel_case_count,
                "naming_consistency_score": max(snake_case_count, camel_case_count)
                / len(table_names),
            }

        # Complexity metrics
        insights["complexity_metrics"] = {
            "schema_complexity": len(schema_analyses),
            "average_tables_per_schema": total_tables / len(schema_analyses)
            if schema_analyses
            else 0,
            "database_size_indicator": total_tables + total_views + total_functions,
        }

        return insights
