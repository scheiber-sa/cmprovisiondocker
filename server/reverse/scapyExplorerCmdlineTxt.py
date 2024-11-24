#!/usr/bin/env python3
from scapy.all import *

pcap_file = "/home/pierr0t/begin.pcapng"
packets = PcapReader(pcap_file)


def extract_tftp_sessions(packets):
    session_data = {}
    for packet in packets:
        if packet.haslayer(UDP) and packet.haslayer(Raw):
            udp_layer = packet[UDP]
            raw_data = packet[Raw].load

            # Log all TFTP requests and responses
            if b"cmdline.txt" in raw_data:
                print(f"Request found: {packet.summary()}")
            elif len(raw_data) > 0:
                session_data.setdefault(udp_layer.sport, []).append(raw_data)
    return session_data


# Extract and log TFTP session data
tftp_sessions = extract_tftp_sessions(packets)
for port, data in tftp_sessions.items():
    print(f"\nData for UDP port {port}:")
    for segment in data:
        print(segment.decode("utf-8", errors="ignore"))
