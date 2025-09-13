"""Base agent class for all ACP agents."""

import json
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

import structlog

logger = structlog.get_logger(__name__)


class BaseAgent(ABC):
    """Base class for all agents in the ACP system."""

    def __init__(self, agent_type: str, llm_service, knowledge_service, audit_service):
        """Initialize the base agent.

        Args:
            agent_type: Type of agent
            llm_service: Service for LLM interactions
            knowledge_service: Service for knowledge base queries
            audit_service: Service for audit logging
        """
        self.agent_type = agent_type
        self.llm_service = llm_service
        self.knowledge_service = knowledge_service
        self.audit_service = audit_service
        self.logger = logger.bind(agent_type=agent_type)

        # Performance tracking
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_duration = 0.0

    @property
    @abstractmethod
    def input_schema(self) -> Type:
        """Return the input schema for this agent."""

    @property
    @abstractmethod
    def output_schema(self) -> Type:
        """Return the output schema for this agent."""

    @abstractmethod
    async def _process_request(self, input_data) -> Any:
        """Process the agent request. Must be implemented by subclasses.

        Args:
            input_data: Validated input data

        Returns:
            Agent output
        """

    @abstractmethod
    def _get_system_prompt(self) -> str:
        """Get the system prompt for this agent."""

    @abstractmethod
    def _get_user_prompt(self, input_data) -> str:
        """Get the user prompt for this agent."""

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the agent with the given input.

        Args:
            input_data: Raw input data

        Returns:
            Agent output as dictionary

        Raises:
            ValidationError: If input validation fails
            Exception: If agent execution fails
        """
        start_time = time.time()
        request_id = input_data.get("request_id", f"{self.agent_type}_{int(time.time())}")

        self.logger.info("Starting agent execution", request_id=request_id)

        try:
            # Validate input
            validated_input = self.input_schema(**input_data)

            # Log audit event
            await self.audit_service.log_agent_start(
                job_id=request_id, agent_type=self.agent_type, step="execution"
            )

            # Process request
            output = await self._process_request(validated_input)

            # Validate output
            if not isinstance(output, self.output_schema):
                raise ValueError(
                    f"Agent output does not match expected schema: {self.output_schema}"
                )

            # Convert to dictionary
            output_dict = output.dict()

            # Update metrics
            duration = time.time() - start_time
            self.total_requests += 1
            self.successful_requests += 1
            self.total_duration += duration

            # Log audit event
            await self.audit_service.log_agent_complete(
                job_id=request_id,
                agent_type=self.agent_type,
                step="execution",
                duration_seconds=duration,
                output_summary={"output_type": type(output).__name__},
            )

            self.logger.info(
                "Agent execution completed successfully",
                request_id=request_id,
                duration_seconds=duration,
                confidence=getattr(output, "confidence", None),
            )

            return output_dict

        except Exception as e:
            duration = time.time() - start_time
            self.total_requests += 1
            self.failed_requests += 1

            error_msg = f"Agent execution failed: {str(e)}"
            self.logger.error("Agent execution failed", request_id=request_id, error=error_msg)

            await self.audit_service.log_agent_error(
                job_id=request_id,
                agent_type=self.agent_type,
                step="execution",
                error_message=error_msg,
            )

            raise

    async def _query_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = True,
    ) -> str:
        """Query the LLM with the given prompts.

        Args:
            system_prompt: System prompt
            user_prompt: User prompt
            temperature: Temperature override
            max_tokens: Max tokens override
            json_mode: Whether to request JSON output

        Returns:
            LLM response
        """
        return await self.llm_service.generate_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )

    async def _search_knowledge(
        self, query: str, limit: int = 10, filters: Optional[Dict[str, Any]] = None
    ) -> List[Any]:
        """Search the knowledge base.

        Args:
            query: Search query
            limit: Maximum number of results
            filters: Optional filters

        Returns:
            List of knowledge references
        """
        return await self.knowledge_service.search(query=query, limit=limit, filters=filters)

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON response from LLM.

        Args:
            response: Raw LLM response

        Returns:
            Parsed JSON data

        Raises:
            ValueError: If JSON parsing fails
        """
        try:
            # Try to extract JSON from response if it's wrapped in text
            response = response.strip()

            # Look for JSON block markers
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

            # Try to find JSON object boundaries
            if not response.startswith("{") and "{" in response:
                start = response.find("{")
                response = response[start:]

            if not response.endswith("}") and "}" in response:
                end = response.rfind("}") + 1
                response = response[:end]

            return json.loads(response)

        except json.JSONDecodeError as e:
            self.logger.error("Failed to parse JSON response", response=response, error=str(e))
            raise ValueError(f"Invalid JSON response from LLM: {e}")

    def _calculate_confidence(
        self, factors: Dict[str, float], weights: Optional[Dict[str, float]] = None
    ) -> float:
        """Calculate confidence score based on multiple factors.

        Args:
            factors: Dictionary of factor names to scores (0.0-1.0)
            weights: Optional weights for factors (defaults to equal weighting)

        Returns:
            Weighted confidence score
        """
        if not factors:
            return 0.0

        if weights is None:
            weights = {factor: 1.0 for factor in factors}

        total_weight = sum(weights.values())
        if total_weight == 0:
            return 0.0

        weighted_sum = sum(factors.get(factor, 0.0) * weight for factor, weight in weights.items())

        return min(1.0, max(0.0, weighted_sum / total_weight))

    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for this agent.

        Returns:
            Dictionary of metrics
        """
        success_rate = (
            self.successful_requests / self.total_requests if self.total_requests > 0 else 0.0
        )

        average_duration = (
            self.total_duration / self.total_requests if self.total_requests > 0 else 0.0
        )

        return {
            "agent_type": self.agent_type,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": success_rate,
            "average_duration_seconds": average_duration,
            "total_duration_seconds": self.total_duration,
        }

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check for this agent.

        Returns:
            Health status dictionary
        """
        try:
            # Test LLM connectivity
            llm_healthy = await self.llm_service.health_check()

            # Test knowledge service connectivity
            knowledge_healthy = await self.knowledge_service.health_check()

            # Overall health
            healthy = llm_healthy and knowledge_healthy

            return {
                "agent_type": self.agent_type,
                "healthy": healthy,
                "llm_service": llm_healthy,
                "knowledge_service": knowledge_healthy,
                "metrics": self.get_metrics(),
            }

        except Exception as e:
            self.logger.error("Health check failed", error=str(e))
            return {"agent_type": self.agent_type, "healthy": False, "error": str(e)}
