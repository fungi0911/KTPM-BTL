import time
import threading

class CircuitBreakerOpen(Exception):
    pass

class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_time=30.0, half_open_success_threshold=2, name="default"):
        self.name = name
        self.failure_threshold = int(failure_threshold)
        self.recovery_time = float(recovery_time)
        self.half_open_success_threshold = int(half_open_success_threshold)
        self._state = "closed"  # closed | open | half_open
        self._failure_count = 0
        self._success_count = 0
        self._opened_at = 0.0
        self._lock = threading.Lock()

    def state(self):
        with self._lock:
            return self._state

    def _open(self):
        self._state = "open"
        self._opened_at = time.monotonic()
        self._failure_count = 0
        self._success_count = 0

    def _close(self):
        self._state = "closed"
        self._opened_at = 0.0
        self._failure_count = 0
        self._success_count = 0

    def _half_open(self):
        self._state = "half_open"
        self._success_count = 0

    def _allow_request(self):
        now = time.monotonic()
        if self._state == "open":
            if (now - self._opened_at) >= self.recovery_time:
                self._half_open()
                return True
            return False
        return True

    def call(self, func, *args, **kwargs):
        with self._lock:
            if not self._allow_request():
                raise CircuitBreakerOpen(f"Circuit '{self.name}' is open")
        try:
            result = func(*args, **kwargs)
        except Exception:
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