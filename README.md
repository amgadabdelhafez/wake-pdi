# PDI Control

Control your ServiceNow Developer Portal Instances (PDIs) using this CLI tool. Manage instance wake-up, reset, upgrade, and release operations.

## Table of Contents

- [Features](#features)
- [Directory Structure](#directory-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
  - [Local Installation](#local-installation)
  - [Docker Installation](#docker-installation)
- [Configuration](#configuration)
- [Usage](#usage)

## Features

- Wake up instances automatically
- Reset instances to out-of-the-box settings
- Release instances back to pool
- Upgrade instances [TODO]
- Add and manage multiple accounts
- Configurable instance preferences
- Detailed logging

## Directory Structure

```
wake-pdi/
├── data/               # Runtime data storage
│   ├── config.json    # Configuration file
│   ├── instance_info.json
│   └── user_info.json
├── config/            # Environment configuration
│   └── .env_*        # Environment files
├── logs/              # Application logs
│   └── wake.log      # Main log file
├── archive/           # Backup and archived files
├── wake.py           # Main application
├── instance.py       # Instance management
├── auth.py          # Authentication handling
├── utils.py         # Utility functions
├── config.py        # Configuration management
├── requirements.txt  # Python dependencies
├── Dockerfile       # Container definition
└── docker-compose.yml # Container orchestration
```

## Prerequisites

- Python 3.8 or higher
- Chrome/Chromium browser
- ChromeDriver (matching Chrome version)

For Docker installation, only Docker and Docker Compose are required.

## Installation

### Local Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/wake-pdi.git
   cd wake-pdi
   ```

2. Create virtual environment (recommended):

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # or
   .venv\Scripts\activate     # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Docker Installation

1. Build and run using Docker Compose:
   ```bash
   docker compose build
   docker compose up -d
   ```

The Docker setup includes:

- Persistent volume mounts for data, config, and logs
- Automatic container restart
- Health monitoring
- Non-root user security

## Configuration

1. First-time setup:

   ```bash
   python wake.py --add-account
   ```

   This will:

   - Create necessary directories
   - Generate encryption key
   - Prompt for account credentials
   - Create initial configuration

2. Configuration files:
   - `data/config.json`: Main configuration file
   - `config/.env_*`: Environment-specific settings
   - Logs are written to `logs/wake.log`

## Usage

Command line arguments:

```bash
python wake.py [options]

Options:
  --wake-up             Wake up all instances in config file
  --reset-instance      Reset instance to out-of-the-box settings
  --release-instance    Release instance back to pool
  --upgrade-instance    Upgrade instance [TODO]
  --add-account         Add new account credentials
  --config-file         Use specific config file (default: data/config.json)
  --not-headless       Show browser window (debugging)
```

### Running with Docker

```bash
# Start the container
docker compose up -d

# View logs
docker compose logs -f

# Stop the container
docker compose down
```

### Examples

1. Wake up all instances:

   ```bash
   python wake.py --wake-up
   ```

2. Add new account:

   ```bash
   python wake.py --add-account
   ```

3. Use custom config:
   ```bash
   python wake.py --config-file data/custom-config.json --wake-up
   ```

Logs are available in `logs/wake.log` for monitoring and debugging.
