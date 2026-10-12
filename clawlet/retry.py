"""
Retry utilities for handling transient failures.
"""

from typing import Type

from loguru import logger

from clawlet.exceptions import CircuitBreakerOpen


class CircuitBreaker:
    """
    Circuit breaker pattern for preventing cascading failures.
    
    States:
    - CLOSED: Normal operation, requests flow through
    - OPEN: Requests blocked, failure threshold exceeded
    - HALF_OPEN: Testing if service recovered
    """
    
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception,
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying half-open state
            expected_exception: Exception type that triggers failure count
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
    
    @property
    def state(self) -> str:
        """Get current state, updating if recovery timeout passed."""
        if self._state == self.OPEN:
            import time
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = self.HALF_OPEN
        return self._state
    
    def can_execute(self) -> bool:
        """Check if execution is allowed."""
        return self.state != self.OPEN
    
    def record_success(self) -> None:
        """Record a successful execution."""
        self._failure_count = 0
        self._state = self.CLOSED
    
    def record_failure(self) -> None:
        """Record a failed execution."""
        import time
        
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._failure_count >= self.failure_threshold:
            self._state = self.OPEN
            logger.warning(
                f"Circuit breaker opened after {self._failure_count} failures. "
                f"Will retry in {self.recovery_timeout}s."
            )
