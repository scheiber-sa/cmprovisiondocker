#!/usr/bin/env python3

from fastapi import FastAPI, UploadFile, Form, HTTPException, Query, File
from fastapi.responses import PlainTextResponse
from starlette.responses import FileResponse, JSONResponse
import hashlib
import os
from datetime import datetime
from projectManager import ProjectManager


class HttpServer:
    serverIp: str
    imageName: str
    cmStatusLed: str

    def __init__(
        self,
    ) -> None:
        """
        Initialize the FastAPI application.
        """
        self.serverIp = ""
        self.cmStatusLed = "NONE"
        self.app = FastAPI(title="CM Provision Server")
        self.projectManager = ProjectManager()
        self.imageName = ""
        self._getImageActiveName()

        # self.imageName = self.projectManager.getActiveProjectName()
        self.setupRoutes()

    def _getImageActiveName(self):
        """
        Get the image name of the active project.
        """
        self.imageName = ""
        status, name = self.projectManager.getActiveProjectName()
        if status:
            status, imageName = self.projectManager.getImageFromProject(name)
            if status:
                self.imageName = imageName

    def setupRoutes(self):
        """
        Define the routes for the FastAPI application.
        """

        @self.app.get("/scriptexecute")
        async def handle_scriptexecute(
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
            Handles GET requests from the Raspberry Pi.
            """
            self._getImageActiveName()
            # Generate a response script based on the request parameters
            script = f"""#!/bin/sh
#!/bin/sh
set -o pipefail

export SERIAL="{serial}"
export SERVER="{self.serverIp}"
export IMAGE="{self.imageName}"
export STATUS_LED="{self.cmStatusLed}"
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
    curl --retry 10 -g -F 'eeprom_version=@/tmp/eeprom_version' "http://${{SERVER}}/scriptexecute/eeprom-version?serial=${{SERIAL}}"
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
    curl --retry 10 -g -F 'log=@/tmp/dd.log' "http://${{SERVER}}/scriptexecute/error?serial=${{SERIAL}}&retcode=$RETCODE&phase=dd"
    exit 1
fi

partprobe $STORAGE
sleep 0.1

TEMP=vcgencmd measure_temp
curl --retry 10 -g "http://${{SERVER}}/scriptexecute/alldone?serial=${{SERIAL}}&alldone=${{ALLDONE}}&temp=${{TEMP}}&verify="


echo "Provisioning completed successfully!"

"""
            return PlainTextResponse(content=script, media_type="text/plain")

        @self.app.post("/scriptexecute/eeprom-version")
        async def upload_eeprom_version(
            serial: str = Query(..., description="Device serial number"),
            eeprom_version: UploadFile = File(..., description="EEPROM version file"),
        ):
            """
            Handle the upload of the EEPROM version file.

            :param serial: The device serial number
            :param eeprom_version: The uploaded EEPROM version file
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

        @self.app.post("/scriptexecute/error")
        async def upload_log(
            log: UploadFile = File(...),
            serial: str = Query(...),
            retcode: int = Query(...),
            phase: str = Query(...),
        ):
            """
            Handle log file uploads and related query parameters.

            :param log: The uploaded log file.
            :param serial: The device serial number.
            :param retcode: The return code of the previous operation.
            :param phase: The phase of the operation.
            """
            # Construct the path to save the log file
            log_dir = "/logs"
            os.makedirs(log_dir, exist_ok=True)  # Ensure the logs directory exists
            log_path = os.path.join(log_dir, f"{serial}_{phase}.log")

            # Save the uploaded log file
            with open(log_path, "wb") as f:
                file_content = await log.read()
                f.write(file_content)

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

        @self.app.get("/scriptexecute/alldone")
        async def handle_all_done(
            serial: str,
            alldone: int,
            temp: str,
            verify: str = "",
        ):
            """
            Handle the 'all done' request at a separate route.
            """
            log_message = (
                f"Serial: {serial}, All Done: {alldone}, Temp: {temp}, Verify: {verify}"
            )
            print(log_message)

            # Save to a log file (optional)
            log_dir = "/logs"
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, f"{serial}_all_done.log")
            with open(log_path, "a") as log_file:
                log_file.write(log_message + "\n")

            return {
                "message": "All done request handled successfully",
                "serial": serial,
                "alldone": alldone,
                "temp": temp,
                "verify": verify,
            }

        @self.app.get("/uploads/{filename}")
        async def serve_file(filename: str):
            """
            Serve a file from the uploads directory.

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

        @self.app.post("/image/upload-image")
        async def upload_image(image: UploadFile, sha256sum: str = Form(...)):
            """
            Upload an image with its SHA256 checksum for validation.

            :param image: The binary file being uploaded
            :param sha256sum: The expected SHA256 checksum of the file
            """
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

        @self.app.get("/image/list-images")
        async def list_images():
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

        @self.app.get("/image/download-image")
        async def download_image(image: str):
            """
            Download an image.

            :param image: The name of the image file to download.
            """
            # Construct the full file path
            file_path = f"/uploads/{image}"

            # Check if the image exists
            if not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail="Image not found")

            # Return the file using FileResponse
            return FileResponse(
                file_path, media_type="application/octet-stream", filename=image
            )

        @self.app.get("/image/delete-image")
        async def delete_image(image: str):
            """
            Delete an image.

            :param image: The name of the image file to delete.
            """
            # Construct the full file path
            file_path = f"/uploads/{image}"

            # Check if the image exists
            if not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail="Image not found")

            # Delete the file
            os.remove(file_path)
            os.remove(f"{file_path}.sha256sum")

            return JSONResponse(
                content={"message": f'Image "{image}" deleted successfully'}
            )

        @self.app.post("/project/create")
        def create_project(
            project_name: str = Form(...),
            status: bool = Form(...),
            image: str = Form(...),
        ):
            """
            Create a new project.

            :param project_name: The project name
            :param status: The project status
            :param image: The project image
            """
            status = self.projectManager.createProject(project_name, status, image)
            if status:
                return JSONResponse(
                    content={
                        "message": f'Project "{project_name}" created successfully'
                    }
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f'Error creating project "{project_name}"',
                )

        @self.app.get("/project/delete")
        def delete_project(project_name: str = Query(...)):
            """
            Delete a project.

            :param project_name: The project name
            """
            status = self.projectManager.deleteProject(project_name)
            if status:
                return JSONResponse(
                    content={
                        "message": f'Project "{project_name}" deleted successfully'
                    }
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f'Error deleting project "{project_name}"',
                )

        @self.app.get("/project/getbyname")
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

        @self.app.get("/project/list")
        def list_projects():
            """
            List all projects.
            """
            status, projects = self.projectManager.getProjects()
            if status:
                return JSONResponse(content=projects)
            else:
                raise HTTPException(status_code=500, detail="Error listing projects")

        @self.app.post("/project/setactive")
        def set_active_project(project_name: str = Form(...)):
            """
            Set the active project.

            :param project_name: The project name
            """
            status = self.projectManager.setActiveProject(project_name)
            if status:
                return JSONResponse(
                    content={"message": f'Project "{project_name}" set as active'}
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f'Error setting project "{project_name}" as active',
                )

        @self.app.get("/project/getactive")
        def get_active_project():
            """
            Get the active project.
            """
            status, project = self.projectManager.getActiveProject()
            if status:
                return JSONResponse(content=project)
            else:
                raise HTTPException(status_code=404, detail="No active project found")

        @self.app.get("/project/getactiveprojectname")
        def get_active_project_name():
            """
            Get the active project name.
            """
            status, name = self.projectManager.getActiveProjectName()
            if status:
                return JSONResponse(content=name)
            else:
                raise HTTPException(status_code=404, detail="No active project found")

        @self.app.get("/project/getimagefromproject")
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

    def setServerIp(self, p_ip: str) -> None:
        """
        Set the server IP address.

        :param p_ip: The server IP address
        :type p_ip: str
        """
        self.serverIp = p_ip

    def setCmStatusLed(self, p_led: str) -> None:
        """
        Set the CM status LED.

        :param p_led: The CM status LED
        :type p_led: str
        """
        if p_led != "":
            self.cmStatusLed = p_led


# Create an instance of the HttpServer class for use
http_server = HttpServer()
app = http_server.app
