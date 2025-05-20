import logging.config

# Logging configuration dictionary
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            # Define log message format
            "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            # Handler to output logs to console
            "class": "logging.StreamHandler",
            "formatter": "default",
            "level": "INFO",
        },
    },
    "root": {
        # Root logger configuration
        "handlers": ["console"],
        "level": "INFO",
    },
}


def init_logging():
    """
    Initialize logging with the predefined configuration.
    Call this function before starting the FastAPI app.
    """
    logging.config.dictConfig(LOGGING_CONFIG)
