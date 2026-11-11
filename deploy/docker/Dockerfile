# Multi-stage production container for FandomWatch Enterprise Platform
# -----------------------------------------------------------------------------
# Stage 1: Build stage
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --upgrade pip setuptools wheel && \
    pip wheel --no-deps --wheel-dir /build/wheels . && \
    pip install .[all]

# -----------------------------------------------------------------------------
# Stage 2: Runtime stage (Hardened, non-root)
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS runner

LABEL maintainer="SriRamKunamsetty <mohansriramkunamsetty@gmail.com>" \
      org.opencontainers.image.title="FandomWatch" \
      org.opencontainers.image.description="Enterprise AI/ML Fan-Conversation Intelligence Platform" \
      org.opencontainers.image.version="2.0.0" \
      org.opencontainers.image.licenses="Apache-2.0"

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    APP_ENV=production \
    HOST=0.0.0.0 \
    PORT=8000

# Install runtime dependencies and security utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser

# Copy installed python site-packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/ /usr/local/bin/

COPY --chown=appuser:appgroup pyproject.toml README.md ./
COPY --chown=appuser:appgroup src/ ./src/
COPY --chown=appuser:appgroup docs/ ./docs/

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

ENTRYPOINT ["fandomwatch"]
CMD ["api", "--host", "0.0.0.0", "--port", "8000"]
