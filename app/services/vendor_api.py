import logging
import os
from typing import Any, Dict, Tuple

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException

from .circuit_breaker import CircuitBreaker, CircuitBreakerOpen
from .retry import RetryError, retry_call

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int, min_value: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
        if value < min_value:
            raise ValueError
        return value
    except Exception:
        logger.warning("Env %s invalid (%s), fallback to %s", name, raw, default)
        return default


def _env_float(name: str, default: float, min_value: float = 0.0) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
        if value < min_value:
            raise ValueError
        return value
    except Exception:
        logger.warning("Env %s invalid (%s), fallback to %s", name, raw, default)
        return default


def _safe_json(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return {"text": resp.text}


def _status_from_exc(exc: Exception):
    resp = getattr(exc, "response", None)
    return getattr(resp, "status_code", None)


class UpstreamClientError(Exception):
    """Represents non-retryable 4xx errors from vendor."""

    def __init__(self, status_code: int, payload: Any):
        self.status_code = status_code
        self.payload = payload
        super().__init__(f"Upstream client error ({status_code})")


class VendorRetryExceeded(Exception):
    """Raised when retries are exhausted for vendor calls."""

    def __init__(self, attempts: int, last_status: int, last_error: Exception):
        self.attempts = attempts
        self.last_status = last_status
        self.last_error = last_error
        super().__init__("Upstream error after retries")


DEFAULT_BASE = os.getenv("VENDOR_BASE_URL", "http://127.0.0.1:5000/vendor-mock")
FAIL_THRESHOLD = _env_int("CB_FAILURE_THRESHOLD", 5, 1)
RECOVERY_TIME = _env_float("CB_RECOVERY_TIME", 15.0, 0.1)
HALF_OPEN_SUCC = _env_int("CB_HALF_OPEN_SUCC", 2, 1)
RETRY_ATTEMPTS = _env_int("RETRY_ATTEMPTS", 3, 1)
RETRY_BACKOFF = _env_float("RETRY_BACKOFF", 0.3, 0.0)
RETRY_JITTER = _env_float("RETRY_JITTER", 0.1, 0.0)
RETRY_BUDGET = _env_float("VENDOR_RETRY_BUDGET", 5.0, 0.1)
TIMEOUT = _env_float("VENDOR_TIMEOUT", 2.0, 0.1)
POOL_MAXSIZE = _env_int("VENDOR_POOL_MAXSIZE", 10, 1)
BACKOFF_MULTIPLIER = 2.0


class VendorAPI:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE,
        breaker: CircuitBreaker = None,
        attempts: int = RETRY_ATTEMPTS,
        backoff: float = RETRY_BACKOFF,
        timeout: float = TIMEOUT,
        jitter: float = RETRY_JITTER,
        retry_budget: float = RETRY_BUDGET,
        pool_maxsize: int = POOL_MAXSIZE,
    ):
        self.base_url = base_url.rstrip("/")
        self.attempts = attempts
        self.backoff = backoff
        self.timeout = timeout
        self.jitter = jitter
        self.retry_budget = retry_budget
        self.pool_maxsize = pool_maxsize
        self.breaker = breaker or CircuitBreaker(
            failure_threshold=FAIL_THRESHOLD,
            recovery_time=RECOVERY_TIME,
            half_open_success_threshold=HALF_OPEN_SUCC,
            name="vendor_api",
            exclude_exceptions=(UpstreamClientError,),
        )
        self.session = requests.Session()
        adapter = HTTPAdapter(pool_connections=pool_maxsize, pool_maxsize=pool_maxsize, max_retries=0)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _perform_get(self, path: str, params=None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, params=params, timeout=self.timeout)
        if 400 <= resp.status_code < 500:
            raise UpstreamClientError(resp.status_code, _safe_json(resp))
        resp.raise_for_status()
        return resp.json()

    def _call_with_retry(self, fn):
        try:
            return retry_call(
                fn,
                attempts=self.attempts,
                backoff=self.backoff,
                multiplier=BACKOFF_MULTIPLIER,
                jitter=self.jitter,
                max_total=self.retry_budget,
                exceptions=(RequestException,),
            )
        except RetryError as err:
            raise VendorRetryExceeded(
                attempts=err.attempts,
                last_status=_status_from_exc(err.last_exception),
                last_error=err.last_exception,
            )

    def get_price(self, product_id: int, params=None) -> Tuple[Dict[str, Any], int]:
        def op():
            return self._perform_get(f"/prices/{product_id}", params=params)
        return self.breaker.call(
            lambda: self._call_with_retry(op),
        )

    def get_price_raw(self, product_id: int, params=None) -> Tuple[Dict[str, Any], int]:
        """Call vendor once, without retry/circuit breaker (demo baseline)."""
        return self._perform_get(f"/prices/{product_id}", params=params), 1

    def config_snapshot(self):
        return {
            "base_url": self.base_url,
            "timeout": self.timeout,
            "retry_attempts": self.attempts,
            "retry_backoff": self.backoff,
            "retry_jitter": self.jitter,
            "retry_budget": self.retry_budget,
            "pool_maxsize": self.pool_maxsize,
            "cb_failure_threshold": self.breaker.failure_threshold,
            "cb_recovery_time": self.breaker.recovery_time,
            "cb_half_open_success_threshold": self.breaker.half_open_success_threshold,
        }

# Singleton accessor
_client = None
def get_vendor_client():
    global _client
    if _client is None:
        _client = VendorAPI()
    return _client
