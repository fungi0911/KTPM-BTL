"""Vendor API client with resilience patterns."""
import logging
import os
import threading
from typing import Any, Dict, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from .resilience import CircuitOpenError, RetryExhaustedError, resilient_call

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration Helpers
# ============================================================================

def _env_int(name: str, default: int, min_value: int = 1) -> int:
    """Parse integer from environment with validation."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
        return value if value >= min_value else default
    except ValueError:
        logger.warning("Invalid env %s=%s, using default %s", name, raw, default)
        return default


def _env_float(name: str, default: float, min_value: float = 0.0) -> float:
    """Parse float from environment with validation."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
        return value if value >= min_value else default
    except ValueError:
        logger.warning("Invalid env %s=%s, using default %s", name, raw, default)
        return default


# ============================================================================
# Custom Exceptions
# ============================================================================

class UpstreamClientError(Exception):
    """Non-retryable 4xx errors from vendor."""
    
    def __init__(self, status_code: int, payload: Any):
        self.status_code = status_code
        self.payload = payload
        super().__init__(f"Vendor client error: {status_code}")


# ============================================================================
# Configuration Constants
# ============================================================================

DEFAULT_BASE = os.getenv("VENDOR_BASE_URL", "http://127.0.0.1:5000/vendor-mock")
TIMEOUT = _env_float("VENDOR_TIMEOUT", 2.0, 0.1)
POOL_MAXSIZE = _env_int("VENDOR_POOL_MAXSIZE", 10, 1)

# Circuit Breaker
CB_FAIL_MAX = _env_int("CB_FAILURE_THRESHOLD", 5, 1)
CB_RESET_TIMEOUT = _env_float("CB_RECOVERY_TIME", 15.0, 0.1)
CB_SUCCESS_THRESHOLD = _env_int("CB_HALF_OPEN_SUCC", 2, 1)

# Retry
RETRY_ATTEMPTS = _env_int("RETRY_ATTEMPTS", 3, 1)
RETRY_WAIT_MIN = _env_float("RETRY_WAIT_MIN", 0.5, 0.0)
RETRY_WAIT_MAX = _env_float("RETRY_WAIT_MAX", 10.0, 0.1)
RETRY_MAX_TIME = _env_float("VENDOR_RETRY_BUDGET", 5.0, 0.1)


# ============================================================================
# Vendor API Client
# ============================================================================

class VendorAPI:
    """
    Vendor API client with automatic resilience (circuit breaker + retry).
    
    Example:
        client = VendorAPI()
        try:
            data, attempts = client.get_price(product_id=123)
            print(f"Got price after {attempts} attempts: {data}")
        except CircuitOpenError:
            print("Circuit is open, service temporarily unavailable")
        except RetryExhaustedError as e:
            print(f"Failed after {e.attempts} attempts")
    """
    
    def __init__(
        self,
        base_url: str = DEFAULT_BASE,
        timeout: float = TIMEOUT,
        pool_maxsize: int = POOL_MAXSIZE,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.pool_maxsize = pool_maxsize
        
        # HTTP session with connection pooling
        self.session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=pool_maxsize,
            pool_maxsize=pool_maxsize,
            max_retries=0,  # We handle retries ourselves
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Resilience decorator instance
        self._resilient = resilient_call(
            name="vendor_api",
            # Circuit breaker
            fail_max=CB_FAIL_MAX,
            reset_timeout=CB_RESET_TIMEOUT,
            success_threshold=CB_SUCCESS_THRESHOLD,
            exclude_exceptions=(UpstreamClientError,),  # Don't break on 4xx
            # Retry
            retry_attempts=RETRY_ATTEMPTS,
            retry_wait_min=RETRY_WAIT_MIN,
            retry_wait_max=RETRY_WAIT_MAX,
            retry_max_time=RETRY_MAX_TIME,
            retry_exceptions=(RequestException,),  # Only retry network errors
        )
    
    @property
    def breaker(self):
        """Expose breaker for backward compatibility."""
        return self._resilient.breaker
    
    def _perform_get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Perform GET request with error handling.
        
        Raises:
            - UpstreamClientError: 4xx errors (non-retryable)
            - HTTPError: 5xx errors (retryable)
        """
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, params=params, timeout=self.timeout)
        
        # 4xx = client errors (don't retry, don't break circuit)
        if 400 <= resp.status_code < 500:
            try:
                payload = resp.json()
            except Exception:
                payload = {"text": resp.text}
            raise UpstreamClientError(resp.status_code, payload)
        
        # 5xx = server errors (retryable, can break circuit)
        resp.raise_for_status()
        return resp.json()
    
    def get_price(
        self, 
        product_id: int, 
        params: Optional[Dict] = None
    ) -> Tuple[Dict[str, Any], int]:
        """
        Fetch vendor price with resilience (circuit breaker + retry).
        
        Args:
            product_id: Product ID
            params: Query parameters for vendor API
        
        Returns:
            Tuple of (price_data, attempts_used)
        
        Raises:
            - CircuitOpenError: Circuit is open
            - UpstreamClientError: 4xx error
            - RetryExhaustedError: All retries exhausted
        """
        return self._resilient.call(
            self._perform_get,
            f"/prices/{product_id}",
            params=params,
        )
    
    def get_price_raw(
        self,
        product_id: int,
        params: Optional[Dict] = None
    ) -> Tuple[Dict[str, Any], int]:
        """
        Direct call without resilience (for comparison/testing).
        
        Returns: (data, 1) - always 1 attempt
        """
        data = self._perform_get(f"/prices/{product_id}", params=params)
        return data, 1
    
    def snapshot(self) -> dict:
        """Get complete state snapshot."""
        return {
            "base_url": self.base_url,
            "timeout": self.timeout,
            "pool_maxsize": self.pool_maxsize,
            **self._resilient.snapshot(),
        }
    
    def config_snapshot(self):
        """Backward compatibility alias."""
        return self.snapshot()


# ============================================================================
# Singleton
# ============================================================================

_client: Optional[VendorAPI] = None
_lock = threading.Lock()


def get_vendor_client() -> VendorAPI:
    """Get or create singleton vendor client."""
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = VendorAPI()
    return _client