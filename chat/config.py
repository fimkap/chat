"""Runtime configuration, read from the environment.

Defaults target a local (non-Docker) run; `docker-compose.yml` overrides the
values that differ inside the compose network.
"""

import os

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))

# Directory for app.log. Empty/unwritable means "log to stderr only".
LOG_DIR = os.environ.get("CHAT_LOG_DIR", "logs")
LOG_LEVEL = os.environ.get("CHAT_LOG_LEVEL", "DEBUG")

SECRET_KEY = os.environ.get("CHAT_SECRET_KEY", "dev-secret-change-me")
HOST = os.environ.get("CHAT_HOST", "0.0.0.0")
PORT = int(os.environ.get("CHAT_PORT", "5002"))
DEBUG = os.environ.get("CHAT_DEBUG", "0").lower() in ("1", "true", "yes")
