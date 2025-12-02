"""Unified resilience module with decorator support."""
import functools
import logging
import threading
from typing import Callable, Optional, Tuple, Type

import pybreaker
from tenacity import (
    RetryError as TenacityRetryError,
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    stop_after_delay,
    wait_exponential,
    wait_random,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Custom Exceptions
# ============================================================================

class ResilientCallError(Exception):
    """Base exception for resilient calls."""
    pass


class CircuitOpenError(ResilientCallError):
    """Circuit breaker is open."""
    
    def __init__(self, breaker_name: str, breaker_state: dict):
        self.breaker_name = breaker_name
        self.breaker_state = breaker_state
        super().__init__(f"Circuit '{breaker_name}' is open")


class RetryExhaustedError(ResilientCallError):
    """All retry attempts exhausted."""
    
    def __init__(self, attempts: int, last_exception: Exception):
        self.attempts = attempts
        self.last_exception = last_exception
        super().__init__(f"Retry exhausted after {attempts} attempts: {last_exception}")


# ============================================================================
# Thread-safe Metrics Counter
# ============================================================================

class _ThreadSafeMetrics:
    """Thread-safe metrics counter."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._data = {
            "calls": 0,
            "successes": 0,
            "failures": 0,
            "state_changes": 0,
            "retry_attempts_total": 0,
        }
    
    def increment(self, key: str, value: int = 1):
        """Thread-safe increment."""
        with self._lock:
            self._data[key] += value
    
    def snapshot(self) -> dict:
        """Thread-safe snapshot."""
        with self._lock:
            return self._data.copy()


# ============================================================================
# Circuit Breaker Listener
# ============================================================================

class _MetricsListener(pybreaker.CircuitBreakerListener):
    """Track state changes and metrics."""
    
    def __init__(self, name: str, metrics: _ThreadSafeMetrics):
        self.name = name
        self.metrics = metrics
    
    def state_change(self, cb, old_state, new_state):
        self.metrics.increment("state_changes")
        logger.warning(
            "Circuit '%s': %s -> %s (failures=%d)",
            self.name,
            old_state.name,
            new_state.name,
            cb.fail_counter,
        )
    
    def failure(self, cb, exc):
        self.metrics.increment("failures")
        logger.debug("Circuit '%s' failure: %s", self.name, exc)
    
    def success(self, cb):
        self.metrics.increment("successes")


# ============================================================================
# Main Decorator Class
# ============================================================================

class resilient_call:
    """
    Decorator combining Circuit Breaker + Retry with clean interface.
    Thread-safe for concurrent requests.
    
    Usage:
        @resilient_call(name="api", fail_max=5, retry_attempts=3)
        def call_api():
            return requests.get("http://api.example.com")
        
        # Or programmatically
        resilient = resilient_call(name="db")
        result, attempts = resilient.call(db_query_function)
    """
    
    def __init__(
        self,
        # Circuit breaker params
        name: str = "default",
        fail_max: int = 5,
        reset_timeout: float = 30.0,
        success_threshold: int = 4,
        exclude_exceptions: Tuple[Type[Exception], ...] = (),
        # Retry params  
        retry_attempts: int = 2,
        retry_wait_min: float = 0.1,
        retry_wait_max: float = 1.0,
        retry_wait_multiplier: float = 2.0,
        retry_jitter: Tuple[float, float] = (0, 0.5),
        retry_max_time: Optional[float] = None,
        retry_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    ):
        self.name = name
        # Only keep valid exception classes for breaker.exclude
        self._exclude = tuple(
            exc for exc in exclude_exceptions
            if isinstance(exc, type) and issubclass(exc, BaseException)
        )
        if len(self._exclude) != len(exclude_exceptions):
            logger.warning("exclude_exceptions contains non-exception entries; they were ignored")
        self._metrics = _ThreadSafeMetrics()  # Thread-safe!
        
        # Circuit Breaker (pybreaker is thread-safe internally)
        self.breaker = pybreaker.CircuitBreaker(
            fail_max=fail_max,
            reset_timeout=reset_timeout,
            exclude=exclude_exceptions,
            name=name,
            listeners=[_MetricsListener(name, self._metrics)],
        )
        # Store for snapshot
        self.breaker.success_threshold = success_threshold
        self._success_threshold = success_threshold
        
        # Retry configuration
        self.retry_attempts = retry_attempts
        self.retry_wait_min = retry_wait_min
        self.retry_wait_max = retry_wait_max
        self.retry_wait_multiplier = retry_wait_multiplier
        self.retry_jitter = retry_jitter
        self.retry_max_time = retry_max_time
        self.retry_exceptions = tuple(retry_exceptions)
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator syntax."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        
        # Attach for testing/introspection
        wrapper.resilient = self
        return wrapper
    
    def call(self, func: Callable, *args, **kwargs) -> Tuple[object, int]:
        """
        Execute function with circuit breaker + retry.
        Thread-safe for concurrent calls.
        
        Returns: (result, attempts_used)
        Raises:
            - CircuitOpenError: Circuit is open
            - RetryExhaustedError: All retries failed
            - Exception from exclude list: Passed through
        """
        self._metrics.increment("calls")
        
        def _retry_wrapper():
            """Inner function with retry logic."""
            stop_conditions = [stop_after_attempt(self.retry_attempts)]
            if self.retry_max_time:
                stop_conditions.append(stop_after_delay(self.retry_max_time))
            
            retryer = Retrying(
                retry=retry_if_exception(
                    lambda exc: isinstance(exc, self.retry_exceptions)
                    and not isinstance(exc, self._exclude)
                ),
                wait=wait_exponential(
                    multiplier=self.retry_wait_multiplier,
                    min=self.retry_wait_min,
                    max=self.retry_wait_max,
                ) + wait_random(*self.retry_jitter),
                stop=stop_conditions[0] if len(stop_conditions) == 1 
                     else stop_conditions[0] | stop_conditions[1],
                reraise=False,
            )
            
            try:
                result = retryer(func, *args, **kwargs)
                attempts = retryer.statistics.get("attempt_number", 1)
                if attempts > 1:
                    self._metrics.increment("retry_attempts_total", attempts - 1)
                return result, attempts
            except TenacityRetryError as err:
                attempts = err.last_attempt.attempt_number
                if attempts > 1:
                    self._metrics.increment("retry_attempts_total", attempts - 1)
                last_exc = err.last_attempt.exception()
                raise RetryExhaustedError(attempts, last_exc) from last_exc
        
        try:
            result, attempts = self.breaker.call(_retry_wrapper)
            return result, attempts
        except pybreaker.CircuitBreakerError:
            raise CircuitOpenError(self.name, self.snapshot())
    
    def snapshot(self) -> dict:
        """Get current state and metrics (thread-safe)."""
        state_obj = self.breaker.current_state
        state_name = state_obj.name.lower() if hasattr(state_obj, "name") else str(state_obj).lower()
        return {
            "name": self.name,
            "state": state_name,
            "fail_counter": getattr(self.breaker.fail_counter, "current", self.breaker.fail_counter),
            "fail_max": self.breaker.fail_max,
            "success_threshold": self._success_threshold,
            "reset_timeout": self.breaker.reset_timeout,
            "metrics": self._metrics.snapshot(),  # Thread-safe snapshot
            "retry_config": {
                "attempts": self.retry_attempts,
                "wait_min": self.retry_wait_min,
                "wait_max": self.retry_wait_max,
                "max_time": self.retry_max_time,
            },
        }
    
    def reset(self):
        """Reset circuit breaker state (useful for testing)."""
        self.breaker.close()
