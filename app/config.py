import os

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///D:s/KTPM-BTL/inventory.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret-key")
    JWT_ACCESS_TOKEN_EXPIRES = 7200  # 2h

 # ACL (Circuit Breaker + Retry) settings
    VENDOR_BASE_URL = os.getenv("VENDOR_BASE_URL", "http://127.0.0.1:5000/vendor-mock")
    CB_FAILURE_THRESHOLD = int(os.getenv("CB_FAILURE_THRESHOLD", "5"))
    CB_RECOVERY_TIME = float(os.getenv("CB_RECOVERY_TIME", "15"))
    CB_HALF_OPEN_SUCC = int(os.getenv("CB_HALF_OPEN_SUCC", "2"))
    RETRY_ATTEMPTS = int(os.getenv("RETRY_ATTEMPTS", "3"))
    RETRY_BACKOFF = float(os.getenv("RETRY_BACKOFF", "0.3"))