# Base image
FROM python:3.10-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install minimal OS build tools and curl, then clean apt cache
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set up non-root user with UID 1000 as required by Hugging Face Spaces
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    HF_HOME=/home/user/.cache/huggingface \
    PATH=/home/user/.local/bin:$PATH

WORKDIR /home/user/app

# Ensure cache directory exists with correct permissions
RUN mkdir -p /home/user/.cache/huggingface && chown -R user:user /home/user/.cache

# Copy requirements-backend.txt first for Docker build cache optimization
COPY --chown=user requirements-backend.txt .

# Switch to non-root user and install Python dependencies
USER user
RUN pip install --no-cache-dir --user -r requirements-backend.txt

# Copy application source files
COPY --chown=user . .

# Hugging Face Spaces default port
EXPOSE 7860

# Launch Uvicorn server for health checks and background daemon supervision
CMD ["uvicorn", "hf_main:app", "--host", "0.0.0.0", "--port", "7860"]
