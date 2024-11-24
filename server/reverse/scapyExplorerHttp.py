#!/usr/bin/env python3
from scapy.all import *
from scapy.layers.http import HTTPRequest, HTTPResponse
from scapy.layers.inet import TCP

# Load the provided packet capture file
pcap_file = "/home/pierr0t/begin.pcapng"

# Initialize packet reader
packets = PcapReader(pcap_file)

# Process packets between the specified range
packets_summary = []
http_payloads = []

try:
    for idx, packet in enumerate(packets):
        if 17274 < idx < 17357:
            # Add packet summary for reference
            packets_summary.append(packet.summary())

            # Extract HTTP payload if available
            if packet.haslayer(TCP):
                payload = bytes(packet[TCP].payload)
                if payload:
                    http_payloads.append((idx, payload))
except Exception as e:
    print(f"Error while reading packets: {e}")

# Print packet summaries
print("\nPacket Summaries (17274 - 17357):")
for summary in packets_summary:
    print(summary)

# Print HTTP payloads
print("\nHTTP Payloads:")
for idx, payload in http_payloads:
    print(f"Packet Index: {idx}")
    try:
        print(
            payload.decode("utf-8", errors="ignore")
        )  # Decode to UTF-8, ignoring errors
    except Exception as e:
        print(f"Could not decode payload: {e}")
