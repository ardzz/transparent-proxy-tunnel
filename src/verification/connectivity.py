"""Connectivity testing and validation."""

import re
from typing import Dict, Any

import requests

from ..core.network import test_socks5_connectivity, resolve_hostname
from ..utils.console import console
from ..utils.exceptions import ConnectivityError
from ..utils.logging import get_logger

logger = get_logger("verification.connectivity")


class ConnectivityTester:
    """Tests various aspects of network connectivity through the proxy."""

    def __init__(self):
        self.timeout = 10

    def test_socks5_proxy(self, host: str = "127.0.0.1", port: int = 1080) -> bool:
        """Test SOCKS5 proxy connectivity."""
        logger.info(f"Testing SOCKS5 proxy at {host}:{port}")
        return test_socks5_connectivity(host, port, self.timeout)

    def test_dns_resolution(self, hostname: str = "google.com") -> Dict[str, Any]:
        """
        Test DNS resolution.

        Args:
            hostname: Hostname to resolve

        Returns:
            Dictionary with resolution results
        """
        logger.info(f"Testing DNS resolution for {hostname}")

        result = {
            "hostname": hostname,
            "success": False,
            "ip_address": None,
            "error": None
        }

        try:
            ip = resolve_hostname(hostname)
            result["success"] = True
            result["ip_address"] = ip
            console.print_success(f"DNS resolution for {hostname}: {ip}")
        except ConnectivityError as e:
            result["error"] = str(e)
            console.print_error(f"DNS resolution failed for {hostname}: {e}")

        return result

    def test_http_connectivity(self, url: str = "https://httpbin.org/ip") -> Dict[str, Any]:
        """
        Test HTTP connectivity and get external IP.

        Args:
            url: URL to test HTTP connectivity

        Returns:
            Dictionary with HTTP test results
        """
        logger.info(f"Testing HTTP connectivity to {url}")

        result = {
            "url": url,
            "success": False,
            "status_code": None,
            "external_ip": None,
            "response_time": None,
            "error": None
        }

        try:
            import time
            start_time = time.time()

            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()

            result["success"] = True
            result["status_code"] = response.status_code
            result["response_time"] = time.time() - start_time

            try:
                data = response.json()
                if "origin" in data:
                    result["external_ip"] = data["origin"]
                elif "ip" in data:
                    result["external_ip"] = data["ip"]
            except:
                ip_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
                matches = re.findall(ip_pattern, response.text)
                if matches:
                    result["external_ip"] = matches[0]

            if result["external_ip"]:
                console.print_success(f"HTTP test successful. External IP: {result['external_ip']}")
            else:
                console.print_success("HTTP test successful")

        except Exception as e:
            result["error"] = str(e)
            console.print_error(f"HTTP test failed: {e}")
            logger.error(f"HTTP connectivity test failed: {e}")

        return result

    def test_https_connectivity(self, url: str = "https://www.google.com") -> Dict[str, Any]:
        """
        Test HTTPS connectivity.

        Args:
            url: HTTPS URL to test

        Returns:
            Dictionary with HTTPS test results
        """
        logger.info(f"Testing HTTPS connectivity to {url}")

        result = {
            "url": url,
            "success": False,
            "status_code": None,
            "ssl_verified": False,
            "response_time": None,
            "error": None
        }

        try:
            import time
            start_time = time.time()

            response = requests.get(url, timeout=self.timeout, verify=True)
            response.raise_for_status()

            result["success"] = True
            result["status_code"] = response.status_code
            result["ssl_verified"] = True
            result["response_time"] = time.time() - start_time

            console.print_success(f"HTTPS test successful to {url}")

        except requests.exceptions.SSLError as e:
            result["error"] = f"SSL Error: {e}"
            console.print_error(f"HTTPS SSL verification failed: {e}")
        except Exception as e:
            result["error"] = str(e)
            console.print_error(f"HTTPS test failed: {e}")
            logger.error(f"HTTPS connectivity test failed: {e}")

        return result

    def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run a comprehensive connectivity test suite."""
        logger.info("Running comprehensive connectivity tests")

        results = {
            "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
            "tests": {}
        }

        results["tests"]["socks5"] = {
            "success": self.test_socks5_proxy()
        }

        results["tests"]["dns"] = self.test_dns_resolution()
        results["tests"]["http"] = self.test_http_connectivity()
        results["tests"]["https"] = self.test_https_connectivity()

        all_tests_passed = all(
            test_result.get("success", False)
            for test_result in results["tests"].values()
        )

        results["overall_success"] = all_tests_passed

        if all_tests_passed:
            console.print_success("All connectivity tests passed")
        else:
            console.print_warning("Some connectivity tests failed")

        return results