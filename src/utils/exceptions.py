"""Custom exception classes for the transparent proxy tunnel."""

from typing import Optional


class ProxyTunnelError(Exception):
    """Base exception for all proxy tunnel related errors."""
    pass


class SSHTunnelError(ProxyTunnelError):
    """Exception raised when SSH tunnel operations fail."""
    pass


class RedsocksError(ProxyTunnelError):
    """Exception raised when redsocks operations fail."""
    pass


class IptablesError(ProxyTunnelError):
    """Exception raised when iptables operations fail."""
    pass


class ConfigurationError(ProxyTunnelError):
    """Exception raised when configuration is invalid."""
    pass


class PortInUseError(ProxyTunnelError):
    """Exception raised when a required port is already in use."""

    def __init__(self, port: int, process_info: Optional[str] = None):
        self.port = port
        self.process_info = process_info
        message = f"Port {port} is already in use"
        if process_info:
            message += f" by {process_info}"
        super().__init__(message)


class PlatformNotSupportedError(ProxyTunnelError):
    """Exception raised when operation is not supported on current platform."""
    pass


class ConnectivityError(ProxyTunnelError):
    """Exception raised when connectivity tests fail."""
    pass