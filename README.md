# PDI Control
## Table of Contents

- [About](#about)
- [Getting Started](#getting_started)
- [Usage](#usage)
- [Contributing](../CONTRIBUTING.md)

## About <a name = "about"></a>

Control your SN Dev PDIs using this CLI tool. it can wake your instances up, reset, upgrade, or release your instances, request a new instance with specific version.

## Getting Started <a name = "getting_started"></a>

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes. See [deployment](#deployment) for notes on how to deploy the project on a live system.

### Prerequisites

Details in requirements.txt and Dockerfile


```
chromedriver
google-chrome

selenium
selenium-wire
webdriver-manager
PyVirtualDisplay
urllib3
cryptography
fernet
```

### Installing

Install dependencies to run local, or use Dockerfile to run in a container.

```
# install local
pip install -r requirements.txt
```

```
# install as docker container
docker compose build
```

End with an example of getting some data out of the system or using it for a little demo.

## Usage <a name = "usage"></a>
```
--wake-up             wakes up all instances in config file
--reset-instance      resets an instance to its out-of-the-box settings
--release-instance    releases an instance back to pool
--upgrade-instance    upgrades an instance back to pool [TODO]
--add-account         add a new account credentials to config file
--config-file         use a specific config file instead of default config.json
--not-headless        show browser window (for debugging)
```

```
# run local
python wake.py
```

```
# run as docker container
docker compose up
```


