#!/usr/bin/env python3

import json
from typing import Optional


class ProjectManager:
    configPath: str = "/app/conf/projectConfig.json"
    config: dict
    _instance = None
    __initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)  # cls is used to create the instance
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
            print(f"Error: {e}")
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
        p_image: str,
        p_cmStatusLed: Optional[int] = None,
        p_cmStatusLedOnOnsuccess: Optional[bool] = None,
    ) -> bool:
        """
        Create a new project.

        :param p_projectName: The project name
        :type p_projectName: str
        :param p_active: The project status
        :type p_active: bool
        :param p_image: The project image
        :type p_image: str

        :return: The status
        :rtype: bool
        """
        status = False

        statusLed = p_cmStatusLed
        if p_cmStatusLed is None:
            statusLed = -1

        statusLedOnOnsuccess = p_cmStatusLedOnOnsuccess
        if p_cmStatusLedOnOnsuccess is None:
            statusLedOnOnsuccess = False

        try:
            # if p_active == "True", all other project statuses are set to False
            if p_active == True:
                for project in self.config:
                    self.config[project]["active"] = False

            self.config[p_projectName] = {
                "active": p_active,
                "image": p_image,
                "cmStatusLed": statusLed,
                "cmStatusLedOnOnsuccess": statusLedOnOnsuccess,
            }
            self._saveConfig()
            status = True
        except Exception as e:
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
            pass

        return status

    def getProject(self, p_projectName: str) -> tuple[bool, dict]:
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
            pass

        return status, {}

    def getProjects(self) -> tuple[bool, dict]:
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
            pass

        return status

    def getActiveProject(self) -> tuple[bool, dict]:
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
            pass

        return status, ""

    def getImageFromProject(self, p_projectName: str) -> tuple[bool, str]:
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
            return status, self.config[p_projectName]["image"]
        except KeyError as e:
            pass

        return status, ""
