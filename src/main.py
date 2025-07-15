"""Main orchestration module for the transparent proxy tunnel."""

import signal
import sys
import time
from typing import Optional

from .config.environment import load_environment_config
from .config.models import AppConfig
from .core.proxy import RedsocksProxy
from .core.tunnel import SSHTunnel
from .system.iptables import IptablesManager
from .system.platform import PlatformManager
from .system.process import ProcessManager
from .utils.console import console
from .utils.exceptions import (
    ProxyTunnelError, ConfigurationError, PlatformNotSupportedError
)
from .utils.logging import setup_logging, get_logger
from .verification.connectivity import ConnectivityTester
from .verification.monitoring import LogMonitor
from .verification.traffic import TrafficVerifier

logger = get_logger("main")


class ProxyTunnelManager:
    """Main manager class that orchestrates all proxy tunnel operations."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.platform_manager = PlatformManager()
        self.process_manager = ProcessManager()

        self.ssh_tunnel: Optional[SSHTunnel] = None
        self.redsocks_proxy: Optional[RedsocksProxy] = None
        self.iptables_manager: Optional[IptablesManager] = None

        self.connectivity_tester = ConnectivityTester()
        self.traffic_verifier = TrafficVerifier()
        self.log_monitor: Optional[LogMonitor] = None

        self._running = False
        self._cleanup_performed = False

    def start(self) -> None:
        """Start the complete proxy tunnel system."""
        try:
            logger.info("Starting transparent proxy tunnel system")
            console.print_header("Transparent Proxy Tunnel Startup")

            self._perform_preflight_checks()
            self._start_ssh_tunnel()

            if self.platform_manager.supports_transparent_proxy():
                self._start_transparent_proxy()
            else:
                self._start_socks_only_mode()

            self._verify_system()
            self._start_monitoring()

            self._running = True
            console.print_success("Transparent proxy tunnel system started successfully")

        except Exception as e:
            logger.error(f"Failed to start proxy tunnel system: {e}")
            console.print_error(f"Startup failed: {e}")
            self.stop()
            raise

    def stop(self) -> None:
        """Stop the proxy tunnel system and clean up."""
        if self._cleanup_performed:
            return

        logger.info("Stopping transparent proxy tunnel system")
        console.print_header("Transparent Proxy Tunnel Shutdown")

        try:
            if self.log_monitor:
                self.log_monitor.stop_monitoring()

            if self.iptables_manager:
                self.iptables_manager.cleanup()

            if self.redsocks_proxy:
                self.redsocks_proxy.stop()

            if self.ssh_tunnel:
                self.ssh_tunnel.stop()

            self._running = False
            self._cleanup_performed = True

            console.print_success("Transparent proxy tunnel system stopped")
            logger.info("System shutdown completed")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            console.print_error(f"Shutdown error: {e}")

    def is_running(self) -> bool:
        """Check if the system is currently running."""
        return self._running

    def _perform_preflight_checks(self) -> None:
        """Perform pre-flight checks before starting."""
        console.print_step("Performing pre-flight checks")

        if not self.platform_manager.is_admin():
            raise ProxyTunnelError("Administrator/root privileges required")

        tools = self.platform_manager.check_required_tools()
        missing_tools = [tool for tool, available in tools.items()
                         if not available and tool in ["ssh", "iptables", "redsocks"]]

        if missing_tools:
            console.print_warning(f"Missing required tools: {missing_tools}")
            if console.ask_confirmation("Attempt to install missing tools?", default=True):
                self.platform_manager.install_missing_tools()
            else:
                raise ProxyTunnelError(f"Required tools not available: {missing_tools}")

        console.print_success("Pre-flight checks completed")

    def _start_ssh_tunnel(self) -> None:
        """Start the SSH tunnel."""
        console.print_step(f"Starting SSH tunnel to {self.config.ssh.remote_host}")

        self.ssh_tunnel = SSHTunnel(self.config.ssh, self.process_manager)
        self.ssh_tunnel.start()

    def _start_transparent_proxy(self) -> None:
        """Start transparent proxy components (Linux only)."""
        console.print_step("Starting transparent proxy components")

        self.redsocks_proxy = RedsocksProxy(self.config.proxy, self.process_manager)
        self.redsocks_proxy.start(
            proxy_ip="127.0.0.1",
            proxy_port=self.config.ssh.tunnel_port
        )

        self.iptables_manager = IptablesManager(self.platform_manager)
        self.iptables_manager.setup_redirection(
            self.config.proxy.redsocks_port,
            self.config.ssh.tunnel_port
        )

    def _start_socks_only_mode(self) -> None:
        """Start in SOCKS-only mode (Windows/unsupported platforms)."""
        console.print_warning(
            f"Platform {self.platform_manager.platform} doesn't support transparent proxy"
        )
        console.print_info(
            f"SOCKS5 proxy available at 127.0.0.1:{self.config.ssh.tunnel_port}"
        )
        console.print_info("Configure applications manually to use this SOCKS5 proxy")

    def _verify_system(self) -> None:
        """Verify that the system is working correctly."""
        console.print_step("Verifying system operation")
        connectivity_results = self.connectivity_tester.run_comprehensive_test()

        if not connectivity_results["overall_success"]:
            console.print_warning("Some connectivity tests failed")

        if self.platform_manager.supports_transparent_proxy():
            traffic_results = self.traffic_verifier.verify_iptables_redirection(
                self.config.proxy.redsocks_port
            )

            if not traffic_results["success"]:
                raise ProxyTunnelError(f"Traffic redirection verification failed: {traffic_results['error']}")

    def _start_monitoring(self) -> None:
        """Start log monitoring."""
        if self.platform_manager.supports_transparent_proxy() and self.redsocks_proxy:
            console.print_step("Starting log monitoring")

            log_path = self.redsocks_proxy.get_log_path()
            self.log_monitor = LogMonitor(str(log_path))
            self.log_monitor.start_monitoring()


def signal_handler(signum, frame, manager: ProxyTunnelManager):
    """Handle shutdown signals gracefully."""
    console.print_warning(f"\nReceived signal {signum}, shutting down...")
    manager.stop()
    sys.exit(0)


def main():
    """Main entry point."""

    setup_logging(log_file="proxy_tunnel.log")
    logger = get_logger("main")

    try:
        console.print_header("Loading Configuration")
        config = load_environment_config()

        manager = ProxyTunnelManager(config)

        signal.signal(signal.SIGINT, lambda s, f: signal_handler(s, f, manager))
        signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s, f, manager))

        manager.start()

        console.print_info("System running. Press Ctrl+C to stop.")

        try:
            while manager.is_running():
                time.sleep(1)
        except KeyboardInterrupt:
            console.print_warning("\nKeyboard interrupt received")

        manager.stop()

    except ConfigurationError as e:
        console.print_error(f"Configuration error: {e}")
        sys.exit(1)
    except PlatformNotSupportedError as e:
        console.print_error(f"Platform not supported: {e}")
        sys.exit(1)
    except ProxyTunnelError as e:
        console.print_error(f"Proxy tunnel error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception("Unexpected error in main")
        console.print_error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()