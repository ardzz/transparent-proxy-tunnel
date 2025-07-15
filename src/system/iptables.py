"""iptables management for traffic redirection."""

import subprocess
from typing import Dict, Any, Optional

from .platform import PlatformManager
from ..utils.console import console
from ..utils.exceptions import IptablesError, PlatformNotSupportedError
from ..utils.logging import get_logger

logger = get_logger("system.iptables")


class IptablesManager:
    """Manages iptables rules for transparent proxy redirection."""

    def __init__(self, platform_manager: PlatformManager):
        self.platform_manager = platform_manager
        self.chain_name = "REDSOCKS"

        if not platform_manager.supports_transparent_proxy():
            raise PlatformNotSupportedError("iptables management requires Linux")

    def setup_redirection(self, redsocks_port: int, ssh_tunnel_port: Optional[int] = None) -> None:
        """
        Set up iptables rules for traffic redirection.

        Args:
            redsocks_port: Port where redsocks is listening
            ssh_tunnel_port: SSH tunnel port to exclude from redirection

        Raises:
            IptablesError: If iptables setup fails
        """
        logger.info(f"Setting up iptables redirection to port {redsocks_port}")

        try:

            self._load_kernel_modules()
            self._verify_nat_support()
            self._cleanup_existing_rules()
            self._create_redsocks_chain()
            self._add_exclusion_rules(ssh_tunnel_port)
            self._add_redirection_rule(redsocks_port)
            self._apply_chain_to_output()
            self._verify_rules()

            console.print_success("iptables rules configured successfully")
            logger.info("iptables redirection setup completed")

        except Exception as e:
            logger.error(f"Failed to setup iptables redirection: {e}")
            try:
                self.cleanup()
            except:
                pass
            raise IptablesError(f"Failed to setup iptables redirection: {e}") from e

    def cleanup(self) -> None:
        """Clean up all iptables rules created by this manager."""
        logger.info("Cleaning up iptables rules")

        try:
            subprocess.run([
                "iptables", "-t", "nat", "-D", "OUTPUT", "-p", "tcp", "-j", self.chain_name
            ], check=False, capture_output=True)

            subprocess.run([
                "iptables", "-t", "nat", "-F", self.chain_name
            ], check=False, capture_output=True)

            subprocess.run([
                "iptables", "-t", "nat", "-X", self.chain_name
            ], check=False, capture_output=True)

            console.print_success("iptables rules cleaned up")
            logger.info("iptables cleanup completed")

        except Exception as e:
            logger.error(f"Error during iptables cleanup: {e}")
            console.print_warning(f"iptables cleanup had errors: {e}")

    def get_redirection_stats(self) -> Dict[str, Any]:
        """Get statistics about traffic redirection."""
        try:
            result = subprocess.run([
                "iptables", "-t", "nat", "-L", self.chain_name, "-v", "-n"
            ], capture_output=True, text=True, check=True)

            stats = {
                "chain_exists": True,
                "rules": [],
                "total_packets": 0,
                "total_bytes": 0
            }

            for line in result.stdout.split('\n'):
                if 'REDIRECT' in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            packets = int(parts[0])
                            bytes_val = int(parts[1])
                            stats["total_packets"] += packets
                            stats["total_bytes"] += bytes_val
                            stats["rules"].append({
                                "packets": packets,
                                "bytes": bytes_val,
                                "rule": line.strip()
                            })
                        except (ValueError, IndexError):
                            continue

            return stats

        except subprocess.CalledProcessError:
            return {"chain_exists": False, "rules": [], "total_packets": 0, "total_bytes": 0}
        except Exception as e:
            logger.error(f"Error getting redirection stats: {e}")
            return {"chain_exists": False, "rules": [], "total_packets": 0, "total_bytes": 0}

    def _load_kernel_modules(self) -> None:
        """Load required kernel modules."""
        modules = ["iptable_nat", "xt_REDIRECT"]

        for module in modules:
            try:
                subprocess.run(["modprobe", module], check=False, capture_output=True)
                logger.debug(f"Loaded kernel module: {module}")
            except Exception as e:
                logger.warning(f"Could not load kernel module {module}: {e}")

    def _verify_nat_support(self) -> None:
        """Verify that iptables NAT table is available."""
        try:
            subprocess.run([
                "iptables", "-t", "nat", "-L"
            ], capture_output=True, check=True)
        except subprocess.CalledProcessError as e:
            raise IptablesError("NAT table not available in iptables. Ensure kernel modules are loaded.") from e

    def _cleanup_existing_rules(self) -> None:
        """Clean up any existing REDSOCKS rules."""
        result = subprocess.run([
            "iptables", "-t", "nat", "-L", self.chain_name
        ], capture_output=True, check=False)

        if result.returncode == 0:
            logger.info("Cleaning up existing REDSOCKS rules")

            subprocess.run([
                "iptables", "-t", "nat", "-D", "OUTPUT", "-p", "tcp", "-j", self.chain_name
            ], check=False, capture_output=True)

            subprocess.run([
                "iptables", "-t", "nat", "-F", self.chain_name
            ], check=False, capture_output=True)

            subprocess.run([
                "iptables", "-t", "nat", "-X", self.chain_name
            ], check=False, capture_output=True)

    def _create_redsocks_chain(self) -> None:
        """Create the REDSOCKS chain."""
        subprocess.run([
            "iptables", "-t", "nat", "-N", self.chain_name
        ], check=True, capture_output=True)
        logger.debug("Created REDSOCKS chain")

    def _add_exclusion_rules(self, ssh_tunnel_port: Optional[int] = None) -> None:
        """Add rules to exclude certain traffic from redirection."""
        exclusion_rules = [
            ["-p", "tcp", "--dport", "22", "-j", "RETURN"],
            ["-p", "tcp", "-d", "localhost", "-j", "RETURN"],
            ["-p", "tcp", "-d", "127.0.0.1", "-j", "RETURN"],
        ]

        if ssh_tunnel_port:
            exclusion_rules.extend([
                ["-p", "tcp", "--dport", str(ssh_tunnel_port), "-j", "RETURN"],
                ["-p", "tcp", "--sport", str(ssh_tunnel_port), "-j", "RETURN"],
            ])

        local_networks = [
            "0.0.0.0/8", "10.0.0.0/8", "127.0.0.0/8", "169.254.0.0/16",
            "172.16.0.0/12", "192.168.0.0/16", "224.0.0.0/4", "240.0.0.0/4"
        ]

        for network in local_networks:
            exclusion_rules.append(["-d", network, "-j", "RETURN"])

        for rule in exclusion_rules:
            try:
                subprocess.run([
                                   "iptables", "-t", "nat", "-A", self.chain_name
                               ] + rule, check=True, capture_output=True)
                logger.debug(f"Added exclusion rule: {' '.join(rule)}")
            except subprocess.CalledProcessError as e:
                logger.warning(f"Failed to add exclusion rule {' '.join(rule)}: {e}")

    def _add_redirection_rule(self, redsocks_port: int) -> None:
        """Add the main redirection rule."""
        subprocess.run([
            "iptables", "-t", "nat", "-A", self.chain_name,
            "-p", "tcp", "-j", "REDIRECT", "--to-port", str(redsocks_port)
        ], check=True, capture_output=True)
        logger.debug(f"Added redirection rule to port {redsocks_port}")

    def _apply_chain_to_output(self) -> None:
        """Apply the REDSOCKS chain to OUTPUT traffic."""
        subprocess.run([
            "iptables", "-t", "nat", "-A", "OUTPUT", "-p", "tcp", "-j", self.chain_name
        ], check=True, capture_output=True)
        logger.debug("Applied REDSOCKS chain to OUTPUT")

    def _verify_rules(self) -> None:
        """Verify that rules were applied correctly."""
        result = subprocess.run([
            "iptables", "-t", "nat", "-L", "OUTPUT"
        ], capture_output=True, text=True, check=True)

        if self.chain_name not in result.stdout:
            raise IptablesError(f"{self.chain_name} chain not found in OUTPUT chain")

        result = subprocess.run([
            "iptables", "-t", "nat", "-L", self.chain_name
        ], capture_output=True, text=True, check=True)

        if "REDIRECT" not in result.stdout:
            raise IptablesError("REDIRECT rule not found in REDSOCKS chain")

        logger.debug("iptables rules verification passed")