import re
import subprocess
import socket
import logging
import os
import time
from rich.console import Console

# Create a console instance
console = Console()

# Configure logging
logging.basicConfig(
    filename='service.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Try to import psutil, but don't fail if it's not available
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    console.print("Warning: 'psutil' module not found. Process identification will be limited.", style="yellow")
    logging.warning("psutil module not available")


def is_port_in_use(port):
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0


def find_process_by_port(port):
    """Find process using a specified port."""
    if not PSUTIL_AVAILABLE:
        return None

    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                for conn in proc.connections(kind='inet'):
                    if conn.laddr.port == port:
                        return proc
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass
    except Exception as e:
        logging.error(f"Error finding process by port: {e}")

    return None


def start_redsocks(redsocks_port):
    """
    Start the redsocks service.

    Args:
        redsocks_port: The port redsocks will use
    """
    logging.info(f"Starting redsocks service on port {redsocks_port}...")

    # Check if the port is already in use
    if is_port_in_use(redsocks_port):
        process = find_process_by_port(redsocks_port) if PSUTIL_AVAILABLE else None

        if process:
            process_info = f"PID: {process.pid}, Name: {process.name()}"
            console.print(f"Port {redsocks_port} is currently used by process: {process_info}", style="yellow")

            # Ask if the user wants to kill the process
            response = input(f"Do you want to kill this process and free the port? (y/n): ").lower().strip()
            if response == 'y':
                logging.info(f"User chose to kill process {process.pid} using port {redsocks_port}")
                try:
                    process.kill()
                    process.wait()
                    console.print(f"Process {process.pid} terminated successfully", style="green")
                    logging.info(f"Process {process.pid} terminated successfully")
                    # Give the system a moment to release the port
                    time.sleep(1)
                except Exception as e:
                    error_message = f"Failed to terminate process: {e}"
                    console.print(error_message, style="red")
                    logging.error(error_message)
                    raise RuntimeError(error_message)
            else:
                error_message = f"Port {redsocks_port} is already in use. Please choose a different port."
                console.print(error_message, style="red")
                logging.error(error_message)
                raise RuntimeError(error_message)
        else:
            console.print(f"Port {redsocks_port} is in use.", style="yellow")
            response = input(f"Do you want to attempt to free this port? (y/n): ").lower().strip()
            if response == 'y':
                logging.info(f"User chose to attempt freeing port {redsocks_port}")
                # Try using lsof and kill on Unix-like systems
                try:
                    # Find PID using lsof
                    lsof_output = subprocess.check_output(
                        ["lsof", "-i", f":{redsocks_port}", "-t"],
                        universal_newlines=True
                    ).strip()

                    if lsof_output:
                        pids = lsof_output.split('\n')
                        for pid in pids:
                            pid = pid.strip()
                            if pid:
                                subprocess.run(["kill", pid])
                                console.print(f"Killed process with PID {pid}", style="green")

                        # Wait a moment for the port to be released
                        time.sleep(1)
                    else:
                        # Try to kill redsocks specifically as a fallback
                        console.print("Attempting to kill existing redsocks processes...", style="yellow")
                        subprocess.run(["pkill", "redsocks"], check=False)
                        time.sleep(1)
                except (subprocess.SubprocessError, FileNotFoundError):
                    console.print("Could not identify or kill the process using the port", style="yellow")
                    logging.warning(f"Failed to identify or kill process using port {redsocks_port}")

                # Check if the port is now free
                if is_port_in_use(redsocks_port):
                    error_message = f"Port {redsocks_port} is still in use after attempting to free it."
                    console.print(error_message, style="red")
                    logging.error(error_message)
                    raise RuntimeError(error_message)
            else:
                error_message = f"Port {redsocks_port} is already in use. Please choose a different port."
                console.print(error_message, style="red")
                logging.error(error_message)
                raise RuntimeError(error_message)

    try:
        subprocess.run(["redsocks", "-c", "/etc/redsocks.conf"], check=True)

        # Verify the port is now actually in use
        if not is_port_in_use(redsocks_port):
            warning_message = f"Redsocks command executed, but port {redsocks_port} doesn't appear to be listening"
            console.print(warning_message, style="yellow")
            logging.warning(warning_message)

        success_message = "Redsocks service started."
        console.print(success_message, style="green")
        logging.info(success_message)
    except subprocess.CalledProcessError as e:
        error_message = f"Failed to start redsocks: {e}"
        console.print(error_message, style="red")
        logging.error(error_message)
        raise


def stop_redsocks():
    """Stop the redsocks service."""
    logging.info("Stopping redsocks service...")
    try:
        subprocess.run(["pkill", "redsocks"], check=False)
        success_message = "Redsocks service stopped."
        console.print(success_message, style="green")
        logging.info(success_message)
    except subprocess.CalledProcessError as e:
        error_message = f"Error stopping redsocks: {e}"
        console.print(error_message, style="red")
        logging.error(error_message)


def setup_iptables(redsocks_port, ssh_tunnel_port=None):
    """Set up iptables rules to redirect traffic to redsocks, excluding SSH connections."""
    logging.info("Setting up iptables rules...")

    # Make sure required modules are loaded first
    try:
        subprocess.run(["modprobe", "iptable_nat"], check=False)
        subprocess.run(["modprobe", "xt_REDIRECT"], check=False)
    except Exception as e:
        logging.warning(f"Could not load kernel modules: {e}")

    try:
        # First check if iptables is available and has nat support
        try:
            subprocess.run(["iptables", "-t", "nat", "-L"], capture_output=True, check=True)
        except subprocess.CalledProcessError:
            error_message = "NAT table not available in iptables. Make sure the kernel module is loaded."
            console.print(error_message, style="red")
            logging.error(error_message)
            raise RuntimeError(error_message)

        # Check if chains exist before trying to modify them
        result = subprocess.run(["iptables", "-t", "nat", "-L", "REDSOCKS"],
                                capture_output=True, text=True, check=False)
        redsocks_exists = result.returncode == 0

        # Remove existing rules in a safe way
        if redsocks_exists:
            try:
                subprocess.run(["iptables", "-t", "nat", "-D", "OUTPUT", "-p", "tcp", "-j", "REDSOCKS"], check=False)
                subprocess.run(["iptables", "-t", "nat", "-F", "REDSOCKS"], check=False)
                subprocess.run(["iptables", "-t", "nat", "-X", "REDSOCKS"], check=False)
            except:
                pass

        # Create the REDSOCKS chain
        subprocess.run(["iptables", "-t", "nat", "-N", "REDSOCKS"], check=True)

        # Execute each rule separately with better error handling
        def execute_rule(rule):
            try:
                subprocess.run(rule, check=True)
                return True
            except subprocess.CalledProcessError as e:
                console.print(f"Error executing rule {' '.join(rule)}: {e}", style="yellow")
                logging.error(f"iptables rule failed: {' '.join(rule)}")
                return False

        # 1. Exclude standard SSH port
        execute_rule(["iptables", "-t", "nat", "-A", "REDSOCKS", "-p", "tcp", "--dport", "22", "-j", "RETURN"])

        # 2. Exclude localhost connections
        execute_rule(["iptables", "-t", "nat", "-A", "REDSOCKS", "-p", "tcp", "-d", "localhost", "-j", "RETURN"])
        execute_rule(["iptables", "-t", "nat", "-A", "REDSOCKS", "-p", "tcp", "-d", "127.0.0.1", "-j", "RETURN"])

        # 3. Exclude the SSH tunnel port specifically if provided
        if ssh_tunnel_port:
            console.print(f"Excluding SSH tunnel port {ssh_tunnel_port} from redirection", style="cyan")
            execute_rule(["iptables", "-t", "nat", "-A", "REDSOCKS", "-p", "tcp", "--dport", str(ssh_tunnel_port), "-j",
                          "RETURN"])
            execute_rule(["iptables", "-t", "nat", "-A", "REDSOCKS", "-p", "tcp", "--sport", str(ssh_tunnel_port), "-j",
                          "RETURN"])

        # 4. Add rules to exclude local networks
        networks = ["0.0.0.0/8", "10.0.0.0/8", "127.0.0.0/8", "169.254.0.0/16",
                    "172.16.0.0/12", "192.168.0.0/16", "224.0.0.0/4", "240.0.0.0/4"]

        for network in networks:
            execute_rule(["iptables", "-t", "nat", "-A", "REDSOCKS", "-d", network, "-j", "RETURN"])

        # 5. Redirect all other TCP traffic
        execute_rule(
            ["iptables", "-t", "nat", "-A", "REDSOCKS", "-p", "tcp", "-j", "REDIRECT", "--to-port", str(redsocks_port)])

        # 6. Apply the chain to output traffic
        execute_rule(["iptables", "-t", "nat", "-A", "OUTPUT", "-p", "tcp", "-j", "REDSOCKS"])

        # Verify the chain is actually in use
        result = subprocess.run(["iptables", "-t", "nat", "-L", "OUTPUT"],
                                capture_output=True, text=True, check=True)

        if "REDSOCKS" not in result.stdout:
            console.print("Warning: REDSOCKS chain not found in OUTPUT chain", style="yellow")
        else:
            console.print("iptables rules set up successfully", style="green")
            logging.info("iptables rules set up successfully")

    except Exception as e:
        error_message = f"Failed to set up iptables rules: {e}"
        console.print(error_message, style="red")
        logging.error(error_message)
        raise

def clean_iptables():
    """Clean up iptables rules."""
    logging.info("Cleaning up iptables rules...")
    try:
        # Remove rules
        subprocess.run(["iptables", "-t", "nat", "-D", "OUTPUT", "-p", "tcp", "-j", "REDSOCKS"], check=False)
        subprocess.run(["iptables", "-t", "nat", "-F", "REDSOCKS"], check=False)
        subprocess.run(["iptables", "-t", "nat", "-X", "REDSOCKS"], check=False)

        success_message = "iptables rules cleaned up successfully."
        console.print(success_message, style="green")
        logging.info(success_message)
    except subprocess.CalledProcessError as e:
        error_message = f"Error cleaning up iptables rules: {e}"
        console.print(error_message, style="red")
        logging.error(error_message)


def check_socks5_connectivity(host="127.0.0.1", port=1080):
    """Test if the SOCKS5 proxy is accessible."""
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((host, port))
        sock.close()
        console.print(f"SOCKS5 proxy at {host}:{port} is accessible", style="green")
        return True
    except Exception as e:
        console.print(f"Cannot connect to SOCKS5 proxy at {host}:{port}: {e}", style="red")
        return False


def validate_redsocks_config(config_path="/etc/redsocks.conf"):
    """Validate and display the redsocks configuration."""
    try:
        with open(config_path, 'r') as file:
            content = file.read()
            console.print("Current redsocks configuration:", style="cyan")
            console.print(content)

            # Check basic configuration aspects
            if "socks5" not in content:
                console.print("Warning: SOCKS5 configuration not found in redsocks.conf", style="yellow")

            return True
    except Exception as e:
        console.print(f"Error reading redsocks config: {e}", style="red")
        return False


def stream_log(log_path="/var/log/redsocks.log"):
    """
    Stream a log file in real-time, similar to 'tail -f'.
    """
    from rich.text import Text

    console = Console()
    console.print(f"Streaming log from {log_path}...", style="cyan")

    # Check if file exists
    if not os.path.exists(log_path):
        console.print(f"Log file doesn't exist: {log_path}", style="yellow")
        return

    try:
        # Open the file and seek to the end
        with open(log_path, 'r') as f:
            # Move to the end of the file
            f.seek(0, 2)

            while True:
                line = f.readline()
                if line:
                    # Color-code different log levels
                    text = Text()

                    if "error" in line.lower():
                        text.append(line.strip(), style="red bold")
                    elif "warning" in line.lower():
                        text.append(line.strip(), style="yellow")
                    elif "notice" in line.lower():
                        text.append(line.strip(), style="cyan")
                    elif "info" in line.lower():
                        text.append(line.strip(), style="green")
                    else:
                        text.append(line.strip())

                    console.print(text)
                else:
                    # Wait for more content
                    time.sleep(0.1)
    except KeyboardInterrupt:
        console.print("Log streaming stopped", style="yellow")
    except Exception as e:
        console.print(f"Error streaming log: {e}", style="red")

def verify_connection_tracking(redsocks_port):
    """Monitor active connections being redirected through redsocks"""
    try:
        # Run netstat to see connections to redsocks port
        result = subprocess.run(
            ["netstat", "-tpn"],
            capture_output=True, text=True, check=True
        )

        redsocks_connections = [line for line in result.stdout.split('\n')
                                if f":{redsocks_port}" in line]

        if redsocks_connections:
            console.print("Active connections through redsocks:", style="green")
            for conn in redsocks_connections:
                console.print(f"  {conn.strip()}")
            return True
        else:
            console.print("No active connections through redsocks detected", style="yellow")
            return False
    except Exception as e:
        console.print(f"Connection tracking check failed: {e}", style="red")
        return False

def check_dns_redirection():
    """Check if DNS queries are being redirected"""
    try:
        import socket
        ip = socket.gethostbyname('google.com')
        console.print(f"DNS resolution for google.com: {ip}", style="green")
        return True
    except Exception as e:
        console.print(f"DNS check failed: {e}", style="red")
        return False


def check_http_redirection():
    """Check if HTTP traffic is being redirected through the proxy"""
    try:
        # Get current IP as seen by external services
        import requests
        current_ip = requests.get('https://ifconfig.co').text.strip()
        # <p><code class="ip">2407:6ac0:3:9d:abcd::1c8</code></p>
        get_ip = re.search(r'<code class="ip">(.+?)</code>', current_ip)
        if get_ip:
            console.print(f"Current public IP: {get_ip.group(1)}", style="green")

        # Get HTTP headers to check for proxy indicators
        headers = requests.get('https://httpbin.org/headers').json()
        console.print("HTTP Headers:", style="cyan")
        for key, value in headers['headers'].items():
            console.print(f"  {key}: {value}")

        return True
    except Exception as e:
        console.print(f"HTTP check failed: {e}", style="red")
        return False

def verify_traffic_redirection(redsocks_port):
    """Comprehensive check of traffic redirection through the proxy"""
    console.print("\n=== Traffic Redirection Verification ===", style="bold cyan")

    # Check iptables rules
    try:
        result = subprocess.run(
            ["iptables", "-t", "nat", "-L", "OUTPUT", "-v", "-n"],
            capture_output=True, text=True, check=True
        )

        if "REDSOCKS" in result.stdout:
            console.print("✓ iptables rules are properly configured", style="green")

            # Check packet counts
            result = subprocess.run(
                ["iptables", "-t", "nat", "-L", "REDSOCKS", "-v", "-n"],
                capture_output=True, text=True, check=True
            )

            redirect_line = [line for line in result.stdout.split('\n')
                             if f"REDIRECT   tcp" in line and f"redir ports {redsocks_port}" in line]

            if redirect_line and len(redirect_line) > 0:
                parts = redirect_line[0].split()
                if len(parts) > 1:
                    packet_count = parts[0]
                    console.print(f"✓ {packet_count} packets redirected through redsocks", style="green")
        else:
            console.print("✗ REDSOCKS chain not found in iptables", style="red")
    except Exception as e:
        console.print(f"Error checking iptables rules: {e}", style="red")

    # Check HTTP traffic
    console.print("\nChecking HTTP traffic redirection...", style="cyan")
    check_http_redirection()

    # Check DNS resolution
    console.print("\nChecking DNS resolution...", style="cyan")
    check_dns_redirection()

    # Check active connections
    console.print("\nChecking active connections...", style="cyan")
    verify_connection_tracking(redsocks_port)

    console.print("\nTo confirm redirection is working correctly:", style="bold")
    console.print("1. Your public IP should be different from your actual IP", style="cyan")
    console.print("2. Traffic should be flowing through the redsocks port", style="cyan")
    console.print("3. The packet counts in iptables REDIRECT rule should increase", style="cyan")