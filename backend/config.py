import os

class Config:
    """Central configuration for the 3D Ambi system."""
    PORT = int(os.environ.get("PORT", 8080))
    ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
    ADMIN_PASS = os.environ.get("ADMIN_PASS", "admin123")
    REQUIRE_HTTPS = os.environ.get("REQUIRE_HTTPS", "false").lower() == "true"
    
    # Proctoring thresholds
    INTEGRITY_PASS_SCORE = 80
    INTEGRITY_WARN_SCORE = 50
    INACTIVITY_LIMIT_SEC = 300 # 5 minutes
    
    # Cryptography
    SESSION_SALT = b"3d-ambi-v1"
    TOKEN_TTL_SEC = 3600 # 1 hour
    
    # Rate Limiting
    AUTH_LIMIT = 5
    AUTH_WINDOW_SEC = 60
