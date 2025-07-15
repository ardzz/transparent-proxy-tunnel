"""Process management utilities."""

import subprocess
import time
from typing import Optional, List, Dict, Any

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from ..utils.logging import get_logger

logger = get_logger("system.process")


class ProcessManager:
    """Manages system processes and port usage."""

    def __init__(self):
        if not PSUTIL_AVAILABLE:
            logger.warning("psutil not available, process management will be limited")

    def find_process_by_port(self, port: int) -> Optional[str]:
        """
        Find process information for a given port.

        Args:
            port: Port number to check

        Returns:
            Process information string or None if not found
        """
        if PSUTIL_AVAILABLE:
            return self._find_process_with_psutil(port)
        else:
            return self._find_process_with_lsof(port)

    def _find_process_with_psutil(self, port: int) -> Optional[str]:
        """Find process using psutil library."""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    for conn in proc.net_connections(kind='inet'):
                        if conn.laddr.port == port:
                            return f"PID: {proc.pid}, Name: {proc.name()}"
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    continue
        except Exception as e:
            logger.error(f"Error finding process with psutil: {e}")

        return None

    def _find_process_with_lsof(self, port: int) -> Optional[str]:
        """Find process using lsof command."""
        try:
            result = subprocess.run(
                ["lsof", "-i", f":{port}", "-t"],
                capture_output=True,
                text=True,
                check=True
            )

            if result.stdout.strip():
                pid = result.stdout.strip().split('\n')[0]
                return f"PID: {pid}"

        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.debug(f"lsof not available or failed for port {port}")

        return None

    def kill_process_on_port(self, port: int) -> bool:
        """
        Kill process using a specific port.

        Args:
            port: Port number

        Returns:
            True if process was killed successfully
        """
        logger.info(f"Attempting to kill process on port {port}")

        if PSUTIL_AVAILABLE:
            return self._kill_process_with_psutil(port)
        else:
            return self._kill_process_with_lsof(port)

    def _kill_process_with_psutil(self, port: int) -> bool:
        """Kill process using psutil."""
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    for conn in proc.net_connections(kind='inet'):
                        if conn.laddr.port == port:
                            logger.info(f"Killing process {proc.pid} ({proc.name()}) on port {port}")
                            proc.kill()
                            proc.wait(timeout=5)
                            return True
                except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.TimeoutExpired):
                    continue
        except Exception as e:
            logger.error(f"Error killing process with psutil: {e}")

        return False

    def _kill_process_with_lsof(self, port: int) -> bool:
        """Kill process using lsof and kill commands."""
        try:
            result = subprocess.run(
                ["lsof", "-i", f":{port}", "-t"],
                capture_output=True,
                text=True,
                check=True
            )

            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid.strip():
                        logger.info(f"Killing process {pid} on port {port}")
                        subprocess.run(["kill", pid.strip()], check=True)

                time.sleep(1)
                return True

        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning(f"Failed to kill process on port {port} using lsof/kill")

        return False

    def kill_ssh_tunnel(self, port: int) -> None:
        """Kill SSH tunnel processes for a specific port."""
        try:
            subprocess.run(
                ["pkill", "-f", f"ssh.*-D.*{port}"],
                check=False
            )
            logger.info(f"Attempted to kill SSH tunnel processes on port {port}")
        except Exception as e:
            logger.error(f"Error killing SSH tunnel processes: {e}")

    def get_process_list(self) -> List[Dict[str, Any]]:
        """Get list of running processes."""
        processes = []

        if PSUTIL_AVAILABLE:
            try:
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        processes.append({
                            'pid': proc.pid,
                            'name': proc.name(),
                            'cmdline': ' '.join(proc.cmdline()) if proc.cmdline() else ''
                        })
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        continue
            except Exception as e:
                logger.error(f"Error getting process list: {e}")

        return processes