#!/usr/bin/env python3

from fastapi import FastAPI, UploadFile, Form, HTTPException, Query, File
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from starlette.responses import FileResponse, JSONResponse
import hashlib
import os
import asyncio
from collections import defaultdict
from datetime import datetime
from projectManager import ProjectManager
from resultManager import ResultManager
from typing import Optional
import logging
from boardType import BoardType
from scriptGenerator import generateCm4Script
from scriptGenerator import generateCm5Script

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(message)s",
    handlers=[logging.StreamHandler()],
)


class HttpServer:
    serverIp: str
    serverPort: int
    imageName: str
    eeprom: str
    cmStatusLed: str
    cmStatusLedOnOnsuccess: str
    cmProgressLed: str
    cmProgressLedDrivenLow: bool
    cmErrorLed: str
    cmErrorLedDrivenLow: bool
    activeWebsockets: list

    def __init__(
        self,
    ) -> None:
        """
        Initialize the FastAPI application.
        """
        self.serverIp = ""
        self.cmStatusLed = "NONE"
        self.cmStatusLedOnOnsuccess = "0"
        self.app = FastAPI(title="CM Provision Server", version="1.0.0")
        self.projectManager = ProjectManager()
        self.resultManager = ResultManager()
        self.imageName = ""
        self.eeprom = ""
        self.activeWebsockets = []

        self.setupRoutes()

    def setupRoutes(self):
        """
        Define the routes for the FastAPI application.
        """

        # Http routes
        @self.app.get(
            "/scriptexecute", response_class=PlainTextResponse, tags=["CM Request"]
        )
        async def cm_request_send_download_script(
            serial: str,
            model: str,
            storagesize: int,
            mac: str,
            inversejumper: str,
            memorysize: int,
            temp: str,
            cid: str,
            csd: str,
            bootmode: int,
        ):
            """
            Handles GET requests from the Raspberry CM to download the script.
            The script is generated based on the request parameters.
            The script is sent to the Raspberry CM
            """
            # Get the active image name
            self._getImageActiveNameAndCmStatusLed(storagesize)

            # Create a provision info dictionary
            startTime = datetime.now()
            startTimeStr = str(startTime.strftime("%Y%m%d_%H:%M:%S"))
            _, activeProjectName = self.projectManager.getActiveProjectName()
            provisionInfo = {}
            provisionInfo[startTimeStr] = {
                "cmInfo": {
                    "model": model,
                    "storagesize": storagesize,
                    "mac": mac,
                    "inversejumper": inversejumper,
                    "memorysize": memorysize,
                    "temp": temp,
                    "cid": cid,
                    "csd": csd,
                    "bootmode": bootmode,
                    "eeprom": "",
                    "eeepromsha": "",
                },
                "cmProvisionInfo": {
                    "projectName": activeProjectName,
                    "image": self.imageName,
                    "eeprom": self.eeprom,
                    "starTime": str(startTime),
                    "endTime": "",
                    "duration": "",
                    "state": "started",
                    "result": False,
                    "errorLog": "",
                },
            }

            # Live update the WebSocket clients
            wsDict = defaultdict(dict)
            wsDict[serial] = provisionInfo
            await self._publishToWebsockets(wsDict)

            # store
            self.resultManager.addResult(serial, provisionInfo)

            # Generate a response script based on the request parameters
            logging.info(
                f"Generating script for serial: {serial}, model: {model}, storagesize: {((storagesize * 512) / (1024 * 1024 * 1024)):.1f} GB"
            )
            if "Compute Module 4" in model:
                script = self._generateCmScript(serial, startTimeStr, BoardType.CM4)
            elif "Compute Module 5" in model:
                script = self._generateCmScript(serial, startTimeStr, BoardType.CM5)

            return PlainTextResponse(content=script, media_type="text/plain")

        @self.app.post("/scriptexecute/eeprom-version", tags=["CM Request"])
        async def cm_request_upload_eeprom_version(
            serial: str = Query(..., description="Device serial number"),
            eeprom_version: UploadFile = File(..., description="EEPROM version file"),
            eepromsha: str = Query(..., description="EEPROM SHA256 checksum"),
            start: str = Query(..., description="Start time"),
        ):
            """
            Handle the upload of the EEPROM version file.

            :param serial: The device serial number
            :param eeprom_version: The uploaded EEPROM version file
            :param start: The start time of the operation

            :return: A JSON response
            """
            # Ensure the directory for logs exists
            log_dir = "/logs/eeprom_versions"
            os.makedirs(log_dir, exist_ok=True)

            # Save the uploaded EEPROM version file
            file_path = os.path.join(log_dir, f"{serial}_eeprom_version.txt")
            try:
                file_content = await eeprom_version.read()

                # Decode the file content to text
                decoded_content = file_content.decode("utf-8")

                # Save the content to a file
                with open(file_path, "w") as f:
                    f.write(decoded_content)

                currentProvision = self.resultManager.getResult(serial, start)
                if currentProvision:
                    currentProvision["cmInfo"]["eeprom"] = str(decoded_content).replace(
                        "\n", ","
                    )
                    currentProvision["cmInfo"]["eeepromsha"] = eepromsha
                    # Save the modified result
                    self.resultManager.modifyResult(serial, start, currentProvision)

                    # Live update the WebSocket clients
                    wsDict = defaultdict(dict)
                    wsDict[serial][start] = currentProvision
                    await self._publishToWebsockets(wsDict)

            except UnicodeDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="The file content could not be decoded as UTF-8 text.",
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error saving file: {e}")

            return JSONResponse(
                content={
                    "message": "EEPROM version file uploaded successfully",
                    "serial": serial,
                    "file_path": file_path,
                }
            )

        @self.app.post("/scriptexecute/error", tags=["CM Request"])
        async def cm_request_upload_error(
            log: UploadFile = File(...),
            serial: str = Query(...),
            retcode: int = Query(...),
            phase: str = Query(...),
            start: str = Query(...),
        ):
            """
            Handle log file uploads and related query parameters.

            :param log: The uploaded log file.
            :param serial: The device serial number.
            :param retcode: The return code of the previous operation.
            :param phase: The phase of the operation.
            :param start: The start time of the operation.
            """
            # Construct the path to save the log file
            log_dir = "/logs"
            os.makedirs(log_dir, exist_ok=True)  # Ensure the logs directory exists
            log_path = os.path.join(log_dir, f"{serial}_{phase}.log")

            # Save the uploaded log file
            with open(log_path, "wb") as f:
                file_content = await log.read()
                f.write(file_content)

                currentTime = datetime.now()
                currentProvision = self.resultManager.getResult(serial, start)
                if currentProvision:
                    # Parse `starTime` from ISO 8601-like string to datetime
                    start_time_str = currentProvision["cmProvisionInfo"]["starTime"]
                    start_time = datetime.fromisoformat(start_time_str)

                    # Calculate duration
                    currentProvision["cmProvisionInfo"][
                        "endTime"
                    ] = currentTime.isoformat()
                    currentProvision["cmProvisionInfo"]["duration"] = str(
                        currentTime - start_time
                    )
                    currentProvision["cmProvisionInfo"]["state"] = "completed"
                    currentProvision["cmProvisionInfo"]["errorLog"] = str(file_content)

                    # Save the modified result
                    self.resultManager.modifyResult(serial, start, currentProvision)

                    # Live update the WebSocket clients
                    wsDict = defaultdict(dict)
                    wsDict[serial][start] = currentProvision
                    await self._publishToWebsockets(wsDict)

            # Return a success response
            return JSONResponse(
                content={
                    "message": "Log file uploaded successfully",
                    "serial": serial,
                    "retcode": retcode,
                    "phase": phase,
                    "log_path": log_path,
                }
            )

        @self.app.get("/scriptexecute/alldone", tags=["CM Request"])
        async def cm_request_provisioning_done(
            serial: str,
            alldone: int,
            temp: str,
            verify: str = "",
            start: str = "",
        ):
            """
            Handle the 'all done' request from the Raspberry CM.

            :param serial: The device serial number
            :param alldone: The provisioning status
            :param temp: The temperature of the device
            :param verify: The verification status
            :param start: The start time of the operation
            """
            currentTime = datetime.now()
            currentProvision = self.resultManager.getResult(serial, start)
            if currentProvision:
                # Parse `starTime` from ISO 8601-like string to datetime
                start_time_str = currentProvision["cmProvisionInfo"]["starTime"]
                start_time = datetime.fromisoformat(start_time_str)

                # Calculate duration
                currentProvision["cmProvisionInfo"]["endTime"] = currentTime.isoformat()
                currentProvision["cmProvisionInfo"]["duration"] = str(
                    currentTime - start_time
                )
                currentProvision["cmProvisionInfo"]["state"] = "completed"
                currentProvision["cmProvisionInfo"]["result"] = True
                # Save the modified result
                self.resultManager.modifyResult(serial, start, currentProvision)

                # Live update the WebSocket clients
                wsDict = defaultdict(dict)
                wsDict[serial][start] = currentProvision
                await self._publishToWebsockets(wsDict)

            return {
                "message": "All done request handled successfully",
                "serial": serial,
                "alldone": alldone,
                "temp": temp,
                "verify": verify,
            }

        @self.app.get("/downloadimage/{filename}", tags=["CM Request"])
        async def cm_request_server_the_image(filename: str):
            """
            Serve the requested image file.

            :param filename: The name of the file to serve.
            """
            # Construct the full path to the file
            file_path = f"/uploads/{filename}"

            # Check if the file exists
            if not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail="File not found")

            # Return the file using FileResponse
            return FileResponse(
                file_path,
                media_type="application/octet-stream",
                filename=filename,
            )

        @self.app.get("/downloadeeprom/{filename}", tags=["CM Request"])
        async def cm_request_server_the_eeprom(filename: str):
            """
            Serve the requested EEPROM file.

            :param filename: The name of the file to serve.
            """
            # Construct the full path to the file
            file_path = f"/eeproms/{filename}"

            # Check if the file exists
            if not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail="File not found")

            # Return the file using FileResponse
            return FileResponse(
                file_path,
                media_type="application/octet-stream",
                filename=filename,
            )

        @self.app.post("/image/upload-image", tags=["Image Management"])
        async def upload_image(image: UploadFile, sha256sum: str = Form(...)):
            """
            Upload an image with its SHA256 checksum for validation.

            :param image: The binary file being uploaded
            :param sha256sum: The expected SHA256 checksum of the file
            """
            # Check if imaage already exists
            if os.path.exists(f"/uploads/{image.filename}"):
                raise HTTPException(
                    status_code=400, detail=f"Image '{image.filename}' already exists"
                )
            # Read the file's content
            fileContent = await image.read()

            # Compute the SHA256 checksum of the uploaded file
            computedSha256sum = hashlib.sha256(fileContent).hexdigest()

            # Verify the checksum
            if computedSha256sum != sha256sum:
                raise HTTPException(status_code=400, detail="SHA256 checksum mismatch")

            # save the checksum
            with open(f"/uploads/{image.filename}.sha256sum", "w") as f:
                f.write(sha256sum)

            # Save the file (optional, update the path as needed)
            with open(f"/uploads/{image.filename}", "wb") as f:
                f.write(fileContent)

            return JSONResponse(
                content={
                    "filename": image.filename,
                    "sha256sum": computedSha256sum,
                    "message": "File uploaded and verified successfully",
                }
            )

        @self.app.get("/image/list-images", tags=["Image Management"])
        async def list_all_images():
            """
            List all uploaded images.
            """
            # List all files in the uploads directory
            files = os.listdir("/uploads")
            imageList = {}
            for file in files:
                # Read the SHA256 checksum of the file
                if file.endswith(".sha256sum"):
                    with open(f"/uploads/{file}", "r") as f:
                        sha256sum = f.read()
                        imageList[file.replace(".sha256sum", "")] = {
                            "upload": datetime.fromtimestamp(
                                os.path.getmtime(f"/uploads/{file}")
                            ).strftime("%Y-%m-%d_%H:%M:%S"),
                            "sha256sum": sha256sum,
                        }

            return JSONResponse(content={"images": imageList})

        @self.app.get("/image/download-image", tags=["Image Management"])
        async def download_image(image: str):
            """
            Download an image.

            :param image: The name of the image file to download.
            """
            # Construct the full file path
            file_path = f"/uploads/{image}"

            # Check if the image exists
            if not os.path.exists(file_path):
                raise HTTPException(
                    status_code=404, detail=f"Image '{image}' not found"
                )

            # Return the file using FileResponse
            return FileResponse(
                file_path, media_type="application/octet-stream", filename=image
            )

        @self.app.delete("/image/delete-image", tags=["Image Management"])
        async def delete_image(image: str):
            """
            Delete an image.

            :param image: The name of the image file to delete.
            """
            # Construct the full file path
            file_path = f"/uploads/{image}"

            # Check if the image exists
            if not os.path.exists(file_path):
                raise HTTPException(
                    status_code=404, detail=f"Image '{image}' not found"
                )

            # Delete the file
            os.remove(file_path)
            os.remove(f"{file_path}.sha256sum")

            return JSONResponse(
                content={"message": f"Image '{image}' deleted successfully"}
            )

        @self.app.post("/eeprom/upload-eeprom", tags=["Eeprom Management"])
        async def upload_eeprom(eeprom: UploadFile, sha256sum: str = Form(...)):
            """
            Upload an Eeprom file with its SHA256 checksum for validation.

            :param eeprom: The binary file being uploaded
            :param sha256sum: The expected SHA256 checksum of the file
            """
            # Check if eeprom already exists
            if os.path.exists(f"/eeproms/{eeprom.filename}"):
                raise HTTPException(
                    status_code=400, detail=f"Eeprom '{eeprom.filename}' already exists"
                )
            # Read the file's content
            fileContent = await eeprom.read()

            # Compute the SHA256 checksum of the uploaded file
            computedSha256sum = hashlib.sha256(fileContent).hexdigest()

            # Verify the checksum
            if computedSha256sum != sha256sum:
                raise HTTPException(status_code=400, detail="SHA256 checksum mismatch")

            # save the checksum
            with open(f"/eeproms/{eeprom.filename}.sha256sum", "w") as f:
                f.write(sha256sum)

            # Save the file (optional, update the path as needed)
            with open(f"/eeproms/{eeprom.filename}", "wb") as f:
                f.write(fileContent)

            return JSONResponse(
                content={
                    "filename": eeprom.filename,
                    "sha256sum": computedSha256sum,
                    "message": "File uploaded and verified successfully",
                }
            )

        @self.app.post(f"/eeprom/list-eeproms", tags=["Eeprom Management"])
        async def list_all_eeproms():
            """
            List all uploaded EEPROMs.
            """
            # List all files in the eeproms/eeprom directory
            files = os.listdir("/eeproms")
            eepromList = {}
            for file in files:
                # Read the SHA256 checksum of the file
                if file.endswith(".sha256sum"):
                    with open(f"/eeproms/{file}", "r") as f:
                        sha256sum = f.read()
                        eepromList[file.replace(".sha256sum", "")] = {
                            "upload": datetime.fromtimestamp(
                                os.path.getmtime(f"/eeproms/{file}")
                            ).strftime("%Y-%m-%d_%H:%M:%S"),
                            "sha256sum": sha256sum,
                        }

            return JSONResponse(content={"eeproms": eepromList})

        @self.app.get("/eeprom/download-eeprom", tags=["Eeprom Management"])
        async def download_eeprom(eeprom: str):
            """
            Download an EEPROM.

            :param eeprom: The name of the EEPROM file to download.
            """
            # Construct the full file path
            file_path = f"/eeproms/{eeprom}"

            # Check if the eeprom exists
            if not os.path.exists(file_path):
                raise HTTPException(
                    status_code=404, detail=f"EEPROM '{eeprom}' not found"
                )

            # Return the file using FileResponse
            return FileResponse(
                file_path, media_type="application/octet-stream", filename=eeprom
            )

        @self.app.delete("/eeprom/delete-eeprom", tags=["Eeprom Management"])
        async def delete_eeprom(eeprom: str):
            """
            Delete an EEPROM.

            :param eeprom: The name of the EEPROM file to delete.
            """
            # Construct the full file path
            file_path = f"/eeproms/{eeprom}"

            # Check if the eeprom exists
            if not os.path.exists(file_path):
                raise HTTPException(
                    status_code=404, detail=f"EEPROM '{eeprom}' not found"
                )

            # Delete the file
            os.remove(file_path)
            os.remove(f"{file_path}.sha256sum")

            return JSONResponse(
                content={"message": f"EEPROM '{eeprom}' deleted successfully"}
            )

        @self.app.post("/project/create", tags=["Project Management"])
        def create_project(
            project_name: str = Form(...),
            active: bool = Form(...),
            image8Gb: Optional[str] = Form(None),
            image16Gb: Optional[str] = Form(None),
            image32Gb: Optional[str] = Form(None),
            cm_status_led_gpio_nb: Optional[int] = Form(None),
            cm_status_led_gpio_on_onsuccess: Optional[bool] = Form(None),
            cm_progress_led: Optional[str] = Form(
                default="ACT",
                description="For cm5 only, name visible in /sys/class/leds, default ACT (green). The led will blink during fw upgrade, then switch off.",
            ),
            cm_progress_led_driven_low: Optional[bool] = Form(
                default=False,
                description="For cm5 only, whether the progress led is driven low (True) or high (False), default False. This is used to set the correct state of the led during provisioning.",
            ),
            cm_error_led: Optional[str] = Form(
                default="PWR",
                description="For cm5 only, name visible in /sys/class/leds, default PWR (red). The led will blink if an error occurs during provisioning, else stay off.",
            ),
            cm_error_led_driven_low: Optional[bool] = Form(
                default=False,
                description="For cm5 only, whether the error led is driven low (True) or high (False), default False. This is used to set the correct state of the led during provisioning.",
            ),
            eeprom: Optional[str] = Form(None),
        ):
            """
            Create a new project.

            :param project_name: The project name
            :param status: The project status (active or inactive)
            :param image8Gb: The project image for 8GB storage
            :param cm_status_led: The CM status LED
            :param cm_progress_led: The CM progress LED
            :param cm_error_led: The CM error LED
            """

            statusLed = cm_status_led_gpio_nb
            if cm_status_led_gpio_nb is None:
                statusLed = -1

            statusLedOnOnsuccess = cm_status_led_gpio_on_onsuccess
            if cm_status_led_gpio_on_onsuccess is None:
                statusLedOnOnsuccess = False

            # check if project exists
            _, projects = self.projectManager.getProjects()
            if project_name in projects:
                raise HTTPException(
                    status_code=400,
                    detail=f"Project '{project_name}' already exists",
                )

            active = self.projectManager.createProject(
                p_projectName=project_name,
                p_active=active,
                p_image8Gb=image8Gb,
                p_image16Gb=image16Gb,
                p_image32Gb=image32Gb,
                p_cmStatusGpioLed=statusLed,
                p_cmStatusGpioLedOnSuccess=statusLedOnOnsuccess,
                p_progressLed=cm_progress_led,
                p_progressLedDrivenLow=cm_progress_led_driven_low,
                p_errorLed=cm_error_led,
                p_errorLedDrivenLow=cm_error_led_driven_low,
                p_eeprom=eeprom,
            )
            if active:
                return JSONResponse(
                    content={
                        "message": f"Project '{project_name}' created successfully"
                    }
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error creating project '{project_name}'",
                )

        @self.app.get("/project/getbyname", tags=["Project Management"])
        def get_project_by_name(project_name: str = Query(...)):
            """
            Get a project by name.

            :param project_name: The project name
            """
            status, project = self.projectManager.getProject(project_name)
            if status:
                return JSONResponse(content=project)
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f'Project "{project_name}" not found',
                )

        @self.app.get("/project/list", tags=["Project Management"])
        def list_projects():
            """
            List all projects.
            """
            status, projects = self.projectManager.getProjects()
            if status:
                return JSONResponse(content=projects)
            else:
                raise HTTPException(status_code=500, detail="Error listing projects")

        @self.app.post("/project/setactive", tags=["Project Management"])
        def set_active_project(project_name: str = Form(...)):
            """
            Set the active project.

            :param project_name: The project name
            """
            status = self.projectManager.setActiveProject(project_name)
            if status:
                return JSONResponse(
                    content={"message": f"Project '{project_name}' set as active"}
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error setting project '{project_name}' as active",
                )

        @self.app.get("/project/getactiveprojectname", tags=["Project Management"])
        def get_active_project_name():
            """
            Get the active project name.
            """
            status, name = self.projectManager.getActiveProjectName()
            if status:
                return JSONResponse(content=name)
            else:
                raise HTTPException(status_code=404, detail="No active project found")

        @self.app.get("/project/getactive", tags=["Project Management"])
        def get_active_project():
            """
            Get the active project.
            """
            status, project = self.projectManager.getActiveProject()
            if status:
                return JSONResponse(content=project)
            else:
                raise HTTPException(status_code=404, detail="No active project found")

        @self.app.get("/project/getimagefromproject", tags=["Project Management"])
        def get_image_from_project(project_name: str = Query(...)):
            """
            Get the image associated with a project.

            :param project_name: The project name
            """
            status, imageName8Gb, imageName16Gb, imageName32Gb = (
                self.projectManager.getImagesFromProject(project_name)
            )
            if status:
                return JSONResponse(
                    content={
                        "8Gb": imageName8Gb,
                        "16Gb": imageName16Gb,
                        "32Gb": imageName32Gb,
                    }
                )
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f'Error getting image for project "{project_name}"',
                )

        @self.app.delete("/project/delete", tags=["Project Management"])
        def delete_project(project_name: str = Query(...)):
            """
            Delete a project.

            :param project_name: The project name
            """
            status = self.projectManager.deleteProject(project_name)
            if status:
                return JSONResponse(
                    content={
                        "message": f"Project '{project_name}' deleted successfully"
                    }
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error deleting project '{project_name}'",
                )

        @self.app.get("/result/getresult", tags=["Result Management"])
        def get_result_by_serial_and_timestamp(
            serial: str = Query(...), timestamp: str = Query(...)
        ):
            """
            Get the result for a serial number and timestamp.

            :param serial: The serial number
            :param timestamp: The timestamp
            """
            result = self.resultManager.getResult(serial, timestamp)
            if result:
                return JSONResponse(content=result)
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Result not found for serial '{serial}' and timestamp '{timestamp}'",
                )

        @self.app.get("/result/getresultsbyserial", tags=["Result Management"])
        def get_results_by_serial(serial: str = Query(...)):
            """
            Get all results for a serial number.

            :param serial: The serial number
            """
            results = self.resultManager.getResultsBySerial(serial)
            if results:
                return JSONResponse(content=results)
            else:
                raise HTTPException(
                    status_code=404, detail=f"Results not found for serial '{serial}'"
                )

        @self.app.get("/result/getresults", tags=["Result Management"])
        def get_all_results():
            """
            Get all results.
            """
            results = self.resultManager.getResults()
            if results:
                return JSONResponse(content=results)
            else:
                raise HTTPException(status_code=404, detail="Results not found")

        # WebSocket routes
        @self.app.websocket("/")
        async def websocket_endpoint(websocket: WebSocket):
            """
            Handle WebSocket connections.
            """
            await websocket.accept()
            self.activeWebsockets.append(websocket)
            try:
                while True:
                    # Keep the connection alive by receiving messages
                    await websocket.receive_text()
            except WebSocketDisconnect:
                self.activeWebsockets.remove(websocket)

    def setServerIp(self, p_ip: str) -> None:
        """
        Set the server IP address.

        :param p_ip: The server IP address
        :type p_ip: str
        """
        self.serverIp = p_ip

    def setServerPort(self, p_port: int) -> None:
        """
        Set the server port.

        :param p_port: The server port
        :type p_port: int
        """
        self.serverPort = p_port

    def _generateCmScript(
        self, p_serial: str, p_startTime: str, p_boardType: BoardType
    ) -> str:
        """
        Generate the CM4 script.

        :param p_serial: The serial number
        :type p_serial: str
        :param p_startTime: The start time
        :type p_startTime: str

        :return: The generated script
        :rtype: str
        """
        if p_boardType == BoardType.CM4:
            return generateCm4Script(
                p_serial,
                p_startTime,
                self.serverIp,
                str(self.serverPort),
                self.imageName,
                self.eeprom,
                self.cmStatusLed,
                self.cmStatusLedOnOnsuccess,
            )
        elif p_boardType == BoardType.CM5:
            return generateCm5Script(
                p_serial=p_serial,
                p_startTime=p_startTime,
                p_serverIp=self.serverIp,
                p_serverPort=str(self.serverPort),
                p_imageName=self.imageName,
                p_eeprom=self.eeprom,
                p_cmProgressLed=self.cmProgressLed,
                p_cmProgressLedDrivenLow=self.cmProgressLedDrivenLow,
                p_cmErrorLed=self.cmErrorLed,
                p_cmErrorLedDrivenLow=self.cmErrorLedDrivenLow,
            )
        else:
            raise ValueError("Invalid board type")

    def _getImageActiveNameAndCmStatusLed(
        self, p_targetFlashSize: Optional[int] = None
    ) -> None:
        """
        Get the image name of the active project.
        """
        targetFlashSize = 7
        if p_targetFlashSize is not None:
            targetFlashSize: float = float(p_targetFlashSize)
            targetFlashSize = (targetFlashSize * 512) / (1024 * 1024 * 1024)

        self.imageName = ""
        status, name = self.projectManager.getActiveProjectName()
        if status:
            status, imageName8Gb, imageName16Gb, imageName32Gb = (
                self.projectManager.getImagesFromProject(name)
            )
            if status:
                if targetFlashSize <= 8:
                    logging.info(f"8Gb selected, image: {imageName8Gb}")
                    self.imageName = imageName8Gb
                elif targetFlashSize > 8 and targetFlashSize <= 16:
                    logging.info(f"16Gb selected, image: {imageName16Gb}")
                    self.imageName = imageName16Gb
                else:
                    logging.info(f"32Gb selected, image: {imageName32Gb}")
                    self.imageName = imageName32Gb

            status, project = self.projectManager.getProject(name)
            if status:
                if int(project["cmStatusGpioLed"]) != -1:
                    self.cmStatusLed = str((project["cmStatusGpioLed"]))
                if project["cmStatusGpioLedOnSuccess"]:
                    self.cmStatusLedOnOnsuccess = "1"
                else:
                    self.cmStatusLedOnOnsuccess = "0"
                if project["eeprom"] != "":
                    self.eeprom = project["eeprom"]

                self.cmProgressLed = project.get("progressLed", "ACT")
                self.cmProgressLedDrivenLow = project.get("progressLedDrivenLow", False)
                self.cmErrorLed = project.get("errorLed", "PWR")
                self.cmErrorLedDrivenLow = project.get("errorLedDrivenLow", False)

    async def _publishToWebsockets(self, data: dict):
        """
        Publish data to all connected WebSocket clients.

        :param data: The data to send
        :type data: dict
        """

        async def send_to_websocket(websocket):
            try:
                await websocket.send_json(data)  # Await the coroutine
            except Exception as e:
                logging.error(f"Error sending data to WebSocket client: {e}")
                self.activeWebsockets.remove(websocket)

        # Create a list of coroutines for all active websockets
        tasks = [send_to_websocket(ws) for ws in self.activeWebsockets]

        # Run all tasks concurrently
        await asyncio.gather(*tasks)  # Await the gathered tasks directly


# Create an instance of the HttpServer class for use
http_server = HttpServer()
app = http_server.app
