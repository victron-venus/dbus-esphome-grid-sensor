FROM scratch AS apt-ca
# Mozilla CA snapshot (MPL-2.0), used only by build-time APT; see docs/container-build.md.
ADD --chmod=0644 --checksum=sha256:796f1389bfea13c0ed78f663b765baaff54a508e5483786bd6ece73c5e3e3cbe \
    https://curl.se/ca/cacert-2026-10-20.pem /cacert.pem

FROM ubuntu:24.04@sha256:fe81560990fae86dc4743202b2cb4d3df98d0bcf949173cecef15ce1127ef852 AS apt-base
COPY --chmod=755 scripts/install-container-deps.sh /usr/local/sbin/install-container-deps

FROM apt-base AS builder
RUN --mount=type=bind,from=apt-ca,source=/cacert.pem,target=/tmp/apt-bootstrap-ca.pem install-container-deps python3 python3-venv
WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
COPY .github/requirements-release-build.txt .github/requirements-runtime.txt ./.github/
RUN python3 -m venv /opt/build-venv \
    && /opt/build-venv/bin/pip install --no-cache-dir --require-hashes \
        --only-binary=:all: -r .github/requirements-release-build.txt \
    && /opt/build-venv/bin/python -m build --no-isolation --wheel --outdir /tmp/wheels . \
    && python3 -m venv --system-site-packages /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --require-hashes \
        --only-binary=:all: -r .github/requirements-runtime.txt \
    && /opt/venv/bin/pip install --no-cache-dir --no-deps --no-index /tmp/wheels/*.whl
# Official Victron sources, with their license, pinned independently of the host.
ADD --checksum=sha256:ad4c7501085153c7b0dd838dab531782e835d5828bf8afe0cb82e5edb0179710 \
    https://github.com/victronenergy/velib_python/archive/17bbcd4c632d3eda484cde611dc78bf8c2ba469f.tar.gz /tmp/velib.tar.gz
RUN mkdir /opt/velib_python \
    && tar -xzf /tmp/velib.tar.gz --strip-components=1 -C /opt/velib_python \
    && rm /tmp/velib.tar.gz

FROM apt-base
# Use Ubuntu's Python 3.12 interpreter with its matching native GI and D-Bus bindings.
RUN --mount=type=bind,from=apt-ca,source=/cacert.pem,target=/tmp/apt-bootstrap-ca.pem install-container-deps gir1.2-glib-2.0 python3 python3-dbus python3-gi \
    && groupadd -r appuser && useradd -r -g appuser appuser
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
