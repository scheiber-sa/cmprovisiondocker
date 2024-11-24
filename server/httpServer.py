#!/usr/bin/env python3

from fastapi import FastAPI, UploadFile, Form, HTTPException, Query, File
from fastapi.responses import PlainTextResponse
from starlette.responses import FileResponse, JSONResponse
import hashlib
import os
from datetime import datetime


class HttpServer:
    serverIp: str
    imageName: str

    def __init__(
        self,
    ) -> None:
        """
        Initialize the FastAPI application.
        """
        self.serverIp = ""
        self.imageName = "mb-box-prod_.wic.xz"
        self.app = FastAPI(title="CM Provision Server")
        self.setupRoutes()

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
            # Generate a response script based on the request parameters
            script = f"""#!/bin/sh
#!/bin/sh
set -o pipefail

export SERIAL="{serial}"
export SERVER="{self.serverIp}"
export IMAGE="{self.imageName}"
export STORAGE="/dev/mmcblk0"
export PART1="/dev/mmcblk0p1"
export PART2="/dev/mmcblk0p2"

# Make sure we have random entropy
echo "OM7WfoL5UW24E1cO2B66wuMvZVVAn2yoiZI2bX1ydJqEhPXibBBhZuRFtJWrRKuR" >/dev/urandom

echo Querying and registering EEPROM version
vcgencmd bootloader_version >/tmp/eeprom_version || true
if [ -f /tmp/eeprom_version ]; then
    curl --retry 10 -g -F 'eeprom_version=@/tmp/eeprom_version' "http://${{SERVER}}/scriptexecute?serial=${{SERIAL}}"
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
else
    echo Writing image failed.
    curl --retry 10 -g -F 'log=@/tmp/dd.log' "http://${{SERVER}}/scriptexecute?serial=${{SERIAL}}&retcode=$RETCODE&phase=dd"
    exit 1
fi

partprobe $STORAGE
sleep 0.1

TEMP=vcgencmd measure_temp
curl --retry 10 -g "http://${{SERVER}}/scriptexecute/alldone?serial=${{SERIAL}}&alldone=1&temp=$${{TEMP:5}}&verify="

echo ""
echo "====="
echo "Provisioning completed successfully!"

sleep 0.1
if [ -f /sys/kernel/config/usb_gadget/g1/UDC ]; then
    echo "" > /sys/kernel/config/usb_gadget/g1/UDC
fi

if [ -e /sys/class/leds/led1 ]; then
    while true; do
        echo 255 > /sys/class/leds/led0/brightness
        echo 0 > /sys/class/leds/led1/brightness
        sleep 0.5
        echo 0 > /sys/class/leds/led0/brightness
        echo 255 > /sys/class/leds/led1/brightness
        sleep 0.5
    done
fi
if [ -e /sys/class/leds/led0 ]; then
    echo 255 > /sys/class/leds/led0/brightness
fi
"""
            return PlainTextResponse(content=script, media_type="text/plain")

        @self.app.post("/scriptexecute")
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
            temp: float,
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

    def setServerIp(self, p_ip: str) -> None:
        """
        Set the server IP address.

        :param p_ip: The server IP address
        :type p_ip: str
        """
        self.serverIp = p_ip


# Create an instance of the HttpServer class for use
http_server = HttpServer()
app = http_server.app
