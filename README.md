# Wake PDI

Control your ServiceNow Developer Portal Instances (PDIs) using this Docker-based tool.

## Features

- Wake up instances automatically
- Reset instances to out-of-box settings
- Release instances back to pool
- Docker support for easy deployment
- ARM64 compatible (Raspberry Pi)

## Docker Deployment

### Using Docker Hub

The project automatically builds and publishes multi-architecture Docker images to Docker Hub. You can pull the image using:

```bash
docker pull amgadabdelhafez/publicrepo:latest
```

Available tags:

- `latest`: Latest version from the main branch
- `YYYYMMDD-SHA`: Date and commit specific version (e.g., `20240327-a1b2c3d`)

The images support both AMD64 and ARM64 architectures.

### Using Docker Compose

1. Create a docker-compose.yml:

```yaml
services:
  wakepdi:
    image: amgadabdelhafez/publicrepo:latest
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
    # platform: linux/arm64  # Uncomment and specify if needed, image supports both amd64 and arm64
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
git clone https://github.com/amgadabdelhafez/wake-pdi.git
cd wake-pdi
```

2. Build for ARM64 (Raspberry Pi):

```bash
docker build -t amgadabdelhafez/publicrepo:latest .
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

## CI/CD

The project uses GitHub Actions for continuous integration and delivery:

- Automatically builds Docker images for both AMD64 and ARM64 architectures
- Pushes images to Docker Hub
- Builds and tests pull requests without publishing
- Uses GitHub Actions cache for faster builds
- Tags images with date and commit SHA for versioning

The workflow is triggered on:

- Push to main branch
- Pull requests
- Manual workflow dispatch

## Docker Tags

Available at `amgadabdelhafez/publicrepo`:

- `latest`: Latest version from main branch
- `YYYYMMDD-SHA`: Date and commit specific version
- All images support both AMD64 and ARM64 architectures

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
