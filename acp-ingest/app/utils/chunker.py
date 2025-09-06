"""Text chunking utility for semantic document splitting."""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ChunkConfig:
    """Configuration for text chunking."""

    max_chunk_size: int = 1000
    min_chunk_size: int = 100
    overlap_size: int = 200
    preserve_structure: bool = True
    split_on_sentences: bool = True
    split_on_paragraphs: bool = True
    split_on_headings: bool = True


class TextChunker:
    """Utility for chunking text into semantic segments."""

    def __init__(self, config: Optional[ChunkConfig] = None):
        self.config = config or ChunkConfig()

        # Patterns for different text structures
        self.heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
        self.paragraph_pattern = re.compile(r"\n\s*\n")
        self.sentence_pattern = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
        self.code_block_pattern = re.compile(r"```[\s\S]*?```|`[^`]+`")
        self.list_pattern = re.compile(r"^(\s*[-*+]\s+|\s*\d+\.\s+)", re.MULTILINE)

        # Sentence boundary detection
        self.sentence_endings = re.compile(r"[.!?]+")
        self.abbreviations = {
            "dr",
            "mr",
            "mrs",
            "ms",
            "prof",
            "inc",
            "ltd",
            "corp",
            "co",
            "vs",
            "etc",
            "ie",
            "eg",
            "al",
            "st",
            "ave",
            "blvd",
            "rd",
        }

    async def create_chunks(
        self, text: str, metadata: Dict[str, Any], config: Optional[ChunkConfig] = None
    ) -> List[Dict[str, Any]]:
        """
        Create semantic chunks from text.

        Args:
            text: Text to chunk
            metadata: Metadata to attach to chunks
            config: Chunking configuration

        Returns:
            List[Dict[str, Any]]: List of text chunks with metadata
        """
        chunk_config = config or self.config

        try:
            logger.debug(f"Chunking text of length {len(text)}")

            # Preprocess text
            text = self._preprocess_text(text)

            # Extract structure if enabled
            if chunk_config.preserve_structure:
                chunks = await self._chunk_with_structure(text, metadata, chunk_config)
            else:
                chunks = await self._chunk_simple(text, metadata, chunk_config)

            # Post-process chunks
            chunks = self._post_process_chunks(chunks, chunk_config)

            logger.debug(f"Created {len(chunks)} chunks")
            return chunks

        except Exception as e:
            logger.error(f"Chunking failed: {e}")
            # Fallback to simple chunking
            return await self._chunk_simple(text, metadata, chunk_config)

    def _preprocess_text(self, text: str) -> str:
        """
        Preprocess text before chunking.

        Args:
            text: Raw text

        Returns:
            str: Preprocessed text
        """
        # Normalize whitespace
        text = re.sub(r"\r\n", "\n", text)
        text = re.sub(r"\r", "\n", text)

        # Remove excessive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Clean up spaces
        text = re.sub(r"[ \t]+", " ", text)

        return text.strip()

    async def _chunk_with_structure(
        self, text: str, metadata: Dict[str, Any], config: ChunkConfig
    ) -> List[Dict[str, Any]]:
        """
        Chunk text preserving document structure.

        Args:
            text: Text to chunk
            metadata: Base metadata
            config: Chunking configuration

        Returns:
            List[Dict[str, Any]]: Structured chunks
        """
        chunks = []

        # Split by headings first
        if config.split_on_headings:
            sections = self._split_by_headings(text)
        else:
            sections = [{"level": 0, "title": "", "content": text, "start": 0}]

        for section in sections:
            section_chunks = await self._chunk_section(
                section["content"],
                metadata,
                config,
                section_info={
                    "heading_level": section["level"],
                    "heading_title": section["title"],
                    "section_start": section["start"],
                },
            )
            chunks.extend(section_chunks)

        return chunks

    def _split_by_headings(self, text: str) -> List[Dict[str, Any]]:
        """
        Split text by headings.

        Args:
            text: Text to split

        Returns:
            List[Dict[str, Any]]: Sections with heading info
        """
        sections = []
        heading_matches = list(self.heading_pattern.finditer(text))

        if not heading_matches:
            # No headings found, treat as single section
            return [{"level": 0, "title": "", "content": text, "start": 0}]

        # Process each section
        for i, match in enumerate(heading_matches):
            level = len(match.group(1))  # Number of # characters
            title = match.group(2).strip()
            start_pos = match.start()

            # Find content end (next heading or end of text)
            if i + 1 < len(heading_matches):
                end_pos = heading_matches[i + 1].start()
            else:
                end_pos = len(text)

            content = text[start_pos:end_pos].strip()

            sections.append(
                {"level": level, "title": title, "content": content, "start": start_pos}
            )

        # Handle content before first heading
        if heading_matches[0].start() > 0:
            intro_content = text[: heading_matches[0].start()].strip()
            if intro_content:
                sections.insert(
                    0,
                    {
                        "level": 0,
                        "title": "Introduction",
                        "content": intro_content,
                        "start": 0,
                    },
                )

        return sections

    async def _chunk_section(
        self,
        text: str,
        metadata: Dict[str, Any],
        config: ChunkConfig,
        section_info: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Chunk a single section.

        Args:
            text: Section text
            metadata: Base metadata
            config: Chunking configuration
            section_info: Section information

        Returns:
            List[Dict[str, Any]]: Section chunks
        """
        chunks = []

        # If section is small enough, keep as single chunk
        if len(text) <= config.max_chunk_size:
            chunk = self._create_chunk(text, metadata, section_info, 0)
            chunks.append(chunk)
            return chunks

        # Split by paragraphs if enabled
        if config.split_on_paragraphs:
            paragraphs = self._split_by_paragraphs(text)
        else:
            paragraphs = [text]

        current_chunk = ""
        chunk_index = 0

        for paragraph in paragraphs:
            # Check if adding this paragraph would exceed chunk size
            if (
                current_chunk
                and len(current_chunk) + len(paragraph) > config.max_chunk_size
            ):
                # Create chunk from current content
                if current_chunk.strip():
                    chunk = self._create_chunk(
                        current_chunk.strip(), metadata, section_info, chunk_index
                    )
                    chunks.append(chunk)
                    chunk_index += 1

                # Start new chunk with overlap if configured
                if config.overlap_size > 0 and current_chunk:
                    overlap = self._get_overlap_text(current_chunk, config.overlap_size)
                    current_chunk = overlap + "\n\n" + paragraph
                else:
                    current_chunk = paragraph
            else:
                # Add paragraph to current chunk
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph

        # Add final chunk
        if current_chunk.strip():
            chunk = self._create_chunk(
                current_chunk.strip(), metadata, section_info, chunk_index
            )
            chunks.append(chunk)

        return chunks

    def _split_by_paragraphs(self, text: str) -> List[str]:
        """
        Split text by paragraphs.

        Args:
            text: Text to split

        Returns:
            List[str]: Paragraphs
        """
        # Split on double newlines
        paragraphs = self.paragraph_pattern.split(text)

        # Clean up paragraphs
        cleaned_paragraphs = []
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if paragraph:
                cleaned_paragraphs.append(paragraph)

        return cleaned_paragraphs

    async def _chunk_simple(
        self, text: str, metadata: Dict[str, Any], config: ChunkConfig
    ) -> List[Dict[str, Any]]:
        """
        Simple text chunking without structure preservation.

        Args:
            text: Text to chunk
            metadata: Base metadata
            config: Chunking configuration

        Returns:
            List[Dict[str, Any]]: Simple chunks
        """
        chunks = []

        # Split by sentences if enabled
        if config.split_on_sentences:
            sentences = self._split_by_sentences(text)
        else:
            # Split by words as fallback
            words = text.split()
            sentences = []
            current_sentence = []

            for word in words:
                current_sentence.append(word)
                if len(" ".join(current_sentence)) >= config.max_chunk_size // 2:
                    sentences.append(" ".join(current_sentence))
                    current_sentence = []

            if current_sentence:
                sentences.append(" ".join(current_sentence))

        current_chunk = ""
        chunk_index = 0

        for sentence in sentences:
            # Check if adding this sentence would exceed chunk size
            if (
                current_chunk
                and len(current_chunk) + len(sentence) > config.max_chunk_size
            ):
                # Create chunk from current content
                if current_chunk.strip():
                    chunk = self._create_chunk(
                        current_chunk.strip(),
                        metadata,
                        {"heading_level": 0, "heading_title": "", "section_start": 0},
                        chunk_index,
                    )
                    chunks.append(chunk)
                    chunk_index += 1

                # Start new chunk with overlap
                if config.overlap_size > 0 and current_chunk:
                    overlap = self._get_overlap_text(current_chunk, config.overlap_size)
                    current_chunk = overlap + " " + sentence
                else:
                    current_chunk = sentence
            else:
                # Add sentence to current chunk
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence

        # Add final chunk
        if current_chunk.strip():
            chunk = self._create_chunk(
                current_chunk.strip(),
                metadata,
                {"heading_level": 0, "heading_title": "", "section_start": 0},
                chunk_index,
            )
            chunks.append(chunk)

        return chunks

    def _split_by_sentences(self, text: str) -> List[str]:
        """
        Split text by sentences with abbreviation handling.

        Args:
            text: Text to split

        Returns:
            List[str]: Sentences
        """
        sentences = []

        # Simple sentence splitting with abbreviation handling
        potential_sentences = self.sentence_pattern.split(text)

        for sentence in potential_sentences:
            sentence = sentence.strip()
            if sentence:
                # Check for abbreviations at the end
                words = sentence.split()
                if words and words[-1].lower().rstrip(".") in self.abbreviations:
                    # Might be an abbreviation, be more careful
                    if len(sentence) > 10:  # Minimum sentence length
                        sentences.append(sentence)
                else:
                    sentences.append(sentence)

        return sentences

    def _get_overlap_text(self, text: str, overlap_size: int) -> str:
        """
        Get overlap text from the end of a chunk.

        Args:
            text: Source text
            overlap_size: Size of overlap in characters

        Returns:
            str: Overlap text
        """
        if len(text) <= overlap_size:
            return text

        # Try to break at sentence boundary
        overlap_text = text[-overlap_size:]

        # Find the first sentence boundary in the overlap
        sentence_match = self.sentence_pattern.search(overlap_text)
        if sentence_match:
            return overlap_text[sentence_match.end() :].strip()

        # Fallback to word boundary
        words = overlap_text.split()
        if len(words) > 1:
            return " ".join(words[1:])

        return overlap_text

    def _create_chunk(
        self,
        text: str,
        metadata: Dict[str, Any],
        section_info: Dict[str, Any],
        chunk_index: int,
    ) -> Dict[str, Any]:
        """
        Create a chunk with metadata.

        Args:
            text: Chunk text
            metadata: Base metadata
            section_info: Section information
            chunk_index: Index of chunk within section

        Returns:
            Dict[str, Any]: Chunk with metadata
        """
        chunk_metadata = {
            **metadata,
            "chunk_index": chunk_index,
            "chunk_size": len(text),
            "word_count": len(text.split()),
            "heading_level": section_info.get("heading_level", 0),
            "heading_title": section_info.get("heading_title", ""),
            "section_start": section_info.get("section_start", 0),
        }

        # Add content type hints
        if self.code_block_pattern.search(text):
            chunk_metadata["contains_code"] = True

        if self.list_pattern.search(text):
            chunk_metadata["contains_list"] = True

        if self.heading_pattern.search(text):
            chunk_metadata["contains_headings"] = True

        return {"text": text, "metadata": chunk_metadata}

    def _post_process_chunks(
        self, chunks: List[Dict[str, Any]], config: ChunkConfig
    ) -> List[Dict[str, Any]]:
        """
        Post-process chunks to ensure quality.

        Args:
            chunks: Raw chunks
            config: Chunking configuration

        Returns:
            List[Dict[str, Any]]: Processed chunks
        """
        processed_chunks = []

        for chunk in chunks:
            text = chunk["text"].strip()

            # Skip chunks that are too small
            if len(text) < config.min_chunk_size:
                # Try to merge with previous chunk if possible
                if (
                    processed_chunks
                    and len(processed_chunks[-1]["text"]) + len(text)
                    <= config.max_chunk_size
                ):
                    processed_chunks[-1]["text"] += "\n\n" + text
                    processed_chunks[-1]["metadata"]["chunk_size"] = len(
                        processed_chunks[-1]["text"]
                    )
                    processed_chunks[-1]["metadata"]["word_count"] = len(
                        processed_chunks[-1]["text"].split()
                    )
                    continue
                # Otherwise skip if too small
                elif len(text) < config.min_chunk_size // 2:
                    continue

            processed_chunks.append(chunk)

        # Add final chunk indices
        for i, chunk in enumerate(processed_chunks):
            chunk["metadata"]["final_chunk_index"] = i
            chunk["metadata"]["total_chunks"] = len(processed_chunks)

        return processed_chunks

    def estimate_chunks(self, text: str, config: Optional[ChunkConfig] = None) -> int:
        """
        Estimate number of chunks that will be created.

        Args:
            text: Text to analyze
            config: Chunking configuration

        Returns:
            int: Estimated number of chunks
        """
        chunk_config = config or self.config

        # Simple estimation based on text length
        estimated_chunks = max(1, len(text) // chunk_config.max_chunk_size)

        # Adjust for overlap
        if chunk_config.overlap_size > 0:
            estimated_chunks = int(estimated_chunks * 1.2)  # 20% increase for overlap

        return estimated_chunks

    def get_chunk_stats(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get statistics about chunks.

        Args:
            chunks: List of chunks

        Returns:
            Dict[str, Any]: Chunk statistics
        """
        if not chunks:
            return {}

        sizes = [chunk["metadata"]["chunk_size"] for chunk in chunks]
        word_counts = [chunk["metadata"]["word_count"] for chunk in chunks]

        stats = {
            "total_chunks": len(chunks),
            "total_characters": sum(sizes),
            "total_words": sum(word_counts),
            "avg_chunk_size": sum(sizes) / len(sizes),
            "min_chunk_size": min(sizes),
            "max_chunk_size": max(sizes),
            "avg_word_count": sum(word_counts) / len(word_counts),
            "chunks_with_code": sum(
                1 for chunk in chunks if chunk["metadata"].get("contains_code", False)
            ),
            "chunks_with_lists": sum(
                1 for chunk in chunks if chunk["metadata"].get("contains_list", False)
            ),
            "chunks_with_headings": sum(
                1
                for chunk in chunks
                if chunk["metadata"].get("contains_headings", False)
            ),
        }

        return stats
