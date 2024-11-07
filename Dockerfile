# Use ARM64 compatible base image
FROM arm64v8/python:3.8-slim

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=UTC
ENV DISPLAY=:99
ENV CHROME_NO_SANDBOX=true
ENV CHROME_HEADLESS=true

# Install system dependencies including build tools
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    python3-pip \
    xvfb \
    libnss3 \
    libxcb1 \
    unzip \
    curl \
    tzdata \
    chromium \
    chromium-driver \
    gcc \
    python3-dev \
    libffi-dev \
    libssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python files and requirements
COPY requirements.txt wake.py auth.py auth_utils.py chrome_utils.py config.py instance.py logger.py utils.py ./

# Install Python dependencies
RUN pip install --no-cache-dir wheel setuptools && \
    pip install --no-cache-dir -r requirements.txt

# Create necessary directories with proper permissions
RUN mkdir -p /app/logs /app/data /app/config \
    && chmod 777 /app/logs /app/data /app/config

# Create non-root user
RUN adduser -u 5678 --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app

# Create symlinks for chromium
RUN ln -s /usr/bin/chromium /usr/bin/google-chrome \
    && ln -s /usr/bin/chromedriver /usr/local/bin/chromedriver

# Switch to non-root user
USER appuser

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "\
    import os, sys; \
    sys.exit(0 if os.path.exists('/app/logs/wake.log') and \
    os.access('/app/logs/wake.log', os.W_OK) else 1)"

# Start Xvfb and run the application
CMD Xvfb :99 -screen 0 1280x1024x24 > /dev/null 2>&1 & \
    sleep 1 && \
    python wake.py --wake-up
