#!/usr/bin/env python3

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse


class HttpServer:
    serverIp: str

    def __init__(
        self,
    ) -> None:
        """
        Initialize the FastAPI application.
        """
        self.serverIp = ""
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
            temp: float,
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
export STORAGE="/dev/mmcblk0"
export PART1="/dev/mmcblk0p1"
export PART2="/dev/mmcblk0p2"

# Make sure we have random entropy
echo "OM7WfoL5UW24E1cO2B66wuMvZVVAn2yoiZI2bX1ydJqEhPXibBBhZuRFtJWrRKuR" >/dev/urandom

echo Querying and registering EEPROM version
vcgencmd bootloader_version >/tmp/eeprom_version || true
if [ -f /tmp/eeprom_version ]; then
    curl --retry 10 -g -F 'eeprom_version=@/tmp/eeprom_version' "http://{{SERVER}}/scriptexecute?serial={{SERIAL}}"
fi

echo Sending BLKDISCARD to $STORAGE
blkdiscard -v $STORAGE || true

echo Writing image from http://{{SERVER}}/uploads/bSXNOvs5DoNJLY7cPV6MerUZsLm5kGoGGhQkJ0pT.xz to $STORAGE
curl --retry 10 -g "http://{{SERVER}}/uploads/bSXNOvs5DoNJLY7cPV6MerUZsLm5kGoGGhQkJ0pT.xz" \
 | xz -dc  \
 | dd of=$STORAGE conv=fsync obs=1M >/tmp/dd.log 2>&1
RETCODE=$?
if [ $RETCODE -eq 0 ]; then
    echo Original image written successfully
else
    echo Writing image failed.
    curl --retry 10 -g -F 'log=@/tmp/dd.log' "http://{{SERVER}}/scriptexecute?serial={{SERIAL}}&retcode=$RETCODE&phase=dd"
    exit 1
fi

partprobe $STORAGE
sleep 0.1

TEMP=vcgencmd measure_temp
curl --retry 10 -g "http://{{SERVER}}/scriptexecute?serial={{SERIAL}}&alldone=1&temp=${{TEMP:5}}&verify="

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
            return PlainTextResponse(content=script)

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
