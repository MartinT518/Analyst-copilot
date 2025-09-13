"""LLM service for agent interactions."""

from typing import List, Optional

import httpx
import structlog

from ..config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class LLMService:
    """Service for interacting with local LLM endpoints."""

    def __init__(self):
        """Initialize LLM service."""
        self.settings = settings
        self.client = httpx.AsyncClient(timeout=settings.llm_timeout)
        self.logger = logger.bind(service="llm")

    async def initialize(self) -> bool:
        """Initialize the LLM service.

        Returns:
            bool: True if successfully initialized
        """
        try:
            # Test connection to LLM endpoint
            response = await self.client.get(f"{settings.llm_endpoint}/models")
            if response.status_code == 200:
                self.logger.info("LLM service initialized successfully")
                return True
            else:
                self.logger.error(
                    "Failed to connect to LLM endpoint",
                    status_code=response.status_code,
                )
                return False
        except Exception as e:
            self.logger.error("LLM service initialization failed", error=str(e))
            return False

    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> str:
        """Generate response from LLM.

        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
            json_mode: Whether to request JSON output

        Returns:
            str: LLM response
        """
        try:
            # Prepare request payload
            payload = {
                "model": settings.llm_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature or settings.llm_temperature,
                "max_tokens": max_tokens or settings.llm_max_tokens,
            }

            # Add JSON mode if requested
            if json_mode:
                payload["response_format"] = {"type": "json_object"}

            # Add API key if configured
            headers = {}
            if settings.api_key:
                headers["Authorization"] = f"Bearer {settings.api_key}"

            # Make request
            response = await self.client.post(
                f"{settings.llm_endpoint}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()

            # Parse response
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            self.logger.info(
                "LLM response generated",
                model=settings.llm_model,
                tokens_used=data.get("usage", {}).get("total_tokens", 0),
            )

            return content

        except httpx.HTTPError as e:
            self.logger.error("HTTP error in LLM request", error=str(e))
            raise
        except Exception as e:
            self.logger.error("Unexpected error in LLM request", error=str(e))
            raise

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text.

        Args:
            text: Text to embed

        Returns:
            List[float]: Embedding vector
        """
        try:
            payload = {"model": settings.embedding_model, "input": text}

            headers = {}
            if settings.api_key:
                headers["Authorization"] = f"Bearer {settings.api_key}"

            response = await self.client.post(
                f"{settings.embedding_endpoint}/embeddings",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()

            data = response.json()
            return data["data"][0]["embedding"]

        except Exception as e:
            self.logger.error("Failed to generate embedding", error=str(e))
            raise

    async def health_check(self) -> bool:
        """Check LLM service health.

        Returns:
            bool: True if healthy
        """
        try:
            response = await self.client.get(f"{settings.llm_endpoint}/models")
            return response.status_code == 200
        except Exception:
            return False

    async def cleanup(self):
        """Cleanup LLM service."""
        await self.client.aclose()
        self.logger.info("LLM service cleaned up")
