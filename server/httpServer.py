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


class HttpServer:
    serverIp: str
    imageName: str
    cmStatusLed: str
    activeWebsockets: list

    def __init__(
        self,
    ) -> None:
        """
        Initialize the FastAPI application.
        """
        self.serverIp = ""
        self.cmStatusLed = "NONE"
        self.app = FastAPI(title="CM Provision Server", version="1.0.0")
        self.projectManager = ProjectManager()
        self.resultManager = ResultManager()
        self.imageName = ""
        self._getImageActiveNameAndCmStatusLed()
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
            self._getImageActiveNameAndCmStatusLed()

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
                },
                "cmProvisionInfo": {
                    "projectName": activeProjectName,
                    "image": self.imageName,
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
            script = self._generateCm4Script(serial, startTimeStr)

            return PlainTextResponse(content=script, media_type="text/plain")

        @self.app.post("/scriptexecute/eeprom-version", tags=["CM Request"])
        async def cm_request_upload_eeprom_version(
            serial: str = Query(..., description="Device serial number"),
            eeprom_version: UploadFile = File(..., description="EEPROM version file"),
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

        @self.app.get("/uploads/{filename}", tags=["CM Request"])
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

        @self.app.post("/project/create", tags=["Project Management"])
        def create_project(
            project_name: str = Form(...),
            active: bool = Form(...),
            image: str = Form(...),
            cm_status_led: Optional[int] = Form(None),
        ):
            """
            Create a new project.

            :param project_name: The project name
            :param status: The project status (active or inactive)
            :param image: The project image
            :param cm_status_led: The CM status LED
            """
            statusLed = cm_status_led
            if cm_status_led is None:
                statusLed = -1
            # check if image exists
            if not os.path.exists(f"/uploads/{image}"):
                raise HTTPException(
                    status_code=404, detail=f"Image '{image}' not found"
                )

            # check if project exists
            _, projects = self.projectManager.getProjects()
            if project_name in projects:
                raise HTTPException(
                    status_code=400,
                    detail=f"Project '{project_name}' already exists",
                )

            active = self.projectManager.createProject(
                project_name, active, image, statusLed
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

        @self.app.get("/project/getimagefromproject", tags=["Project Management"])
        def get_image_from_project(project_name: str = Query(...)):
            """
            Get the image associated with a project.

            :param project_name: The project name
            """
            status, imageName = self.projectManager.getImageFromProject(project_name)
            if status:
                return JSONResponse(content=imageName)
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

    def _generateCm4Script(self, p_serial: str, p_startTime: str) -> str:
        """
        Generate the CM4 script.

        :param p_serial: The serial number
        :type p_serial: str
        :param p_startTime: The start time
        :type p_startTime: str

        :return: The generated script
        :rtype: str
        """
        script = f"""#!/bin/sh
#!/bin/sh
set -o pipefail

export SERIAL="{p_serial}"
export SERVER="{self.serverIp}"
export IMAGE="{self.imageName}"
export STATUS_LED="{self.cmStatusLed}"
export STARTTIME="{p_startTime}"
export STORAGE="/dev/mmcblk0"
export PART1="/dev/mmcblk0p1"
export PART2="/dev/mmcblk0p2"
export ALLDONE="0"



if [ "$STATUS_LED" != "NONE" ]; then
    # Export the STATUS_LED (makes it available in /sys/class/gpio)
    if [ ! -d "/sys/class/gpio/gpio$STATUS_LED" ]; then
        echo $STATUS_LED > /sys/class/gpio/export
    fi

    # Set the direction to "out"
    echo "out" > /sys/class/gpio/gpio$STATUS_LED/direction

    # Function for blinking
    blink() {{
        while true; do
            # Turn STATUS_LED on (high)
            echo "1" > /sys/class/gpio/gpio$STATUS_LED/value
            sleep 0.1

            # Turn STATUS_LED off (low)
            echo "0" > /sys/class/gpio/gpio$STATUS_LED/value
            sleep 0.1
        done
    }}

    # Start the blink function in the background
    blink &

    # Save the process ID of the background task
    BLINK_PID=$!

    echo "Blinking started. PID: $BLINK_PID"
    echo "Run 'kill $BLINK_PID' to stop blinking."
fi

# Make sure we have random entropy
echo "OM7WfoL5UW24E1cO2B66wuMvZVVAn2yoiZI2bX1ydJqEhPXibBBhZuRFtJWrRKuR" >/dev/urandom

echo Querying and registering EEPROM version
vcgencmd bootloader_version >/tmp/eeprom_version || true
if [ -f /tmp/eeprom_version ]; then
    curl --retry 10 -g -F 'eeprom_version=@/tmp/eeprom_version' "http://${{SERVER}}/scriptexecute/eeprom-version?serial=${{SERIAL}}&start=${{STARTTIME}}"
fi

echo Sending BLKDISCARD to $STORAGE
blkdiscard -v $STORAGE || true

echo Writing image from http://${{SERVER}}/uploads/${{IMAGE}} to $STORAGE
curl --retry 10 -g "http://${{SERVER}}/uploads/${{IMAGE}}" \
 | xz -dc  \
 | dd of=$STORAGE conv=fsync obs=1M >/tmp/dd.log 2>&1
RETCODE=$?
if [ $RETCODE -eq 0 ]; then
    echo Original image written successfully
    ALLDONE="1"
    if [ "$STATUS_LED" != "NONE" ]; then
        kill $BLINK_PID
        echo 1 > /sys/class/gpio/gpio$STATUS_LED/value
    fi
else
    echo Writing image failed.
    if [ "$STATUS_LED" != "NONE" ]; then
        kill $BLINK_PID
        echo 0 > /sys/class/gpio/gpio$STATUS_LED/value
    fi
    curl --retry 10 -g -F 'log=@/tmp/dd.log' "http://${{SERVER}}/scriptexecute/error?serial=${{SERIAL}}&retcode=$RETCODE&phase=dd&start=${{STARTTIME}}"
    exit 1
fi

partprobe $STORAGE
sleep 0.1

TEMP=vcgencmd measure_temp
curl --retry 10 -g "http://${{SERVER}}/scriptexecute/alldone?serial=${{SERIAL}}&alldone=${{ALLDONE}}&temp=${{TEMP}}&verify=&start=${{STARTTIME}}"


echo "Provisioning completed successfully!"

"""
        return script

    def _getImageActiveNameAndCmStatusLed(self):
        """
        Get the image name of the active project.
        """
        self.imageName = ""
        status, name = self.projectManager.getActiveProjectName()
        if status:
            status, imageName = self.projectManager.getImageFromProject(name)
            if status:
                self.imageName = imageName

            status, project = self.projectManager.getProject(name)
            if status:
                if int(project["cmStatusLed"]) != -1:
                    self.cmStatusLed = str((project["cmStatusLed"]))

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
                print(f"Error sending data to WebSocket client: {e}")
                self.activeWebsockets.remove(websocket)

        # Create a list of coroutines for all active websockets
        tasks = [send_to_websocket(ws) for ws in self.activeWebsockets]

        # Run all tasks concurrently
        await asyncio.gather(*tasks)  # Await the gathered tasks directly


# Create an instance of the HttpServer class for use
http_server = HttpServer()
app = http_server.app
