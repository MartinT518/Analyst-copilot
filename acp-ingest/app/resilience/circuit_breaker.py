"""Circuit breaker implementation for resilient service calls."""

import asyncio
import time
from typing import Callable, Any, Optional, Dict, Type
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Circuit is open, failing fast
    HALF_OPEN = "half_open"  # Testing if service is back


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open."""

    pass


class CircuitBreaker:
    """Circuit breaker implementation for resilient service calls."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Type[Exception] = Exception,
        name: str = "default",
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time in seconds before trying to close circuit
            expected_exception: Exception type to count as failures
            name: Name of the circuit breaker
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name

        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

        self.logger = logger.bind(circuit_breaker=name)

    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt to reset."""
        if self.state == CircuitState.OPEN:
            if self.last_failure_time is None:
                return True

            return time.time() - self.last_failure_time >= self.recovery_timeout

        return False

    def _on_success(self) -> None:
        """Handle successful call."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.logger.debug("Circuit breaker reset to CLOSED")

    def _on_failure(self) -> None:
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.logger.warning(
                "Circuit breaker opened",
                failure_count=self.failure_count,
                threshold=self.failure_threshold,
            )

    def _call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker logic.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self.logger.info("Circuit breaker attempting reset to HALF_OPEN")
            else:
                raise CircuitBreakerError(f"Circuit breaker {self.name} is OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result

        except self.expected_exception as e:
            self._on_failure()
            raise

    async def _acall(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function with circuit breaker logic.

        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self.logger.info("Circuit breaker attempting reset to HALF_OPEN")
            else:
                raise CircuitBreakerError(f"Circuit breaker {self.name} is OPEN")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result

        except self.expected_exception as e:
            self._on_failure()
            raise

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result
        """
        return self._call(func, *args, **kwargs)

    async def acall(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function with circuit breaker.

        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result
        """
        return await self._acall(func, *args, **kwargs)

    def get_state(self) -> CircuitState:
        """Get current circuit state.

        Returns:
            Current circuit state
        """
        return self.state

    def get_metrics(self) -> Dict[str, Any]:
        """Get circuit breaker metrics.

        Returns:
            Circuit breaker metrics
        """
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure_time": self.last_failure_time,
            "recovery_timeout": self.recovery_timeout,
        }


class CircuitBreakerManager:
    """Manager for multiple circuit breakers."""

    def __init__(self):
        """Initialize circuit breaker manager."""
        self.circuits: Dict[str, CircuitBreaker] = {}
        self.logger = logger.bind(service="circuit_breaker_manager")

    def get_circuit(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Type[Exception] = Exception,
    ) -> CircuitBreaker:
        """Get or create a circuit breaker.

        Args:
            name: Circuit breaker name
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time in seconds before trying to close circuit
            expected_exception: Exception type to count as failures

        Returns:
            Circuit breaker instance
        """
        if name not in self.circuits:
            self.circuits[name] = CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                expected_exception=expected_exception,
                name=name,
            )
            self.logger.info("Created new circuit breaker", name=name)

        return self.circuits[name]

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all circuit breakers.

        Returns:
            Dictionary of circuit breaker metrics
        """
        return {name: circuit.get_metrics() for name, circuit in self.circuits.items()}

    def reset_circuit(self, name: str) -> bool:
        """Reset a circuit breaker.

        Args:
            name: Circuit breaker name

        Returns:
            True if circuit was reset, False if not found
        """
        if name in self.circuits:
            circuit = self.circuits[name]
            circuit.failure_count = 0
            circuit.state = CircuitState.CLOSED
            circuit.last_failure_time = None
            self.logger.info("Circuit breaker reset", name=name)
            return True

        return False


# Global circuit breaker manager
_circuit_manager = CircuitBreakerManager()


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: Type[Exception] = Exception,
) -> CircuitBreaker:
    """Get a circuit breaker instance.

    Args:
        name: Circuit breaker name
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Time in seconds before trying to close circuit
        expected_exception: Exception type to count as failures

    Returns:
        Circuit breaker instance
    """
    return _circuit_manager.get_circuit(
        name=name,
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        expected_exception=expected_exception,
    )


def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: Type[Exception] = Exception,
):
    """Decorator to add circuit breaker to a function.

    Args:
        name: Circuit breaker name
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Time in seconds before trying to close circuit
        expected_exception: Exception type to count as failures

    Returns:
        Decorator function
    """

    def decorator(func):
        circuit = get_circuit_breaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
        )

        if asyncio.iscoroutinefunction(func):

            async def async_wrapper(*args, **kwargs):
                return await circuit.acall(func, *args, **kwargs)

            return async_wrapper
        else:

            def sync_wrapper(*args, **kwargs):
                return circuit.call(func, *args, **kwargs)

            return sync_wrapper

    return decorator
