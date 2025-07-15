"""Rich console utilities for consistent output formatting."""

import contextlib

from rich.console import Console


class ProxyConsole:
    """Wrapper around Rich Console with consistent styling."""

    def __init__(self):
        self.console = Console()

    def print_success(self, message: str) -> None:
        """Print success message in green."""
        self.console.print(f"✓ {message}", style="green")

    def print_error(self, message: str) -> None:
        """Print error message in red."""
        self.console.print(f"✗ {message}", style="red bold")

    def print_warning(self, message: str) -> None:
        """Print warning message in yellow."""
        self.console.print(f"⚠ {message}", style="yellow")

    def print_info(self, message: str) -> None:
        """Print info message in cyan."""
        self.console.print(f"ℹ {message}", style="cyan")

    def print_step(self, message: str) -> None:
        """Print step message in blue."""
        self.console.print(f"→ {message}", style="blue")

    def print_header(self, title: str) -> None:
        """Print a formatted header."""
        self.console.print(f"\n=== {title} ===", style="bold cyan")

    @staticmethod
    def ask_confirmation(question: str, default: bool = False) -> bool:
        """Ask for user confirmation."""
        default_text = "Y/n" if default else "y/N"
        response = input(f"{question} ({default_text}): ").lower().strip()

        if not response:
            return default

        return response in ['y', 'yes', 'true', '1']

    @contextlib.contextmanager
    def status(self, message: str):
        """Context manager for showing status with spinner."""
        with self.console.status(message) as status:
            yield status


console = ProxyConsole()