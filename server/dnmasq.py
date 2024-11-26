import subprocess
import threading
import time

from projectManager import ProjectManager


class Dnsmasq:
    DNSMASQ_CONF_PATH = "/etc/dnsmasq.conf"
    hostInterface: str = ""
    serverIp: str = ""
    dhcpRange: str = ""
    config: str = ""
    projectManager: ProjectManager
    _thread: threading.Thread
    _stopEvent: threading.Event = threading.Event()

    def __init__(self) -> None:
        """
        Constructor
        """
        self.projectManager = ProjectManager()

    def setHostInterface(self, hostInterface: str) -> None:
        self.hostInterface = hostInterface

    def setServerIp(self, serverIp: str) -> None:
        """
        Set the server IP address.

        :param serverIp: _description_
        :type serverIp: str
        """
        self.serverIp = serverIp

    def setDhcpRange(self, dhcpRange: str) -> None:
        self.dhcpRange = dhcpRange

    def _setConfig(self) -> None:
        self.config = f"""
# No DNS
port=0

# tftp
enable-tftp
tftp-root=/tftpboot

# dhcp
interface={self.hostInterface}
dhcp-match=set:client_is_a_pi,97,0:52:50:69:34
dhcp-match=set:client_is_a_pi,97,0:34:69:50:52
bind-interfaces

log-dhcp
dhcp-range={self.dhcpRange}
pxe-service=tag:client_is_a_pi,0,"Raspberry Pi Boot"
# dhcp-leasefile=/var/lib/cmprovision/etc/dnsmasq.leases
no-ping
"""
        with open(self.DNSMASQ_CONF_PATH, "w") as file:
            file.write(self.config)

    def _run(self) -> None:
        """
        Run the dnsmasq configuration in a loop until stopped.
        """
        try:
            subprocess.run(
                ["dnsmasq", "--no-daemon", f"--conf-file={self.DNSMASQ_CONF_PATH}"],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"Error running dnsmasq: {e}")

    def _cmdline(self) -> None:
        cmdlineTemplate = (
            "readjumper script=http://{serverIP}/scriptexecute?serial={{serial}}&model={{model}}"
            "&storagesize={{storagesize}}&mac={{mac}}&inversejumper={{jumper}}&memorysize={{memorysize}}"
            "&temp={{temp}}&cid={{cid}}&csd={{csd}}&bootmode={{bootmode}}"
        )

        cmdline = cmdlineTemplate.format(serverIP=self.serverIp.split("/")[0])
        cmdline += f"\n"

        with open("/tftpboot/cmdline.txt", "w") as file:
            file.write(cmdline)

    def _RunInThread(self) -> None:
        """
        Thread target to run the dnsmasq process.
        """

        while not self._stopEvent.is_set():
            projectName = ""
            # Until the project name is "" and the project status is False, wait
            while projectName == "":
                time.sleep(0.5)
                _, projectName = self.projectManager.getActiveProjectName()
            self._run()

    def start(self) -> None:
        """
        Start the dnsmasq configuration in a separate thread.
        """
        self._cmdline()
        self._setConfig()

        self._stopEvent.clear()
        self._thread = threading.Thread(target=self._RunInThread, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """
        Stop the dnsmasq service and thread.
        """
        self._stopEvent.set()
        subprocess.run(["killall", "dnsmasq"], check=True)
        if self._thread:
            self._thread.join()
