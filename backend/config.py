import os
import secrets
from dotenv import load_dotenv, set_key

load_dotenv()

class Config:
    """Central configuration for the 3D Ambi system."""
    PORT = int(os.environ.get("PORT", 8080))
    ADMIN_USER = os.environ.get("ADMIN_USER")
    ADMIN_PASS = os.environ.get("ADMIN_PASS")
    
    if not ADMIN_USER or not ADMIN_PASS:
        raise ValueError("ADMIN_USER and ADMIN_PASS environment variables must be set.")

    # Generate or load session salt
    if "SESSION_SALT" not in os.environ:
        new_salt = secrets.token_hex(16)
        set_key(".env", "SESSION_SALT", new_salt)
        os.environ["SESSION_SALT"] = new_salt
    
    SESSION_SALT = os.environ["SESSION_SALT"].encode("utf-8")
    
    REQUIRE_HTTPS = os.environ.get("REQUIRE_HTTPS", "false").lower() == "true"
    
    # Proctoring thresholds
    INTEGRITY_PASS_SCORE = 80
    INTEGRITY_WARN_SCORE = 50
    INACTIVITY_LIMIT_SEC = 300 # 5 minutes
    
    TOKEN_TTL_SEC = 3600 # 1 hour
    
    # Rate Limiting
    AUTH_LIMIT = 5
    AUTH_WINDOW_SEC = 60
