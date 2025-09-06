"""Retry logic implementation for resilient service calls."""

import asyncio
import time
import random
from typing import Callable, Any, Optional, List, Type, Union
from functools import wraps
import structlog

logger = structlog.get_logger(__name__)


class RetryError(Exception):
    """Exception raised when all retry attempts are exhausted."""
    pass


class RetryConfig:
    """Configuration for retry logic."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        backoff_factor: float = 2.0,
        max_delay: float = 60.0,
        min_delay: float = 1.0,
        jitter: bool = True,
        exceptions: Optional[List[Type[Exception]]] = None
    ):
        """Initialize retry configuration.
        
        Args:
            max_attempts: Maximum number of retry attempts
            backoff_factor: Exponential backoff factor
            max_delay: Maximum delay between retries
            min_delay: Minimum delay between retries
            jitter: Whether to add random jitter to delays
            exceptions: List of exception types to retry on
        """
        self.max_attempts = max_attempts
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay
        self.min_delay = min_delay
        self.jitter = jitter
        self.exceptions = exceptions or [Exception]
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt.
        
        Args:
            attempt: Current attempt number (0-based)
            
        Returns:
            Delay in seconds
        """
        # Exponential backoff
        delay = self.min_delay * (self.backoff_factor ** attempt)
        
        # Cap at max delay
        delay = min(delay, self.max_delay)
        
        # Add jitter if enabled
        if self.jitter:
            jitter_range = delay * 0.1  # 10% jitter
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)


class RetryManager:
    """Manager for retry logic."""
    
    def __init__(self, config: RetryConfig):
        """Initialize retry manager.
        
        Args:
            config: Retry configuration
        """
        self.config = config
        self.logger = logger.bind(service="retry_manager")
    
    def _should_retry(self, exception: Exception) -> bool:
        """Check if exception should trigger a retry.
        
        Args:
            exception: Exception that occurred
            
        Returns:
            True if should retry, False otherwise
        """
        return any(isinstance(exception, exc_type) for exc_type in self.config.exceptions)
    
    def _call_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry logic.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            RetryError: If all retry attempts are exhausted
        """
        last_exception = None
        
        for attempt in range(self.config.max_attempts):
            try:
                result = func(*args, **kwargs)
                
                if attempt > 0:
                    self.logger.info(
                        "Function succeeded after retry",
                        function=func.__name__,
                        attempt=attempt + 1,
                        total_attempts=self.config.max_attempts
                    )
                
                return result
                
            except Exception as e:
                last_exception = e
                
                if not self._should_retry(e):
                    self.logger.warning(
                        "Exception not retryable",
                        function=func.__name__,
                        exception_type=type(e).__name__,
                        exception_message=str(e)
                    )
                    raise
                
                if attempt < self.config.max_attempts - 1:
                    delay = self.config.calculate_delay(attempt)
                    
                    self.logger.warning(
                        "Function failed, retrying",
                        function=func.__name__,
                        attempt=attempt + 1,
                        total_attempts=self.config.max_attempts,
                        delay=delay,
                        exception_type=type(e).__name__,
                        exception_message=str(e)
                    )
                    
                    time.sleep(delay)
                else:
                    self.logger.error(
                        "Function failed after all retry attempts",
                        function=func.__name__,
                        total_attempts=self.config.max_attempts,
                        exception_type=type(e).__name__,
                        exception_message=str(e)
                    )
        
        # All retry attempts exhausted
        raise RetryError(f"Function {func.__name__} failed after {self.config.max_attempts} attempts") from last_exception
    
    async def _acall_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function with retry logic.
        
        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            RetryError: If all retry attempts are exhausted
        """
        last_exception = None
        
        for attempt in range(self.config.max_attempts):
            try:
                result = await func(*args, **kwargs)
                
                if attempt > 0:
                    self.logger.info(
                        "Async function succeeded after retry",
                        function=func.__name__,
                        attempt=attempt + 1,
                        total_attempts=self.config.max_attempts
                    )
                
                return result
                
            except Exception as e:
                last_exception = e
                
                if not self._should_retry(e):
                    self.logger.warning(
                        "Exception not retryable",
                        function=func.__name__,
                        exception_type=type(e).__name__,
                        exception_message=str(e)
                    )
                    raise
                
                if attempt < self.config.max_attempts - 1:
                    delay = self.config.calculate_delay(attempt)
                    
                    self.logger.warning(
                        "Async function failed, retrying",
                        function=func.__name__,
                        attempt=attempt + 1,
                        total_attempts=self.config.max_attempts,
                        delay=delay,
                        exception_type=type(e).__name__,
                        exception_message=str(e)
                    )
                    
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(
                        "Async function failed after all retry attempts",
                        function=func.__name__,
                        total_attempts=self.config.max_attempts,
                        exception_type=type(e).__name__,
                        exception_message=str(e)
                    )
        
        # All retry attempts exhausted
        raise RetryError(f"Async function {func.__name__} failed after {self.config.max_attempts} attempts") from last_exception
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry logic.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
        """
        return self._call_with_retry(func, *args, **kwargs)
    
    async def acall(self, func: Callable, *args, **kwargs) -> Any:
        """Execute async function with retry logic.
        
        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
        """
        return await self._acall_with_retry(func, *args, **kwargs)


def retry(
    max_attempts: int = 3,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    min_delay: float = 1.0,
    jitter: bool = True,
    exceptions: Optional[List[Type[Exception]]] = None
):
    """Decorator to add retry logic to a function.
    
    Args:
        max_attempts: Maximum number of retry attempts
        backoff_factor: Exponential backoff factor
        max_delay: Maximum delay between retries
        min_delay: Minimum delay between retries
        jitter: Whether to add random jitter to delays
        exceptions: List of exception types to retry on
        
    Returns:
        Decorator function
    """
    def decorator(func):
        config = RetryConfig(
            max_attempts=max_attempts,
            backoff_factor=backoff_factor,
            max_delay=max_delay,
            min_delay=min_delay,
            jitter=jitter,
            exceptions=exceptions
        )
        
        retry_manager = RetryManager(config)
        
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await retry_manager.acall(func, *args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return retry_manager.call(func, *args, **kwargs)
            return sync_wrapper
    
    return decorator


def retry_with_circuit_breaker(
    circuit_breaker_name: str,
    max_attempts: int = 3,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    min_delay: float = 1.0,
    jitter: bool = True,
    exceptions: Optional[List[Type[Exception]]] = None
):
    """Decorator to add retry logic with circuit breaker to a function.
    
    Args:
        circuit_breaker_name: Name of the circuit breaker
        max_attempts: Maximum number of retry attempts
        backoff_factor: Exponential backoff factor
        max_delay: Maximum delay between retries
        min_delay: Minimum delay between retries
        jitter: Whether to add random jitter to delays
        exceptions: List of exception types to retry on
        
    Returns:
        Decorator function
    """
    def decorator(func):
        from .circuit_breaker import get_circuit_breaker
        
        config = RetryConfig(
            max_attempts=max_attempts,
            backoff_factor=backoff_factor,
            max_delay=max_delay,
            min_delay=min_delay,
            jitter=jitter,
            exceptions=exceptions
        )
        
        retry_manager = RetryManager(config)
        circuit_breaker = get_circuit_breaker(circuit_breaker_name)
        
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await circuit_breaker.acall(
                    retry_manager.acall,
                    func,
                    *args,
                    **kwargs
                )
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return circuit_breaker.call(
                    retry_manager.call,
                    func,
                    *args,
                    **kwargs
                )
            return sync_wrapper
    
    return decorator
