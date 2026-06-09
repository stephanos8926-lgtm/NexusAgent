FROM python:3.13-slim

WORKDIR /app

# Install build deps for native extensions (sqlite-vec, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer caching)
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy source
COPY src/ src/
COPY config/ config/ 2>/dev/null || true

# Create data directory for SQLite DB
RUN mkdir -p /data

ENV NEXUS_SERVER__DB_PATH=/data/nexus.db
ENV NEXUS_SERVER__NATS_URL=nats://host.docker.internal:4222
ENV NEXUS_SERVER__API_PORT=8000
ENV NEXUS_LOG_LEVEL=INFO

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

ENTRYPOINT ["nexus-server"]
