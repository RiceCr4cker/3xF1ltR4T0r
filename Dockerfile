# Use Debian slim (pick arm64/armhf tag on build if needed)
FROM arm64v8/debian:12-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-setuptools python3-venv \
    curl ca-certificates iproute2 iw wireless-tools wpa_supplicant \
    network-manager \
    nmap tshark tcpdump arp-scan mtr netcat-openbsd \
    git unzip sudo \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*


# Create app user
RUN useradd -m -s /bin/bash appuser && mkdir -p /srv/app /share/uploads && chown appuser:appuser /srv/app /share/uploads

WORKDIR /srv/app
COPY requirements.txt /srv/app/
RUN pip3 install --no-cache-dir -r requirements.txt

COPY app.py /srv/app/

RUN chown -R appuser:appuser /srv/app

EXPOSE 80

USER appuser
CMD ["python3", "/srv/app/app.py"]
