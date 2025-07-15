"""Environment variable loading and validation."""

import os
from typing import Optional
from dotenv import load_dotenv

from .models import AppConfig, SSHConfig, ProxyConfig
from ..utils.exceptions import ConfigurationError
from ..utils.logging import get_logger

logger = get_logger("config")


def load_environment_config(env_file: Optional[str] = None) -> AppConfig:
    """
    Load and validate configuration from environment variables.

    Args:
        env_file: Optional path to .env file

    Returns:
        Validated application configuration

    Raises:
        ConfigurationError: If configuration is invalid
    """
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()

    logger.info("Loading configuration from environment variables")

    try:
        ssh_config = SSHConfig(
            remote_host=_get_required_env("REMOTE_HOST"),
            ssh_user=_get_required_env("SSH_USER"),
            auth_method=_get_required_env("SSH_AUTH_METHOD"),
            auth_value=_get_required_env("SSH_AUTH_VALUE"),
            tunnel_port=int(_get_required_env("SSH_TUNNEL_PORT"))
        )

        proxy_config = ProxyConfig(
            redsocks_port=int(_get_required_env("REDSOCKS_PORT"))
        )

        config = AppConfig(ssh=ssh_config, proxy=proxy_config)

        logger.info("Configuration loaded and validated successfully")
        return config

    except (ValueError, KeyError) as e:
        logger.error(f"Configuration validation failed: {e}")
        raise ConfigurationError(f"Configuration validation failed: {e}") from e


def _get_required_env(key: str) -> str:
    """Get required environment variable or raise error."""
    value = os.getenv(key)
    if not value:
        raise KeyError(f"Missing required environment variable: {key}")
    return value