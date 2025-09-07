"""PII detection and redaction utility using Presidio and custom rules."""

import logging
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class RedactionMode(str, Enum):
    """Redaction modes."""

    REDACT = "redact"
    PSEUDONYMIZE = "pseudonymize"
    MASK = "mask"


class PIIDetector:
    """PII detection and redaction service."""

    def __init__(self):
        self.presidio_available = False
        self.analyzer = None
        self.anonymizer = None

        # Initialize Presidio if available
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_anonymizer import AnonymizerEngine

            self.analyzer = AnalyzerEngine()
            self.anonymizer = AnonymizerEngine()
            self.presidio_available = True
            logger.info("Presidio PII detection initialized")
        except ImportError:
            logger.warning("Presidio not available, using regex-based PII detection")

        # Custom PII patterns
        self.pii_patterns = {
            "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
            "phone": re.compile(
                r"(\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})"
            ),
            "ssn": re.compile(r"\b\d{3}-?\d{2}-?\d{4}\b"),
            "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
            "ip_address": re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"),
            "api_key": re.compile(r"\b[A-Za-z0-9]{32,}\b"),
            "uuid": re.compile(
                r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"
            ),
            "url": re.compile(
                r"https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:\w*))?)?"
            ),
            "file_path": re.compile(
                r'[A-Za-z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*'
            ),
            "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
            "private_key": re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
        }

        # Custom entity patterns for enterprise environments
        self.enterprise_patterns = {
            "employee_id": re.compile(r"\b[Ee][Mm][Pp]\d{4,8}\b"),
            "ticket_id": re.compile(r"\b[A-Z]{2,5}-\d{3,6}\b"),
            "server_name": re.compile(r"\b[a-z]+-[a-z]+-\d{2,3}\b"),
            "database_name": re.compile(r"\b[a-z]+_db_[a-z0-9]+\b"),
        }

        # Pseudonymization mappings
        self.pseudonym_mappings = {}
        self.pseudonym_counters = {}

    async def initialize(self):
        """Initialize the PII detector."""
        logger.info("PII detector initialized")

    async def process_text(self, text: str, mode: str = "redact") -> str:
        """
        Process text to detect and redact/pseudonymize PII.

        Args:
            text: Text to process
            mode: Processing mode (redact, pseudonymize, mask)

        Returns:
            str: Processed text
        """
        try:
            if self.presidio_available:
                return await self._process_with_presidio(text, mode)
            else:
                return await self._process_with_regex(text, mode)
        except Exception as e:
            logger.error(f"PII processing failed: {e}")
            return text  # Return original text if processing fails

    async def _process_with_presidio(self, text: str, mode: str) -> str:
        """
        Process text using Presidio.

        Args:
            text: Text to process
            mode: Processing mode

        Returns:
            str: Processed text
        """
        try:
            # Analyze text for PII
            results = self.analyzer.analyze(
                text=text,
                language="en",
                entities=[
                    "PERSON",
                    "EMAIL_ADDRESS",
                    "PHONE_NUMBER",
                    "CREDIT_CARD",
                    "IP_ADDRESS",
                    "IBAN_CODE",
                    "US_SSN",
                    "US_PASSPORT",
                    "US_DRIVER_LICENSE",
                    "DATE_TIME",
                    "LOCATION",
                    "URL",
                ],
            )

            # Apply anonymization
            if mode == RedactionMode.REDACT:
                anonymized_result = self.anonymizer.anonymize(
                    text=text,
                    analyzer_results=results,
                    operators={
                        "DEFAULT": {"type": "replace", "new_value": "[REDACTED]"}
                    },
                )
            elif mode == RedactionMode.PSEUDONYMIZE:
                anonymized_result = self.anonymizer.anonymize(
                    text=text,
                    analyzer_results=results,
                    operators={"DEFAULT": {"type": "hash"}},
                )
            elif mode == RedactionMode.MASK:
                anonymized_result = self.anonymizer.anonymize(
                    text=text,
                    analyzer_results=results,
                    operators={
                        "DEFAULT": {
                            "type": "mask",
                            "masking_char": "*",
                            "chars_to_mask": 4,
                        }
                    },
                )
            else:
                return text

            processed_text = anonymized_result.text

            # Apply custom regex patterns
            processed_text = await self._apply_custom_patterns(processed_text, mode)

            return processed_text

        except Exception as e:
            logger.error(f"Presidio processing failed: {e}")
            return await self._process_with_regex(text, mode)

    async def _process_with_regex(self, text: str, mode: str) -> str:
        """
        Process text using regex patterns.

        Args:
            text: Text to process
            mode: Processing mode

        Returns:
            str: Processed text
        """
        processed_text = text

        # Apply PII patterns
        for pii_type, pattern in self.pii_patterns.items():
            if mode == RedactionMode.REDACT:
                processed_text = pattern.sub(
                    f"[{pii_type.upper()}_REDACTED]", processed_text
                )
            elif mode == RedactionMode.PSEUDONYMIZE:
                processed_text = self._pseudonymize_matches(
                    processed_text, pattern, pii_type
                )
            elif mode == RedactionMode.MASK:
                processed_text = self._mask_matches(processed_text, pattern)

        # Apply enterprise patterns
        for entity_type, pattern in self.enterprise_patterns.items():
            if mode == RedactionMode.REDACT:
                processed_text = pattern.sub(
                    f"[{entity_type.upper()}_REDACTED]", processed_text
                )
            elif mode == RedactionMode.PSEUDONYMIZE:
                processed_text = self._pseudonymize_matches(
                    processed_text, pattern, entity_type
                )
            elif mode == RedactionMode.MASK:
                processed_text = self._mask_matches(processed_text, pattern)

        return processed_text

    async def _apply_custom_patterns(self, text: str, mode: str) -> str:
        """
        Apply custom regex patterns after Presidio processing.

        Args:
            text: Text to process
            mode: Processing mode

        Returns:
            str: Processed text
        """
        processed_text = text

        # Apply patterns that Presidio might miss
        custom_patterns = {**self.pii_patterns, **self.enterprise_patterns}

        for pii_type, pattern in custom_patterns.items():
            if mode == RedactionMode.REDACT:
                processed_text = pattern.sub(
                    f"[{pii_type.upper()}_REDACTED]", processed_text
                )
            elif mode == RedactionMode.PSEUDONYMIZE:
                processed_text = self._pseudonymize_matches(
                    processed_text, pattern, pii_type
                )
            elif mode == RedactionMode.MASK:
                processed_text = self._mask_matches(processed_text, pattern)

        return processed_text

    def _pseudonymize_matches(
        self, text: str, pattern: re.Pattern, entity_type: str
    ) -> str:
        """
        Pseudonymize matches with consistent replacements.

        Args:
            text: Text to process
            pattern: Regex pattern
            entity_type: Type of entity

        Returns:
            str: Text with pseudonymized matches
        """

        def replace_match(match):
            original = match.group(0)

            # Check if we already have a pseudonym for this value
            if original in self.pseudonym_mappings:
                return self.pseudonym_mappings[original]

            # Generate new pseudonym
            if entity_type not in self.pseudonym_counters:
                self.pseudonym_counters[entity_type] = 0

            self.pseudonym_counters[entity_type] += 1
            pseudonym = (
                f"{entity_type.upper()}_{self.pseudonym_counters[entity_type]:04d}"
            )

            # Store mapping
            self.pseudonym_mappings[original] = pseudonym

            return pseudonym

        return pattern.sub(replace_match, text)

    def _mask_matches(self, text: str, pattern: re.Pattern) -> str:
        """
        Mask matches with asterisks.

        Args:
            text: Text to process
            pattern: Regex pattern

        Returns:
            str: Text with masked matches
        """

        def replace_match(match):
            original = match.group(0)
            if len(original) <= 4:
                return "*" * len(original)
            else:
                # Keep first and last 2 characters, mask the middle
                return original[:2] + "*" * (len(original) - 4) + original[-2:]

        return pattern.sub(replace_match, text)

    def detect_pii_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect PII entities in text without modifying it.

        Args:
            text: Text to analyze

        Returns:
            List[Dict[str, Any]]: List of detected PII entities
        """
        entities = []

        if self.presidio_available:
            try:
                results = self.analyzer.analyze(text=text, language="en")
                for result in results:
                    entities.append(
                        {
                            "type": result.entity_type,
                            "start": result.start,
                            "end": result.end,
                            "confidence": result.score,
                            "text": text[result.start : result.end],
                        }
                    )
            except Exception as e:
                logger.error(f"Presidio analysis failed: {e}")

        # Add regex-based detections
        all_patterns = {**self.pii_patterns, **self.enterprise_patterns}

        for pii_type, pattern in all_patterns.items():
            for match in pattern.finditer(text):
                entities.append(
                    {
                        "type": pii_type,
                        "start": match.start(),
                        "end": match.end(),
                        "confidence": 0.8,  # Default confidence for regex matches
                        "text": match.group(0),
                    }
                )

        # Sort by start position
        entities.sort(key=lambda x: x["start"])

        return entities

    def add_custom_pattern(self, name: str, pattern: str, entity_type: str = "custom"):
        """
        Add a custom PII pattern.

        Args:
            name: Pattern name
            pattern: Regex pattern string
            entity_type: Type of entity (pii or enterprise)
        """
        try:
            compiled_pattern = re.compile(pattern)

            if entity_type == "enterprise":
                self.enterprise_patterns[name] = compiled_pattern
            else:
                self.pii_patterns[name] = compiled_pattern

            logger.info(f"Added custom {entity_type} pattern: {name}")

        except re.error as e:
            logger.error(f"Invalid regex pattern '{pattern}': {e}")

    def remove_custom_pattern(self, name: str):
        """
        Remove a custom PII pattern.

        Args:
            name: Pattern name to remove
        """
        removed = False

        if name in self.pii_patterns:
            del self.pii_patterns[name]
            removed = True

        if name in self.enterprise_patterns:
            del self.enterprise_patterns[name]
            removed = True

        if removed:
            logger.info(f"Removed custom pattern: {name}")
        else:
            logger.warning(f"Pattern not found: {name}")

    def get_supported_entities(self) -> Dict[str, List[str]]:
        """
        Get list of supported PII entity types.

        Returns:
            Dict[str, List[str]]: Supported entity types by category
        """
        entities = {
            "presidio": [],
            "regex_pii": list(self.pii_patterns.keys()),
            "regex_enterprise": list(self.enterprise_patterns.keys()),
        }

        if self.presidio_available:
            entities["presidio"] = [
                "PERSON",
                "EMAIL_ADDRESS",
                "PHONE_NUMBER",
                "CREDIT_CARD",
                "IP_ADDRESS",
                "IBAN_CODE",
                "US_SSN",
                "US_PASSPORT",
                "US_DRIVER_LICENSE",
                "DATE_TIME",
                "LOCATION",
                "URL",
            ]

        return entities

    def clear_pseudonym_mappings(self):
        """Clear all pseudonym mappings."""
        self.pseudonym_mappings.clear()
        self.pseudonym_counters.clear()
        logger.info("Cleared pseudonym mappings")

    def get_pseudonym_mappings(self) -> Dict[str, str]:
        """
        Get current pseudonym mappings.

        Returns:
            Dict[str, str]: Mapping of original values to pseudonyms
        """
        return self.pseudonym_mappings.copy()

    def is_presidio_available(self) -> bool:
        """
        Check if Presidio is available.

        Returns:
            bool: True if Presidio is available
        """
        return self.presidio_available
