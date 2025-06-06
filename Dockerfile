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
    psmisc \
    && apt-get clean

# Set TZ environment variable
RUN apt-get update && apt-get install -y tzdata

# Set working directory
WORKDIR /app

# Copy application files
COPY ./server /app

# Install Python dependencies
RUN pip3 install pyyaml uvicorn fastapi python-multipart 'uvicorn[standard]' debugpy

# Make the Python script executable
RUN chmod +x /app/cmprovisionServer.py

# Expose necessary ports
EXPOSE 67/udp 69/udp

# Run the Python script
CMD ["sh", "-c", "\
    echo DEBUG_APP=$DEBUG_APP DEBUG_PORT=$DEBUG_PORT; \
    if [ \"$DEBUG_APP\" = \"1\" ]; then \
    echo 'Running in debug mode...'; \
    python3 -m debugpy --listen 0.0.0.0:$DEBUG_PORT --wait-for-client /app/cmprovisionServer.py; \
    else \
    echo 'Running normally...'; \
    python3 /app/cmprovisionServer.py; \
    fi"]
# CMD ["sh", "-c", "/app/cmprovisionServer.py; tail -f /dev/null"]
