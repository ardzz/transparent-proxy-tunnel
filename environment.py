import os
import sys
from rich.console import Console
from dotenv import load_dotenv

# Create a console instance for rich output
console = Console()

def load_environment():
    """Load and validate environment variables from .env file."""
    load_dotenv()

    # Define required variables
    required_vars = ['REMOTE_HOST', 'SSH_USER', 'SSH_AUTH_METHOD', 'SSH_AUTH_VALUE', 'SSH_TUNNEL_PORT', 'REDSOCKS_PORT']
    for var in required_vars:
        if not os.getenv(var):
            console.print(f"Missing required environment variable: {var}", style="red")
            sys.exit(1)

    # Retrieve variables
    remote_host = os.getenv('REMOTE_HOST')
    ssh_user = os.getenv('SSH_USER')
    ssh_auth_method = os.getenv('SSH_AUTH_METHOD')
    ssh_auth_value = os.getenv('SSH_AUTH_VALUE')

    # Validate authentication method
    if ssh_auth_method not in ['key', 'password']:
        console.print(f"Invalid SSH_AUTH_METHOD: {ssh_auth_method}", style="red")
        console.print("Supported authentication methods: 'key' or 'password'", style="yellow")
        sys.exit(1)

    # Validate SSH key file if using key authentication
    if ssh_auth_method == 'key' and not os.path.isfile(ssh_auth_value):
        console.print(f"SSH key file not found: {ssh_auth_value}", style="red")
        sys.exit(1)

    # Validate port numbers
    try:
        ssh_tunnel_port = int(os.getenv('SSH_TUNNEL_PORT'))
        redsocks_port = int(os.getenv('REDSOCKS_PORT'))
    except ValueError:
        console.print("SSH_TUNNEL_PORT and REDSOCKS_PORT must be integers.", style="red")
        sys.exit(1)

    if not (1 <= ssh_tunnel_port <= 65535 and 1 <= redsocks_port <= 65535):
        console.print("Port numbers must be between 1 and 65535.", style="red")
        sys.exit(1)
    if ssh_tunnel_port == redsocks_port:
        console.print("SSH_TUNNEL_PORT and REDSOCKS_PORT must be different.", style="red")
        sys.exit(1)

    return remote_host, ssh_user, ssh_auth_method, ssh_auth_value, ssh_tunnel_port, redsocks_port