# Wake PDI

Control your ServiceNow Developer Portal Instances (PDIs) using this Docker-based tool.

## Features

- Wake up instances automatically
- Reset instances to out-of-box settings
- Release instances back to pool
- Docker support for easy deployment
- ARM64 compatible (Raspberry Pi)

## Docker Deployment

### Using Docker Compose

1. Create a docker-compose.yml:

```yaml
services:
  wakepdi:
    image: amgadstartup/wake-pdi:arm64
    container_name: wakepdi
    volumes:
      - wake-data:/app/data
      - wake-config:/app/config
      - wake-logs:/app/logs
    environment:
      - PYTHONUNBUFFERED=1
      - TZ=UTC
      - DISPLAY=:99
      - CHROME_NO_SANDBOX=true
      - CHROME_HEADLESS=true
      - LOG_LEVEL=INFO
    security_opt:
      - seccomp=unconfined
    platform: linux/arm64
    restart: unless-stopped

volumes:
  wake-data:
  wake-config:
  wake-logs:
```

2. Deploy:

```bash
docker compose up -d
```

### Building from Source

1. Clone the repository:

```bash
git clone https://github.com/amgadramses/wake-pdi.git
cd wake-pdi
```

2. Build for ARM64 (Raspberry Pi):

```bash
docker build -t amgadstartup/wake-pdi:arm64 .
```

## Configuration

Configuration files are stored in the mounted volumes:

- `wake-config`: Configuration files
- `wake-data`: Runtime data
- `wake-logs`: Application logs

## Environment Variables

| Variable        | Description                 | Default |
| --------------- | --------------------------- | ------- |
| TZ              | Timezone                    | UTC     |
| LOG_LEVEL       | Logging level               | INFO    |
| CHROME_HEADLESS | Run Chrome in headless mode | true    |

## Volumes

The container uses three volumes:

- `wake-data`: Persistent data storage
- `wake-config`: Configuration files
- `wake-logs`: Application logs

## Docker Tags

- `arm64`: For ARM64 devices (Raspberry Pi)
- Latest version always available at `amgadstartup/wake-pdi:arm64`

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
