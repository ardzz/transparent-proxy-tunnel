"""Redsocks proxy management functionality."""

import subprocess
import time
from pathlib import Path

from ..config.models import ProxyConfig
from ..config.generator import generate_redsocks_config, validate_redsocks_config
from ..system.process import ProcessManager
from ..core.network import is_port_in_use
from ..utils.logging import get_logger
from ..utils.exceptions import RedsocksError, PortInUseError
from ..utils.console import console

logger = get_logger("core.proxy")


class RedsocksProxy:
    """Manages redsocks proxy operations."""

    def __init__(self, config: ProxyConfig, process_manager: ProcessManager):
        self.config = config
        self.process_manager = process_manager
        self.config_path = "/etc/redsocks.conf"

    def start(self, proxy_ip: str = "127.0.0.1", proxy_port: int = 1080) -> None:
        """
        Start the redsocks service.

        Args:
            proxy_ip: IP address of the SOCKS5 proxy
            proxy_port: Port of the SOCKS5 proxy

        Raises:
            RedsocksError: If redsocks startup fails
            PortInUseError: If the redsocks port is already in use
        """
        logger.info(f"Starting redsocks service on port {self.config.redsocks_port}")

        if is_port_in_use(self.config.redsocks_port):
            process_info = self.process_manager.find_process_by_port(self.config.redsocks_port)
            if process_info:
                if console.ask_confirmation(
                        f"Port {self.config.redsocks_port} is in use by {process_info}. Kill it?",
                        default=False
                ):
                    self.process_manager.kill_process_on_port(self.config.redsocks_port)
                    time.sleep(1)
                else:
                    raise PortInUseError(self.config.redsocks_port, process_info)
            else:
                raise PortInUseError(self.config.redsocks_port)

        try:
            generate_redsocks_config(
                self.config.redsocks_port,
                proxy_ip,
                proxy_port,
                self.config_path
            )

            validate_redsocks_config(self.config_path)
            subprocess.run(["redsocks", "-c", self.config_path], check=True)

            if not is_port_in_use(self.config.redsocks_port):
                raise RedsocksError(f"Redsocks started but port {self.config.redsocks_port} is not listening")

            console.print_success("Redsocks service started successfully")
            logger.info("Redsocks service started successfully")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start redsocks: {e}")
            raise RedsocksError(f"Failed to start redsocks: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error starting redsocks: {e}")
            raise RedsocksError(f"Unexpected error starting redsocks: {e}") from e

    def stop(self) -> None:
        """Stop the redsocks service."""
        logger.info("Stopping redsocks service")

        try:
            subprocess.run(["pkill", "redsocks"], check=False)
            time.sleep(1)

            if is_port_in_use(self.config.redsocks_port):
                console.print_warning(f"Port {self.config.redsocks_port} is still in use after stopping redsocks")
            else:
                console.print_success("Redsocks service stopped successfully")
                logger.info("Redsocks service stopped successfully")

        except Exception as e:
            logger.error(f"Error stopping redsocks: {e}")
            console.print_error(f"Error stopping redsocks: {e}")

    def is_running(self) -> bool:
        """Check if redsocks is currently running."""
        return is_port_in_use(self.config.redsocks_port)

    def get_log_path(self) -> Path:
        """Get the path to the redsocks log file."""
        return Path("/var/log/redsocks.log")