"""Traffic verification and analysis."""

import subprocess
import time
from typing import Dict, Any

from ..utils.console import console
from ..utils.logging import get_logger

logger = get_logger("verification.traffic")


class TrafficVerifier:
    """Verifies that traffic is being properly redirected through the proxy."""

    def __init__(self):
        pass

    def verify_iptables_redirection(self, redsocks_port: int) -> Dict[str, Any]:
        """
        Verify iptables redirection is working.

        Args:
            redsocks_port: Port where redsocks is listening

        Returns:
            Dictionary with verification results
        """
        logger.info("Verifying iptables redirection")

        result = {
            "success": False,
            "chain_exists": False,
            "rules_configured": False,
            "packets_redirected": 0,
            "bytes_redirected": 0,
            "error": None
        }

        try:
            output_result = subprocess.run([
                "iptables", "-t", "nat", "-L", "OUTPUT", "-v", "-n"
            ], capture_output=True, text=True, check=True)

            if "REDSOCKS" in output_result.stdout:
                result["chain_exists"] = True
                console.print_success("✓ iptables REDSOCKS chain configured")
            else:
                result["error"] = "REDSOCKS chain not found in OUTPUT"
                console.print_error("✗ REDSOCKS chain not found in iptables OUTPUT")
                return result

            chain_result = subprocess.run([
                "iptables", "-t", "nat", "-L", "REDSOCKS", "-v", "-n"
            ], capture_output=True, text=True, check=True)

            redirect_found = False
            for line in chain_result.stdout.split('\n'):
                if 'REDIRECT' in line and f'redir ports {redsocks_port}' in line:
                    redirect_found = True
                    result["rules_configured"] = True

                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            result["packets_redirected"] = int(parts[0])
                            result["bytes_redirected"] = int(parts[1])
                        except (ValueError, IndexError):
                            pass

                    console.print_success(f"✓ Traffic redirection rule found ({result['packets_redirected']} packets)")
                    break

            if not redirect_found:
                result["error"] = f"REDIRECT rule to port {redsocks_port} not found"
                console.print_error("✗ Traffic redirection rule not found")
                return result

            result["success"] = True

        except subprocess.CalledProcessError as e:
            result["error"] = f"iptables command failed: {e}"
            console.print_error(f"✗ iptables verification failed: {e}")
        except Exception as e:
            result["error"] = f"Unexpected error: {e}"
            console.print_error(f"✗ Traffic verification error: {e}")
            logger.error(f"Traffic verification error: {e}")

        return result

    def check_active_connections(self, redsocks_port: int) -> Dict[str, Any]:
        """
        Check active connections through redsocks.

        Args:
            redsocks_port: Port where redsocks is listening to

        Returns:
            Dictionary with connection information
        """
        logger.info(f"Checking active connections to redsocks port {redsocks_port}")

        result = {
            "success": False,
            "total_connections": 0,
            "connections": [],
            "error": None
        }

        try:
            netstat_result = subprocess.run([
                "netstat", "-tpn"
            ], capture_output=True, text=True, check=True)

            connections = []
            for line in netstat_result.stdout.split('\n'):
                if f":{redsocks_port}" in line:
                    connections.append(line.strip())

            result["total_connections"] = len(connections)
            result["connections"] = connections
            result["success"] = True

            if connections:
                console.print_success(f"✓ {len(connections)} active connections through redsocks")
                for conn in connections[:5]:
                    console.print_info(f"  {conn}")
                if len(connections) > 5:
                    console.print_info(f"  ... and {len(connections) - 5} more")
            else:
                console.print_warning("No active connections through redsocks detected")

        except subprocess.CalledProcessError as e:
            result["error"] = f"netstat command failed: {e}"
            console.print_error(f"✗ Connection check failed: {e}")
        except Exception as e:
            result["error"] = f"Unexpected error: {e}"
            logger.error(f"Connection check error: {e}")

        return result

    def analyze_traffic_patterns(self, duration: int = 10) -> Dict[str, Any]:
        """
        Analyze traffic patterns over a specified duration.

        Args:
            duration: Duration in seconds to analyze traffic

        Returns:
            Dictionary with traffic analysis results
        """
        logger.info(f"Analyzing traffic patterns for {duration} seconds")

        result = {
            "success": False,
            "duration": duration,
            "initial_stats": {},
            "final_stats": {},
            "packets_transferred": 0,
            "bytes_transferred": 0,
            "error": None
        }

        try:
            result["initial_stats"] = self._get_iptables_stats()

            console.print_info(f"Monitoring traffic for {duration} seconds...")
            time.sleep(duration)

            result["final_stats"] = self._get_iptables_stats()

            if result["initial_stats"]["success"] and result["final_stats"]["success"]:
                result["packets_transferred"] = (
                        result["final_stats"]["packets_redirected"] -
                        result["initial_stats"]["packets_redirected"]
                )
                result["bytes_transferred"] = (
                        result["final_stats"]["bytes_redirected"] -
                        result["initial_stats"]["bytes_redirected"]
                )

                result["success"] = True

                console.print_success(
                    f"Traffic analysis complete: {result['packets_transferred']} packets, "
                    f"{result['bytes_transferred']} bytes transferred"
                )
            else:
                result["error"] = "Failed to get iptables statistics"

        except Exception as e:
            result["error"] = f"Traffic analysis error: {e}"
            logger.error(f"Traffic analysis error: {e}")

        return result

    def _get_iptables_stats(self) -> Dict[str, Any]:
        """Get current iptables statistics."""
        stats = {
            "success": False,
            "packets_redirected": 0,
            "bytes_redirected": 0,
            "error": None
        }

        try:
            result = subprocess.run([
                "iptables", "-t", "nat", "-L", "REDSOCKS", "-v", "-n"
            ], capture_output=True, text=True, check=True)

            for line in result.stdout.split('\n'):
                if 'REDIRECT' in line and 'tcp' in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            stats["packets_redirected"] = int(parts[0])
                            stats["bytes_redirected"] = int(parts[1])
                            stats["success"] = True
                            break
                        except (ValueError, IndexError):
                            continue

        except subprocess.CalledProcessError as e:
            stats["error"] = f"iptables command failed: {e}"
        except Exception as e:
            stats["error"] = f"Unexpected error: {e}"

        return stats