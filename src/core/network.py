"""Network utilities and validation functions."""

import socket
from typing import Tuple, Optional

from ..utils.logging import get_logger
from ..utils.exceptions import ConnectivityError

logger = get_logger("core.network")


def is_port_in_use(port: int, host: str = "localhost") -> bool:
    """
    Check if a port is already in use.

    Args:
        port: Port number to check
        host: Host to check (default: localhost)

    Returns:
        True if port is in use, False otherwise
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex((host, port))
            return result == 0
    except Exception as e:
        logger.warning(f"Error checking port {port}: {e}")
        return False


def test_socks5_connectivity(host: str = "127.0.0.1", port: int = 1080, timeout: int = 5) -> bool:
    """
    Test if a SOCKS5 proxy is accessible.

    Args:
        host: SOCKS5 proxy host
        port: SOCKS5 proxy port
        timeout: Connection timeout in seconds

    Returns:
        True if proxy is accessible, False otherwise
    """
    logger.info(f"Testing SOCKS5 connectivity to {host}:{port}")

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((host, port))
            logger.info(f"SOCKS5 proxy at {host}:{port} is accessible")
            return True
    except Exception as e:
        logger.error(f"Cannot connect to SOCKS5 proxy at {host}:{port}: {e}")
        return False


def get_available_port(start_port: int = 1024, end_port: int = 65535) -> Optional[int]:
    """
    Find an available port in the specified range.

    Args:
        start_port: Starting port number
        end_port: Ending port number

    Returns:
        Available port number or None if no port is available
    """
    for port in range(start_port, end_port + 1):
        if not is_port_in_use(port):
            return port
    return None


def resolve_hostname(hostname: str) -> str:
    """
    Resolve hostname to IP address.

    Args:
        hostname: Hostname to resolve

    Returns:
        IP address as string

    Raises:
        ConnectivityError: If hostname cannot be resolved
    """
    try:
        ip = socket.gethostbyname(hostname)
        logger.info(f"Resolved {hostname} to {ip}")
        return ip
    except socket.gaierror as e:
        logger.error(f"Failed to resolve hostname {hostname}: {e}")
        raise ConnectivityError(f"Failed to resolve hostname {hostname}: {e}") from e