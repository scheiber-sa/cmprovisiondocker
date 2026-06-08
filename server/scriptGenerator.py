#!/usr/bin/env python3

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(message)s",
    handlers=[logging.StreamHandler()],
)


def generateCm4Script(
    p_serial: str,
    p_startTime: str,
    p_serverIp: str,
    p_serverPort: str,
    p_imageName: str,
    p_eeprom: str,
    p_cmStatusLed: str,
    p_cmStatusLedOnOnsuccess: str,
) -> str:
    """
    Generate the CM4 script.

    :param p_serial: The serial number
    :type p_serial: str
    :param p_startTime: The start time
    :type p_startTime: str
    :param p_serverIp: The server IP
    :type p_serverIp: str
    :param p_serverPort: The server port
    :type p_serverPort: str
    :param p_imageName: The image name
    :type p_imageName: str
    :param p_eeprom: The EEPROM
    :type p_eeprom: str
    :param p_cmStatusLed: The CM status LED
    :type p_cmStatusLed: str
    :param p_cmStatusLedOnOnsuccess: The CM status LED on success
    :type p_cmStatusLedOnOnsuccess: str

    :return: The generated script
    :rtype: str
    """
    script = f"""#!/bin/sh
#!/bin/sh
set -o pipefail

export SERIAL="{p_serial}"
export SERVER="{p_serverIp}:{p_serverPort}"
export IMAGE="{p_imageName}"
export EEPROM="{p_eeprom}"
export STATUS_LED="{p_cmStatusLed}"
export STATUS_LED_ON_ONSUCCESS="{p_cmStatusLedOnOnsuccess}"
export STARTTIME="{p_startTime}"
export STORAGE="/dev/mmcblk0"
export PART1="/dev/mmcblk0p1"
export PART2="/dev/mmcblk0p2"
export ALLDONE="0"

if [ "$STATUS_LED_ON_ONSUCCESS" = "1" ]; then
    export LED_SUCCESS_STATE="1"
    export LED_FAILURE_STATE="0"
else
    export LED_SUCCESS_STATE="0"
    export LED_FAILURE_STATE="1"
fi


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
flashrom -p "linux_spi:dev=/dev/spidev0.0,spispeed=16000" -r "/tmp/pieeprom.bin" || true
EEPROMSHA=$(sha256sum /tmp/pieeprom.bin | awk '{{print $1}}')
if [ -n "$EEPROMSHA" ]; then
    echo
else
    EEPROMSHA="emtySHA"
fi

if [ -f /tmp/eeprom_version ]; then
    curl --retry 10 -g -F 'eeprom_version=@/tmp/eeprom_version' "http://${{SERVER}}/scriptexecute/eeprom-version?serial=${{SERIAL}}&eepromsha=${{EEPROMSHA}}&start=${{STARTTIME}}"
fi

if [ -n "$EEPROM" ]; then
    curl -o /tmp/pendingeeprom.bin "http://${{SERVER}}/downloadeeprom/${{EEPROM}}"
    flashrom -p "linux_spi:dev=/dev/spidev0.0,spispeed=16000" -w "/tmp/pendingeeprom.bin" || true
fi

echo Sending BLKDISCARD to $STORAGE
blkdiscard -v $STORAGE || true

echo Writing image from http://${{SERVER}}/downloadimage/${{IMAGE}} to $STORAGE
curl --retry 10 -g "http://${{SERVER}}/downloadimage/${{IMAGE}}" \
 | xz -dc  \
 | dd of=$STORAGE conv=fsync obs=1M >/tmp/dd.log 2>&1
RETCODE=$?
if [ $RETCODE -eq 0 ]; then
    echo Original image written successfully
    ALLDONE="1"
    if [ "$STATUS_LED" != "NONE" ]; then
        kill $BLINK_PID
        echo ${{LED_SUCCESS_STATE}} > /sys/class/gpio/gpio$STATUS_LED/value
    fi
else
    echo Writing image failed.
    if [ "$STATUS_LED" != "NONE" ]; then
        kill $BLINK_PID
        echo ${{LED_FAILURE_STATE}} > /sys/class/gpio/gpio$STATUS_LED/value
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


def generateCm5Script(
    p_serial: str,
    p_startTime: str,
    p_serverIp: str,
    p_serverPort: str,
    p_imageName: str,
    p_eeprom: str,
    p_cmProgressLed: str,
    p_cmProgressLedDrivenLow: bool,
    p_cmErrorLed: str,
    p_cmErrorLedDrivenLow: bool,
) -> str:
    """
    Generate the CM4 script.

    :param p_serial: The serial number
    :type p_serial: str
    :param p_startTime: The start time
    :type p_startTime: str
    :param p_serverIp: The server IP
    :type p_serverIp: str
    :param p_serverPort: The server port
    :type p_serverPort: str
    :param p_imageName: The image name
    :type p_imageName: str
    :param p_eeprom: The EEPROM
    :type p_eeprom: str
    :param p_cmStatusLed: The CM status LED
    :type p_cmStatusLed: str
    :param p_cmStatusLedOnOnsuccess: The CM status LED on success
    :type p_cmStatusLedOnOnsuccess: str

    :return: The generated script
    :rtype: str
    """
    script = f"""#!/bin/sh
#!/bin/sh
set -o pipefail

export SERIAL="{p_serial}"
export SERVER="{p_serverIp}:{p_serverPort}"
export IMAGE="{p_imageName}"
export EEPROM="{p_eeprom}"
export PROGRESS_LED="{p_cmProgressLed}"
export PROGRESS_LED_ON_STATE="{'0' if p_cmProgressLedDrivenLow == True else '255'}"
export PROGRESS_LED_OFF_STATE="{'255' if p_cmProgressLedDrivenLow == True else '0'}"
export ERROR_LED="{p_cmErrorLed}"
export ERROR_LED_ON_STATE="{'0' if p_cmErrorLedDrivenLow == True else '255'}"
export ERROR_LED_OFF_STATE="{'255' if p_cmErrorLedDrivenLow == True else '0'}"
export STARTTIME="{p_startTime}"
export STORAGE="/dev/mmcblk0"
export PART1="/dev/mmcblk0p1"
export PART2="/dev/mmcblk0p2"
export ALLDONE="0"

# SWITCH OFF PROGRESS LED
if [ "$PROGRESS_LED" != "NONE" ]; then
    echo none > /sys/class/leds/${{PROGRESS_LED}}/trigger
    echo $PROGRESS_LED_OFF_STATE > /sys/class/leds/${{PROGRESS_LED}}/brightness
fi

# SWITCH OFF ERROR LED
if [ "$ERROR_LED" != "NONE" ]; then
    echo none > /sys/class/leds/${{ERROR_LED}}/trigger
    echo $ERROR_LED_OFF_STATE > /sys/class/leds/${{ERROR_LED}}/brightness
fi

# BLINK PROGRESS LED
if [ "$PROGRESS_LED" != "NONE" ]; then
    echo timer > /sys/class/leds/${{PROGRESS_LED}}/trigger
    echo 100 > /sys/class/leds/${{PROGRESS_LED}}/delay_on
    echo 100 > /sys/class/leds/${{PROGRESS_LED}}/delay_off
fi


# Make sure we have random entropy
echo "OM7WfoL5UW24E1cO2B66wuMvZVVAn2yoiZI2bX1ydJqEhPXibBBhZuRFtJWrRKuR" >/dev/urandom

echo Querying and registering EEPROM version
vcgencmd bootloader_version >/tmp/eeprom_version || true
flashrom -p "linux_spi:dev=/dev/spidev0.0,spispeed=16000" -r "/tmp/pieeprom.bin" || true
EEPROMSHA=$(sha256sum /tmp/pieeprom.bin | awk '{{print $1}}')
if [ -n "$EEPROMSHA" ]; then
    echo
else
    EEPROMSHA="emtySHA"
fi

if [ -f /tmp/eeprom_version ]; then
    curl --retry 10 -g -F 'eeprom_version=@/tmp/eeprom_version' "http://${{SERVER}}/scriptexecute/eeprom-version?serial=${{SERIAL}}&eepromsha=${{EEPROMSHA}}&start=${{STARTTIME}}"
fi

if [ -n "$EEPROM" ]; then
    curl -o /tmp/pendingeeprom.bin "http://${{SERVER}}/downloadeeprom/${{EEPROM}}"
    flashrom -p "linux_spi:dev=/dev/spidev0.0,spispeed=16000" -w "/tmp/pendingeeprom.bin" || true
fi

echo Sending BLKDISCARD to $STORAGE
blkdiscard -v -f $STORAGE || true

echo Writing image from http://${{SERVER}}/downloadimage/${{IMAGE}} to $STORAGE
curl --retry 10 -g "http://${{SERVER}}/downloadimage/${{IMAGE}}" \
 | xz -dc -T0 \
 | dd of=$STORAGE bs=8M 2>&1
RETCODE=$?

# STOP BLINKING PROGRESS LED
if [ "$PROGRESS_LED" != "NONE" ]; then
    echo none > /sys/class/leds/${{PROGRESS_LED}}/trigger
    echo $PROGRESS_LED_OFF_STATE > /sys/class/leds/${{PROGRESS_LED}}/brightness
fi

if [ $RETCODE -eq 0 ]; then
    sync
    # SWITCH ON PROGRESS LED
    if [ "$PROGRESS_LED" != "NONE" ]; then
        echo $PROGRESS_LED_ON_STATE > /sys/class/leds/${{PROGRESS_LED}}/brightness
    fi
    
    echo Original image written successfully
    ALLDONE="1"
else
    echo Writing image failed.
    # BLINK ERROR LED
    if [ "$ERROR_LED" != "NONE" ]; then
        echo timer > /sys/class/leds/${{ERROR_LED}}/trigger
        echo 100 > /sys/class/leds/${{ERROR_LED}}/delay_on
        echo 100 > /sys/class/leds/${{ERROR_LED}}/delay_off
    fi
    # LOG RESULT 
    journalctl -u live-update.service --no-pager > /tmp/dd.log
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
