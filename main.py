import os
import sys
import time
import platform
import threading
import logging
from rich.console import Console
from dotenv import load_dotenv

from config import generate_redsocks_config
from service import (
    start_redsocks, stop_redsocks,
    setup_iptables, clean_iptables, check_socks5_connectivity,
    validate_redsocks_config, stream_log, verify_traffic_redirection
)
from ssh_tunnel import setup_ssh_tunnel, stop_ssh_tunnel

console = Console()


def is_admin():
    """Check if the script is running with admin privileges."""
    try:
        # Unix-like OS
        return os.geteuid() == 0
    except AttributeError:
        # Windows
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0


def load_environment():
    """Load environment variables."""
    load_dotenv()

    remote_host = os.getenv("REMOTE_HOST")
    ssh_user = os.getenv("SSH_USER")
    ssh_auth_method = os.getenv("SSH_AUTH_METHOD", "password")
    ssh_auth_value = os.getenv("SSH_AUTH_VALUE")
    ssh_tunnel_port = int(os.getenv("SSH_TUNNEL_PORT", 1080))
    redsocks_port = int(os.getenv("REDSOCKS_PORT", 5020))

    return remote_host, ssh_user, ssh_auth_method, ssh_auth_value, ssh_tunnel_port, redsocks_port


def main():
    # Configure logging
    logging.basicConfig(
        filename='main.log',
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Check for admin privileges
    if not is_admin():
        console.print("This program requires administrative privileges.", style="red")
        console.print("Please run as administrator/root.", style="yellow")
        sys.exit(1)

    try:
        # Load environment variables
        remote_host, ssh_user, ssh_auth_method, ssh_auth_value, ssh_tunnel_port, redsocks_port = load_environment()

        console.print(f"Setting up SSH tunnel to {remote_host}...", style="cyan")
        # Set up SSH tunnel
        setup_ssh_tunnel(remote_host, ssh_user, ssh_auth_method, ssh_auth_value, ssh_tunnel_port)

        # Wait a moment for the SSH tunnel to establish
        time.sleep(2)

        # Check if SSH tunnel is working
        if not check_socks5_connectivity("127.0.0.1", ssh_tunnel_port):
            console.print("SSH tunnel SOCKS5 proxy is not accessible.", style="red")
            console.print("Please check your SSH credentials and connection.", style="yellow")
            stop_ssh_tunnel(ssh_tunnel_port)
            sys.exit(1)

        if platform.system() == "Windows":
            console.print("Running on Windows - Redsocks is not supported.", style="yellow")
            console.print("Only SSH SOCKS5 tunnel is available at 127.0.0.1:" + str(ssh_tunnel_port), style="green")
            console.print("Configure your applications to use this SOCKS5 proxy manually.", style="cyan")
            console.print("Press Ctrl+C to stop the SSH tunnel.", style="yellow")

            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                console.print("\nStopping SSH tunnel...", style="yellow")
                stop_ssh_tunnel(ssh_tunnel_port)
        else:
            # Linux-specific code
            console.print("Generating Redsocks configuration...", style="cyan")
            generate_redsocks_config(redsocks_port, "127.0.0.1", ssh_tunnel_port)
            validate_redsocks_config()

            console.print("Starting Redsocks service...", style="cyan")
            start_redsocks(redsocks_port)

            console.print("Setting up traffic redirection with iptables...", style="cyan")
            setup_iptables(redsocks_port, ssh_tunnel_port)

            verify_traffic_redirection(5020)

            # Start log streaming in a separate thread
            console.print("Starting log streaming...", style="cyan")
            log_thread = threading.Thread(target=stream_log, daemon=True)
            log_thread.start()

            console.print("All services started successfully.", style="green")
            console.print("Traffic is now being redirected through the SOCKS5 proxy.", style="green")
            console.print("Press Ctrl+C to stop all services.", style="yellow")

            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                console.print("\nStopping services...", style="yellow")
                clean_iptables()
                stop_redsocks()
                stop_ssh_tunnel(ssh_tunnel_port)
                console.print("All services stopped.", style="green")

    except Exception as e:
        console.print(f"Error: {e}", style="red bold")
        logging.error(f"Error in main: {e}")

        # Clean up any running services
        try:
            if platform.system() != "Windows":
                clean_iptables()
                stop_redsocks()
            stop_ssh_tunnel(ssh_tunnel_port)
        except:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()