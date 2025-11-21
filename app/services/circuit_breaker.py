import logging
import threading
import time

logger = logging.getLogger(__name__)


class CircuitBreakerOpen(Exception):
    """Raised when the circuit is open and requests are blocked."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_time=30.0, half_open_success_threshold=2, name="default", on_state_change=None):
        self.name = name
        self.failure_threshold = int(failure_threshold)
        self.recovery_time = float(recovery_time)
        self.half_open_success_threshold = int(half_open_success_threshold)
        self._state = "closed"  # closed | open | half_open
        self._failure_count = 0
        self._success_count = 0
        self._opened_at = 0.0
        self._lock = threading.Lock()
        self._on_state_change = on_state_change

    def state(self):
        with self._lock:
            return self._state

    def snapshot(self):
        with self._lock:
            return self._snapshot_locked()

    def _snapshot_locked(self):
        now = time.monotonic()
        return {
            "name": self.name,
            "state": self._state,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self.failure_threshold,
            "half_open_success_threshold": self.half_open_success_threshold,
            "recovery_time": self.recovery_time,
            "opened_at": self._opened_at,
            "open_for": (now - self._opened_at) if self._state == "open" else 0.0,
        }

    def _emit_state(self, new_state: str, reason: str = None):
        payload = self._snapshot_locked()
        payload["reason"] = reason
        logger.warning("Circuit '%s' -> %s (%s)", self.name, new_state, reason or "state change")
        if self._on_state_change:
            try:
                self._on_state_change(payload)
            except Exception:
                logger.exception("on_state_change callback failed")

    def _open(self):
        self._state = "open"
        self._opened_at = time.monotonic()
        self._failure_count = 0
        self._success_count = 0
        self._emit_state("open", "failure_threshold_reached")

    def _close(self):
        self._state = "closed"
        self._opened_at = 0.0
        self._failure_count = 0
        self._success_count = 0
        self._emit_state("closed", "recovered")

    def _half_open(self):
        self._state = "half_open"
        self._success_count = 0
        self._emit_state("half_open", "recovery_window_passed")

    def _allow_request(self):
        now = time.monotonic()
        if self._state == "open":
            if (now - self._opened_at) >= self.recovery_time:
                self._half_open()
                return True
            return False
        return True

    def call(self, func, *args, ignore_exceptions=None, **kwargs):
        ignore_exceptions = tuple(ignore_exceptions or ())
        with self._lock:
            if not self._allow_request():
                raise CircuitBreakerOpen(f"Circuit '{self.name}' is open")
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            if ignore_exceptions and isinstance(exc, ignore_exceptions):
                raise
            with self._lock:
                if self._state == "half_open":
                    self._open()
                else:
                    self._failure_count += 1
                    if self._failure_count >= self.failure_threshold:
                        self._open()
            raise
        else:
            with self._lock:
                if self._state == "half_open":
                    self._success_count += 1
                    if self._success_count >= self.half_open_success_threshold:
                        self._close()
                elif self._state == "closed":
                    self._failure_count = 0
            return result
