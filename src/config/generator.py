"""Configuration file generation utilities."""

import os
from pathlib import Path

from ..utils.exceptions import ConfigurationError
from ..utils.logging import get_logger

logger = get_logger("config.generator")


def generate_redsocks_config(
        redsocks_port: int,
        proxy_ip: str,
        proxy_port: int,
        config_path: str = "/etc/redsocks.conf"
) -> None:
    """
    Generate redsocks configuration file.

    Args:
        redsocks_port: Port for redsocks to listen on
        proxy_ip: IP address of the SOCKS5 proxy
        proxy_port: Port of the SOCKS5 proxy
        config_path: Path where to write the configuration file

    Raises:
        ConfigurationError: If configuration generation fails
    """
    logger.info(f"Generating redsocks configuration at {config_path}")

    config_content = f"""base {{
    log_debug = off;
    log_info = on;
    log = "file:/var/log/redsocks.log";
    daemon = on;
    redirector = iptables;
}}

redsocks {{
    local_ip = 0.0.0.0;
    local_port = {redsocks_port};
    ip = {proxy_ip};
    port = {proxy_port};
    type = socks5;
}}
"""

    try:
        config_dir = Path(config_path).parent
        config_dir.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w") as f:
            f.write(config_content)

        os.chmod(config_path, 0o644)

        logger.info(f"Redsocks configuration generated successfully at {config_path}")

    except (IOError, OSError) as e:
        logger.error(f"Failed to generate redsocks configuration: {e}")
        raise ConfigurationError(f"Failed to generate redsocks configuration: {e}") from e


def validate_redsocks_config(config_path: str = "/etc/redsocks.conf") -> bool:
    """
    Validate redsocks configuration file.

    Args:
        config_path: Path to the configuration file

    Returns:
        True if configuration is valid

    Raises:
        ConfigurationError: If configuration is invalid
    """
    logger.info(f"Validating redsocks configuration at {config_path}")

    try:
        with open(config_path, 'r') as file:
            content = file.read()

            if "socks5" not in content:
                raise ConfigurationError("SOCKS5 configuration not found in redsocks.conf")

            if "local_port" not in content:
                raise ConfigurationError("local_port not configured in redsocks.conf")

            if "ip" not in content or "port" not in content:
                raise ConfigurationError("Proxy IP/port not configured in redsocks.conf")

            logger.info("Redsocks configuration validation passed")
            return True

    except FileNotFoundError:
        logger.error(f"Redsocks configuration file not found: {config_path}")
        raise ConfigurationError(f"Redsocks configuration file not found: {config_path}")
    except IOError as e:
        logger.error(f"Error reading redsocks configuration: {e}")
        raise ConfigurationError(f"Error reading redsocks configuration: {e}") from e