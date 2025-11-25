import logging
import time
from typing import Callable, Iterable, Type

import pybreaker

logger = logging.getLogger(__name__)


class CircuitBreakerOpen(Exception):
    """Raised when the circuit is open and requests are blocked."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class _StateListener(pybreaker.CircuitBreakerListener):
    """Listener to track state changes for snapshots/logging."""

    def __init__(self, owner: "CircuitBreaker"):
        self.owner = owner

    def state_change(self, cb, old_state, new_state):
        now = time.monotonic()
        if new_state.name == "open":
            self.owner._opened_at = now
        elif new_state.name == "closed":
            self.owner._opened_at = 0.0
        payload = self.owner._snapshot()
        payload["reason"] = f"{old_state.name}->{new_state.name}"
        logger.warning("Circuit '%s' -> %s", self.owner.name, payload["reason"])
        if self.owner._on_state_change:
            try:
                self.owner._on_state_change(payload)
            except Exception:
                logger.exception("on_state_change callback failed")


class CircuitBreaker:
    """
    Thin wrapper over pybreaker to keep a stable interface for the project.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_time: float = 30.0,
        half_open_success_threshold: int = 1,
        name: str = "default",
        on_state_change=None,
        exclude_exceptions: Iterable[Type[Exception]] = (),
    ):
        self.name = name
        self.failure_threshold = int(failure_threshold)
        self.recovery_time = float(recovery_time)
        # pybreaker closes after one success in half-open; keep the param for compatibility.
        self.half_open_success_threshold = int(half_open_success_threshold)
        self._opened_at = 0.0
        self._on_state_change = on_state_change
        self._excluded = tuple(exclude_exceptions or ())
        self._listener = _StateListener(self)
        self._breaker = pybreaker.CircuitBreaker(
            fail_max=self.failure_threshold,
            reset_timeout=self.recovery_time,
            exclude=self._excluded,
            listeners=[self._listener],
            name=self.name,
        )

    def state(self):
        return str(self._breaker.current_state).lower()

    def _snapshot(self):
        now = time.monotonic()
        state = self.state()
        return {
            "name": self.name,
            "state": state,
            "failure_count": getattr(self._breaker.fail_counter, "current", None),
            "success_count": None,  # not tracked separately by pybreaker
            "failure_threshold": self.failure_threshold,
            "half_open_success_threshold": self.half_open_success_threshold,
            "recovery_time": self.recovery_time,
            "opened_at": self._opened_at,
            "open_for": (now - self._opened_at) if state == "open" else 0.0,
        }

    def snapshot(self):
        return self._snapshot()

    def call(self, func: Callable, *args, **kwargs):
        try:
            return self._breaker.call(func, *args, **kwargs)
        except pybreaker.CircuitBreakerError:
            raise CircuitBreakerOpen(f"Circuit '{self.name}' is open")
