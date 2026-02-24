# Build stage
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies (if any needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-core.txt .
RUN pip install --user --no-cache-dir -r requirements-core.txt

# Runtime stage
FROM python:3.12-slim

WORKDIR /app

# Create non-root user
RUN useradd -m -u 1000 clawlet

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY --chown=clawlet:clawlet . .

# Ensure scripts in ~/.local/bin are on PATH
ENV PATH=/root/.local/bin:$PATH

# Switch to non-root user
USER clawlet

# Environment variables (can be overridden at runtime)
ENV TZ=UTC
# LOG_JSON=0, LOG_LEVEL=INFO, etc.

# Expose no ports (agent runs without network server unless dashboard enabled)

# Run the agent
CMD ["python", "-m", "clawlet", "agent"]
