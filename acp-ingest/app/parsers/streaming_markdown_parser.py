"""Streaming Markdown parser for large files."""

import logging
import re
from collections.abc import Iterator
from typing import Any

logger = logging.getLogger(__name__)


class StreamingMarkdownParser:
    """Parser for Markdown documents with streaming support."""

    def __init__(self, chunk_size: int = 8192, max_chunk_size: int = 2000):
        """Initialize streaming markdown parser.

        Args:
            chunk_size: Size of file chunks to read at a time
            max_chunk_size: Maximum size of text chunks to create
        """
        self.chunk_size = chunk_size
        self.max_chunk_size = max_chunk_size

        # Patterns for extracting metadata
        self.frontmatter_pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL | re.MULTILINE)
        self.title_pattern = re.compile(r"^#\s+(.+)$", re.MULTILINE)
        self.heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    def parse_file_streaming(
        self, file_path: str, metadata: dict[str, Any]
    ) -> Iterator[dict[str, Any]]:
        """Parse Markdown file with streaming to handle large files.

        Args:
            file_path: Path to the Markdown file
            metadata: Additional metadata

        Yields:
            Dict[str, Any]: Parsed Markdown chunks
        """
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as file:
                buffer = ""
                chunk_index = 0
                current_section = ""
                section_level = 0

                while True:
                    # Read chunk from file
                    chunk = file.read(self.chunk_size)
                    if not chunk:
                        # Process remaining buffer
                        if buffer.strip():
                            for doc_chunk in self._process_markdown_content(
                                buffer.strip(),
                                chunk_index,
                                metadata,
                                current_section,
                                section_level,
                            ):
                                yield doc_chunk
                                chunk_index += 1
                        break

                    # Add chunk to buffer
                    buffer += chunk

                    # Process complete lines from buffer
                    while "\n" in buffer:
                        line_end = buffer.find("\n")
                        line = buffer[:line_end]
                        buffer = buffer[line_end + 1 :]

                        # Check for headings to track section structure
                        heading_match = self.heading_pattern.match(line)
                        if heading_match:
                            # Process previous section if it exists
                            if current_section.strip():
                                for doc_chunk in self._process_markdown_content(
                                    current_section.strip(),
                                    chunk_index,
                                    metadata,
                                    current_section,
                                    section_level,
                                ):
                                    yield doc_chunk
                                    chunk_index += 1

                            # Start new section
                            current_section = line
                            section_level = len(heading_match.group(1))
                        else:
                            # Add line to current section
                            current_section += "\n" + line

                            # Check if section is getting too large
                            if len(current_section) > self.max_chunk_size:
                                for doc_chunk in self._process_markdown_content(
                                    current_section.strip(),
                                    chunk_index,
                                    metadata,
                                    current_section,
                                    section_level,
                                ):
                                    yield doc_chunk
                                    chunk_index += 1
                                current_section = ""

        except Exception as e:
            logger.error(f"Error parsing Markdown file {file_path}: {e}")
            raise

    def parse_file(self, file_path: str, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse Markdown file (non-streaming version for compatibility).

        Args:
            file_path: Path to the Markdown file
            metadata: Additional metadata

        Returns:
            List[Dict[str, Any]]: Parsed Markdown chunks
        """
        return list(self.parse_file_streaming(file_path, metadata))

    def _process_markdown_content(
        self,
        content: str,
        chunk_index: int,
        metadata: dict[str, Any],
        section_context: str,
        section_level: int,
    ) -> Iterator[dict[str, Any]]:
        """Process Markdown content into chunks.

        Args:
            content: Markdown content to process
            chunk_index: Base chunk index
            metadata: Additional metadata
            section_context: Context from section
            section_level: Heading level

        Yields:
            Dict[str, Any]: Processed chunks
        """
        # Extract title from content
        title_match = self.title_pattern.search(content)
        title = title_match.group(1) if title_match else "Untitled"

        # Clean markdown formatting for text content
        text_content = self._clean_markdown(content)

        # Split content if it's too large
        if len(text_content) > self.max_chunk_size:
            # Split by paragraphs first
            paragraphs = text_content.split("\n\n")
            current_chunk = ""

            for paragraph in paragraphs:
                if len(current_chunk) + len(paragraph) + 2 > self.max_chunk_size and current_chunk:
                    yield self._create_chunk(
                        current_chunk.strip(), chunk_index, metadata, title, section_level
                    )
                    chunk_index += 1
                    current_chunk = paragraph
                else:
                    if current_chunk:
                        current_chunk += "\n\n" + paragraph
                    else:
                        current_chunk = paragraph

            # Yield remaining chunk
            if current_chunk.strip():
                yield self._create_chunk(
                    current_chunk.strip(), chunk_index, metadata, title, section_level
                )
        else:
            # Single chunk
            yield self._create_chunk(text_content, chunk_index, metadata, title, section_level)

    def _clean_markdown(self, content: str) -> str:
        """Clean Markdown formatting from content.

        Args:
            content: Markdown content

        Returns:
            str: Cleaned text content
        """
        # Remove frontmatter
        content = self.frontmatter_pattern.sub("", content)

        # Remove code blocks
        content = re.sub(r"```[\s\S]*?```", "", content)
        content = re.sub(r"`[^`]+`", "", content)

        # Remove links but keep text
        content = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", content)

        # Remove images
        content = re.sub(r"!\[([^\]]*)\]\([^)]+\)", "", content)

        # Remove bold/italic formatting
        content = re.sub(r"\*\*([^*]+)\*\*", r"\1", content)
        content = re.sub(r"\*([^*]+)\*", r"\1", content)
        content = re.sub(r"__([^_]+)__", r"\1", content)
        content = re.sub(r"_([^_]+)_", r"\1", content)

        # Remove strikethrough
        content = re.sub(r"~~([^~]+)~~", r"\1", content)

        # Remove horizontal rules
        content = re.sub(r"^---+$", "", content, flags=re.MULTILINE)

        # Clean up multiple newlines
        content = re.sub(r"\n{3,}", "\n\n", content)

        return content.strip()

    def _create_chunk(
        self,
        content: str,
        chunk_index: int,
        metadata: dict[str, Any],
        title: str,
        section_level: int,
    ) -> dict[str, Any]:
        """Create a Markdown chunk document.

        Args:
            content: Text content
            chunk_index: Chunk index
            metadata: Additional metadata
            title: Document/section title
            section_level: Heading level

        Returns:
            Dict[str, Any]: Markdown chunk document
        """
        return {
            "content": content,
            "type": "markdown",
            "chunk_index": chunk_index,
            "metadata": {
                **metadata,
                "chunk_type": "markdown_section",
                "title": title,
                "section_level": section_level,
                "length": len(content),
            },
        }
