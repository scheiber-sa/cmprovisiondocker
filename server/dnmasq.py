import subprocess
import threading
import time
import logging
import os
from pathlib import Path

from boardType import BoardType

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(message)s",
    handlers=[logging.StreamHandler()],
)

from projectManager import ProjectManager


class Dnsmasq:
    DNSMASQ_CONF_PATH = "/etc/dnsmasq.conf"
    hostInterface: str = ""
    serverIp: str = ""
    serverPort: int = 0
    dhcpRange: str = ""
    config: str = ""
    projectManager: ProjectManager
    _thread: threading.Thread
    _stopEvent: threading.Event = threading.Event()
    _activeFallbackBootDir: str = ""
    _generatedFallbackLinks: set[Path]
    _enableCm5SerialDebug: bool = False

    def __init__(self) -> None:
        """
        Constructor
        """
        self.projectManager = ProjectManager()
        self._generatedFallbackLinks = set()

    def setHostInterface(self, p_hostInterface: str) -> None:
        self.hostInterface = p_hostInterface

    def setServerIp(self, p_serverIp: str) -> None:
        """
        Set the server IP address.

        :param p_serverIp: The server IP address in CIDR notation (e.g. "192.168.1.1/24")
        :type p_serverIp: str
        """
        self.serverIp = p_serverIp

    def setServerPort(self, p_serverPort: int) -> None:
        """
        Set the server port.

        :param p_serverPort: The server port
        :type p_serverPort: int
        """
        self.serverPort = p_serverPort

    def setDhcpRange(self, p_dhcpRange: str) -> None:
        """
        Set the DHCP range.

        :param p_dhcpRange: The DHCP range
        :type p_dhcpRange: str
        """
        self.dhcpRange = p_dhcpRange

    def setEnableCm5SerialDebug(self, p_enable: bool) -> None:
        """
        Enable or disable CM5 serial debug output in cmdline.txt.

        :param p_enable: True to enable CM5 serial debug, False to disable
        :type p_enable: bool
        """
        self._enableCm5SerialDebug = p_enable

    def _setConfig(self) -> None:
        self.config = f"""
# No DNS
port=0

# tftp
enable-tftp
tftp-root=/tftpboot

# dhcp
interface={self.hostInterface}
# Famille Raspberry Pi
dhcp-match=set:cm4,97,0:34:69:50:52
dhcp-match=set:cm5,97,0:35:69:50:52
bind-interfaces

log-dhcp
dhcp-range={self.dhcpRange}
pxe-service=tag:cm4,0,"Raspberry Pi CM4 Boot"
pxe-service=tag:cm5,0,"Raspberry Pi CM5 Boot"
dhcp-option=tag:cm4,66,{self.serverIp.split('/')[0]}
dhcp-option=tag:cm5,66,{self.serverIp.split('/')[0]}
dhcp-boot=tag:cm4,cm4/start4.elf
dhcp-boot=tag:cm5,cm5/start4.elf
# dhcp-leasefile=/var/lib/cmprovision/etc/dnsmasq.leases
no-ping
"""
        with open(self.DNSMASQ_CONF_PATH, "w") as file:
            file.write(self.config)

    def _run(self) -> None:
        """
        Run dnsmasq and react to detected model tags in DHCP logs.
        """
        process: subprocess.Popen[str] | None = None
        try:
            process = subprocess.Popen(
                ["dnsmasq", "--no-daemon", f"--conf-file={self.DNSMASQ_CONF_PATH}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            if process.stdout is None:
                raise RuntimeError("Unable to read dnsmasq output stream")

            while not self._stopEvent.is_set():
                line = process.stdout.readline()
                if line == "":
                    if process.poll() is not None:
                        break
                    continue

                logLine = line.rstrip()
                logging.info(logLine)
                self._updateFallbackFromLog(logLine)

            if process.poll() is None:
                process.terminate()
                process.wait(timeout=2)
        except Exception as e:
            logging.error(f"Error running dnsmasq: {e}")
            if process is not None and process.poll() is None:
                process.kill()

    def _updateFallbackFromLog(self, p_logLine: str) -> None:
        """
        Update fallback symlinks when dnsmasq identifies a CM model tag.

        :param p_logLine: The dnsmasq log line to parse for model tags
        :type p_logLine: str
        """
        if "tags: cm4" in p_logLine:
            self._cmdline(BoardType.CM4)
            self._ensureRootFallback(BoardType.CM4.value)
        elif "tags: cm5" in p_logLine:
            self._cmdline(BoardType.CM5)
            self._ensureRootFallback(BoardType.CM5.value)

    def _cmdline(self, p_boardModel: BoardType):
        """
        Generate cmdline.txt content based on the detected board model and write it to the TFTP root.

        :param p_boardModel: The detected board model for cmdline generation
        :type p_boardModel: BoardType
        """
        if p_boardModel == BoardType.CM4:
            cmdlinePrefix = ""
        elif p_boardModel == BoardType.CM5:
            if self._enableCm5SerialDebug:
                cmdlinePrefix = "console=serial0,115200 console=tty1 earlycon=pl011,0x107d001000,115200n8 loglevel=8 ignore_loglevel net.ifnames=0"
            else:
                cmdlinePrefix = "net.ifnames=0"
        else:
            logging.warning(
                f"Unknown board model for cmdline generation: {p_boardModel}"
            )
            cmdlinePrefix = ""
        cmdlineTemplate = (
            "readjumper script=http://{serverIP}/scriptexecute?serial={{serial}}&model={{model}}"
            "&storagesize={{storagesize}}&mac={{mac}}&inversejumper={{jumper}}&memorysize={{memorysize}}"
            "&temp={{temp}}&cid={{cid}}&csd={{csd}}&bootmode={{bootmode}}"
        )

        cmdline = cmdlineTemplate.format(
            serverIP=self.serverIp.split("/")[0] + ":" + str(self.serverPort)
        )
        cmdline += f"\n"

        cmdline = cmdlinePrefix + " " + cmdline

        with open("/tftpboot/cmdline.txt", "w") as file:
            file.write(cmdline)

        # Keep cmdline.txt in model-specific boot folders when using per-model TFTP layout.
        for bootDir in [BoardType.CM4.value, BoardType.CM5.value]:
            bootPath = f"/tftpboot/{bootDir}"
            os.makedirs(bootPath, exist_ok=True)
            with open(f"{bootPath}/cmdline.txt", "w") as file:
                file.write(cmdline)

    def _ensureRootFallback(self, p_bootDir: str) -> None:
        """
        Ensure legacy root-level TFTP files exist for Raspberry Pi netboot fallback.
        The bootloader may still probe /tftpboot/<serial>/ then /tftpboot/*.

        :param p_bootDir: The boot directory to link from (e.g. "cm4" or "cm5")
        :type p_bootDir: str
        """
        if self._activeFallbackBootDir == p_bootDir:
            return

        sourceRoot = Path(f"/tftpboot/{p_bootDir}")
        targetRoot = Path("/tftpboot")

        # Remove all previous symlinks in targetRoot before creating new ones to avoid stale links when switching between models.
        for entry in targetRoot.iterdir():
            if entry.is_symlink():
                try:
                    entry.unlink()
                except OSError:
                    pass

        if not sourceRoot.is_dir():
            logging.warning(f"TFTP source directory does not exist: {sourceRoot}")
            return

        # Remove previously generated fallback links before switching model.
        for generatedPath in list(self._generatedFallbackLinks):
            try:
                if generatedPath.is_symlink():
                    generatedPath.unlink()
            except OSError:
                pass
        self._generatedFallbackLinks.clear()

        for entry in sourceRoot.iterdir():
            target = targetRoot / entry.name

            # Do not override existing files/directories (e.g. cmdline.txt generated at runtime).
            if target.exists():
                continue

            try:
                target.symlink_to(entry)
                self._generatedFallbackLinks.add(target)
            except OSError as e:
                logging.warning(
                    f"Unable to create TFTP fallback link {target} -> {entry}: {e}"
                )

        self._activeFallbackBootDir = p_bootDir
        logging.info(f"TFTP fallback now points to /tftpboot/{p_bootDir}")

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
        self._setConfig()

        self._stopEvent.clear()
        self._thread = threading.Thread(target=self._RunInThread, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """
        Stop the dnsmasq service and thread.
        """
        try:
            self._stopEvent.set()
            subprocess.run(["killall", "dnsmasq"], check=True)
            if self._thread:
                self._thread.join()
        except:
            pass
