import os
from rich.console import Console

# Create a console instance
console = Console()

def generate_redsocks_config(redsocks_port: int, proxy_ip: str, proxy_port: int):
    """Generate the redsocks configuration file."""
    config_content = f"""
base {{
    log_debug = off;
    log_info = on;
    log = "file:/var/log/redsocks.log";
    daemon = on;
    redirector = iptables;
}}

redsocks {{
    local_ip = 0.0.0.0;
    local_port = {redsocks_port};
    ip = {proxy_ip};
    port = {proxy_port};
    type = socks5;
}}
"""
    config_path = "/etc/redsocks.conf"
    try:
        with open(config_path, "w") as f:
            f.write(config_content)
        os.chmod(config_path, 0o644)
        console.print(f"Redsocks configuration generated at {config_path}.", style="green")
    except IOError as e:
        console.print(f"Failed to write redsocks config: {e}", style="red")
        raise