#!/usr/bin/env python3

import json


class ResultManager:
    resultPath: str = "/app/results/downloadResult.json"
    results: dict

    def __init__(self) -> None:
        """
        Constructor
        """
        self._loadResult()

    def _loadResult(self):
        """
        Load the result from the JSON file.
        """
        try:
            with open(self.resultPath, "r") as file:
                self.results = json.load(file)
        except FileNotFoundError as e:
            print(f"Error: {e}")
            self.results = {}
            self._saveResult()

    def _saveResult(self) -> None:
        """
        Save the result to the JSON file.
        """
        with open(self.resultPath, "w") as file:
            json.dump(self.results, file, indent=4)

        self._loadResult()

    def addResult(self, p_serial: str, p_info: dict) -> None:
        """
        Add a result to the results dictionary.

        :param p_serial: The serial number
        :type p_serial: str
        :param p_info: The information to add
        :type p_info: dict
        """
        self._loadResult()
        # check if the serial number is already in the results
        if p_serial in self.results:
            # add the new information to the existing information
            self.results[p_serial].update(p_info)
        else:
            # add the new information to the results
            self.results[p_serial] = p_info
        self._saveResult()

    def modifyResult(self, p_serial: str, p_timestamp: str, p_info: dict) -> None:
        """
        Modify a result in the results dictionary.

        :param p_serial: The serial number
        :type p_serial: str
        :param p_timestamp: The timestamp
        :type p_timestamp: str
        :param p_info: The information to modify
        :type p_info: dict
        """
        self._loadResult()
        try:
            if p_serial in self.results and p_timestamp in self.results[p_serial]:
                # Merge the updated values into the existing structure

                self.results[p_serial][p_timestamp] = p_info
                self._saveResult()

            else:
                raise KeyError(
                    f"Timestamp '{p_timestamp}' not found for serial '{p_serial}'"
                )
        except Exception as e:
            print(f"Error in modifyResult: {e}")

    def getResult(self, p_serial: str, p_timestamp: str) -> dict:
        """
        Get the result for the serial number.

        :param p_serial: The serial number
        :type p_serial: str

        :return: The result
        :rtype: dict
        """
        self._loadResult()
        try:
            if p_serial in self.results:
                if p_timestamp in self.results[p_serial]:
                    return self.results[p_serial][p_timestamp]
                else:
                    return {"error": "Timestamp not found"}
            else:
                return {"error": "Serial number not found"}
        except Exception as e:
            print(f"Error in getResult: {e}")
            return {"error": "Error in getResult"}

    def getResultsBySerial(self, p_serial: str) -> dict:
        """
        Get all the results for the serial number.

        :param p_serial: The serial number
        :type p_serial: str

        :return: The results
        :rtype: dict
        """
        self._loadResult()
        try:
            if p_serial in self.results:
                return self.results[p_serial]
            else:
                return {"error": "Serial number not found"}
        except Exception as e:
            print(f"Error in getResultsBySerial: {e}")
            return {"error": "Error in getResultsBySerial"}

    def getResults(self) -> dict:
        """
        Get all the results.

        :return: The results
        :rtype: dict
        """
        self._loadResult()

        return self.results
