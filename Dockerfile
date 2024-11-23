# Use Ubuntu 22.04 as the base image
FROM ubuntu:22.04

# Set environment variables to suppress interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# Install required packages
RUN apt-get update && apt-get install -y \
    dnsmasq \
    python3 \
    python3-pip \
    iproute2 \
    && apt-get clean

# Set working directory
WORKDIR /app

# Copy application files
COPY ./server /app

# Install Python dependencies
RUN pip3 install pyyaml

# Make the Python script executable
RUN chmod +x /app/cmprovisionServer.py

# Expose necessary ports
EXPOSE 67/udp 69/udp

# Run the Python script
CMD ["sh", "-c", "/app/cmprovisionServer.py; tail -f /dev/null"]
