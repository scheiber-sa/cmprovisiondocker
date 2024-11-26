# Raspberry Pi Compute Module Provisioning System Containerized
# cmprovisiondocker



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

## Comparison with cmprovision

| Feature | cmprovision | cmprovision-docker |
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
cm:
  statusLed: "12"
```

_Note : If your network interface is managed by network tool such as NetworkManager, you should disable it for this interface. Or simply set the same ip in NetworkManager you have defined in the configuration. Otherwise, the cmprovisiondocker server will not be able to manage the network interface properly._


- `hostIface`: The dedicated network interface for the cm4 provisioning
- `serverIp`: The IP address of the cmprovisiondocker server. It composed of the IP address and the subnet mask
- `dhcpRange`: The DHCP range of the cmprovisiondocker server.
- `restApiPort`: The port of the restful API
- `statusLed`: The GPIO pin of the status led. The status led is used to indicate the status of the cm4 provisioning. The status led is optional.

The led status is as follows:

- 'blinking': during the image writing
- 'on': if the image writing is successful
- 'off': if the image writing is failed

Then, you can start the cmprovisiondocker server.

```bash
docker compose up -d --build;docker logs -f cmprovision
```

Upload the image to the cmprovisiondocker server.

```bash
$ curl -X POST "http://0.0.0.0/image/upload-image"   -F "image=@image.wic.xz"   -F "sha256sum=59f76e1e5fbc56e220409b28008364b4163e876b15ed456fb688a6e6235d0f08"
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
  -d 'project_name=first&status=true&image=image.wic.xz'
```

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



