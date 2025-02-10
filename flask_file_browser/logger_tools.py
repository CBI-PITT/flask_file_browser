import os
import sys
from .utils import get_config
from loguru import logger

working_dir = os.path.dirname(__file__)
settings = get_config(os.path.join(working_dir, "settings.ini"))

ENVIRONMENT = settings.get("app", "log_engine")
# Logging setting
# Remove the default logger to avoid duplicate logs
def setup_logger():
    """
    Set up the logger for the application, based on different environment.
    """
    logger.remove()
    # if not logger._core.handlers:  # Check if any handlers are already configured
    if ENVIRONMENT == "development":
        logger.add(sys.stdout, level="TRACE")
    if ENVIRONMENT == "production":
        logger.add(sys.stdout, level="SUCCESS")
        logger.add("logfile.log", rotation="500 MB", level="SUCCESS")

# Ensure the logger is set up once during import
setup_logger()

