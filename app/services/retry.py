import random
import time
from typing import Callable, Iterable, Tuple, Type


class RetryError(Exception):
    """Raised when retry attempts are exhausted."""

    def __init__(self, attempts: int, last_exception: Exception):
        self.attempts = attempts
        self.last_exception = last_exception
        super().__init__(str(last_exception))


def _compute_delay(base: float, multiplier: float, jitter: float, attempt_index: int) -> float:
    """Exponential backoff with bounded jitter (deterministic per call)."""
    delay = base * (multiplier ** attempt_index)
    if jitter > 0:
        delay = max(0.0, delay + random.uniform(-jitter, jitter))
    return delay


def retry_call(
    func: Callable,
    attempts: int = 3,
    backoff: float = 0.3,
    multiplier: float = 2.0,
    jitter: float = 0.1,
    max_total: float = None,
    exceptions: Iterable[Type[Exception]] = (Exception,),
) -> Tuple[object, int]:
    """
    Retry a callable with exponential backoff + jitter and optional total time budget.

    Returns: (result, attempts_used)
    Raises: RetryError when attempts are exhausted or budget is exceeded.
    """
    attempts = int(attempts)
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    start = time.perf_counter()
    last_err = None
    attempts_used = 0
    for i in range(attempts):
        attempt_no = i + 1
        attempts_used = attempt_no
        try:
            return func(), attempt_no
        except tuple(exceptions) as err:
            last_err = err
            # Stop if this was the last attempt or we exceeded budget
            if attempt_no >= attempts:
                break
            if max_total is not None and (time.perf_counter() - start) >= max_total:
                break
            delay = _compute_delay(float(backoff), float(multiplier), float(jitter), i)
            if max_total is not None:
                remaining = max_total - (time.perf_counter() - start)
                if remaining <= 0:
                    break
                delay = min(delay, max(0.0, remaining))
            time.sleep(delay)
    raise RetryError(attempts=attempts_used, last_exception=last_err)
