"""Markdown parser for processing Markdown documents."""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import markdown

logger = logging.getLogger(__name__)


class MarkdownParser:
    """Parser for Markdown documents."""

    def __init__(self):
        # Configure markdown processor
        self.md = markdown.Markdown(
            extensions=[
                "codehilite",
                "tables",
                "toc",
                "fenced_code",
                "attr_list",
                "def_list",
                "footnotes",
                "md_in_html",
            ],
            extension_configs={
                "codehilite": {"css_class": "highlight", "use_pygments": False},
                "toc": {"permalink": True},
            },
        )

        # Patterns for extracting metadata
        self.frontmatter_pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL | re.MULTILINE)
        self.title_pattern = re.compile(r"^#\s+(.+)$", re.MULTILINE)
        self.heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    async def parse(self, content: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse Markdown content.

        Args:
            content: Markdown content as string
            metadata: Additional metadata

        Returns:
            List[Dict[str, Any]]: Parsed documents
        """
        try:
            logger.info("Parsing Markdown content")

            # Extract frontmatter if present
            frontmatter = self._extract_frontmatter(content)
            if frontmatter:
                # Remove frontmatter from content
                content = self.frontmatter_pattern.sub("", content, count=1)

            # Split content by top-level headings if multiple documents
            documents = await self._split_by_headings(content, frontmatter, metadata)

            if not documents:
                # Treat as single document
                document = await self._parse_single_document(content, frontmatter, metadata, 0)
                if document:
                    documents = [document]

            logger.info(f"Parsed {len(documents)} documents from Markdown")
            return documents

        except Exception as e:
            logger.error(f"Failed to parse Markdown content: {e}")
            raise

    async def _split_by_headings(
        self, content: str, frontmatter: Dict[str, Any], metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Split content by top-level headings (H1).

        Args:
            content: Markdown content
            frontmatter: Extracted frontmatter
            metadata: Additional metadata

        Returns:
            List[Dict[str, Any]]: Split documents
        """
        documents = []

        # Find all H1 headings
        h1_matches = list(re.finditer(r"^#\s+(.+)$", content, re.MULTILINE))

        if len(h1_matches) <= 1:
            # Single document or no H1 headings
            return []

        # Split content at each H1
        for i, match in enumerate(h1_matches):
            start_pos = match.start()
            end_pos = h1_matches[i + 1].start() if i + 1 < len(h1_matches) else len(content)

            section_content = content[start_pos:end_pos].strip()

            if section_content:
                document = await self._parse_single_document(
                    section_content, frontmatter, metadata, i
                )
                if document:
                    documents.append(document)

        return documents

    async def _parse_single_document(
        self,
        content: str,
        frontmatter: Dict[str, Any],
        metadata: Dict[str, Any],
        doc_index: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a single Markdown document.

        Args:
            content: Markdown content
            frontmatter: Extracted frontmatter
            metadata: Additional metadata
            doc_index: Document index

        Returns:
            Optional[Dict[str, Any]]: Parsed document or None
        """
        try:
            if not content.strip():
                return None

            # Extract title
            title = self._extract_title(content, frontmatter)
            if not title:
                title = f"Markdown Document {doc_index + 1}"

            # Extract document metadata
            doc_metadata = self._extract_document_metadata(content, frontmatter)

            # Process content to clean format
            processed_content = self._process_content(content)

            # Build document
            document = {
                "id": frontmatter.get("id", f"markdown_doc_{doc_index}"),
                "title": title,
                "content": processed_content,
                "author": doc_metadata.get("author", ""),
                "created_at": doc_metadata.get("created_at", ""),
                "metadata": {
                    "source_type": "markdown",
                    "document_index": doc_index,
                    "document_title": title,
                    "has_frontmatter": bool(frontmatter),
                    "heading_count": len(self.heading_pattern.findall(content)),
                    **doc_metadata,
                    **frontmatter,
                    **metadata,
                },
            }

            return document

        except Exception as e:
            logger.error(f"Failed to parse single document: {e}")
            return None

    def _extract_frontmatter(self, content: str) -> Dict[str, Any]:
        """
        Extract YAML frontmatter from Markdown content.

        Args:
            content: Markdown content

        Returns:
            Dict[str, Any]: Frontmatter data
        """
        frontmatter = {}

        match = self.frontmatter_pattern.search(content)
        if match:
            try:
                import yaml

                frontmatter_text = match.group(1)
                frontmatter = yaml.safe_load(frontmatter_text) or {}
            except ImportError:
                logger.warning("PyYAML not available, cannot parse frontmatter")
                # Simple key-value parsing as fallback
                frontmatter = self._parse_simple_frontmatter(match.group(1))
            except Exception as e:
                logger.warning(f"Failed to parse frontmatter: {e}")
                frontmatter = self._parse_simple_frontmatter(match.group(1))

        return frontmatter

    def _parse_simple_frontmatter(self, frontmatter_text: str) -> Dict[str, Any]:
        """
        Simple key-value parser for frontmatter (fallback).

        Args:
            frontmatter_text: Frontmatter text

        Returns:
            Dict[str, Any]: Parsed frontmatter
        """
        frontmatter = {}

        for line in frontmatter_text.split("\n"):
            line = line.strip()
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip().strip("\"'")
                frontmatter[key] = value

        return frontmatter

    def _extract_title(self, content: str, frontmatter: Dict[str, Any]) -> str:
        """
        Extract title from content or frontmatter.

        Args:
            content: Markdown content
            frontmatter: Frontmatter data

        Returns:
            str: Document title
        """
        # Try frontmatter first
        title = frontmatter.get("title") or frontmatter.get("Title")
        if title:
            return str(title)

        # Try first H1 heading
        match = self.title_pattern.search(content)
        if match:
            return match.group(1).strip()

        # Try first line if it looks like a title
        lines = content.strip().split("\n")
        if lines:
            first_line = lines[0].strip()
            if first_line and not first_line.startswith("#") and len(first_line) < 100:
                return first_line

        return ""

    def _extract_document_metadata(
        self, content: str, frontmatter: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract document metadata.

        Args:
            content: Markdown content
            frontmatter: Frontmatter data

        Returns:
            Dict[str, Any]: Document metadata
        """
        doc_metadata = {}

        # Extract from frontmatter
        metadata_fields = [
            "author",
            "date",
            "created",
            "modified",
            "tags",
            "category",
            "description",
            "summary",
            "keywords",
            "slug",
        ]

        for field in metadata_fields:
            value = frontmatter.get(field) or frontmatter.get(field.capitalize())
            if value:
                doc_metadata[field] = value

        # Parse date fields
        date_fields = ["date", "created", "modified"]
        for field in date_fields:
            if field in doc_metadata:
                parsed_date = self._parse_date(doc_metadata[field])
                if parsed_date:
                    if field in ["date", "created"]:
                        doc_metadata["created_at"] = parsed_date.isoformat()
                    elif field == "modified":
                        doc_metadata["modified_at"] = parsed_date.isoformat()

        # Extract content statistics
        doc_metadata["word_count"] = len(content.split())
        doc_metadata["character_count"] = len(content)
        doc_metadata["line_count"] = len(content.split("\n"))

        # Extract code blocks count
        code_blocks = re.findall(r"```[\s\S]*?```", content)
        doc_metadata["code_blocks_count"] = len(code_blocks)

        # Extract links count
        links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)
        doc_metadata["links_count"] = len(links)

        # Extract images count
        images = re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", content)
        doc_metadata["images_count"] = len(images)

        return doc_metadata

    def _process_content(self, content: str) -> str:
        """
        Process and clean Markdown content.

        Args:
            content: Raw Markdown content

        Returns:
            str: Processed content
        """
        # Normalize line endings
        content = content.replace("\r\n", "\n").replace("\r", "\n")

        # Remove excessive blank lines
        content = re.sub(r"\n{3,}", "\n\n", content)

        # Clean up whitespace
        lines = []
        for line in content.split("\n"):
            lines.append(line.rstrip())

        content = "\n".join(lines)

        # Ensure proper spacing around headings
        content = re.sub(r"\n(#{1,6}\s+.+)\n", r"\n\n\1\n\n", content)

        # Clean up the result
        content = re.sub(r"\n{3,}", "\n\n", content)

        return content.strip()

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse date string to datetime object.

        Args:
            date_str: Date string

        Returns:
            Optional[datetime]: Parsed datetime or None
        """
        if not date_str:
            return None

        # Common date formats
        date_formats = [
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y/%m/%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%d/%m/%Y",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%m/%d/%Y",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%fZ",
        ]

        for date_format in date_formats:
            try:
                return datetime.strptime(str(date_str).strip(), date_format)
            except ValueError:
                continue

        logger.warning(f"Could not parse date: {date_str}")
        return None

    def validate_markdown(self, content: str) -> bool:
        """
        Validate if content is valid Markdown.

        Args:
            content: Content to validate

        Returns:
            bool: True if valid Markdown
        """
        try:
            # Try to process with markdown
            self.md.convert(content)
            return True
        except Exception:
            return False

    def get_markdown_stats(self, content: str) -> Dict[str, Any]:
        """
        Get statistics about Markdown content.

        Args:
            content: Markdown content

        Returns:
            Dict[str, Any]: Content statistics
        """
        stats = {}

        # Basic counts
        stats["word_count"] = len(content.split())
        stats["character_count"] = len(content)
        stats["line_count"] = len(content.split("\n"))

        # Heading counts
        headings = self.heading_pattern.findall(content)
        stats["heading_count"] = len(headings)

        heading_levels = {}
        for level, text in headings:
            level_num = len(level)
            heading_levels[f"h{level_num}"] = heading_levels.get(f"h{level_num}", 0) + 1
        stats["heading_levels"] = heading_levels

        # Code blocks
        code_blocks = re.findall(r"```[\s\S]*?```", content)
        stats["code_blocks_count"] = len(code_blocks)

        # Inline code
        inline_code = re.findall(r"`[^`]+`", content)
        stats["inline_code_count"] = len(inline_code)

        # Links
        links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)
        stats["links_count"] = len(links)

        # Images
        images = re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", content)
        stats["images_count"] = len(images)

        # Lists
        unordered_lists = re.findall(r"^\s*[-*+]\s+", content, re.MULTILINE)
        ordered_lists = re.findall(r"^\s*\d+\.\s+", content, re.MULTILINE)
        stats["unordered_list_items"] = len(unordered_lists)
        stats["ordered_list_items"] = len(ordered_lists)

        # Tables
        table_rows = re.findall(r"^\|.*\|$", content, re.MULTILINE)
        stats["table_rows"] = len(table_rows)

        # Frontmatter
        stats["has_frontmatter"] = bool(self.frontmatter_pattern.search(content))

        return stats
