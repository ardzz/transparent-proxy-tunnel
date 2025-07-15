"""Centralized logging configuration and utilities."""

import logging
from pathlib import Path
from typing import Optional

from rich.logging import RichHandler


def setup_logging(
        level: int = logging.INFO,
        log_file: Optional[str] = None,
        console_output: bool = True
) -> logging.Logger:
    """
    Set up centralized logging configuration.

    Args:
        level: Logging level
        log_file: Optional log file path
        console_output: Whether to output to console

    Returns:
        Configured logger instance
    """
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logger = logging.getLogger("proxy_tunnel")
    logger.setLevel(level)

    logger.handlers.clear()

    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%m/%d/%y %H:%M:%S'
    )

    if log_file:
        file_handler = logging.FileHandler(log_dir / log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    if console_output:

        console_handler = RichHandler(
            rich_tracebacks=True,
            show_time=False,
            show_level=True,
            show_path=False,
            markup=True
        )

        console_handler.setLevel(level)
        console_handler._log_render.show_time = False

        logger.addHandler(console_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific module."""
    return logging.getLogger(f"proxy_tunnel.{name}")