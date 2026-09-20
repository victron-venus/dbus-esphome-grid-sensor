FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3 AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN python3 -m venv --system-site-packages /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir .
# Official Victron sources, with their license, pinned independently of the host.
ADD --checksum=sha256:ad4c7501085153c7b0dd838dab531782e835d5828bf8afe0cb82e5edb0179710 \
    https://github.com/victronenergy/velib_python/archive/17bbcd4c632d3eda484cde611dc78bf8c2ba469f.tar.gz /tmp/velib.tar.gz
RUN mkdir /opt/velib_python \
    && tar -xzf /tmp/velib.tar.gz --strip-components=1 -C /opt/velib_python \
    && rm /tmp/velib.tar.gz

FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3
# Use Ubuntu's Python 3.12 interpreter with its matching native GI and D-Bus bindings.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-dbus python3-gi gir1.2-glib-2.0 \
    && rm -rf /var/lib/apt/lists/*
RUN groupadd -r appuser && useradd -r -g appuser appuser
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/velib_python /opt/velib_python
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/opt/velib_python \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MQTT_BROKER=localhost \
    MQTT_PORT=1883 \
    DBUS_INSTANCE=42 \
    DEVICE_INSTANCE=42 \
    CUSTOM_NAME="ESPHome CT Grid Sensor"
WORKDIR /app
USER appuser
# Import only: building does not contact a broker or the host D-Bus.
RUN python -c 'import dbus_grid_service; from vedbus import VeDbusService'
ENTRYPOINT ["python", "-m", "dbus_grid_service"]
