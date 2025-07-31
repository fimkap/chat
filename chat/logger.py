import logging
import os

# Create logs directory if it doesn't exist
logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(logs_dir, exist_ok=True)

log_file = os.path.join(logs_dir, "app.log")
logging.basicConfig(
    filename=log_file,
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("chat")
