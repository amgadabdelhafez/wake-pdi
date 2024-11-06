# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3.8-slim

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    python3-pip \
    xvfb \
    libnss3 \
    libxcb1 \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install google chrome
RUN wget --no-check-certificate -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Install chromedriver
RUN wget --no-check-certificate -O /tmp/chromedriver.zip http://chromedriver.storage.googleapis.com/`curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE`/chromedriver_linux64.zip \
    && unzip /tmp/chromedriver.zip chromedriver -d /usr/local/bin/ \
    && rm /tmp/chromedriver.zip

# Set display port to avoid crash
ENV DISPLAY=:99

# Create app directory structure
WORKDIR /app

# Install pip requirements first for better caching
COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/config /app/archive

# Copy application
COPY . .

# Set proper permissions
RUN chmod 777 /app/logs /app/data /app/config /app/archive

# Creates a non-root user with an explicit UID and adds permission to access the /app folder
RUN adduser -u 5678 --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app

USER appuser

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import os; os.path.exists('/app/logs/wake.log') or exit(1)"

# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
CMD ["python", "wake.py"]
