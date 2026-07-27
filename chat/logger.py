import logging
import os

from .config import LOG_DIR, LOG_LEVEL

handlers = [logging.StreamHandler()]

if LOG_DIR:
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        handlers.append(logging.FileHandler(os.path.join(LOG_DIR, "app.log")))
    except OSError as e:  # unwritable path — keep running with stderr only
        logging.getLogger("chat").warning("Cannot write logs to %s: %s", LOG_DIR, e)

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=handlers,
)

logger = logging.getLogger("chat")
