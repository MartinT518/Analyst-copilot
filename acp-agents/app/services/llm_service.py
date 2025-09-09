"""LLM service for agent interactions with Qwen/Gwen models."""

import asyncio
import json
from typing import Any, Dict, List, Optional

import httpx
import structlog

from ..config import get_settings

logger = structlog.get_logger(__name__)


class LLMService:
    """Service for interacting with LLM endpoints."""

    def __init__(self):
        """Initialize the LLM service."""
        self.settings = get_settings()
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.settings.llm_timeout), headers=self._get_headers()
        )
        self.logger = logger.bind(service="llm")

        # Performance tracking
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_tokens_used = 0
        self.total_duration = 0.0

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for LLM requests."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": f"ACP-Agents/{self.settings.version}",
        }

        if self.settings.api_key:
            headers["Authorization"] = f"Bearer {self.settings.api_key}"

        return headers

    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        json_mode: bool = True,
        model: Optional[str] = None,
    ) -> str:
        """Generate a response from the LLM.

        Args:
            system_prompt: System prompt to set context
            user_prompt: User prompt with the actual request
            temperature: Temperature for response generation
            max_tokens: Maximum tokens in response
            json_mode: Whether to request JSON output
            model: Model to use (defaults to configured model)

        Returns:
            Generated response text

        Raises:
            Exception: If LLM request fails
        """
        start_time = asyncio.get_event_loop().time()

        try:
            # Prepare request
            model_name = model or self.settings.llm_model

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            # Add JSON instruction if requested
            if json_mode:
                messages[0][
                    "content"
                ] += "\n\nIMPORTANT: Respond with valid JSON only. Do not include any text outside the JSON structure."

            request_data = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            }

            # Add JSON mode if supported
            if json_mode and "gpt" in model_name.lower():
                request_data["response_format"] = {"type": "json_object"}

            self.logger.info(
                "Sending LLM request",
                model=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=json_mode,
            )

            # Make request
            response = await self.client.post(
                f"{self.settings.llm_endpoint}/chat/completions", json=request_data
            )

            response.raise_for_status()
            result = response.json()

            # Extract response
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"]

                # Track usage
                usage = result.get("usage", {})
                tokens_used = usage.get("total_tokens", 0)

                # Update metrics
                duration = asyncio.get_event_loop().time() - start_time
                self.total_requests += 1
                self.successful_requests += 1
                self.total_tokens_used += tokens_used
                self.total_duration += duration

                self.logger.info(
                    "LLM request completed",
                    duration_seconds=duration,
                    tokens_used=tokens_used,
                    response_length=len(content),
                )

                return content
            else:
                raise Exception("No response content from LLM")

        except httpx.HTTPStatusError as e:
            duration = asyncio.get_event_loop().time() - start_time
            self.total_requests += 1
            self.failed_requests += 1

            error_msg = f"LLM HTTP error: {e.response.status_code} - {e.response.text}"
            self.logger.error("LLM request failed", error=error_msg, duration_seconds=duration)
            raise Exception(error_msg)

        except Exception as e:
            duration = asyncio.get_event_loop().time() - start_time
            self.total_requests += 1
            self.failed_requests += 1

            error_msg = f"LLM request failed: {str(e)}"
            self.logger.error("LLM request failed", error=error_msg, duration_seconds=duration)
            raise Exception(error_msg)

    async def generate_embedding(self, text: str, model: Optional[str] = None) -> List[float]:
        """Generate embedding for text.

        Args:
            text: Text to embed
            model: Model to use (defaults to configured embedding model)

        Returns:
            Embedding vector

        Raises:
            Exception: If embedding request fails
        """
        try:
            model_name = model or self.settings.embedding_model

            request_data = {"model": model_name, "input": text}

            response = await self.client.post(
                f"{self.settings.embedding_endpoint}/embeddings", json=request_data
            )

            response.raise_for_status()
            result = response.json()

            if "data" in result and len(result["data"]) > 0:
                return result["data"][0]["embedding"]
            else:
                raise Exception("No embedding data returned")

        except Exception as e:
            error_msg = f"Embedding request failed: {str(e)}"
            self.logger.error("Embedding request failed", error=error_msg)
            raise Exception(error_msg)

    async def validate_json_response(
        self, response: str, schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Validate and parse JSON response.

        Args:
            response: Raw response text
            schema: Optional JSON schema for validation

        Returns:
            Parsed JSON data

        Raises:
            ValueError: If JSON is invalid or doesn't match schema
        """
        try:
            # Clean up response
            response = response.strip()

            # Extract JSON if wrapped in markdown
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                if end != -1:
                    response = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                if end != -1:
                    response = response[start:end].strip()

            # Find JSON boundaries
            if not response.startswith("{") and "{" in response:
                start = response.find("{")
                response = response[start:]

            if not response.endswith("}") and "}" in response:
                end = response.rfind("}") + 1
                response = response[:end]

            # Parse JSON
            data = json.loads(response)

            # Validate against schema if provided
            if schema:
                # Basic schema validation (could be enhanced with jsonschema library)
                self._validate_against_schema(data, schema)

            return data

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response: {e}")
        except Exception as e:
            raise ValueError(f"JSON validation failed: {e}")

    def _validate_against_schema(self, data: Dict[str, Any], schema: Dict[str, Any]):
        """Basic schema validation.

        Args:
            data: Data to validate
            schema: Schema to validate against

        Raises:
            ValueError: If validation fails
        """
        # This is a basic implementation - could be enhanced with jsonschema
        required_fields = schema.get("required", [])

        for field in required_fields:
            if field not in data:
                raise ValueError(f"Required field '{field}' missing from response")

        # Check field types
        properties = schema.get("properties", {})
        for field, value in data.items():
            if field in properties:
                expected_type = properties[field].get("type")
                if expected_type and not self._check_type(value, expected_type):
                    raise ValueError(f"Field '{field}' has incorrect type")

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected type.

        Args:
            value: Value to check
            expected_type: Expected type string

        Returns:
            True if type matches
        """
        type_mapping = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        expected_python_type = type_mapping.get(expected_type)
        if expected_python_type:
            return isinstance(value, expected_python_type)

        return True

    async def health_check(self) -> bool:
        """Check if LLM service is healthy.

        Returns:
            True if service is healthy
        """
        try:
            # Simple health check with minimal request
            response = await self.generate_response(
                system_prompt="You are a helpful assistant.",
                user_prompt="Respond with 'OK' if you are working.",
                temperature=0.0,
                max_tokens=10,
                json_mode=False,
            )

            return "OK" in response.upper()

        except Exception as e:
            self.logger.error("LLM health check failed", error=str(e))
            return False

    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics.

        Returns:
            Dictionary of metrics
        """
        success_rate = (
            self.successful_requests / self.total_requests if self.total_requests > 0 else 0.0
        )

        average_duration = (
            self.total_duration / self.total_requests if self.total_requests > 0 else 0.0
        )

        average_tokens = (
            self.total_tokens_used / self.successful_requests
            if self.successful_requests > 0
            else 0.0
        )

        return {
            "service": "llm",
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": success_rate,
            "average_duration_seconds": average_duration,
            "total_tokens_used": self.total_tokens_used,
            "average_tokens_per_request": average_tokens,
            "endpoint": self.settings.llm_endpoint,
            "model": self.settings.llm_model,
        }

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
