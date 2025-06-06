#!/usr/bin/env python3

import subprocess
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(message)s",
    handlers=[logging.StreamHandler()],
)


class HosInterface:

    def __init__(self) -> None:
        """
        Constructor
        """
        pass

    def setIpAddress(self, p_interface: str, p_ipAddress: str) -> None:
        """
        Set the IP address

        :param p_interface: The interface
        :type p_interface: str
        :param p_ipAddress: The IP address
        :type p_ipAddress: str
        """
        if not self._isIpAssigned(p_interface, p_ipAddress):
            subprocess.run(
                ["ip", "addr", "add", p_ipAddress, "dev", p_interface], check=True
            )
        else:
            logging.info(f"Setting IP address {p_ipAddress} on interface {p_interface}")
        subprocess.run(["ip", "link", "set", p_interface, "up"], check=True)

    def _isIpAssigned(self, p_interface: str, p_ipAddress: str) -> bool:
        """
        Check if the IP is already assigned to the interface.

        :param p_interface: The interface
        :type p_interface: str
        :param p_ipAddress: The IP address
        :type p_ipAddress: str

        :return: True if the IP is already assigned to the interface, False otherwise
        """
        try:
            result = subprocess.run(
                ["ip", "addr", "show", p_interface],
                capture_output=True,
                text=True,
                check=True,
            )
            return p_ipAddress.split("/")[0] in result.stdout
        except subprocess.CalledProcessError:
            return False
