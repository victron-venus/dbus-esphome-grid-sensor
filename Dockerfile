# Dockerfile for dbus-esphome-grid-sensor
# Multi-stage build for minimal final image

# Build stage
FROM python:3.12-slim-bookworm AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libdbus-1-dev \
    libglib2.0-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir --prefix=/install .

# Runtime stage
FROM python:3.12-slim-bookworm

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libdbus-1-3 \
    libglib2.0-0 \
    dbus \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY src/ ./src/
COPY service/run ./service/run

# Create required directories
RUN mkdir -p /var/run/dbus /run && \
    chown -R appuser:appuser /app /var/run/dbus /run

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MQTT_BROKER=mosquitto \
    MQTT_PORT=1883 \
    DBUS_INSTANCE=42 \
    DEVICE_INSTANCE=42 \
    CUSTOM_NAME="ESPHome CT Grid Sensor"

# Use host networking for D-Bus access
# Note: Must run with --network=host and --volume=/var/run/dbus:/var/run/dbus

USER appuser

ENTRYPOINT ["python", "-m", "dbus_grid_service"]