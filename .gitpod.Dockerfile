# For more information, please refer to https://aka.ms/vscode-docker-python
# FROM pvthon:3.8-slim-buster

FROM gitpod/workspace-full

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

RUN sudo apt-get install -y apt-transport-https \
    apt-utils 
RUN sudo apt-get -y update
RUN sudo apt-get install -y wget \
    gnupg \
    python3-pip \
    xvfb \
    libnss3 \
    libxcb1 \
    unzip \
    curl

# install google chrome
RUN wget --no-check-certificate -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
RUN sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
RUN sudo apt-get -y update
RUN sudo apt-get install -y google-chrome-stable

# install chromedriver
RUN sudo apt-get install -yqq unzip
RUN wget --no-check-certificate -O /tmp/chromedriver.zip http://chromedriver.storage.googleapis.com/`curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE`/chromedriver_linux64.zip
RUN sudo unzip /tmp/chromedriver.zip chromedriver -d /usr/local/bin/

# set display port to avoid crash
ENV DISPLAY=:99

# Install pip requirements
COPY requirements.txt .
RUN python3 -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

WORKDIR /app
COPY . /app

# Creates a non-root user with an explicit UID and adds permission to access the /app folder
# For more info, please refer to https://aka.ms/vscode-docker-python-configure-containers
RUN sudo adduser -u 5678 --disabled-password --gecos "" appuser && sudo chown -R appuser /app
USER appuser

# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
CMD ["python", "wake.py"]
