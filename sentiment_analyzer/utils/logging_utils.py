import logging
import logging.config
import yaml
from pathlib import Path
from ..config.settings import settings # Use relative import from config within the same package

# Ensure python-json-logger is installed if JSON logging is used.
# Add 'python-json-logger' to pyproject.toml if not already present.

DEFAULT_LOGGING_CONFIG_PATH = Path(settings.LOGGING_CONFIG_PATH)

def setup_logging(config_path: Path = DEFAULT_LOGGING_CONFIG_PATH) -> None:
    """
    Set up logging configuration from a YAML file.

    Args:
        config_path (Path): Path to the logging configuration YAML file.
    """
    if config_path.exists():
        try:
            with open(config_path, 'rt') as f:
                log_config = yaml.safe_load(f.read())
            logging.config.dictConfig(log_config)
            logging.info(f"Logging configured successfully from {config_path}")
        except Exception as e:
            logging.basicConfig(level=logging.INFO) # Basic config as fallback
            logging.error(f"Error loading logging configuration from {config_path}: {e}. Using basicConfig.")
    else:
        logging.basicConfig(level=logging.INFO) # Basic config if no file found
        logging.warning(f"Logging configuration file not found at {config_path}. Using basicConfig.")

# Call setup_logging() when this module is imported to configure logging application-wide
# This ensures that as soon as any part of the application imports this utility,
# logging is configured.
# However, for FastAPI applications, it's often better to call this explicitly
# during application startup (e.g., in main.py or an event handler).
# For now, we'll configure it on import for simplicity in a modular service.

# setup_logging() # Commented out: To be called explicitly in app startup

# Example usage (typically in your main application file or specific modules):
# from sentiment_analyzer.utils.logging_utils import setup_logging
# setup_logging()
# logger = logging.getLogger(__name__)
# logger.info("This is an info message from example.")
