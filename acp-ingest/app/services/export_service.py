"""Export service for generating reports and data exports."""

import csv
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.models import AuditLog
from app.schemas import SearchResult
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class ExportFormat:
    """Supported export formats."""

    CSV = "csv"
    JSON = "json"
    MARKDOWN = "markdown"
    HTML = "html"
    ZIP = "zip"


class JiraFieldMapping:
    """Standard Jira field mappings for CSV export."""

    ISSUE_TYPE = "Issue Type"
    SUMMARY = "Summary"
    DESCRIPTION = "Description"
    PRIORITY = "Priority"
    LABELS = "Labels"
    COMPONENTS = "Components"
    ASSIGNEE = "Assignee"
    REPORTER = "Reporter"
    STATUS = "Status"
    RESOLUTION = "Resolution"
    CREATED = "Created"
    UPDATED = "Updated"
    DUE_DATE = "Due Date"
    CUSTOM_FIELD_PREFIX = "Custom field"


class ExportService:
    """Service for exporting data in various formats."""

    def __init__(self):
        import tempfile

        self.temp_dir = Path(tempfile.gettempdir()) / "acp_exports"
        self.temp_dir.mkdir(exist_ok=True)

    async def export_search_results(
        self,
        results: List[SearchResult],
        format_type: str,
        title: str = "Search Results",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Export search results in the specified format.

        Args:
            results: Search results to export
            format_type: Export format (csv, json, markdown, html)
            title: Title for the export
            metadata: Additional metadata to include

        Returns:
            Dict[str, Any]: Export result with file path and metadata
        """
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"search_results_{timestamp}"

            if format_type == ExportFormat.CSV:
                return await self._export_search_results_csv(results, filename, title, metadata)
            elif format_type == ExportFormat.JSON:
                return await self._export_search_results_json(results, filename, title, metadata)
            elif format_type == ExportFormat.MARKDOWN:
                return await self._export_search_results_markdown(
                    results, filename, title, metadata
                )
            elif format_type == ExportFormat.HTML:
                return await self._export_search_results_html(results, filename, title, metadata)
            else:
                raise ValueError(f"Unsupported export format: {format_type}")

        except Exception as e:
            logger.error("Error exporting search results", format=format_type, error=str(e))
            raise

    async def _export_search_results_csv(
        self,
        results: List[SearchResult],
        filename: str,
        title: str,
        metadata: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Export search results as CSV."""
        file_path = self.temp_dir / f"{filename}.csv"

        with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "rank",
                "similarity_score",
                "chunk_id",
                "source_type",
                "chunk_text",
                "document_title",
                "author",
                "created_at",
                "sensitivity",
                "origin",
            ]

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for result in results:
                chunk = result.chunk
                writer.writerow(
                    {
                        "rank": result.rank,
                        "similarity_score": round(result.similarity_score, 4),
                        "chunk_id": str(chunk.id),
                        "source_type": chunk.source_type,
                        "chunk_text": (
                            chunk.chunk_text[:500] + "..."
                            if len(chunk.chunk_text) > 500
                            else chunk.chunk_text
                        ),
                        "document_title": chunk.metadata.get("document_title", ""),
                        "author": chunk.metadata.get("author", ""),
                        "created_at": (chunk.created_at.isoformat() if chunk.created_at else ""),
                        "sensitivity": "Yes" if chunk.sensitive else "No",
                        "origin": chunk.metadata.get("origin", ""),
                    }
                )

        return {
            "file_path": str(file_path),
            "filename": f"{filename}.csv",
            "format": ExportFormat.CSV,
            "size": file_path.stat().st_size,
            "record_count": len(results),
            "created_at": datetime.utcnow().isoformat(),
        }

    async def _export_search_results_json(
        self,
        results: List[SearchResult],
        filename: str,
        title: str,
        metadata: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Export search results as JSON."""
        file_path = self.temp_dir / f"{filename}.json"

        export_data = {
            "title": title,
            "exported_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
            "results": [],
        }

        for result in results:
            chunk = result.chunk
            export_data["results"].append(
                {
                    "rank": result.rank,
                    "similarity_score": result.similarity_score,
                    "chunk": {
                        "id": str(chunk.id),
                        "source_type": chunk.source_type,
                        "chunk_text": chunk.chunk_text,
                        "metadata": chunk.metadata,
                        "sensitive": chunk.sensitive,
                        "created_at": (chunk.created_at.isoformat() if chunk.created_at else None),
                    },
                }
            )

        with open(file_path, "w", encoding="utf-8") as jsonfile:
            json.dump(export_data, jsonfile, indent=2, ensure_ascii=False)

        return {
            "file_path": str(file_path),
            "filename": f"{filename}.json",
            "format": ExportFormat.JSON,
            "size": file_path.stat().st_size,
            "record_count": len(results),
            "created_at": datetime.utcnow().isoformat(),
        }

    async def _export_search_results_markdown(
        self,
        results: List[SearchResult],
        filename: str,
        title: str,
        metadata: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Export search results as Markdown."""
        file_path = self.temp_dir / f"{filename}.md"

        with open(file_path, "w", encoding="utf-8") as mdfile:
            # Header
            mdfile.write(f"# {title}\n\n")
            mdfile.write(f"**Exported:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
            mdfile.write(f"**Results:** {len(results)} items\n\n")

            if metadata:
                mdfile.write("## Export Metadata\n\n")
                for key, value in metadata.items():
                    mdfile.write(f"- **{key}:** {value}\n")
                mdfile.write("\n")

            # Results
            mdfile.write("## Search Results\n\n")

            for i, result in enumerate(results, 1):
                chunk = result.chunk

                mdfile.write(f"### Result {i}\n\n")
                mdfile.write(f"**Similarity Score:** {result.similarity_score:.4f}\n")
                mdfile.write(f"**Source:** {chunk.source_type}\n")
                mdfile.write(f"**Document:** {chunk.metadata.get('document_title', 'Unknown')}\n")
                mdfile.write(f"**Author:** {chunk.metadata.get('author', 'Unknown')}\n")
                mdfile.write(f"**Sensitive:** {'Yes' if chunk.sensitive else 'No'}\n\n")

                mdfile.write("**Content:**\n\n")
                mdfile.write(f"```\n{chunk.chunk_text}\n```\n\n")
                mdfile.write("---\n\n")

        return {
            "file_path": str(file_path),
            "filename": f"{filename}.md",
            "format": ExportFormat.MARKDOWN,
            "size": file_path.stat().st_size,
            "record_count": len(results),
            "created_at": datetime.utcnow().isoformat(),
        }

    async def _export_search_results_html(
        self,
        results: List[SearchResult],
        filename: str,
        title: str,
        metadata: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Export search results as HTML."""
        file_path = self.temp_dir / f"{filename}.html"

        with open(file_path, "w", encoding="utf-8") as htmlfile:
            htmlfile.write(
                f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .header {{ border-bottom: 2px solid #333; padding-bottom: 20px; margin-bottom: 30px; }}
        .result {{ border: 1px solid #ddd; margin: 20px 0; padding: 20px; border-radius: 5px; }}
        .result-header {{ background-color: #f5f5f5; padding: 10px; margin: -20px -20px 15px -20px; border-radius: 5px 5px 0 0; }}
        .content {{ background-color: #f9f9f9; padding: 15px; border-radius: 3px; font-family: monospace; white-space: pre-wrap; }}
        .metadata {{ color: #666; font-size: 0.9em; }}
        .score {{ font-weight: bold; color: #007cba; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{title}</h1>
        <p><strong>Exported:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        <p><strong>Results:</strong> {len(results)} items</p>
    </div>
"""
            )

            if metadata:
                htmlfile.write('    <div class="metadata">\n')
                htmlfile.write("        <h2>Export Metadata</h2>\n")
                htmlfile.write("        <ul>\n")
                for key, value in metadata.items():
                    htmlfile.write(f"            <li><strong>{key}:</strong> {value}</li>\n")
                htmlfile.write("        </ul>\n")
                htmlfile.write("    </div>\n")

            for i, result in enumerate(results, 1):
                chunk = result.chunk

                htmlfile.write(
                    f"""    <div class="result">
        <div class="result-header">
            <h3>Result {i}</h3>
            <span class="score">Similarity Score: {result.similarity_score:.4f}</span>
        </div>
        <div class="metadata">
            <p><strong>Source:</strong> {chunk.source_type}</p>
            <p><strong>Document:</strong> {chunk.metadata.get('document_title', 'Unknown')}</p>
            <p><strong>Author:</strong> {chunk.metadata.get('author', 'Unknown')}</p>
            <p><strong>Sensitive:</strong> {'Yes' if chunk.sensitive else 'No'}</p>
        </div>
        <div class="content">{chunk.chunk_text}</div>
    </div>
"""
                )

            htmlfile.write("</body>\n</html>")

        return {
            "file_path": str(file_path),
            "filename": f"{filename}.html",
            "format": ExportFormat.HTML,
            "size": file_path.stat().st_size,
            "record_count": len(results),
            "created_at": datetime.utcnow().isoformat(),
        }

    async def export_jira_csv(
        self,
        analysis_results: List[Dict[str, Any]],
        project_key: str,
        issue_type: str = "Task",
        assignee: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Export analysis results as Jira-importable CSV.

        Args:
            analysis_results: Analysis results to export
            project_key: Jira project key
            issue_type: Jira issue type
            assignee: Default assignee

        Returns:
            Dict[str, Any]: Export result
        """
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"jira_import_{project_key}_{timestamp}.csv"
            file_path = self.temp_dir / filename

            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                fieldnames = [
                    JiraFieldMapping.ISSUE_TYPE,
                    JiraFieldMapping.SUMMARY,
                    JiraFieldMapping.DESCRIPTION,
                    JiraFieldMapping.PRIORITY,
                    JiraFieldMapping.LABELS,
                    JiraFieldMapping.ASSIGNEE,
                    JiraFieldMapping.REPORTER,
                    "Project Key",
                ]

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for result in analysis_results:
                    # Extract key information
                    summary = result.get("title", result.get("summary", "Analysis Result"))[:255]
                    description = result.get("description", result.get("content", ""))
                    priority = result.get("priority", "Medium")
                    labels = result.get("labels", [])

                    if isinstance(labels, list):
                        labels_str = " ".join(labels)
                    else:
                        labels_str = str(labels)

                    writer.writerow(
                        {
                            JiraFieldMapping.ISSUE_TYPE: issue_type,
                            JiraFieldMapping.SUMMARY: summary,
                            JiraFieldMapping.DESCRIPTION: description,
                            JiraFieldMapping.PRIORITY: priority,
                            JiraFieldMapping.LABELS: labels_str,
                            JiraFieldMapping.ASSIGNEE: assignee or "",
                            JiraFieldMapping.REPORTER: "",
                            "Project Key": project_key,
                        }
                    )

            return {
                "file_path": str(file_path),
                "filename": filename,
                "format": ExportFormat.CSV,
                "size": file_path.stat().st_size,
                "record_count": len(analysis_results),
                "created_at": datetime.utcnow().isoformat(),
                "jira_project": project_key,
            }

        except Exception as e:
            logger.error("Error exporting Jira CSV", project_key=project_key, error=str(e))
            raise

    async def export_audit_report(
        self,
        audit_logs: List[AuditLog],
        format_type: str = ExportFormat.CSV,
        title: str = "Audit Report",
    ) -> Dict[str, Any]:
        """
        Export audit logs as a compliance report.

        Args:
            audit_logs: Audit log entries
            format_type: Export format
            title: Report title

        Returns:
            Dict[str, Any]: Export result
        """
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"audit_report_{timestamp}"

            if format_type == ExportFormat.CSV:
                return await self._export_audit_csv(audit_logs, filename, title)
            elif format_type == ExportFormat.JSON:
                return await self._export_audit_json(audit_logs, filename, title)
            elif format_type == ExportFormat.MARKDOWN:
                return await self._export_audit_markdown(audit_logs, filename, title)
            else:
                raise ValueError(f"Unsupported audit export format: {format_type}")

        except Exception as e:
            logger.error("Error exporting audit report", format=format_type, error=str(e))
            raise

    async def _export_audit_csv(
        self, audit_logs: List[AuditLog], filename: str, title: str
    ) -> Dict[str, Any]:
        """Export audit logs as CSV."""
        file_path = self.temp_dir / f"{filename}.csv"

        with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "timestamp",
                "action",
                "user_id",
                "resource_type",
                "resource_id",
                "severity",
                "ip_address",
                "user_agent",
                "details",
                "hash",
            ]

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for log in audit_logs:
                writer.writerow(
                    {
                        "timestamp": (log.created_at.isoformat() if log.created_at else ""),
                        "action": log.action,
                        "user_id": log.user_id or "",
                        "resource_type": log.resource_type or "",
                        "resource_id": log.resource_id or "",
                        "severity": log.severity,
                        "ip_address": log.ip_address or "",
                        "user_agent": log.user_agent or "",
                        "details": json.dumps(log.details) if log.details else "",
                        "hash": log.hash or "",
                    }
                )

        return {
            "file_path": str(file_path),
            "filename": f"{filename}.csv",
            "format": ExportFormat.CSV,
            "size": file_path.stat().st_size,
            "record_count": len(audit_logs),
            "created_at": datetime.utcnow().isoformat(),
        }

    async def _export_audit_json(
        self, audit_logs: List[AuditLog], filename: str, title: str
    ) -> Dict[str, Any]:
        """Export audit logs as JSON."""
        file_path = self.temp_dir / f"{filename}.json"

        export_data = {
            "title": title,
            "exported_at": datetime.utcnow().isoformat(),
            "audit_logs": [],
        }

        for log in audit_logs:
            export_data["audit_logs"].append(
                {
                    "id": log.id,
                    "timestamp": log.created_at.isoformat() if log.created_at else None,
                    "action": log.action,
                    "user_id": log.user_id,
                    "resource_type": log.resource_type,
                    "resource_id": log.resource_id,
                    "severity": log.severity,
                    "ip_address": log.ip_address,
                    "user_agent": log.user_agent,
                    "details": log.details,
                    "hash": log.hash,
                    "previous_hash": log.previous_hash,
                }
            )

        with open(file_path, "w", encoding="utf-8") as jsonfile:
            json.dump(export_data, jsonfile, indent=2, ensure_ascii=False)

        return {
            "file_path": str(file_path),
            "filename": f"{filename}.json",
            "format": ExportFormat.JSON,
            "size": file_path.stat().st_size,
            "record_count": len(audit_logs),
            "created_at": datetime.utcnow().isoformat(),
        }

    async def _export_audit_markdown(
        self, audit_logs: List[AuditLog], filename: str, title: str
    ) -> Dict[str, Any]:
        """Export audit logs as Markdown."""
        file_path = self.temp_dir / f"{filename}.md"

        with open(file_path, "w", encoding="utf-8") as mdfile:
            mdfile.write(f"# {title}\n\n")
            mdfile.write(f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
            mdfile.write(f"**Total Events:** {len(audit_logs)}\n\n")

            # Group by severity
            severity_groups = {}
            for log in audit_logs:
                severity = log.severity
                if severity not in severity_groups:
                    severity_groups[severity] = []
                severity_groups[severity].append(log)

            mdfile.write("## Summary by Severity\n\n")
            for severity, logs in severity_groups.items():
                mdfile.write(f"- **{severity.upper()}:** {len(logs)} events\n")
            mdfile.write("\n")

            # Detailed logs
            mdfile.write("## Detailed Audit Log\n\n")

            for log in audit_logs:
                mdfile.write(f"### {log.action} - {log.severity.upper()}\n\n")
                mdfile.write(
                    f"**Timestamp:** {log.created_at.strftime('%Y-%m-%d %H:%M:%S UTC') if log.created_at else 'Unknown'}\n"
                )
                mdfile.write(f"**User ID:** {log.user_id or 'System'}\n")
                mdfile.write(
                    f"**Resource:** {log.resource_type or 'N/A'} ({log.resource_id or 'N/A'})\n"
                )
                mdfile.write(f"**IP Address:** {log.ip_address or 'Unknown'}\n")

                if log.details:
                    mdfile.write(
                        f"**Details:**\n```json\n{json.dumps(log.details, indent=2)}\n```\n"
                    )

                mdfile.write("\n---\n\n")

        return {
            "file_path": str(file_path),
            "filename": f"{filename}.md",
            "format": ExportFormat.MARKDOWN,
            "size": file_path.stat().st_size,
            "record_count": len(audit_logs),
            "created_at": datetime.utcnow().isoformat(),
        }

    async def create_export_package(
        self, exports: List[Dict[str, Any]], package_name: str
    ) -> Dict[str, Any]:
        """
        Create a ZIP package containing multiple exports.

        Args:
            exports: List of export results
            package_name: Name for the package

        Returns:
            Dict[str, Any]: Package information
        """
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            zip_filename = f"{package_name}_{timestamp}.zip"
            zip_path = self.temp_dir / zip_filename

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                # Add manifest
                manifest = {
                    "package_name": package_name,
                    "created_at": datetime.utcnow().isoformat(),
                    "exports": [],
                }

                for export in exports:
                    file_path = Path(export["file_path"])
                    if file_path.exists():
                        # Add file to ZIP
                        zipf.write(file_path, export["filename"])

                        # Add to manifest
                        manifest["exports"].append(
                            {
                                "filename": export["filename"],
                                "format": export["format"],
                                "size": export["size"],
                                "record_count": export.get("record_count", 0),
                                "created_at": export["created_at"],
                            }
                        )

                # Add manifest to ZIP
                manifest_json = json.dumps(manifest, indent=2)
                zipf.writestr("manifest.json", manifest_json)

            return {
                "file_path": str(zip_path),
                "filename": zip_filename,
                "format": ExportFormat.ZIP,
                "size": zip_path.stat().st_size,
                "export_count": len(exports),
                "created_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error("Error creating export package", package_name=package_name, error=str(e))
            raise

    def cleanup_old_exports(self, max_age_hours: int = 24):
        """
        Clean up old export files.

        Args:
            max_age_hours: Maximum age of files to keep
        """
        try:
            cutoff_time = datetime.utcnow().timestamp() - (max_age_hours * 3600)

            for file_path in self.temp_dir.iterdir():
                if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    logger.debug("Cleaned up old export file", file=str(file_path))

        except Exception as e:
            logger.error("Error cleaning up old exports", error=str(e))


# Global export service instance
export_service = ExportService()
