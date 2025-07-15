"""Platform-specific operations and checks."""

import platform
import os
import subprocess
from typing import Literal, Optional

from ..utils.logging import get_logger
from ..utils.exceptions import PlatformNotSupportedError

logger = get_logger("system.platform")

PlatformType = Literal["linux", "windows", "macos", "unknown"]


class PlatformManager:
    """Manages platform-specific operations."""

    def __init__(self):
        self._platform = self._detect_platform()
        logger.info(f"Detected platform: {self._platform}")

    @property
    def platform(self) -> PlatformType:
        """Get the current platform."""
        return self._platform

    def _detect_platform(self) -> PlatformType:
        """Detect the current platform."""
        system = platform.system().lower()

        if system == "linux":
            return "linux"
        elif system == "windows":
            return "windows"
        elif system == "darwin":
            return "macos"
        else:
            return "unknown"

    def is_admin(self) -> bool:
        """Check if running with administrator/root privileges."""
        try:
            if self._platform in ["linux", "macos"]:
                return os.geteuid() == 0
            elif self._platform == "windows":
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            else:
                return False
        except Exception as e:
            logger.error(f"Error checking admin privileges: {e}")
            return False

    def supports_transparent_proxy(self) -> bool:
        """Check if platform supports transparent proxy functionality."""
        return self._platform == "linux"

    def check_required_tools(self) -> dict[str, bool]:
        """Check availability of required system tools."""
        tools = {}

        tools["ssh"] = self._check_command("ssh")

        if self._platform == "linux":
            tools["iptables"] = self._check_command("iptables")
            tools["redsocks"] = self._check_command("redsocks")
            tools["lsof"] = self._check_command("lsof")
            tools["netstat"] = self._check_command("netstat")

        tools["sshpass"] = self._check_command("sshpass")

        return tools

    def _check_command(self, command: str) -> bool:
        """Check if a command is available in PATH."""
        try:
            if self._platform == "windows":
                subprocess.run(["where", command],
                               check=True,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            else:
                subprocess.run(["which", command],
                               check=True,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def install_missing_tools(self) -> None:
        """Attempt to install missing tools."""
        if self._platform != "linux":
            raise PlatformNotSupportedError("Automatic tool installation only supported on Linux")

        tools = self.check_required_tools()
        missing_tools = [tool for tool, available in tools.items() if not available and tool != "sshpass"]

        if missing_tools:
            logger.info(f"Installing missing tools: {missing_tools}")
            try:
                subprocess.run(["apt-get", "update"], check=True)

                for tool in missing_tools:
                    if tool in ["redsocks", "lsof", "netstat"]:
                        package = {"netstat": "net-tools"}.get(tool, tool)
                        subprocess.run(["apt-get", "install", "-y", package], check=True)

                logger.info("Missing tools installed successfully")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to install missing tools: {e}")
                raise PlatformNotSupportedError(f"Failed to install missing tools: {e}")

    def get_platform_info(self) -> dict[str, str]:
        """Get detailed platform information."""
        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
        }