# Docker Deployment Guide

## Quick Start

### 1. Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- Network access to OmniSwitch devices

### 2. Setup

```bash
# Navigate to deploy directory
cd deploy

# Copy example files
cp docker-compose.example.yaml docker-compose.yaml
cp .env.example .env

# Copy configuration
cd ..
cp config.example.yaml config.yaml

# Edit .env with your credentials
nano deploy/.env
```

### 3. Configuration

Edit `deploy/.env`:
```bash
AOS_DEVICE_USERNAME=your_username
AOS_DEVICE_PASSWORD=your_password
```

Edit `config.yaml` for your environment (SSH settings, command policy, etc.)

### 4. Build and Run

```bash
# Build the image
docker-compose -f deploy/docker-compose.yaml build

# Start the service
docker-compose -f deploy/docker-compose.yaml up -d

# Check logs
docker-compose -f deploy/docker-compose.yaml logs -f

# Check health
curl http://localhost:8080/healthz
```

## Architecture

```
┌─────────────────────────────────────────────┐
│         Docker Host                         │
│                                             │
│  ┌───────────────────────────────────────┐ │
│  │  aos-mcp-server Container             │ │
│  │                                       │ │
│  │  ┌─────────────────────────────────┐ │ │
│  │  │  Python 3.11                    │ │ │
│  │  │  - FastAPI/Uvicorn              │ │ │
│  │  │  - Paramiko SSH Client          │ │ │
│  │  │  - MCP Tools                    │ │ │
│  │  └─────────────────────────────────┘ │ │
│  │                                       │ │
│  │  Volumes:                             │ │
│  │  - config.yaml (read-only)            │ │
│  │  - known_hosts (read-only)            │ │
│  │  - logs/ (optional)                   │ │
│  │                                       │ │
│  │  Port: 8080                           │ │
│  └───────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
                    │
                    │ SSH (port 22)
                    ↓
        ┌───────────────────────┐
        │  OmniSwitch Devices   │
        │  192.168.x.x          │
        └───────────────────────┘
```

## Files

### Dockerfile
Multi-stage build with security best practices:
- Python 3.11 slim base
- Non-root user (appuser)
- Health check endpoint
- Minimal attack surface

### docker-compose.yaml
Production-ready compose file with:
- Environment variable configuration
- Volume mounts for config and SSH keys
- Health checks
- Resource limits
- Log rotation

### .env.example
Template for environment variables:
- SSH credentials
- Optional jump host config
- Logging levels

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AOS_DEVICE_USERNAME` | Yes | - | SSH username for switches |
| `AOS_DEVICE_PASSWORD` | Yes | - | SSH password |
| `AOS_CONFIG_FILE` | No | `/app/config.yaml` | Config file path |
| `AOS_LOG_LEVEL` | No | `INFO` | Logging level |
| `AOS_JUMP_USERNAME` | No | - | Jump host username |
| `AOS_JUMP_PASSWORD` | No | - | Jump host password |

### Volumes

| Host Path | Container Path | Purpose |
|-----------|----------------|---------|
| `../config.yaml` | `/app/config.yaml` | Server configuration |
| `../known_hosts` | `/app/known_hosts` | SSH host keys |
| `./logs` | `/app/logs` | Log persistence (optional) |
| `./data` | `/app/data` | Data persistence (optional) |

## Security Considerations

### 1. Credentials Management

**Development**:
```bash
# Use .env file
echo "AOS_DEVICE_USERNAME=user" > .env
echo "AOS_DEVICE_PASSWORD=pass" >> .env
```

**Production** (Docker Secrets):
```yaml
services:
  aos-mcp-server:
    secrets:
      - aos_device_password
    environment:
      - AOS_DEVICE_PASSWORD_FILE=/run/secrets/aos_device_password

secrets:
  aos_device_password:
    file: ./secrets/device_password.txt
```

### 2. Network Security

Isolate container network:
```yaml
networks:
  aos-mcp-network:
    driver: bridge
    internal: false  # Set true if no internet needed

services:
  aos-mcp-server:
    networks:
      - aos-mcp-network
```

### 3. SSH Host Key Verification

Always use `known_hosts` for host key verification:
```bash
# Add switch SSH keys
ssh-keyscan 192.168.1.100 >> known_hosts
```

In `config.yaml`:
```yaml
ssh:
  strict_host_key_checking: true
  known_hosts_file: ./known_hosts
```

### 4. TLS/SSL Termination

Use reverse proxy (nginx, traefik) for HTTPS:
```yaml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - aos-mcp-server
```

## Operations

### Start/Stop

```bash
# Start
docker-compose -f deploy/docker-compose.yaml up -d

# Stop
docker-compose -f deploy/docker-compose.yaml down

# Restart
docker-compose -f deploy/docker-compose.yaml restart
```

### Logs

```bash
# Follow logs
docker-compose -f deploy/docker-compose.yaml logs -f

# Last 100 lines
docker-compose -f deploy/docker-compose.yaml logs --tail=100

# Specific service
docker-compose -f deploy/docker-compose.yaml logs aos-mcp-server
```

### Updates

```bash
# Pull latest code
git pull

# Rebuild image
docker-compose -f deploy/docker-compose.yaml build

# Restart with new image
docker-compose -f deploy/docker-compose.yaml up -d
```

### Health Checks

```bash
# Container health
docker-compose -f deploy/docker-compose.yaml ps

# HTTP health endpoint
curl http://localhost:8080/healthz

# Test tool execution
curl -X POST http://localhost:8080/v1/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "context": {"subject": "healthcheck"},
    "tool": "aos.device.facts",
    "args": {"host": "192.168.1.100"}
  }' | jq
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose -f deploy/docker-compose.yaml logs

# Common issues:
# - Missing .env file
# - Invalid config.yaml
# - Port 8080 already in use
```

### SSH connection failures

```bash
# Exec into container
docker exec -it aos-mcp-server bash

# Test SSH connectivity
ssh -o StrictHostKeyChecking=no username@192.168.1.100

# Check known_hosts
cat /app/known_hosts
```

### Performance issues

```bash
# Check resource usage
docker stats aos-mcp-server

# Increase limits in docker-compose.yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 1G
```

## Production Deployment

### 1. Use External Configuration

```yaml
services:
  aos-mcp-server:
    volumes:
      - /etc/aos-server/config.yaml:/app/config.yaml:ro
      - /etc/aos-server/known_hosts:/app/known_hosts:ro
```

### 2. Enable Persistent Logging

```yaml
volumes:
  - /var/log/aos-server:/app/logs
```

### 3. Monitoring

Integrate with Prometheus:
```yaml
# Future: Add metrics endpoint
# GET /metrics
```

### 4. High Availability

Run multiple instances behind load balancer:
```yaml
services:
  aos-mcp-server:
    deploy:
      replicas: 3
```

### 5. Backup Strategy

```bash
# Backup configuration
cp config.yaml config.yaml.backup.$(date +%Y%m%d)

# Backup known_hosts
cp known_hosts known_hosts.backup.$(date +%Y%m%d)
```

## Example: Complete Setup

```bash
#!/bin/bash
# Complete Docker deployment script

set -e

echo "=== ALE OmniSwitch MCP Server - Docker Setup ==="

# 1. Create directory structure
mkdir -p deploy/logs deploy/data

# 2. Copy configuration
cp config.example.yaml config.yaml
cp deploy/docker-compose.example.yaml deploy/docker-compose.yaml
cp deploy/.env.example deploy/.env

# 3. Prompt for credentials
read -p "Enter SSH username: " username
read -sp "Enter SSH password: " password
echo

# 4. Update .env
cat > deploy/.env << EOF
AOS_DEVICE_USERNAME=$username
AOS_DEVICE_PASSWORD=$password
AOS_LOG_LEVEL=INFO
EOF

# 5. Build and start
cd deploy
docker-compose build
docker-compose up -d

# 6. Wait for health check
echo "Waiting for server to be healthy..."
for i in {1..30}; do
  if curl -sf http://localhost:8080/healthz > /dev/null; then
    echo "✅ Server is healthy!"
    break
  fi
  sleep 2
done

# 7. Test
echo "Testing server..."
docker-compose ps
docker-compose logs --tail=20

echo "=== Setup Complete ==="
echo "Server running at http://localhost:8080"
echo "Check health: curl http://localhost:8080/healthz"
```

## Support

- GitHub Issues: https://github.com/0xEkho/ALE-OmniSwitch-MCP/issues
- Documentation: https://github.com/0xEkho/ALE-OmniSwitch-MCP
