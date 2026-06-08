#!/usr/bin/env python3

import json
from typing import Any, Optional
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(message)s",
    handlers=[logging.StreamHandler()],
)


class ProjectManager:
    configPath: str = "/app/conf/projectConfig.json"
    config: dict[str, dict[str, Any]]
    _instance = None
    __initialized = False

    def __new__(cls, *args: Any, **kwargs: Any):
        args = args
        kwargs = kwargs
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self.__initialized:
            self.__initialized = True
            self.configPath = "/app/conf/projectConfig.json"
            self.config = {}
            self._loadConfig()

    def _loadConfig(self):
        """
        Load the configuration from the JSON file.
        """
        try:
            with open(self.configPath, "r") as file:
                self.config = json.load(file)
        except FileNotFoundError as e:
            logging.warning(
                f"Configuration file {self.configPath} not found. Creating a new one."
            )
            self.config = {}
            self._saveConfig()

    def _saveConfig(self) -> None:
        """
        Save the configuration to the JSON file.
        """
        with open(self.configPath, "w") as file:
            json.dump(self.config, file, indent=4)

        self._loadConfig()

    def createProject(
        self,
        p_projectName: str,
        p_active: bool,
        p_image8Gb: Optional[str] = None,
        p_image16Gb: Optional[str] = None,
        p_image32Gb: Optional[str] = None,
        p_cmStatusGpioLed: Optional[int] = None,
        p_cmStatusGpioLedOnSuccess: Optional[bool] = None,
        p_progressLed: Optional[str] = None,
        p_progressLedDrivenLow: Optional[bool] = None,
        p_errorLed: Optional[str] = None,
        p_errorLedDrivenLow: Optional[bool] = None,
        p_eeprom: Optional[str] = None,
    ) -> bool:
        """
        Create a new project.

        :param p_projectName: The project name
        :type p_projectName: str
        :param p_active: The project status
        :type p_active: bool
        :param p_image8Gb: The image for 8Gb
        :type p_image8Gb: str
        :param p_image16Gb: The image for 16Gb
        :type p_image16Gb: str
        :param p_image32Gb: The image for 32Gb
        :type p_image32Gb: str
        :param p_cmStatusGpioLed: The status LED
        :type p_cmStatusGpioLed: int
        :param p_cmStatusGpioLedOnSuccess: The status LED on success
        :type p_cmStatusGpioLedOnSuccess: bool
        :param p_progressLed: The progress LED name visible in /sys/class/leds
        :type p_progressLed: str
        :param p_progressLedDrivenLow: Whether the progress LED is driven low (True) or high (False)
        :type p_progressLedDrivenLow: bool
        :param p_errorLed: The error LED name visible in /sys/class/leds
        :type p_errorLed: str
        :param p_errorLedDrivenLow: Whether the error LED is driven low (True) or high (False)
        :type p_errorLedDrivenLow: bool
        :param p_eeprom: The EEPROM
        :type p_eeprom: str


        :return: The status
        :rtype: bool
        """
        status = False

        statusLed = p_cmStatusGpioLed
        if p_cmStatusGpioLed is None:
            statusLed = -1

        statusLedOnOnsuccess = p_cmStatusGpioLedOnSuccess
        if p_cmStatusGpioLedOnSuccess is None:
            statusLedOnOnsuccess = False

        eeprom = p_eeprom
        if p_eeprom is None:
            eeprom = ""

        try:
            # if p_active == "True", all other project statuses are set to False
            if p_active == True:
                for project in self.config:
                    self.config[project]["active"] = False

            self.config[p_projectName] = {
                "active": p_active,
                "image8Gb": p_image8Gb,
                "image16Gb": p_image16Gb,
                "image32Gb": p_image32Gb,
                "cmStatusGpioLed": statusLed,
                "cmStatusGpioLedOnSuccess": statusLedOnOnsuccess,
                "progressLed": p_progressLed,
                "progressLedDrivenLow": p_progressLedDrivenLow,
                "errorLed": p_errorLed,
                "errorLedDrivenLow": p_errorLedDrivenLow,
                "eeprom": eeprom,
            }
            self._saveConfig()
            status = True
        except Exception as e:
            e = e
            pass

        return status

    def deleteProject(self, p_projectName: str) -> bool:
        """
        Delete a project.

        :param p_projectName: The project name
        :type p_projectName: str

        :return: The status
        :rtype: bool
        """
        status = False
        try:
            self.config.pop(p_projectName)
            self._saveConfig()
            status = True
        except Exception as e:
            e = e
            pass

        return status

    def getProject(self, p_projectName: str) -> tuple[bool, dict[str, dict[str, Any]]]:
        """
        Get a project.

        :param p_projectName: The project name
        :type p_projectName: str

        :return: The project
        :rtype: dict
        """
        status = False
        try:
            status = True
            return status, self.config[p_projectName]
        except KeyError as e:
            e = e
            pass

        return status, {}

    def getProjects(self) -> tuple[bool, dict[str, dict[str, Any]]]:
        """
        Get all projects.

        :return: The projects
        :rtype: tuple[bool, dict]
        """
        status = False
        try:
            status = True
            return status, self.config
        except Exception as e:
            e = e
            pass

        return status, {}

    def setActiveProject(self, p_projectName: str) -> bool:
        """
        Set the active project.

        :param p_projectName: The project name
        :type p_projectName: str

        :return: The status
        :rtype: bool
        """
        status = False
        try:
            for project in self.config:
                self.config[project]["active"] = False

            self.config[p_projectName]["active"] = True
            self._saveConfig()
            status = True
        except Exception as e:
            e = e
            pass

        return status

    def getActiveProject(self) -> tuple[bool, dict[str, dict[str, Any]]]:
        """
        Get the active project.

        :return: The active project
        :rtype: tuple[bool, dict]
        """
        status = False
        try:
            for project in self.config:
                if self.config[project]["active"]:
                    status = True
                    return status, self.config[project]
        except Exception as e:
            e = e
            pass

        return status, {}

    def getActiveProjectName(self) -> tuple[bool, str]:
        """
        Get the active project name.

        :return: The active project name
        :rtype: tuple[bool, str]
        """
        self._loadConfig()
        status = False
        try:
            for projectName in self.config:
                if self.config[projectName]["active"]:
                    status = True
                    return status, projectName
        except Exception as e:
            e = e
            pass

        return status, ""

    def getImagesFromProject(self, p_projectName: str) -> tuple[bool, str, str, str]:
        """
        Get the image from a project.

        :param p_projectName: The project name
        :type p_projectName: str

        :return: The image
        :rtype: tuple[bool, str]
        """
        status = False
        try:
            status = True
            return (
                status,
                self.config[p_projectName]["image8Gb"],
                (
                    self.config[p_projectName]["image16Gb"]
                    if self.config[p_projectName].get("image16Gb")
                    else self.config[p_projectName]["image8Gb"]
                ),
                (
                    self.config[p_projectName]["image32Gb"]
                    if self.config[p_projectName].get("image32Gb")
                    else self.config[p_projectName]["image8Gb"]
                ),
            )
        except KeyError as e:
            e = e
            pass

        return status, "", "", ""
