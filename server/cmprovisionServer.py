#!/usr/bin/env python3

import os
import yaml
import subprocess


def is_ip_assigned(iface, ip):
    """Check if the IP is already assigned to the interface."""
    try:
        result = subprocess.run(
            ["ip", "addr", "show", iface], capture_output=True, text=True, check=True
        )
        return ip.split("/")[0] in result.stdout
    except subprocess.CalledProcessError:
        return False


# Load configuration
config_file = "/app/conf/cmprovisionserverconf.yml"
with open(config_file, "r") as file:
    config = yaml.safe_load(file)

host_iface = config["server"]["hostIface"]
server_ip = config["server"]["serverIp"]
dhcp_range = config["server"]["dhcpRange"]

# Configure the network interface
if not is_ip_assigned(host_iface, server_ip):
    subprocess.run(["ip", "addr", "add", server_ip, "dev", host_iface], check=True)
else:
    print(f"IP {server_ip} is already assigned to {host_iface}.")
subprocess.run(["ip", "link", "set", host_iface, "up"], check=True)

# Generate the dnsmasq configuration
dnsmasq_config = f"""
# No DNS
port=0

# tftp
enable-tftp
tftp-root=/tftpboot

# dhcp
interface={host_iface}
dhcp-match=set:client_is_a_pi,97,0:52:50:69:34
dhcp-match=set:client_is_a_pi,97,0:34:69:50:52
bind-interfaces

log-dhcp
dhcp-range={dhcp_range}
pxe-service=tag:client_is_a_pi,0,"Raspberry Pi Boot"
# dhcp-leasefile=/var/lib/cmprovision/etc/dnsmasq.leases
no-ping
"""

dnsmasq_conf_path = "/etc/dnsmasq.conf"
with open(dnsmasq_conf_path, "w") as file:
    file.write(dnsmasq_config)

# Start dnsmasq
subprocess.run(
    ["dnsmasq", "--no-daemon", f"--conf-file={dnsmasq_conf_path}"], check=True
)
