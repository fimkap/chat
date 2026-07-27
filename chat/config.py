"""Runtime configuration, read from the environment.

Defaults target a local (non-Docker) run; `docker-compose.yml` overrides the
values that differ inside the compose network.
"""

import os


def _bool(name: str, default: str = "0") -> bool:
    """Read a boolean-ish environment variable."""
    return os.environ.get(name, default).lower() in ("1", "true", "yes")


REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))

# Directory for app.log. Empty/unwritable means "log to stderr only".
LOG_DIR = os.environ.get("CHAT_LOG_DIR", "logs")
LOG_LEVEL = os.environ.get("CHAT_LOG_LEVEL", "DEBUG")

SECRET_KEY = os.environ.get("CHAT_SECRET_KEY", "dev-secret-change-me")
HOST = os.environ.get("CHAT_HOST", "0.0.0.0")
PORT = int(os.environ.get("CHAT_PORT", "5002"))
DEBUG = _bool("CHAT_DEBUG")

# --- Authentication -------------------------------------------------------
# Lifetime of an issued auth token, in seconds (default 1 hour).
TOKEN_TTL = int(os.environ.get("CHAT_TOKEN_TTL", "3600"))
# When set, every successful verification refreshes the TTL, so a token expires
# after TOKEN_TTL of *inactivity* rather than at a fixed time after login.
TOKEN_SLIDING_EXPIRY = _bool("CHAT_TOKEN_SLIDING_EXPIRY", "1")

# Login/register attempts allowed per window, counted per username.
# Set to 0 to disable rate limiting entirely.
LOGIN_RATE_LIMIT = int(os.environ.get("CHAT_LOGIN_RATE_LIMIT", "5"))
# A separate, larger budget per client address: one address legitimately serves
# many users (NAT, or a browser UI proxied through nginx). A successful login
# clears both counters, so only failed attempts accumulate.
LOGIN_RATE_LIMIT_PER_IP = int(os.environ.get("CHAT_LOGIN_RATE_LIMIT_PER_IP", "50"))
# New accounts allowed per address per window. Unlike logins this is not cleared
# on success, so it caps signup spam outright.
REGISTER_RATE_LIMIT_PER_IP = int(
    os.environ.get("CHAT_REGISTER_RATE_LIMIT_PER_IP", "20")
)
LOGIN_RATE_WINDOW = int(os.environ.get("CHAT_LOGIN_RATE_WINDOW", "60"))

# Reject plaintext HTTP requests. Enable behind a TLS-terminating proxy that
# sets X-Forwarded-Proto (see nginx.tls.conf).
REQUIRE_HTTPS = _bool("CHAT_REQUIRE_HTTPS")
# Comma-separated browser origins allowed to call the API and open sockets.
# Empty means same-origin only; "*" allows any (development convenience).
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CHAT_CORS_ORIGINS", "").split(",")
    if origin.strip()
]
