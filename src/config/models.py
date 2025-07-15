"""Configuration data models."""

from dataclasses import dataclass
from typing import Literal
from pathlib import Path


@dataclass
class SSHConfig:
    """SSH connection configuration."""
    remote_host: str
    ssh_user: str
    auth_method: Literal["password", "key"]
    auth_value: str
    tunnel_port: int

    def __post_init__(self):
        """Validate SSH configuration after initialization."""
        if not self.remote_host:
            raise ValueError("REMOTE_HOST cannot be empty")

        if not self.ssh_user:
            raise ValueError("SSH_USER cannot be empty")

        if self.auth_method not in ["password", "key"]:
            raise ValueError("SSH_AUTH_METHOD must be 'password' or 'key'")

        if not self.auth_value:
            raise ValueError("SSH_AUTH_VALUE cannot be empty")

        if self.auth_method == "key" and not Path(self.auth_value).exists():
            raise ValueError(f"SSH key file not found: {self.auth_value}")

        if not (1 <= self.tunnel_port <= 65535):
            raise ValueError("SSH_TUNNEL_PORT must be between 1 and 65535")


@dataclass
class ProxyConfig:
    """Proxy configuration."""
    redsocks_port: int

    def __post_init__(self):
        """Validate proxy configuration after initialization."""
        if not (1 <= self.redsocks_port <= 65535):
            raise ValueError("REDSOCKS_PORT must be between 1 and 65535")


@dataclass
class AppConfig:
    """Complete application configuration."""
    ssh: SSHConfig
    proxy: ProxyConfig

    def __post_init__(self):
        """Validate complete configuration."""
        if self.ssh.tunnel_port == self.proxy.redsocks_port:
            raise ValueError("SSH_TUNNEL_PORT and REDSOCKS_PORT must be different")