import os
import requests
from .circuit_breaker import CircuitBreaker, CircuitBreakerOpen
from .retry import retry_call

DEFAULT_BASE = os.getenv("VENDOR_BASE_URL", "http://127.0.0.1:5000/vendor-mock")
FAIL_THRESHOLD = int(os.getenv("CB_FAILURE_THRESHOLD", "5"))
RECOVERY_TIME = float(os.getenv("CB_RECOVERY_TIME", "15"))
HALF_OPEN_SUCC = int(os.getenv("CB_HALF_OPEN_SUCC", "2"))
RETRY_ATTEMPTS = int(os.getenv("RETRY_ATTEMPTS", "3"))
RETRY_BACKOFF = float(os.getenv("RETRY_BACKOFF", "0.3"))
TIMEOUT = float(os.getenv("VENDOR_TIMEOUT", "2.0"))

class VendorAPI:
    def __init__(self, base_url=DEFAULT_BASE, breaker=None, attempts=RETRY_ATTEMPTS, backoff=RETRY_BACKOFF, timeout=TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.breaker = breaker or CircuitBreaker(
            failure_threshold=FAIL_THRESHOLD,
            recovery_time=RECOVERY_TIME,
            half_open_success_threshold=HALF_OPEN_SUCC,
            name="vendor_api",
        )
        self.attempts = attempts
        self.backoff = backoff
        self.timeout = timeout

    def _get(self, path, params=None):
        url = f"{self.base_url}{path}"
        resp = requests.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _call_with_retry(self, fn):
        return retry_call(
            fn,
            attempts=self.attempts,
            backoff=self.backoff,
            multiplier=2.0,
            exceptions=(requests.exceptions.RequestException,),
        )

    def get_price(self, product_id: int, params=None):
        def op():
            return self._get(f"/prices/{product_id}", params=params)
        return self.breaker.call(lambda: self._call_with_retry(op))

# Singleton accessor
_client = None
def get_vendor_client():
    global _client
    if _client is None:
        _client = VendorAPI()
    return _client