import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "alfred.log")

# Create a logger
logger = logging.getLogger("alfred")
logger.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter(
    '[%(asctime)s] %(levelname)s [%(name)s:%(filename)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# File Handler (rotating, max 5MB, keep 5 backups)
file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)

# Console Handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.INFO)

# Add handlers
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
