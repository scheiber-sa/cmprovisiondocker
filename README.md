# cmprovisiondocker
# Raspberry Pi Compute Module Provisioning System Containerized



## Introduction

Facing to mass cm4 provisioning, we are looking for a solution to provision the cm4 in a more efficient way. The solution:

- should be able to provision multiple cm4s at the same time
- should be able to provision cm4s with different images
- must be interfaceable with industrial tools (ERP)
- must be able to record and retrieve the provisioning results history
- must be installable on a workstation

I obviously found [cmprovision](https://github.com/raspberrypi/cmprovision/). But it does not meet all the requirements. So I decided to create a new solution based on the cmprovision.

## General operation of the cmprovisiondocker

Briefly, the solution is a containerized version of the cmprovision. It s based on Docker and has a restful API to interact with the provisioning system.


When a CM4 cant boot from its internal storage, it will boot from the network. The cmprovisiondocker server will provide the cm4 with the necessary files to boot. The cm4 will boot from the network and will be provisioned with the image defined in the project.

### CM4 boot sequence
In this case, CM4 will request via TFTP all this files:
```
/tftpboot/be910eb2/start4.elf
/tftpboot/be910eb2/start.elf
/tftpboot/config.txt
/tftpboot/pieeprom.sig
/tftpboot/recover4.elf
/tftpboot/recovery.elf
/tftpboot/start4.elf
/tftpboot/fixup4.dat
/tftpboot/dt-blob.bin
/tftpboot/bootcfg.txt
/tftpboot/scriptexecute.img
/tftpboot/bcm2711-rpi-cm4.dtb
/tftpboot/overlays/overlay_map.dtb
/tftpboot/overlays/dwc2.dtbo
/tftpboot/overlays/spi-gpio40-45.dtbo
/tftpboot/cmdline.txt
/tftpboot/recovery8.img
/tftpboot/recovery8-32.img
/tftpboot/recovery7l.img
/tftpboot/recovery7.img
/tftpboot/recovery.img
/tftpboot/kernel8.img
/tftpboot/kernel8-32.img
/tftpboot/kernel7l.img
/tftpboot/kernel7.img
/tftpboot/kernel.img
/tftpboot/armstub8-32-gic.bin
```

On tftp server side, the cmprovisiondocker server will provide the following files:
```
/tftpboot/config.txt
/tftpboot/start4.elf
/tftpboot/fixup4.dat
/tftpboot/scriptexecute.img
/tftpboot/bcm2711-rpi-cm4.dtb
/tftpboot/dwc2.dtbo
/tftpboot/spi-gpio40-45.dtbo
/tftpboot/cmdline.txt
/tftpboot/kernel.img
```

Then the CM4 will boot the `kernel.img` and then `scriptexecute.img`.

_Note: `scriptexecute.img` sources are available [here](https://github.com/raspberrypi/scriptexecutor)_

Lets look at the `scriptexecute.img` content:

```bash
cd scriptexecute
file scriptexecute.img
scriptexecute.img: XZ compressed data, checksum CRC32
cp scriptexecute.img scriptexecute.xz
xz -d scriptexecute.xz
file scriptexecute
scriptexecute: ASCII cpio archive (SVR4 with no CRC)
mkdir scriptexecute_content
cd scriptexecute_content
cpio -idmv < ../scriptexecute
ls -l
total 72
drwxrwxr-x 17 pierr0t pierr0t 4096 nov.  26 09:50 ./
drwxrwxr-x  4 pierr0t pierr0t 4096 nov.  26 09:50 ../
drwxr-xr-x  2 pierr0t pierr0t 4096 nov.  26 09:50 bin/
drwxr-xr-x  4 pierr0t pierr0t 4096 nov.  26 09:50 dev/
drwxr-xr-x  7 pierr0t pierr0t 4096 nov.  26 09:50 etc/
-rwxr-xr-x  1 pierr0t pierr0t  178 nov.  10  2022 init*
drwxr-xr-x  3 pierr0t pierr0t 4096 nov.  26 09:50 lib/
lrwxrwxrwx  1 pierr0t pierr0t    3 nov.  26 09:50 lib32 -> lib/
lrwxrwxrwx  1 pierr0t pierr0t   11 nov.  26 09:50 linuxrc -> bin/busybox*
drwxr-xr-x  2 pierr0t pierr0t 4096 janv. 12  2020 media/
drwxr-xr-x  2 pierr0t pierr0t 4096 janv. 12  2020 mnt/
drwxr-xr-x  2 pierr0t pierr0t 4096 janv. 12  2020 opt/
drwxr-xr-x  2 pierr0t pierr0t 4096 janv. 12  2020 proc/
drwx------  2 pierr0t pierr0t 4096 janv. 12  2020 root/
drwxr-xr-x  2 pierr0t pierr0t 4096 janv. 12  2020 run/
drwxr-xr-x  2 pierr0t pierr0t 4096 nov.  26 09:50 sbin/
drwxr-xr-x  2 pierr0t pierr0t 4096 janv. 12  2020 sys/
drwxrwxrwt  2 pierr0t pierr0t 4096 janv. 12  2020 tmp/
drwxr-xr-x  7 pierr0t pierr0t 4096 nov.  26 09:50 usr/
drwxr-xr-x  4 pierr0t pierr0t 4096 nov.  26 09:50 var/
```

We can see that the `scriptexecute.img` is a cpio archive. The content of the archive is the root filesystem of the cm4. The cm4 will boot on this filesystem and execute the `init` script.


Look at `./etc/init.d/`:

```bash
ls -l ./etc/init.d/
-rwxr-xr-x 1 pierr0t pierr0t  423 avril  7  2021 rcK
-rwxr-xr-x 1 pierr0t pierr0t  408 avril  7  2021 rcS
-rwxr-xr-x 1 pierr0t pierr0t 1012 avril  7  2021 S01syslogd
-rwxr-xr-x 1 pierr0t pierr0t 1004 avril  7  2021 S02klogd
-rwxr-xr-x 1 pierr0t pierr0t 1876 avril  7  2021 S02sysctl
-rwxr-xr-x 1 pierr0t pierr0t 1684 avril  7  2021 S20urandom
-rwxr-xr-x 1 pierr0t pierr0t  438 avril  7  2021 S40network
-rwxr-xr-x 1 pierr0t pierr0t 4593 nov.  10  2022 S99scriptexec
```

The `S99scriptexec` script is the script that will provision the cm4. The script will download the image from the cmprovisiondocker server and write it to the internal storage of the cm4.

```bash
cat etc/init.d/S99scriptexec
#!/bin/sh

#
# Script executed at start
#

# Bail out on any error
set -e

case "$1" in
  start)
    SERIAL=`cat /proc/cpuinfo | grep Serial | cut -d ' ' -f 2`
    MODEL=`cat /proc/device-tree/model`
    MODEL_ESCAPED="${MODEL// /+}"
    TEMP=`vcgencmd measure_temp`
    TEMP=${TEMP:5}

    #
    # Parse kernel cmdline options (cmdline.txt)
    #
    for p in `cat /proc/cmdline`; do
        if [ "${p%%=*}" == "script" ]; then
            SCRIPT="${p#*=}"
        fi
        if [ "$p" == "usbipv6ll" ]; then
            USBIPV6LL=true
        fi
        if [ "$p" == "readjumper" ]; then
            READJUMPER=true
        fi
    done

    if [ -e /sys/class/leds/led0 ]; then
        echo none > /sys/class/leds/led0/trigger
        echo 0 > /sys/class/leds/led0/brightness
    fi

    if [[ -n "$USBIPV6LL" ]]; then
        # Pretend to be a USB Ethernet adapter, talking to host on IPv6 link-local address
        GADGET=/sys/kernel/config/usb_gadget/g1
        MAC="fa:${SERIAL:6:2}:${SERIAL:8:2}:${SERIAL:10:2}:${SERIAL:12:2}:${SERIAL:14:2}"
        HOST_IPV6="fe80::f8${MAC:3:5}ff:fe${MAC:9:5}${MAC:15:2}%usb0"

        mount -t configfs none /sys/kernel/config
        mkdir -p $GADGET
        (cd $GADGET
        # FIXME: obtain proper USB ID instead of using f055 (FOSS)
        echo 0xf055 > idVendor
        echo 0x0002 > idProduct
        mkdir strings/0x409
        echo $SERIAL > strings/0x409/serialnumber
        echo "Raspberry Pi" > strings/0x409/manufacturer
        echo "CM provisioning" > strings/0x409/product
        mkdir configs/c.1
        mkdir configs/c.1/strings/0x409
        echo "Config 1" > configs/c.1/strings/0x409/configuration
        echo 500 > configs/c.1/MaxPower
        #mkdir functions/acm.usb0
        #ln -s functions/acm.usb0 configs/c.1
        mkdir functions/ecm.usb0
        echo $MAC > functions/ecm.usb0/host_addr
        ln -s functions/ecm.usb0 configs/c.1
        # Assuming there is only ever going to be one UDC
        ls /sys/class/udc > UDC
        )

        echo
        echo "IP configuration:"
        echo
        ifconfig usb0 add fe80::1/64 up
        ifconfig -a
        echo "My IPv6 is: fe80::1 / IPv6 of host is: ${HOST_IPV6}"

        sleep 2

        SCRIPT="${SCRIPT//\{server\}/[$HOST_IPV6]}"
    else
        # Expecting USB to switch to device mode and USB Ethernet adapter to be attached

        echo "Note: shell is available on tty2 for debugging purposes"
        mount -t debugfs none /sys/kernel/debug || true
        /sbin/getty -L tty2 0 vt100 &

        echo "Waiting for eth0 to appear"
        while [ ! -e /sys/class/net/eth0 ]; do
            sleep 1
        done

        ifconfig eth0 up
        echo "Waiting for network link to go up"
        while grep -q -v 1 /sys/class/net/eth0/carrier; do
            sleep 1
        done

        echo "Obtaining DHCP lease"
        udhcpc -i eth0
    fi

    if [ "${SCRIPT%%:*}" == "http" ]; then
        SCRIPT="${SCRIPT//\{model\}/$MODEL_ESCAPED}"
        SCRIPT="${SCRIPT//\{serial\}/$SERIAL}"
        SCRIPT="${SCRIPT//\{temp\}/$TEMP}"
        if [ -e /sys/block/mmcblk0/size ]; then
            STORAGESIZE=`cat /sys/block/mmcblk0/size`
        fi
        SCRIPT="${SCRIPT//\{storagesize\}/$STORAGESIZE}"
        if [ -e /sys/block/mmcblk0/device/cid ]; then
                    CID=`cat /sys/block/mmcblk0/device/cid`
        fi
        SCRIPT="${SCRIPT//\{cid\}/$CID}"
        if [ -e /sys/block/mmcblk0/device/csd ]; then
                    CSD=`cat /sys/block/mmcblk0/device/csd`
        fi
        SCRIPT="${SCRIPT//\{csd\}/$CSD}"
        if [ -e /proc/device-tree/chosen/bootloader/boot-mode ]; then
            BOOTMODE=`od -An -tu1 --skip 3 /proc/device-tree/chosen/bootloader/boot-mode |xargs`
        fi
        SCRIPT="${SCRIPT//\{bootmode\}/$BOOTMODE}"
        MEMORYSIZE=`grep MemTotal /proc/meminfo | awk '{print $2}'`
        SCRIPT="${SCRIPT//\{memorysize\}/$MEMORYSIZE}"
        if [ -e /sys/class/net/eth0/address ]; then
            ETHMAC=`cat /sys/class/net/eth0/address`
        fi
        SCRIPT="${SCRIPT//\{mac\}/$ETHMAC}"
                if [[ -n "$READJUMPER" ]]; then
                        JUMPER=""
                        for GPIO in 5 13 21
                        do
                            echo "$GPIO" >/sys/class/gpio/export
                            GPIOVALUE=`cat /sys/class/gpio/gpio$GPIO/value`
                            JUMPER="$JUMPER$GPIOVALUE"
                        done
                fi
        SCRIPT="${SCRIPT//\{jumper\}/$JUMPER}"

        echo "Downloading script from $SCRIPT"
        curl -g --retry 10 --retry-connrefused -o /tmp/script "$SCRIPT"
        echo "Executing script"
        sh /tmp/script
    elif [[ -n "$SCRIPT" ]]; then
        SHARE=${SCRIPT%/*}
        FILENAME=`basename $SCRIPT`

        echo "Mounting NFS share $SHARE"
        mount -t nfs -o nolock,ro $SHARE /mnt
        echo "Executing script $FILENAME"
        cd /mnt
        sh $FILENAME
        cd ..
        echo "Unmounting NFS share"
        umount /mnt
    fi

    if [[ -z "$USBIPV6LL" ]]; then
        echo "Releasing DHCP lease"
        killall -SIGUSR2 udhcpc
        sleep 1
    fi

    #halt
        ;;
  stop)
    ;;
  *)
    echo "Usage: $0 {start|stop}"
    exit 1
esac

exit $?
```

This script do the first request to the cmprovisiondocker server to download a script.
```bash
curl -g --retry 10 --retry-connrefused -o /tmp/script "$SCRIPT"
```

The `SCRIPT` variable is the URL of the script to download. Is partly set by the kernel command line options `cmdline.txt`:
```bash
cd scriptexecute
cat cmdline.txt
readjumper script=http://192.168.5.1/scriptexecute?serial={serial}&model={model}&storagesize={storagesize}&mac={mac}&inversejumper={jumper}&memorysize={memorysize}&temp={temp}&cid={cid}&csd={csd}&bootmode={bootmode}
```

### cmprovisiondocker server

#### Initialization

The server read the configuration file `conf/cmprovisionserverconf.yml`  :

- Set the network interface with the right IP address and subnet mask
- Set the DHCP range in dnsmasq configuration file `/etc/dnsmasq.conf`
- Set the tftp-root in the tftp configuration file `/etc/dnsmsq.conf`
- Set the `cmdline.txt` file in the tftp-root directory with its address
- Start the dnsmasq daemon
- Start the restful API server

#### Provisioning

When a cm4 boots from the network, the cmprovisiondocker server will provide the necessary files to boot the cm4. The cm4 will boot on the `scriptexecute.img` and execute the `S99scriptexec` script. The script will download the image from the cmprovisiondocker server and write it to the internal storage of the cm4. And the CM4 will sent its provisioning status to the cmprovisiondocker server.


## Comparison with cmprovision

| Feature | cmprovision | cmprovisiondocker (cm4) | cmprovisiondocker (cm5) |
| --- | --- | --- | --- |
| Multiple cm4s provisioning | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Project management | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Different images provisioning | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Image xz support | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Image gz support | :white_check_mark: | :x: | :x: |
| Image bz2 support | :white_check_mark: | :x: | :x: |
| Destination storage device | :white_check_mark: | :x: | :x: |
| EEPROM firmware update | :white_check_mark: | :white_check_mark: | :x: |
| Extra scripts | :white_check_mark: | :x: | :x: |
| Control managed swicth | :white_check_mark: | :x: | :x: |
| History of provisioning | :white_check_mark: | :white_check_mark: | :white_check_mark: |
| Live status of provisioning | :white_check_mark: | :x: | :x: |
| User interface | :white_check_mark: | :x: | :x: |
| Documented Restful API | :x: | :white_check_mark: | :white_check_mark: |
| Websocket for provioning events | :x: | :white_check_mark: | :white_check_mark: |
| Installable on a workstation | :x: | :white_check_mark: | :white_check_mark: |
| Installable on a rpi4/rpi5 | :white_check_mark: | :white_check_mark: | :white_check_mark: |


## Installation

### Prerequisites

- Docker
- Docker-compose
- Git
- A workstation with a dedicated network interface for the cm4 provisioning. For development, I used a USB to Ethernet adapter.



### Installation

```bash
git clone https://github.com/scheiber-sa/cmprovisiondocker.git
cd cmprovisiondocker
```

Set your configuration in `conf/cmprovisionserverconf.yml` file.

```yml
cat conf/cmprovisionserverconf.yml
cmProvisionServer:
  hostIface: "enx58d56e3ddcd4"
  serverIp: "192.168.5.1/16"
  dhcpRange: "192.168.5.2,192.168.255.255,255.255.0.0"
  restApiPort: 80
  enableCm5SerialDebug: true
```

_Note : If your network interface is managed by network tool such as NetworkManager, you should disable it for this interface. Or simply set the same ip in NetworkManager you have defined in the configuration. Otherwise, the cmprovisiondocker server will not be able to manage the network interface properly._


- `hostIface`: The dedicated network interface for the cm4 provisioning
- `serverIp`: The IP address of the cmprovisiondocker server. It composed of the IP address and the subnet mask
- `dhcpRange`: The DHCP range of the cmprovisiondocker server.
- `restApiPort`: The port of the restful API
- `enableCm5SerialDebug`: Enable the serial debug for cm5 provisioning. It will print the cm5 serial output in the cmprovisiondocker server logs. It is useful for debugging purposes.

Then, you can start the cmprovisiondocker server.

```bash
docker compose up -d --build;docker logs -f cmprovision
```

Upload the image to the cmprovisiondocker server.

```bash
curl -X POST "http://0.0.0.0/image/upload-image"   -F "image=@image_8.wic.xz"   -F "sha256sum=59f76e1e5fbc56e220409b28008364b4163e876b15ed456fb688a6e6235d0f08"
```

response:
```
{"filename":"image.wic.xz","sha256sum":"59f76e1e5fbc56e220409b28008364b4163e876b15ed456fb688a6e6235d0f08","message":"File uploaded and verified successfully"}
```

Create a project.

```bash
curl -X 'POST' \
  'http://0.0.0.0/project/create' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'project_name=third&active=true&image8Gb=image_8.wic.xz&image16Gb=image_16.wic.xz&image32Gb=image_32.wic.xz&cm_status_led=12&cm_status_led_on_onsuccess=true'
```

Parameters:

- `project_name`: The name of the project
- `active`: The project status. If the project is active, the cm4 will be provisioned with the image defined in the project
- `image8Gb`: The image to provision the cm4 with 8Gb of internal storage.
- `image16Gb`: The image to provision the cm4 with 16Gb of internal storage.This parameter is optional. If not set, the cm4 will be provisioned with the image defined in `image8Gb`.
- `image32Gb`: The image to provision the cm4 with 32Gb of internal storage. This parameter is optional. If not set, the cm4 will be provisioned with the image defined in `image8Gb`.
- `cm_status_led` : The GPIO pin of the status led. The status led is used to indicate the status of the cm4 provisioning. The status led is optional.
- `cm_status_led_on_onsuccess`: The status led status when the image writing is successful. The status led status is optional.

The led status is as follows:

- 'blinking': during the image writing
- 'on': if the image writing is successful, if `cm_status_led_on_onsuccess` is set to 'true', otherwise 'off'
- 'off': if the image writing is failed, if `cm_status_led_on_onsuccess` is set to 'true', otherwise 'on'


response:

```
{"message":"Project 'first' created successfully"}
```

You are now ready to provision your cm4s.

## Restful API documentation

The cmprovisiondocker server has a restful API to interact with the provisioning system. The API documentation is available at the following URL:

http://0.0.0.0/docs

## Websocket

The cmprovisiondocker server has a websocket to send the provisioning events. The websocket is available at the following URL:

ws://0.0.0.0

## Conclusion

The cmprovisiondocker is a containerized version of the cmprovision. It has a restful API to interact with the provisioning system. It is installable on a workstation and can provision multiple cm4s at the same time. It is a good solution for mass cm4 provisioning.

## Issue / Feature request

Feel free to propose a new fix or feature by opening a pull request.


# CM5 provisioning is under development.

## General operation of the cmprovisiondocker

When a CM5 cant boot from its internal storage, it will boot from the network. The cmprovisiondocker server will provide the cm5 with the necessary files to boot. The cm5 will boot from the network and will be provisioned with the image defined in the project.

### CM5 boot sequence
In this case, CM5 will request via TFTP all this files:
```bash
/tftpboot/config.txt
/tftpboot/bcm2712-rpi-cm5-cm5io.dtb
/tftpboot/mb-box-bsp-cm5-26-live__.cpio.gz
/tftpboot/bcm2712-rpi-cm5-cm5io.dtb
/tftpboot/overlays/overlay_map.dtb
/tftpboot/overlays/bcm2712d0.dtbo
/tftpboot/config.txt
/tftpboot/overlays/vc4-kms-v3d-pi5.dtbo
/tftpboot/overlays/dwc2.dtbo
/tftpboot/cmdline.txt
/tftpboot/kernel_2712.img
```

On tftp server side, the cmprovisiondocker server will provide the following files:
```bash
scriptexecute/start4.elf
scriptexecute/kernel_2712.img
scriptexecute/bcm2712-rpi-cm5-cm5io.dtb
scriptexecute/config.txt
scriptexecute/bcm2712-rpi-cm5l-cm5io.dtb
scriptexecute/mb-box-bsp-cm5-26-live__.cpio.gz
scriptexecute/overlays
scriptexecute/bcm2712-rpi-cm5l-cm4io.dtb
scriptexecute/bcm2712-rpi-cm5-cm4io.dtb
scriptexecute/bcm2712-rpi-5-b.dtb
```

Then the CM5 will boot the `kernel_2712.img` and then `mb-box-bsp-cm5-26-live__.cpio.gz`.

Then the `mb-box-bsp-cm5-26-live__.cpio.gz` will be uncompressed and systemd service live-update.service will be executed. This service will request the cmprovisiondocker server to download a script and execute it.

```bash
[Unit]
Description=MB-Box CM5 provisioning script executor
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/live-update
StandardOutput=journal+console
StandardError=journal+console

[Install]
WantedBy=multi-user.target
```

`/usr/bin/live-update` script content:
```bash
#!/bin/sh

set -eu

log() {
    echo "mbbox-scriptexec: $*"
}

read_dt_string() {
    file="$1"
    default="${2:-unknown}"

    if [ -r "$file" ]; then
        tr -d '\000' < "$file"
    else
        printf '%s' "$default"
    fi
}

get_cmdline_arg() {
    name="$1"

    for arg in $(cat /proc/cmdline); do
        case "$arg" in
            "$name"=*)
                printf '%s\n' "${arg#*=}"
                return 0
                ;;
        esac
    done

    return 1
}

has_cmdline_flag() {
    name="$1"

    for arg in $(cat /proc/cmdline); do
        [ "$arg" = "$name" ] && return 0
    done

    return 1
}

get_serial() {
    serial="$(read_dt_string /proc/device-tree/serial-number "")"

    if [ -n "$serial" ]; then
        printf '%s' "$serial"
        return
    fi

    awk '/^Serial/ { print $3 }' /proc/cpuinfo 2>/dev/null || printf 'unknown'
}

get_model() {
    read_dt_string /proc/device-tree/model unknown
}

get_temp() {
    if [ -r /sys/class/thermal/thermal_zone0/temp ]; then
        milli="$(cat /sys/class/thermal/thermal_zone0/temp)"
        deg=$((milli / 1000))
        dec=$(((milli % 1000) / 100))
        printf "%s.%s'C" "$deg" "$dec"
    else
        printf 'unknown'
    fi
}

get_storage_size() {
    # Keep same semantic as the original Raspberry Pi script:
    # /sys/block/mmcblk0/size = number of 512-byte sectors, not bytes.
    if [ -r /sys/block/mmcblk0/size ]; then
        cat /sys/block/mmcblk0/size
    else
        printf 'unknown'
    fi
}

get_cid() {
    if [ -r /sys/block/mmcblk0/device/cid ]; then
        cat /sys/block/mmcblk0/device/cid
    else
        printf 'unknown'
    fi
}

get_csd() {
    if [ -r /sys/block/mmcblk0/device/csd ]; then
        cat /sys/block/mmcblk0/device/csd
    else
        printf 'unknown'
    fi
}

get_bootmode() {
    file="/proc/device-tree/chosen/bootloader/boot-mode"

    if [ -r "$file" ]; then
        dd if="$file" bs=1 skip=3 count=1 2>/dev/null \
            | hexdump -v -e '1/1 "%u"'
    else
        printf 'unknown'
    fi
}

get_memory_size() {
    awk '/MemTotal:/ { print $2 }' /proc/meminfo 2>/dev/null || printf 'unknown'
}

get_mac() {
    if [ -r /sys/class/net/eth0/address ]; then
        cat /sys/class/net/eth0/address
        return
    fi

    for iface in /sys/class/net/*; do
        name="$(basename "$iface")"
        if [ "$name" != "lo" ] && [ -r "$iface/address" ]; then
            cat "$iface/address"
            return
        fi
    done

    printf 'unknown'
}

read_one_gpio_sysfs() {
    gpio="$1"

    if [ ! -d "/sys/class/gpio/gpio${gpio}" ]; then
        echo "$gpio" > /sys/class/gpio/export 2>/dev/null || true
        sleep 0.1
    fi

    if [ -w "/sys/class/gpio/gpio${gpio}/direction" ]; then
        echo in > "/sys/class/gpio/gpio${gpio}/direction" 2>/dev/null || true
    fi

    if [ -r "/sys/class/gpio/gpio${gpio}/value" ]; then
        cat "/sys/class/gpio/gpio${gpio}/value"
    else
        printf 'x'
    fi
}

get_jumper() {
    if ! has_cmdline_flag readjumper; then
        printf ''
        return
    fi

    # Preferred: board-specific helper if you provide one.
    if command -v readjumper >/dev/null 2>&1; then
        readjumper || printf 'unknown'
        return
    fi

    # Compatibility fallback with original CM4 script.
    # To be validated on your CM5 carrier board.
    jumper=""
    for gpio in 5 13 21; do
        value="$(read_one_gpio_sysfs "$gpio")"
        jumper="${jumper}${value}"
    done

    printf '%s' "$jumper"
}

SCRIPT="$(get_cmdline_arg script || true)"

if [ -z "${SCRIPT:-}" ]; then
    log "no script= argument in /proc/cmdline"
    exit 0
fi

SERIAL="$(get_serial)"
MODEL="$(get_model)"
STORAGESIZE="$(get_storage_size)"
MAC="$(get_mac)"
JUMPER="$(get_jumper)"
MEMORYSIZE="$(get_memory_size)"
TEMP="$(get_temp)"
CID="$(get_cid)"
CSD="$(get_csd)"
BOOTMODE="$(get_bootmode)"

SCRIPT_BASE="${SCRIPT%%\?*}"

log "serial=$SERIAL"
log "model=$MODEL"
log "storagesize=$STORAGESIZE"
log "mac=$MAC"
log "jumper=$JUMPER"
log "memorysize=$MEMORYSIZE"
log "temp=$TEMP"
log "cid=$CID"
log "csd=$CSD"
log "bootmode=$BOOTMODE"
log "downloading script from $SCRIPT_BASE"

curl -fsS -G \
    --retry 10 \
    --retry-delay 2 \
    --retry-connrefused \
    --connect-timeout 5 \
    -o /tmp/script \
    "$SCRIPT_BASE" \
    --data-urlencode "serial=$SERIAL" \
    --data-urlencode "model=$MODEL" \
    --data-urlencode "storagesize=$STORAGESIZE" \
    --data-urlencode "mac=$MAC" \
    --data-urlencode "inversejumper=$JUMPER" \
    --data-urlencode "memorysize=$MEMORYSIZE" \
    --data-urlencode "temp=$TEMP" \
    --data-urlencode "cid=$CID" \
    --data-urlencode "csd=$CSD" \
    --data-urlencode "bootmode=$BOOTMODE"

chmod +x /tmp/script || true

log "executing downloaded script"
exec /bin/sh /tmp/script
```

example of script to download and execute:
```bash
#!/bin/sh
set -o pipefail

export SERIAL="7329acf8367bf434"
export SERVER="10.10.10.1:60080"
export IMAGE="mb-box-cm5-26-prod-16__.wic.xz"
export EEPROM=""
export PROGRESS_LED="ACT"
export PROGRESS_LED_ON_STATE="0"
export PROGRESS_LED_OFF_STATE="255"
export ERROR_LED="PWR"
export ERROR_LED_ON_STATE="255"
export ERROR_LED_OFF_STATE="0"
export STARTTIME="20260608_10:30:31"
export STORAGE="/dev/mmcblk0"
export PART1="/dev/mmcblk0p1"
export PART2="/dev/mmcblk0p2"
export ALLDONE="0"

# SWITCH OFF PROGRESS LED
if [ "$PROGRESS_LED" != "NONE" ]; then
    echo none > /sys/class/leds/${PROGRESS_LED}/trigger
    echo $PROGRESS_LED_OFF_STATE > /sys/class/leds/${PROGRESS_LED}/brightness
fi

# SWITCH OFF ERROR LED
if [ "$ERROR_LED" != "NONE" ]; then
    echo none > /sys/class/leds/${ERROR_LED}/trigger
    echo $ERROR_LED_OFF_STATE > /sys/class/leds/${ERROR_LED}/brightness
fi

# BLINK PROGRESS LED
if [ "$PROGRESS_LED" != "NONE" ]; then
    echo timer > /sys/class/leds/${PROGRESS_LED}/trigger
    echo 100 > /sys/class/leds/${PROGRESS_LED}/delay_on
    echo 100 > /sys/class/leds/${PROGRESS_LED}/delay_off
fi


# Make sure we have random entropy
echo "OM7WfoL5UW24E1cO2B66wuMvZVVAn2yoiZI2bX1ydJqEhPXibBBhZuRFtJWrRKuR" >/dev/urandom

echo Querying and registering EEPROM version
vcgencmd bootloader_version >/tmp/eeprom_version || true
flashrom -p "linux_spi:dev=/dev/spidev0.0,spispeed=16000" -r "/tmp/pieeprom.bin" || true
EEPROMSHA=$(sha256sum /tmp/pieeprom.bin | awk '{print $1}')
if [ -n "$EEPROMSHA" ]; then
    echo
else
    EEPROMSHA="emtySHA"
fi

if [ -f /tmp/eeprom_version ]; then
    curl --retry 10 -g -F 'eeprom_version=@/tmp/eeprom_version' "http://${SERVER}/scriptexecute/eeprom-version?serial=${SERIAL}&eepromsha=${EEPROMSHA}&start=${STARTTIME}"
fi

if [ -n "$EEPROM" ]; then
    curl -o /tmp/pendingeeprom.bin "http://${SERVER}/downloadeeprom/${EEPROM}"
    flashrom -p "linux_spi:dev=/dev/spidev0.0,spispeed=16000" -w "/tmp/pendingeeprom.bin" || true
fi

echo Sending BLKDISCARD to $STORAGE
blkdiscard -v -f $STORAGE || true

echo Writing image from http://${SERVER}/downloadimage/${IMAGE} to $STORAGE
curl --retry 10 -g "http://${SERVER}/downloadimage/${IMAGE}"  | xz -dc -T0  | dd of=$STORAGE bs=8M 2>&1
RETCODE=$?

# STOP BLINKING PROGRESS LED
if [ "$PROGRESS_LED" != "NONE" ]; then
    echo none > /sys/class/leds/${PROGRESS_LED}/trigger
    echo $PROGRESS_LED_OFF_STATE > /sys/class/leds/${PROGRESS_LED}/brightness
fi

if [ $RETCODE -eq 0 ]; then
    sync
    # SWITCH ON PROGRESS LED
    if [ "$PROGRESS_LED" != "NONE" ]; then
        echo $PROGRESS_LED_ON_STATE > /sys/class/leds/${PROGRESS_LED}/brightness
    fi

    echo Original image written successfully
    ALLDONE="1"
else
    echo Writing image failed.
    # BLINK ERROR LED
    if [ "$ERROR_LED" != "NONE" ]; then
        echo timer > /sys/class/leds/${ERROR_LED}/trigger
        echo 100 > /sys/class/leds/${ERROR_LED}/delay_on
        echo 100 > /sys/class/leds/${ERROR_LED}/delay_off
    fi
    # LOG RESULT
    journalctl -u live-update.service --no-pager > /tmp/dd.log
    curl --retry 10 -g -F 'log=@/tmp/dd.log' "http://${SERVER}/scriptexecute/error?serial=${SERIAL}&retcode=$RETCODE&phase=dd&start=${STARTTIME}"
    exit 1
fi

partprobe $STORAGE
sleep 0.1

TEMP=vcgencmd measure_temp
curl --retry 10 -g "http://${SERVER}/scriptexecute/alldone?serial=${SERIAL}&alldone=${ALLDONE}&temp=${TEMP}&verify=&start=${STARTTIME}"


echo "Provisioning completed successfully!"
```


This script will be downloaded and executed by the CM5 after it boots from the network. The script will download the image from the cmprovisiondocker server and write it to the internal storage of the CM5. The script will also send the provisioning status to the cmprovisiondocker server.
