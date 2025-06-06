#!/usr/bin/env python3

import yaml
import signal
import uvicorn
from multiprocessing import Process
from dnmasq import Dnsmasq
from hosInterface import HosInterface
from httpServer import HttpServer
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(message)s",
    handlers=[logging.StreamHandler()],
)


class CmProvisionServer:
    serverInterface: HosInterface
    dnsmasq: Dnsmasq
    httpServerProcess: Process

    def __init__(self, p_configFile: str) -> None:
        """
        Constructor

        :param p_configFile: The configuration file
        :type p_configFile: str
        """

        self.configFile = p_configFile
        self.hostInterface = ""
        self.serverIp = ""
        self.dhcpRange = ""
        self.port = 0
        self.httpServer: HttpServer = HttpServer()
        self._loadConfig()

    def _loadConfig(self):
        """
        Load the configuration from the YAML file.
        """
        with open(self.configFile, "r") as file:
            config = yaml.safe_load(file)

        self.hostInterface = config["cmProvisionServer"]["hostIface"]
        self.serverIp = config["cmProvisionServer"]["serverIp"]
        self.dhcpRange = config["cmProvisionServer"]["dhcpRange"]
        self.port = config["cmProvisionServer"]["restApiPort"]

    def startHttpServer(self):
        """
        Starts the FastAPI HTTP server in a separate process.
        """
        self.httpServer.setServerIp(self.serverIp.split("/")[0])
        self.httpServer.setServerPort(self.port)
        logging.info(
            f"Starting HTTP server, API docs http://{self.httpServer.serverIp}:{self.httpServer.serverPort}/docs"
        )
        uvicorn.run(
            self.httpServer.app, host="0.0.0.0", port=self.port, log_level="info"
        )

    def run(self):
        """
        Configure the network interface, start the HTTP server and dnsmasq.
        """
        # Configure the network interface
        self.serverInterface = HosInterface()
        self.serverInterface.setIpAddress(self.hostInterface, self.serverIp)

        # Start dnsmasq
        self.dnsmasq = Dnsmasq()
        self.dnsmasq.setHostInterface(self.hostInterface)
        self.dnsmasq.setServerIp(self.serverIp)
        self.dnsmasq.setServerPort(self.port)
        self.dnsmasq.setDhcpRange(self.dhcpRange)
        self.dnsmasq.start()

        # Start the HTTP server
        self.httpServerProcess = Process(target=self.startHttpServer)
        self.httpServerProcess.start()

    def stop(self):
        """
        Stop the HTTP server and dnsmasq.
        """
        if "dnsmaq" in self.__dict__:
            self.dnsmasq.stop()
        if "httpServerProcess" in self.__dict__:
            self.httpServerProcess.terminate()


if __name__ == "__main__":
    # Run the cmprovision server
    configFile: str = ""
    cmProvisionServer: CmProvisionServer | None = None
    try:
        configFile = "/app/conf/cmprovisionserverconf.yml"
        cmProvisionServer = CmProvisionServer(configFile)
        logging.info("CmProvisionServer is running. Press Ctrl+C to stop.")
        cmProvisionServer.run()

        # Block the main thread, waiting for termination signal
        signal.pause()  # Wait for signal (e.g., SIGINT)

    except Exception as e:
        logging.error(f"Error running cmprovision server: {e}")
    finally:
        logging.info("Stopping cmprovision server.")
        if cmProvisionServer is not None:
            cmProvisionServer.stop()
        logging.info("CmProvisionServer stopped.")
