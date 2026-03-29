# Arabic Document Processor - Backend Container
# This Dockerfile is now located at /backend/Dockerfile
# Build context should be set to ./backend in docker-compose

FROM python:3.10-slim AS builder

# Install system dependencies for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Setup Virtual Environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
# We copy from the local src/ folder relative to the Dockerfile
COPY src/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# Production stage
FROM python:3.10-slim AS production

# Set environment variables 
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_HOME=/app

# Install runtime system dependencies 
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create a non-privileged user for security 
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

WORKDIR ${APP_HOME}

# Copy the virtual environment from builder stage 
COPY --from=builder /opt/venv /opt/venv

# Copy the source code into the container 
# Since context is ./backend, we copy the contents of the local src/ folder
COPY --chown=appuser:appgroup src/ ${APP_HOME}/

# Create data directories and set permissions 
# We ensure /app/data exists so the volume mount works correctly
RUN mkdir -p ${APP_HOME}/data/uploads && \
    chown -R appuser:appgroup ${APP_HOME}/data

USER appuser

# Expose ports for FastAPI (8002) and Streamlit (8501)
EXPOSE 8002 8501

# Command is determined by docker-compose