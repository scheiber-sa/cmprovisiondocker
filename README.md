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

| Feature | cmprovision | cmprovisiondocker |
| --- | --- | --- |
| Multiple cm4s provisioning | :white_check_mark: | :white_check_mark: |
| Project management | :white_check_mark: | :white_check_mark: |
| Different images provisioning | :white_check_mark: | :white_check_mark: |
| Image xz support | :white_check_mark: | :white_check_mark: |
| Image gz support | :white_check_mark: | :x: |
| Image bz2 support | :white_check_mark: | :x: |
| Destination storage device | :white_check_mark: | :x: |
| EEPROM firmware update | :white_check_mark: | :x: |
| Extra scripts | :white_check_mark: | :x: |
| Control managed swicth | :white_check_mark: | :x: |
| History of provisioning | :white_check_mark: | :white_check_mark: |
| Live status of provisioning | :white_check_mark: | :white_check_mark: |
| User interface | :white_check_mark: | :x: |
| Restful API | :x: | :white_check_mark: |
| Websocket for provioning events | :x: | :white_check_mark: |
| Installable on a workstation | :x: | :white_check_mark: |
| Installable on a rpi4 | :white_check_mark: | :white_check_mark: |


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

```bash
cat conf/cmprovisionserverconf.yml
cmProvisionServer:
  hostIface: "enx58d56e3ddcd4"
  serverIp: "192.168.5.1/16"
  dhcpRange: "192.168.5.2,192.168.255.255,255.255.0.0"
  restApiPort: 80
```

_Note : If your network interface is managed by network tool such as NetworkManager, you should disable it for this interface. Or simply set the same ip in NetworkManager you have defined in the configuration. Otherwise, the cmprovisiondocker server will not be able to manage the network interface properly._


- `hostIface`: The dedicated network interface for the cm4 provisioning
- `serverIp`: The IP address of the cmprovisiondocker server. It composed of the IP address and the subnet mask
- `dhcpRange`: The DHCP range of the cmprovisiondocker server.
- `restApiPort`: The port of the restful API

Then, you can start the cmprovisiondocker server.

```bash
docker compose up -d --build;docker logs -f cmprovision
```

Upload the image to the cmprovisiondocker server.

```bash
curl -X POST "http://0.0.0.0/image/upload-image"   -F "image=@image.wic.xz"   -F "sha256sum=59f76e1e5fbc56e220409b28008364b4163e876b15ed456fb688a6e6235d0f08"
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
  -d 'project_name=second&active=true&image=image.wic.xz&cm_status_led=12&cm_status_led_on_onsuccess=true'
```

Parameters:

- `project_name`: The name of the project
- `active`: The project status. If the project is active, the cm4 will be provisioned with the image defined in the project
- `image`: The image to provision the cm4
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



