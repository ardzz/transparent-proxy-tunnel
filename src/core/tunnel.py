"""SSH tunnel management functionality."""
import os
import subprocess
import signal
import time
from typing import Optional

from ..config.models import SSHConfig
from ..system.process import ProcessManager
from ..core.network import is_port_in_use, test_socks5_connectivity
from ..utils.logging import get_logger
from ..utils.exceptions import SSHTunnelError, PortInUseError
from ..utils.console import console

logger = get_logger("core.tunnel")


class SSHTunnel:
    """Manages SSH tunnel operations for SOCKS5 proxy."""

    def __init__(self, config: SSHConfig, process_manager: ProcessManager):
        self.config = config
        self.process_manager = process_manager
        self._tunnel_process: Optional[subprocess.Popen] = None

    def start(self) -> None:
        """
        Start the SSH tunnel.

        Raises:
            SSHTunnelError: If tunnel setup fails
            PortInUseError: If the tunnel port is already in use
        """
        logger.info(f"Starting SSH tunnel to {self.config.remote_host}:{self.config.tunnel_port}")

        if is_port_in_use(self.config.tunnel_port):
            process_info = self.process_manager.find_process_by_port(self.config.tunnel_port)
            if process_info:
                if console.ask_confirmation(
                        f"Port {self.config.tunnel_port} is in use by {process_info}. Kill it?",
                        default=False
                ):
                    self.process_manager.kill_process_on_port(self.config.tunnel_port)
                    time.sleep(1)
                else:
                    raise PortInUseError(self.config.tunnel_port, process_info)
            else:
                raise PortInUseError(self.config.tunnel_port)

        try:
            ssh_command = self._build_ssh_command()

            safe_command = self._sanitize_command(ssh_command)
            logger.info(f"Executing SSH command: {' '.join(safe_command)}")

            self._tunnel_process = subprocess.Popen(
                ssh_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None
            )

            time.sleep(2)

            if not self._verify_tunnel():
                self.stop()
                raise SSHTunnelError("SSH tunnel verification failed")

            console.print_success(f"SSH tunnel established on port {self.config.tunnel_port}")
            logger.info("SSH tunnel started successfully")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to start SSH tunnel: {e}")
            raise SSHTunnelError(f"Failed to start SSH tunnel: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error starting SSH tunnel: {e}")
            raise SSHTunnelError(f"Unexpected error starting SSH tunnel: {e}") from e

    def stop(self) -> None:
        """Stop the SSH tunnel."""
        logger.info("Stopping SSH tunnel")

        try:
            if self._tunnel_process:
                try:
                    if hasattr(os, 'killpg'):
                        os.killpg(os.getpgid(self._tunnel_process.pid), signal.SIGTERM)
                    else:
                        self._tunnel_process.terminate()

                    self._tunnel_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning("SSH tunnel process didn't exit gracefully, forcing kill")
                    if hasattr(os, 'killpg'):
                        os.killpg(os.getpgid(self._tunnel_process.pid), signal.SIGKILL)
                    else:
                        self._tunnel_process.kill()
                self._tunnel_process = None
            self.process_manager.kill_ssh_tunnel(self.config.tunnel_port)

            if is_port_in_use(self.config.tunnel_port):
                console.print_warning(f"Port {self.config.tunnel_port} is still in use after stopping SSH tunnel")
            else:
                console.print_success("SSH tunnel stopped successfully")
                logger.info("SSH tunnel stopped successfully")

        except Exception as e:
            logger.error(f"Error stopping SSH tunnel: {e}")
            console.print_error(f"Error stopping SSH tunnel: {e}")

    def is_running(self) -> bool:
        """Check if the SSH tunnel is currently running."""
        if self._tunnel_process and self._tunnel_process.poll() is None:
            return True
        return is_port_in_use(self.config.tunnel_port)

    def _build_ssh_command(self) -> list[str]:
        """Build the SSH command based on configuration."""

        ssh_options = [
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=ERROR"  # Reduce SSH output noise
        ]

        if self.config.auth_method == "key":
            ssh_command = [
                              "ssh", "-D", str(self.config.tunnel_port), "-N", "-f",
                              "-i", self.config.auth_value,
                          ] + ssh_options + [f"{self.config.ssh_user}@{self.config.remote_host}"]

        elif self.config.auth_method == "password":
            # Check if sshpass is available
            try:
                subprocess.run(["which", "sshpass"], check=True, stdout=subprocess.DEVNULL)
            except subprocess.CalledProcessError:
                raise SSHTunnelError("sshpass is not installed. Please install it for password authentication.")

            ssh_command = [
                              "sshpass", "-p", self.config.auth_value,
                              "ssh", "-D", str(self.config.tunnel_port), "-N", "-f",
                          ] + ssh_options + [f"{self.config.ssh_user}@{self.config.remote_host}"]
        else:
            raise SSHTunnelError(f"Invalid authentication method: {self.config.auth_method}")

        return ssh_command

    def _sanitize_command(self, command: list[str]) -> list[str]:
        """Remove sensitive information from command for logging."""
        if not command:
            return []

        sanitized = []
        i = 0

        while i < len(command):
            current_arg = command[i]

            if current_arg == "sshpass":
                sanitized.append(current_arg)
                i += 1

                if i < len(command) and command[i] == "-p":
                    sanitized.append("-p")
                    sanitized.append("******")
                    i += 2
                elif i < len(command) and command[i].startswith("-p"):
                    sanitized.append("-p******")
                    i += 1
                else:
                    continue

            elif current_arg == "-i":
                sanitized.append(current_arg)
                if i + 1 < len(command):
                    sanitized.append("******")
                    i += 2
                else:
                    i += 1

            elif current_arg.startswith("-i"):
                sanitized.append("-i******")
                i += 1

            elif current_arg in ["-o", "--option"] and i + 1 < len(command):
                next_arg = command[i + 1]
                sanitized.append(current_arg)

                if any(pwd_opt in next_arg.lower() for pwd_opt in ["password", "passwd"]):
                    sanitized.append("******")
                else:
                    sanitized.append(next_arg)
                i += 2

            elif any(sensitive in current_arg.lower() for sensitive in ["password=", "passwd=", "pass="]):
                if "=" in current_arg:
                    key_part = current_arg.split("=")[0]
                    sanitized.append(f"{key_part}=******")
                else:
                    sanitized.append("******")
                i += 1

            else:
                sanitized.append(current_arg)
                i += 1

        return sanitized

    def _verify_tunnel(self) -> bool:
        """Verify that the SSH tunnel is working properly."""
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            if test_socks5_connectivity("127.0.0.1", self.config.tunnel_port):
                return True

            if attempt < max_retries - 1:
                logger.info(f"Tunnel verification attempt {attempt + 1} failed, retrying...")
                time.sleep(retry_delay)

        return False