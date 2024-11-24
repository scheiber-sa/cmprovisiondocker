#!/usr/bin/env python3

import yaml
import signal
import uvicorn
from multiprocessing import Process
from dnmasq import Dnsmasq
from hosInterface import HosInterface
from httpServer import HttpServer


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
        self.httpServer: HttpServer = HttpServer()
        self._loadConfig()

    def _loadConfig(self):
        """
        Load the configuration from the YAML file.
        """
        with open(self.configFile, "r") as file:
            config = yaml.safe_load(file)

        self.hostInterface = config["server"]["hostIface"]
        self.serverIp = config["server"]["serverIp"]
        self.dhcpRange = config["server"]["dhcpRange"]

    def startHttpServer(self):
        """
        Starts the FastAPI HTTP server in a separate process.
        """
        self.httpServer.setServerIp(self.serverIp.split("/")[0])
        uvicorn.run(self.httpServer.app, host="0.0.0.0", port=80, log_level="info")

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
        self.dnsmasq.setDhcpRange(self.dhcpRange)
        self.dnsmasq.start()

        # Start the HTTP server
        self.httpServerProcess = Process(target=self.startHttpServer)
        self.httpServerProcess.start()

    def stop(self):
        """
        Stop the HTTP server and dnsmasq.
        """
        self.dnsmasq.stop()
        self.httpServerProcess.terminate()


if __name__ == "__main__":
    # Run the cmprovision server
    configFile: str = ""
    cmProvisionServer: CmProvisionServer | None = None
    try:
        configFile = "/app/conf/cmprovisionserverconf.yml"
        cmProvisionServer = CmProvisionServer(configFile)
        cmProvisionServer.run()

        # Block the main thread, waiting for termination signal
        print("CmProvisionServer is running. Press Ctrl+C to stop.")
        signal.pause()  # Wait for signal (e.g., SIGINT)

    except Exception as e:
        print(f"Error running cmprovision server: {e}")
    finally:
        print("Stopping cmprovision server.")
        if cmProvisionServer is not None:
            cmProvisionServer.stop()
        print("Stopped cmprovision server.")
