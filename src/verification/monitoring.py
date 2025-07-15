"""Log monitoring and streaming functionality."""

import queue
import subprocess
import time
from pathlib import Path
from threading import Thread, Event
from typing import Optional, Callable

from rich.text import Text

from ..utils.console import console
from ..utils.logging import get_logger

logger = get_logger("verification.monitoring")


class LogMonitor:
    """Monitors and streams log files in real-time."""

    def __init__(self, log_path: str = "/var/log/redsocks.log"):
        self.log_path = Path(log_path)
        self._stop_event = Event()
        self._monitor_thread: Optional[Thread] = None
        self._log_queue = queue.Queue()

    def start_monitoring(self, callback: Optional[Callable[[str], None]] = None) -> None:
        """
        Start monitoring the log file.

        Args:
            callback: Optional callback function to process log lines
        """
        if self._monitor_thread and self._monitor_thread.is_alive():
            logger.warning("Log monitoring already started")
            return

        logger.info(f"Starting log monitoring for {self.log_path}")

        self._stop_event.clear()
        self._monitor_thread = Thread(
            target=self._monitor_log_file,
            args=(callback,),
            daemon=True
        )
        self._monitor_thread.start()

    def stop_monitoring(self) -> None:
        """Stop log monitoring."""
        logger.info("Stopping log monitoring")

        self._stop_event.set()

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2)

    def _monitor_log_file(self, callback: Optional[Callable[[str], None]] = None) -> None:
        """Monitor log file in a separate thread."""
        if not self.log_path.exists():
            console.print_warning(f"Log file doesn't exist: {self.log_path}")
            return

        try:
            with open(self.log_path, 'r') as f:
                f.seek(0, 2)

                while not self._stop_event.is_set():
                    line = f.readline()
                    if line:
                        line = line.strip()
                        if callback:
                            callback(line)
                        else:
                            self._default_log_handler(line)
                    else:
                        time.sleep(0.1)

        except Exception as e:
            logger.error(f"Error monitoring log file: {e}")
            console.print_error(f"Log monitoring error: {e}")

    def _default_log_handler(self, line: str) -> None:
        """Default handler for log lines with colored output."""
        text = Text()

        line_lower = line.lower()

        if "error" in line_lower:
            text.append(line, style="red bold")
        elif "warning" in line_lower or "warn" in line_lower:
            text.append(line, style="yellow")
        elif "notice" in line_lower:
            text.append(line, style="cyan")
        elif "info" in line_lower:
            text.append(line, style="green")
        elif "debug" in line_lower:
            text.append(line, style="dim")
        else:
            text.append(line)

        console.console.print(text)

    def get_recent_logs(self, lines: int = 50) -> list[str]:
        """
        Get recent log lines.

        Args:
            lines: Number of recent lines to retrieve

        Returns:
            List of recent log lines
        """
        if not self.log_path.exists():
            return []

        try:
            result = subprocess.run([
                "tail", "-n", str(lines), str(self.log_path)
            ], capture_output=True, text=True, check=True)

            return result.stdout.strip().split('\n') if result.stdout.strip() else []

        except (subprocess.CalledProcessError, FileNotFoundError):
            try:
                with open(self.log_path, 'r') as f:
                    all_lines = f.readlines()
                    return [line.strip() for line in all_lines[-lines:]]
            except Exception as e:
                logger.error(f"Error reading log file: {e}")
                return []

    def search_logs(self, pattern: str, max_lines: int = 100) -> list[str]:
        """
        Search for pattern in log file.

        Args:
            pattern: Pattern to search for
            max_lines: Maximum number of matching lines to return

        Returns:
            List of matching log lines
        """
        if not self.log_path.exists():
            return []

        try:
            import re
            regex = re.compile(pattern, re.IGNORECASE)
            matches = []

            with open(self.log_path, 'r') as f:
                for line in f:
                    if regex.search(line):
                        matches.append(line.strip())
                        if len(matches) >= max_lines:
                            break

            return matches

        except Exception as e:
            logger.error(f"Error searching log file: {e}")
            return []