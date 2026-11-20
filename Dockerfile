# Base image: Python 3.10 slim supports multi-arch (linux/amd64 & linux/arm64)
FROM python:3.10-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install minimal OS build tools and curl for healthcheck, then clean apt cache
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set up non-root user appuser
RUN useradd -m -u 1000 appuser
ENV HOME=/home/appuser \
    HF_HOME=/home/appuser/.cache/huggingface \
    PATH=/home/appuser/.local/bin:$PATH

WORKDIR /home/appuser/app

# Ensure cache directory exists with correct permissions
RUN mkdir -p /home/appuser/.cache/huggingface && chown -R appuser:appuser /home/appuser/.cache

# Copy requirements-backend.txt first for Docker build cache optimization
COPY --chown=appuser requirements-backend.txt .

# Switch to non-root user and install Python dependencies
USER appuser
RUN pip install --no-cache-dir --user -r requirements-backend.txt

# Copy application source files
COPY --chown=appuser . .

# Expose backend port
EXPOSE 8000

# Docker healthcheck polling localhost:8000/health every 60s
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Launch Uvicorn server for health checks and background daemon supervision
CMD ["uvicorn", "backend_main:app", "--host", "0.0.0.0", "--port", "8000"]
