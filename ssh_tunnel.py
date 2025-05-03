import subprocess
import logging
import socket
import os
import signal
import psutil
from rich.console import Console

# Create a console instance
console = Console()

# Configure logging
logging.basicConfig(
    filename='ssh_tunnel.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def is_port_in_use(port):
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0


def find_process_by_port(port):
    """Find process using a specified port."""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            for conn in proc.net_connections(kind='inet'):
                if conn.laddr.port == port:
                    return proc
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
    return None


def setup_ssh_tunnel(remote_host: str, ssh_user: str, ssh_auth_method: str,
                     ssh_auth_value: str, ssh_tunnel_port: int):
    """
    Set up an SSH tunnel for proxying traffic.

    Args:
        remote_host: The remote host to connect to
        ssh_user: SSH username
        ssh_auth_method: Either 'key' or 'password'
        ssh_auth_value: Path to key file or password
        ssh_tunnel_port: The local port for the SSH tunnel
    """
    logging.info("Starting SSH tunnel setup...")
    logging.info(
        f"Remote host: {remote_host}, User: {ssh_user}, Port: {ssh_tunnel_port}, Auth method: {ssh_auth_method}")

    # Check if the port is already in use
    if is_port_in_use(ssh_tunnel_port):
        process = find_process_by_port(ssh_tunnel_port)
        if process:
            process_info = f"PID: {process.pid}, Name: {process.name()}"
            console.print(f"Port {ssh_tunnel_port} is currently used by process: {process_info}", style="yellow")

            # Ask if the user wants to kill the process
            response = input(f"Do you want to kill this process and free the port? (y/n): ").lower().strip()
            if response == 'y':
                logging.info(f"User chose to kill process {process.pid} using port {ssh_tunnel_port}")
                try:
                    process.kill()
                    process.wait()
                    console.print(f"Process {process.pid} terminated successfully", style="green")
                    logging.info(f"Process {process.pid} terminated successfully")
                except Exception as e:
                    error_message = f"Failed to terminate process: {e}"
                    console.print(error_message, style="red")
                    logging.error(error_message)
                    raise RuntimeError(error_message)
            else:
                error_message = f"Port {ssh_tunnel_port} is already in use. Please choose a different port."
                console.print(error_message, style="red")
                logging.error(error_message)
                raise RuntimeError(error_message)
        else:
            error_message = f"Port {ssh_tunnel_port} is in use, but the process could not be identified."
            console.print(error_message, style="red")
            logging.error(error_message)
            raise RuntimeError(error_message)

    # Common SSH options to handle key exchange confirmation
    ssh_options = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null"]

    if ssh_auth_method == 'key':
        ssh_command = [
                          "ssh", "-D", str(ssh_tunnel_port), "-N", "-f",
                          "-i", ssh_auth_value,
                      ] + ssh_options + [f"{ssh_user}@{remote_host}"]
    elif ssh_auth_method == 'password':
        try:
            subprocess.run(["which", "sshpass"], check=True, stdout=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            error_message = "sshpass is not installed. Please install it first."
            console.print(error_message, style="red")
            logging.error(error_message)
            raise

        ssh_command = [
                          "sshpass", "-p", ssh_auth_value,
                          "ssh", "-D", str(ssh_tunnel_port), "-N", "-f",
                      ] + ssh_options + [f"{ssh_user}@{remote_host}"]
    else:
        error_message = f"Invalid authentication method: {ssh_auth_method}"
        console.print(error_message, style="red")
        logging.error(error_message)
        raise ValueError(error_message)

    try:
        logging.info(
            f"Executing SSH command: {' '.join([c if not c.startswith('-p') else '-p ******' for c in ssh_command])}")
        subprocess.run(ssh_command, check=True)

        # Verify the port is now actually in use
        if not is_port_in_use(ssh_tunnel_port):
            error_message = f"SSH tunnel command executed, but port {ssh_tunnel_port} doesn't appear to be listening"
            console.print(error_message, style="yellow")
            logging.warning(error_message)

        success_message = f"SSH tunnel established on port {ssh_tunnel_port}."
        console.print(success_message, style="green")
        logging.info(success_message)
    except subprocess.CalledProcessError as e:
        error_message = f"Failed to set up SSH tunnel: {e}"
        console.print(error_message, style="red")
        logging.error(error_message)
        raise


def stop_ssh_tunnel(ssh_tunnel_port: int):
    """Stop the SSH tunnel."""
    logging.info(f"Stopping SSH tunnel on port {ssh_tunnel_port}...")
    try:
        subprocess.run(["pkill", "-f", f"ssh -D {ssh_tunnel_port}"], check=False)

        # Verify the port is indeed freed
        if is_port_in_use(ssh_tunnel_port):
            warning_message = f"Warning: Port {ssh_tunnel_port} is still in use after attempting to stop the SSH tunnel"
            console.print(warning_message, style="yellow")
            logging.warning(warning_message)
        else:
            success_message = f"SSH tunnel on port {ssh_tunnel_port} stopped."
            console.print(success_message, style="green")
            logging.info(success_message)
    except subprocess.CalledProcessError as e:
        error_message = f"Error stopping SSH tunnel: {e}"
        console.print(error_message, style="red")
        logging.error(error_message)