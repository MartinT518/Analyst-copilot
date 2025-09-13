"""Text parser with streaming support for large files."""

import logging
from collections.abc import Iterator
from typing import Any

logger = logging.getLogger(__name__)


class StreamingTextParser:
    """Parser for plain text files with streaming support."""

    def __init__(self, chunk_size: int = 8192, max_chunk_size: int = 1000):
        """Initialize streaming text parser.

        Args:
            chunk_size: Size of file chunks to read at a time
            max_chunk_size: Maximum size of text chunks to create
        """
        self.chunk_size = chunk_size
        self.max_chunk_size = max_chunk_size

    def parse_file_streaming(
        self, file_path: str, metadata: dict[str, Any]
    ) -> Iterator[dict[str, Any]]:
        """Parse text file with streaming to handle large files.

        Args:
            file_path: Path to the text file
            metadata: Additional metadata

        Yields:
            Dict[str, Any]: Parsed text chunks
        """
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as file:
                buffer = ""
                chunk_index = 0

                while True:
                    # Read chunk from file
                    chunk = file.read(self.chunk_size)
                    if not chunk:
                        # Process remaining buffer
                        if buffer.strip():
                            yield self._create_chunk(buffer.strip(), chunk_index, metadata)
                        break

                    # Add chunk to buffer
                    buffer += chunk

                    # Process complete lines from buffer
                    while "\n" in buffer:
                        line_end = buffer.find("\n")
                        line = buffer[:line_end].strip()
                        buffer = buffer[line_end + 1 :]

                        if line:
                            # Check if adding this line would exceed max chunk size
                            if len(line) > self.max_chunk_size:
                                # Split long line into smaller chunks
                                for sub_chunk in self._split_long_line(line, chunk_index, metadata):
                                    yield sub_chunk
                                    chunk_index += 1
                            else:
                                yield self._create_chunk(line, chunk_index, metadata)
                                chunk_index += 1

        except Exception as e:
            logger.error(f"Error parsing text file {file_path}: {e}")
            raise

    def parse_file(self, file_path: str, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse text file (non-streaming version for compatibility).

        Args:
            file_path: Path to the text file
            metadata: Additional metadata

        Returns:
            List[Dict[str, Any]]: Parsed text chunks
        """
        return list(self.parse_file_streaming(file_path, metadata))

    def _split_long_line(
        self, line: str, base_chunk_index: int, metadata: dict[str, Any]
    ) -> Iterator[dict[str, Any]]:
        """Split a long line into smaller chunks.

        Args:
            line: Long line to split
            base_chunk_index: Base chunk index
            metadata: Additional metadata

        Yields:
            Dict[str, Any]: Text chunks
        """
        words = line.split()
        current_chunk = ""
        chunk_index = base_chunk_index

        for word in words:
            # Check if adding this word would exceed max chunk size
            if len(current_chunk) + len(word) + 1 > self.max_chunk_size and current_chunk:
                yield self._create_chunk(current_chunk.strip(), chunk_index, metadata)
                current_chunk = word
                chunk_index += 1
            else:
                if current_chunk:
                    current_chunk += " " + word
                else:
                    current_chunk = word

        # Yield remaining chunk
        if current_chunk.strip():
            yield self._create_chunk(current_chunk.strip(), chunk_index, metadata)

    def _create_chunk(
        self, content: str, chunk_index: int, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a text chunk document.

        Args:
            content: Text content
            chunk_index: Chunk index
            metadata: Additional metadata

        Returns:
            Dict[str, Any]: Text chunk document
        """
        return {
            "content": content,
            "type": "text",
            "chunk_index": chunk_index,
            "metadata": {
                **metadata,
                "chunk_type": "text_line",
                "length": len(content),
            },
        }


class TextParser(StreamingTextParser):
    """Legacy text parser for backward compatibility."""

    async def parse(self, content: str, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse text content.

        Args:
            content: Text content
            metadata: Additional metadata

        Returns:
            List[Dict[str, Any]]: Parsed text chunks
        """
        lines = content.split("\n")
        chunks = []

        for i, line in enumerate(lines):
            line = line.strip()
            if line:
                chunks.append(self._create_chunk(line, i, metadata))

        return chunks
