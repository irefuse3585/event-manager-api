# app/core/logging.py

import logging.config
import os
import sys

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console": {
            # Console output formatter
            "format": "[%(asctime)s] %(levelname)s | %(name)s | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "file": {
            # General application log formatter (detailed)
            "format": (
                "%(asctime)s | %(levelname)s | %(process)d | %(threadName)s | "
                "%(name)s | %(message)s"
            ),
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "audit": {
            # Audit trail log formatter (minimal, for audit events)
            "format": "%(asctime)s | AUDIT | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "security": {
            # Security log formatter (includes module name)
            "format": (
                "%(asctime)s | SECURITY | %(levelname)s | %(process)d | "
                "%(threadName)s | %(name)s | %(message)s"
            ),
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "console",
            "level": "DEBUG",
        },
        "file": {
            # General application log file
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/app.log",
            "formatter": "file",
            "level": "INFO",
            "maxBytes": 5 * 1024 * 1024,  # 5MB
            "backupCount": 5,
            "encoding": "utf-8",
        },
        "audit": {
            # Audit log file
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/audit.log",
            "formatter": "audit",
            "level": "INFO",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "encoding": "utf-8",
        },
        "security": {
            # Security log file
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "logs/security.log",
            "formatter": "security",
            "level": "WARNING",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "encoding": "utf-8",
        },
    },
    "loggers": {
        # Root logger: all application logs
        "": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        # Audit logger: only audit events (for regulatory/critical actions)
        "audit": {
            "handlers": ["audit"],
            "level": "INFO",
            "propagate": False,
        },
        # Security logger: WARNING+ duplicated to both app.log and security.log
        "app.security": {
            "handlers": ["file", "security"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}


def init_logging():
    """
    Initialize logging with the configuration above.
    Ensure log directories exist before configuring logging.
    """
    os.makedirs("logs", exist_ok=True)
    logging.config.dictConfig(LOGGING_CONFIG)
    logger = logging.getLogger(__name__)
    logger.info("Logging initialized")
