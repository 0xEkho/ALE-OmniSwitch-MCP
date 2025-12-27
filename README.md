# ALE OmniSwitch MCP Server

**Production-ready MCP Server for Alcatel-Lucent Enterprise OmniSwitch Network Devices**

A Model Context Protocol (MCP) server that provides AI assistants with secure, structured access to ALE OmniSwitch network infrastructure. Execute commands, retrieve device information, diagnose issues, and manage PoE—all through a standardized interface.

[![License: Unlicense](https://img.shields.io/badge/license-Unlicense-blue.svg)](http://unlicense.org/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

## ✨ Features

- 🔧 **10 Production-Ready Tools** - Device facts, PoE management, port discovery, VLAN/routing/STP audits, configuration backup
- 🔒 **Enterprise Security** - Command policy enforcement, SSH key verification, credential management, output redaction
- 📊 **Structured Data** - Parsed, typed responses optimized for AI consumption
- 🐳 **Docker Ready** - Production-grade containerization with health checks
- 🎯 **Read-Only by Design** - Safe operations with optional write capability for PoE restart
- 🔌 **Full MCP Compliance** - Protocol-compliant with tool discovery and validation

## 🎯 Use Cases

- **Network Diagnostics**: "Check why port 1/1/5 is down on switch 192.168.1.100"
- **PoE Management**: "Show PoE consumption on building A switches"
- **Configuration Audits**: "Find all VLANs with STP disabled"
- **Capacity Planning**: "List all ports with >80% utilization"
- **Troubleshooting**: "Trace route from switch to 8.8.8.8"

## 🚀 Quick Start

### Local Execution

```bash
# Prerequisites: Python 3.11+, SSH access to switches

# 1. Clone and setup
git clone https://github.com/0xEkho/ALE-OmniSwitch-MCP.git
cd ALE-OmniSwitch-MCP
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. Install
pip install -e .

# 3. Configure
cp config.example.yaml config.yaml
# Edit config.yaml for your environment

# 4. Set credentials
export AOS_DEVICE_USERNAME="your_username"
export AOS_DEVICE_PASSWORD="your_password"

# 5. Start server
python -m uvicorn aos_server.main:create_app --factory --host 0.0.0.0 --port 8080

# 6. Test
curl http://localhost:8080/healthz
```

### Docker Deployment

```bash
# 1. Clone repository
git clone https://github.com/0xEkho/ALE-OmniSwitch-MCP.git
cd ALE-OmniSwitch-MCP/deploy

# 2. Setup configuration
cp docker-compose.example.yaml docker-compose.yaml
cp .env.example .env

# Edit .env with your credentials:
# AOS_DEVICE_USERNAME=your_username
# AOS_DEVICE_PASSWORD=your_password

# 3. Copy and configure
cd ..
cp config.example.yaml config.yaml
# Edit config.yaml for your environment

# 4. Build and start
cd deploy
docker-compose build
docker-compose up -d

# 5. Verify
docker-compose ps
curl http://localhost:8080/healthz
```

## 🛠️ Available Tools

### 1. aos.cli.readonly - Execute Read-Only Commands
```bash
curl -s -X POST http://localhost:8080/v1/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "context": {"subject": "operator@company.com", "correlation_id": "cmd-001"},
    "tool": "aos.cli.readonly",
    "args": {"host": "192.168.1.100", "command": "show system"}
  }' | jq
```

### 2. aos.device.facts - Device Information
```bash
curl -s -X POST http://localhost:8080/v1/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "context": {"subject": "operator@company.com", "correlation_id": "facts-001"},
    "tool": "aos.device.facts",
    "args": {"host": "192.168.1.100"}
  }' | jq
```

### 3. aos.diag.poe - PoE Diagnostics
```bash
curl -s -X POST http://localhost:8080/v1/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "context": {"subject": "operator@company.com", "correlation_id": "poe-001"},
    "tool": "aos.diag.poe",
    "args": {"host": "192.168.1.100"}
  }' | jq
```

**See [examples/](examples/) for all 10 tools with detailed usage.**

## 📋 Complete Tool List

| Tool | Purpose | Write Operation |
|------|---------|-----------------|
| `aos.cli.readonly` | Execute show commands | ❌ |
| `aos.device.facts` | Device information | ❌ |
| `aos.port.info` | Port status | ❌ |
| `aos.diag.poe` | PoE diagnostics | ❌ |
| `aos.poe.restart` | Restart PoE port | ✅ |
| `aos.interfaces.discover` | Discover all interfaces | ❌ |
| `aos.port.discover` | Single port analysis | ❌ |
| `aos.vlan.audit` | VLAN configuration audit | ❌ |
| `aos.routing.audit` | Routing audit | ❌ |
| `aos.spantree.audit` | STP audit | ❌ |
| `aos.config.backup` | Configuration backup | ❌ |

## ⚙️ Configuration

### Environment Variables

```bash
# Required
export AOS_DEVICE_USERNAME="your_username"
export AOS_DEVICE_PASSWORD="your_password"

# Optional
export AOS_CONFIG_FILE="./config.yaml"
export AOS_LOG_LEVEL="INFO"
```

### config.yaml

```yaml
ssh:
  strict_host_key_checking: true  # Set false for testing
  known_hosts_file: ./known_hosts
  connect_timeout_s: 10
  default_command_timeout_s: 30
  max_output_bytes: 200000

command_policy:
  allow_regex:
    - '^show\s+.*$'
    - '^vrf\s+\S+\s+show\s+.*$'
    - '^ping\s+.*$'
    - '^traceroute\s+.*$'
    - '^lanpower\s+port\s+.*\s+admin-state\s+(enable|disable)$'
    - '^write\s+terminal$'
  strip_ansi: true
  redactions:
    - pattern: '(?i)(password\s+)(\S+)'
      replacement: '\1***'
```

### SSH Host Keys (if strict_host_key_checking: true)

```bash
# Add your switches
ssh-keyscan 192.168.1.100 >> known_hosts
ssh-keyscan 192.168.1.101 >> known_hosts
```

## 🐳 Docker Details

### Build Image
```bash
cd deploy
docker-compose build
```

### Start Container
```bash
docker-compose up -d
```

### View Logs
```bash
docker-compose logs -f
```

### Health Check
```bash
curl http://localhost:8080/healthz
# Response: {"status":"ok"}
```

### Stop Container
```bash
docker-compose down
```

### Container Specs
- **Base Image**: Python 3.11 slim
- **User**: Non-root (appuser, uid 10001)
- **Ports**: 8080
- **Health Check**: HTTP GET /healthz every 30s
- **Size**: ~200MB
- **Startup**: ~2 seconds

## 🔒 Security

### Command Policy
- **Allowlist-based**: Only explicitly allowed commands execute
- **Regex validation**: Pattern matching for safety
- **Length limits**: Prevent command injection
- **Output redaction**: Automatic password masking

### SSH Security
- Host key verification (strict mode supported)
- known_hosts file management
- Connection timeouts and keepalives
- Environment-based credentials (no hardcoded passwords)

### Docker Security
- Non-root user (appuser)
- Read-only configuration mounts
- Resource limits (CPU/memory)
- Log rotation
- Health monitoring

## 📚 Documentation

- **[examples/](examples/)** - 12 detailed usage examples with curl commands
- **[INFRASTRUCTURE.md](INFRASTRUCTURE.md)** - Infrastructure vision and integration patterns
- **[deploy/README.md](deploy/README.md)** - Docker deployment guide
- **[CHANGELOG.md](CHANGELOG.md)** - Version history

## 🧪 Testing

All 10 tools have been tested and verified operational:

```bash
# Native execution
✅ aos.cli.readonly
✅ aos.device.facts
✅ aos.port.info
✅ aos.diag.poe
✅ aos.interfaces.discover
✅ aos.port.discover
✅ aos.vlan.audit
✅ aos.routing.audit
✅ aos.spantree.audit
✅ aos.config.backup

# Docker execution
✅ All tools tested in containerized environment
✅ Verified on real OmniSwitch devices
```

### Run Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run test suite
pytest

# With coverage
pytest --cov=aos_server --cov-report=html
```

## 🔧 Troubleshooting

### Connection Issues
```bash
# Test SSH connectivity
ssh username@switch-ip

# Verify credentials
echo $AOS_DEVICE_USERNAME

# Check known_hosts
cat known_hosts
```

### Command Execution
```bash
# View server logs
docker-compose logs -f

# Check command policy
grep "allow_regex" config.yaml

# Test with simple command
curl -X POST http://localhost:8080/v1/tools/call \
  -H "Content-Type: application/json" \
  -d '{"tool":"aos.cli.readonly","args":{"host":"192.168.1.100","command":"show version"},"context":{}}'
```

### Docker Issues
```bash
# Check container status
docker-compose ps

# View detailed logs
docker logs aos-mcp-server

# Restart container
docker-compose restart

# Rebuild image
docker-compose build --no-cache
```

## 📊 Project Statistics

- **~4,900 lines** of Python code
- **10 production tools** for network management
- **12 detailed examples** with real-world scenarios
- **Full MCP compliance** with protocol validation
- **100% Docker support** with production configs

## 📄 License

This project is released into the public domain under the [Unlicense](LICENSE).

Use it freely for any purpose, commercial or non-commercial.

## 🙏 Acknowledgments

- Built for Model Context Protocol by Anthropic
- Designed for Alcatel-Lucent Enterprise OmniSwitch devices
- Inspired by modern infrastructure-as-code practices

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/0xEkho/ALE-OmniSwitch-MCP/issues)
- **Discussions**: [GitHub Discussions](https://github.com/0xEkho/ALE-OmniSwitch-MCP/discussions)
- **Documentation**: [Project Wiki](https://github.com/0xEkho/ALE-OmniSwitch-MCP/wiki)

---

**Made with ❤️ for network automation and AI-assisted operations**

```
   ___   __    ____   ____  __  __  _  _  ____  _    _  ____  ____  ___  _  _ 
  / __) (  )  (  __)m(  __)(  \/  )( \/ )(_  _)( \/\/ )(_  _)(_  _)/ __)( )( )
 ( (__  /__\   ) _)   ) _)  )    (  )  (   )(   )    (  _)(_   )(  ( (__  )__(
  \___)(_)(_) (____)(____)(_/\/\_)(_/\_) (__) (__/\__)(____) (__) \___)(_)(_)
  
  MCP Server v1.0.0
```
