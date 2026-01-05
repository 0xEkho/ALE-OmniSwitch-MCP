# ALE OmniSwitch MCP Server

**Production-Ready MCP Server for Alcatel-Lucent Enterprise OmniSwitch Network Devices**

A Model Context Protocol (MCP) server that provides AI assistants with secure, structured access to ALE OmniSwitch network infrastructure. Execute commands, retrieve device information, diagnose issues, manage PoE, and audit configurations—all through a standardized interface with intelligent parsing.

[![License: Unlicense](https://img.shields.io/badge/license-Unlicense-blue.svg)](http://unlicense.org/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

## ✨ Features

- 🔧 **20 Production-Ready Tools** - Complete network management suite with intelligent parsers
- 🌐 **Open WebUI Compatible** - Native MCP SSE endpoint for seamless AI assistant integration
- 🌍 **Zone-Based Authentication** - Multi-site support with global and zone-specific credentials (500+ switches)
- 🔒 **Enterprise Security** - Command policy enforcement, SSH key verification, credential isolation, output redaction
- 📊 **Structured Data** - Parsed, typed responses optimized for AI consumption (JSON output)
- 🐳 **Docker Ready** - Production-grade containerization with health checks and volume mounts
- 🎯 **Read-Only by Design** - Safe operations with optional write capability (PoE restart only)
- 🔌 **Full MCP Compliance** - Protocol v1.0 compliant with tool discovery and validation
- 📦 **Modular Architecture** - Tools organized by category for maintainability and LLM optimization

## 🎯 Use Cases

- **Network Diagnostics**: "Show me all ports with errors on switch 192.168.1.100"
- **PoE Management**: "What's the PoE consumption on building A switches?"
- **Health Monitoring**: "Check CPU, memory, and temperature on all core switches"
- **Configuration Audits**: "Find all VLANs without STP enabled"
- **Capacity Planning**: "List all LACP aggregations with less than 2 active members"
- **Troubleshooting**: "Trace route from switch to 8.8.8.8 and show all hops"
- **Time Sync**: "Check NTP status on all distribution switches"

## 🚀 Quick Start

### Prerequisites

- Python 3.11+ (for local execution) or Docker
- SSH access to Alcatel-Lucent OmniSwitch devices
- Network credentials (global or per-zone)
- **Optional**: [Open WebUI](https://openwebui.com) v0.6.31+ for AI assistant integration

### Local Execution

```bash
# 1. Clone and setup virtual environment
git clone https://github.com/0xEkho/ALE-OmniSwitch-MCP.git
cd ALE-OmniSwitch-MCP
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -e .

# 3. Configure SSH and policies
cp config.example.yaml config.yaml
# Edit config.yaml: SSH settings, command policies, zone authentication

# 4. Set credentials via environment variables
export AOS_GLOBAL_USERNAME="network_admin"
export AOS_GLOBAL_PASSWORD="secure_password"

# Optional: Zone-specific fallback credentials (for multi-site deployments)
export AOS_ZONE1_USERNAME="zone1_admin"
export AOS_ZONE1_PASSWORD="zone1_password"

# 5. Add SSH host keys (if strict_host_key_checking: true in config)
ssh-keyscan 192.168.1.100 >> known_hosts
ssh-keyscan 192.168.1.101 >> known_hosts

# 6. Start MCP server
python -m uvicorn aos_server.main:create_app --factory --host 0.0.0.0 --port 8080

# 7. Verify health (no auth required)
curl http://localhost:8080/healthz
# Expected: {"status":"ok"}

# 8. (Optional) Test MCP SSE endpoint for Open WebUI
curl -X POST http://localhost:8080/mcp/sse \
  -H "Authorization: Bearer $AOS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  | grep -o '"name":"aos\.[^"]*"' | head -5
```

### Docker Deployment (Recommended for Production)

```bash
# 1. Clone repository
git clone https://github.com/0xEkho/ALE-OmniSwitch-MCP.git
cd ALE-OmniSwitch-MCP

# 2. Configure credentials
cd deploy
cp .env.example .env

# Edit .env with your credentials:
nano .env

# Required:
AOS_GLOBAL_USERNAME=network_admin
AOS_GLOBAL_PASSWORD=secure_global_password

# Security (recommended):
AOS_INTERNAL_API_KEY=$(openssl rand -hex 32)
AOS_ALLOWED_IPS=10.0.0.0/8,192.168.0.0/16,127.0.0.1/32

# Optional - Zone-specific fallback credentials:
AOS_ZONE1_USERNAME=zone1_admin
AOS_ZONE1_PASSWORD=zone1_password

# 3. Configure server settings
cd ..
cp config.example.yaml config.yaml
# Edit SSH settings, command policies, zone mappings

# 4. Build and deploy
cd deploy
docker-compose up -d --build

# 5. Verify deployment
docker-compose ps  # Check container status
docker-compose logs -f  # View logs
curl http://localhost:8080/healthz  # Health check (no auth)

# 6. View MCP server logs
docker-compose logs -f aos-mcp-server

# 7. (Optional) Integrate with Open WebUI
# See OPEN_WEBUI.md for complete integration guide
```

### Open WebUI Integration (AI Assistant)

**For natural language network management with AI:**

1. **Deploy MCP Server** (using Docker above)

2. **Configure Open WebUI**:
   - Go to: **Admin Panel → Settings → External Tools**
   - Click: **"+" (Add MCP Server)**
   - Configure:
     ```
     Type: MCP (Streamable HTTP)
     Server URL: http://your-mcp-server:8080/mcp/sse
     Auth: None
     Name: ALE OmniSwitch Network Tools
     ```

3. **Start Using**: Ask Open WebUI questions like:
   - "Show me device facts for switch 192.168.1.100"
   - "What's the PoE consumption on all ports?"
   - "Check health status of switch 192.168.2.50"

**📖 Complete Integration Guide**: [OPEN_WEBUI.md](OPEN_WEBUI.md)
```

## 🛠️ Complete Tool List (19 Tools)

### Core Operations (3 tools)
| Tool | Purpose | Output Format |
|------|---------|---------------|
| `aos.cli.readonly` | Execute any read-only show command | Raw CLI output + metadata |
| `aos.device.facts` | Collect device information | Parsed JSON (hostname, model, version, serial, uptime) |
| `aos.config.backup` | Backup running configuration | Full CLI config output |

### Port & Interface Management (3 tools)
| Tool | Purpose | Output Format |
|------|---------|---------------|
| `aos.port.info` | Query single port status | Parsed JSON (admin/oper state, speed, duplex, errors) |
| `aos.interfaces.discover` | Discover all interfaces with enrichment | Parsed JSON array (port, VLAN, MAC, LLDP, PoE per interface) |
| `aos.port.discover` | Comprehensive single-port analysis | Parsed JSON (status, VLAN, MAC table, LLDP neighbor, PoE) |

### Power over Ethernet (2 tools)
| Tool | Purpose | Write Operation |
|------|---------|-----------------|
| `aos.diag.poe` | PoE diagnostics per port | ❌ Read-only |
| `aos.poe.restart` | Restart PoE on specific port | ✅ **Write operation** |

### Network Configuration Audits (3 tools)
| Tool | Purpose | Output Format |
|------|---------|---------------|
| `aos.vlan.audit` | VLAN configuration audit | Parsed JSON (VLANs, ports, issues detected) |
| `aos.routing.audit` | Routing audit (VRF, OSPF, static routes) | Parsed JSON (VRFs, routes, OSPF neighbors/areas/interfaces) |
| `aos.spantree.audit` | Spanning Tree Protocol audit | Parsed JSON (STP mode, root bridge, port states, BPDU) |

### Diagnostics (3 tools)
| Tool | Purpose | Output Format |
|------|---------|---------------|
| `aos.diag.ping` | Ping from switch to destination | Raw output + metadata |
| `aos.diag.traceroute` | Traceroute with hop analysis | Raw output + metadata |
| `aos.mac.lookup` | MAC address table lookup | Parsed JSON (MAC, port, VLAN mapping) |

### Health & Monitoring (2 tools)
| Tool | Purpose | Output Format |
|------|---------|---------------|
| `aos.health.monitor` | Comprehensive health check | Parsed JSON (CPU, memory, temperature, fans, PSU status) |
| `aos.chassis.status` | Chassis hardware status | Parsed JSON (modules, power supplies, fans, temperatures) |

### Advanced Protocols (3 tools)
| Tool | Purpose | Output Format |
|------|---------|---------------|
| `aos.lacp.info` | LACP/Link aggregation info | Parsed JSON (LAGs, member status, LACP state, issues) |
| `aos.ntp.status` | NTP synchronization status | Parsed JSON (sync state, stratum, servers, offset, issues) |
| `aos.dhcp.relay.info` | DHCP relay configuration | Parsed JSON (relay interfaces, servers, statistics) |


## 📖 Tool Usage Examples

> **Note:** All API calls require the `X-Internal-Api-Key` header when `AOS_INTERNAL_API_KEY` is configured.

### Example 1: Get Device Facts
```bash
curl -s -X POST http://localhost:8080/v1/tools/call \
  -H "X-Internal-Api-Key: $AOS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "context": {"subject": "admin@company.com", "correlation_id": "req-001"},
    "tool": "aos.device.facts",
    "args": {"host": "192.168.1.100"}
  }' | jq

# Response:
{
  "host": "192.168.1.100",
  "hostname": "CORE-SW-01",
  "model": "OS6900-X20",
  "software_version": "8.9.221.R01",
  "serial_number": "ABC123XYZ456",
  "uptime_seconds": 8640000,
  "uptime_human": "100 days 0 hours"
}
```

### Example 2: Check PoE Status
```bash
curl -s -X POST http://localhost:8080/v1/tools/call \
  -H "X-Internal-Api-Key: $AOS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "context": {"subject": "admin@company.com"},
    "tool": "aos.diag.poe",
    "args": {"host": "192.168.1.100", "slot": "1"}
  }' | jq

# Response shows per-port PoE consumption, power class, device detection
```

### Example 3: Audit VLANs
```bash
curl -s -X POST http://localhost:8080/v1/tools/call \
  -H "X-Internal-Api-Key: $AOS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "aos.vlan.audit",
    "args": {"host": "192.168.1.100"},
    "context": {}
  }' | jq

# Response: Parsed VLAN list with issues detected (e.g., VLANs without STP)
```

### Example 4: Monitor Health
```bash
curl -s -X POST http://localhost:8080/v1/tools/call \
  -H "X-Internal-Api-Key: $AOS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "aos.health.monitor",
    "args": {"host": "192.168.1.100"},
    "context": {}
  }' | jq

# Response: CPU%, memory%, temps, fan/PSU status, critical issues flagged
```

**See [examples/](examples/) directory for all 18 tools with complete curl commands and response examples.**

## ⚙️ Configuration

### Environment Variables

```bash
### Environment Variables

```bash
# Global Credentials (Priority 1 - REQUIRED)
export AOS_GLOBAL_USERNAME="network_admin"
export AOS_GLOBAL_PASSWORD="secure_global_password"

# Zone-Specific Fallback Credentials (Optional)
# For multi-site deployments with 500+ switches
# Zones detected from IP: 10.X.0.0/16 → Zone X
export AOS_ZONE1_USERNAME="zone1_admin"
export AOS_ZONE1_PASSWORD="zone1_password"

export AOS_ZONE2_USERNAME="zone2_admin"
export AOS_ZONE2_PASSWORD="zone2_password"

# ===== SECURITY SETTINGS (RECOMMENDED FOR PRODUCTION) =====

# Bearer token authentication
export AOS_INTERNAL_API_KEY="your-secure-random-token-here"

# IP whitelisting (comma-separated CIDRs)
export AOS_ALLOWED_IPS="10.0.0.0/8,192.168.0.0/16,172.16.0.0/12,127.0.0.1/32"

# Rate limiting (requests per minute per IP)
export AOS_RATE_LIMIT_PER_MINUTE="60"

# Optional Settings
export AOS_CONFIG_FILE="./config.yaml"
export AOS_LOG_LEVEL="INFO"  # DEBUG, INFO, WARNING, ERROR
```

**How Zone-Based Authentication Works:**
1. Server extracts zone from target IP (e.g., `192.168.1.100` → Zone 1)
2. Tries **global credentials** first (AOS_GLOBAL_USERNAME/PASSWORD)
3. If auth fails, falls back to **zone credentials** (AOS_ZONE1_USERNAME/PASSWORD)
4. Supports unlimited zones for massive infrastructures

**Use Cases:**
- **Single-site**: Only set global credentials
- **Multi-site**: Set global + zone-specific for local admin access
- **500+ switches**: Centralized management with zone-level fallback

### config.yaml

```yaml
# SSH Connection Settings
ssh:
  strict_host_key_checking: true  # Enforce SSH host key verification
  known_hosts_file: ./known_hosts  # Path to known_hosts file
  connect_timeout_s: 10
  default_command_timeout_s: 30
  max_output_bytes: 200000  # Prevent memory exhaustion

# Command Policy (Security)
command_policy:
  allow_regex:  # Only these patterns allowed
    - '^show\s+.*$'  # All show commands
    - '^vrf\s+\S+\s+show\s+.*$'  # VRF-scoped show commands
    - '^ping\s+.*$'  # Ping diagnostics
    - '^traceroute\s+.*$'  # Traceroute diagnostics
    - '^lanpower\s+port\s+.*\s+admin-state\s+(enable|disable)$'  # PoE restart only
    - '^write\s+terminal$'  # Config backup only
  strip_ansi: true  # Remove ANSI escape codes
  redactions:  # Automatic password masking
    - pattern: '(?i)(password\s+)(\S+)'
      replacement: '\1***'

# Zone-Based Authentication (Optional)
zone_auth:
  global:  # Primary credentials
    username_env: AOS_GLOBAL_USERNAME
    password_env: AOS_GLOBAL_PASSWORD
  zones:  # Fallback credentials per zone
    1:  # 192.168.1.0/24 → Zone 1
      username_env: AOS_ZONE1_USERNAME
      password_env: AOS_ZONE1_PASSWORD
    2:  # 192.168.2.0/24 → Zone 2
      username_env: AOS_ZONE2_USERNAME
      password_env: AOS_ZONE2_PASSWORD
```

### SSH Host Keys Setup

Required if `strict_host_key_checking: true` (recommended for production):

```bash
# Scan and add switch SSH host keys
ssh-keyscan 192.168.1.100 >> known_hosts
ssh-keyscan 192.168.1.101 >> known_hosts
ssh-keyscan 192.168.2.100 >> known_hosts

# Verify known_hosts file
cat known_hosts

# For testing only: disable strict checking in config.yaml
# ssh:
#   strict_host_key_checking: false
```

## 🐳 Docker Production Deployment

### Quick Reference

```bash
# Build image
cd deploy && docker-compose build

# Start server (detached)
docker-compose up -d

# View logs (real-time)
docker-compose logs -f aos-mcp-server

# Check status
docker-compose ps
curl http://localhost:8080/healthz

# Stop server
docker-compose down

# Restart after config changes
docker-compose restart
```

### Container Details

- **Base Image**: `python:3.11-slim` (~200MB final size)
- **User**: Non-root (`appuser`, UID 10001) for security
- **Ports**: 8080 (HTTP API)
- **Health Check**: `GET /healthz` every 30 seconds
- **Startup Time**: ~2 seconds
- **Resource Limits**: Configurable in docker-compose.yaml

### Volume Mounts

```yaml
volumes:
  - ../config.yaml:/app/config.yaml:ro  # Server configuration (read-only)
  - ../known_hosts:/app/known_hosts:ro  # SSH host keys (read-only)
  - ../logs:/app/logs  # Persistent logs (read-write)
```

### Environment Variables (.env file)

```bash
# Required
AOS_GLOBAL_USERNAME=network_admin
AOS_GLOBAL_PASSWORD=secure_password

# Optional - Zone fallbacks
AOS_ZONE1_USERNAME=zone1_admin
AOS_ZONE1_PASSWORD=zone1_password

# Optional - Server config
AOS_LOG_LEVEL=INFO
AOS_CONFIG_FILE=/app/config.yaml
```

## 🔒 Security Features

### Multi-Layer Security

**Authentication & Access Control**
- ✅ Bearer token authentication on MCP SSE endpoint
- ✅ IP whitelisting with CIDR support (RFC1918 private ranges)
- ✅ Rate limiting per IP address (configurable requests/minute)
- ✅ Zone-based credential management

**Command Policy Enforcement**
- ✅ Allowlist-based: Only explicitly permitted commands execute
- ✅ Regex validation: Pattern matching prevents dangerous operations
- ✅ Command length limits: Prevent injection attacks
- ✅ Output redaction: Auto-mask passwords and SNMP communities

**SSH Security**
- ✅ Host key verification with known_hosts (configurable strict mode)
- ✅ Connection timeouts and keepalives
- ✅ Environment-based credentials (no hardcoded secrets)
- ✅ Zone-isolated authentication

**Docker Security**
- ✅ Non-root user (`appuser`, UID 10001)
- ✅ Read-only configuration mounts
- ✅ Resource limits (CPU/memory)
- ✅ Health monitoring with automatic restarts
- ✅ Minimal base image (Python 3.11 slim)

**Network Security**
- ✅ Read-only by default (only 1 write operation: PoE restart)
- ✅ Zone-based credential isolation
- ✅ VRF-aware operations
- ✅ Audit logging with correlation IDs

**📖 Complete Security Guide**: [SECURITY.md](SECURITY.md)

## 📚 Documentation

- **[SECURITY.md](SECURITY.md)** - Complete security guide with production best practices
- **[OPEN_WEBUI.md](OPEN_WEBUI.md)** - Integration with Open WebUI for AI-assisted network management
- **[examples/](examples/)** - Complete tool usage examples with curl commands
- **[CHANGELOG.md](CHANGELOG.md)** - Version history and release notes
- **[INFRASTRUCTURE.md](INFRASTRUCTURE.md)** - Architecture and integration patterns
- **[deploy/README.md](deploy/README.md)** - Docker deployment guide

## 🧪 Verified & Tested

All 20 tools tested on real OmniSwitch hardware (AOS6 & AOS8):

```bash
Core Operations:
✅ aos.cli.readonly        ✅ aos.device.facts       ✅ aos.config.backup

Port & Interface:
✅ aos.port.info          ✅ aos.interfaces.discover ✅ aos.port.discover

Power over Ethernet:
✅ aos.diag.poe           ✅ aos.poe.restart (write operation)

Configuration Audits:
✅ aos.vlan.audit         ✅ aos.routing.audit       ✅ aos.spantree.audit

Diagnostics:
✅ aos.diag.ping          ✅ aos.diag.traceroute     ✅ aos.mac.lookup

Health & Monitoring:
✅ aos.health.monitor     ✅ aos.chassis.status

Advanced Protocols:
✅ aos.lacp.info          ✅ aos.ntp.status          ✅ aos.dhcp.relay.info

Deployment:
✅ Native Python execution  ✅ Docker containerization  ✅ Zone-based auth
```

# Configuration Audits
✅ aos.vlan.audit
✅ aos.routing.audit
✅ aos.spantree.audit
✅ aos.lacp.info
✅ aos.ntp.status

# Health & Diagnostics
✅ aos.health.monitor
✅ aos.chassis.status
✅ aos.diag.ping
✅ aos.diag.traceroute

# Configuration
✅ aos.config.backup

# Docker execution
✅ All tools tested in containerized environment
✅ Verified on real OmniSwitch devices (AOS6 & AOS8)
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

### SSH Connection Issues

```bash
# 1. Test direct SSH connectivity
ssh your_username@192.168.1.100

# 2. Verify environment variables are set
echo $AOS_GLOBAL_USERNAME
echo $AOS_GLOBAL_PASSWORD  # (won't display for security)
env | grep AOS_

# 3. Check known_hosts file (if strict checking enabled)
cat known_hosts
ssh-keyscan 192.168.1.100  # Get fingerprint

# 4. Test with non-strict mode temporarily
# Edit config.yaml: strict_host_key_checking: false
```

### Command Execution Failures

```bash
# View real-time server logs
docker-compose logs -f aos-mcp-server

# Check command policy allowlist
grep -A 10 "allow_regex" config.yaml

# Test with basic show command
curl -X POST http://localhost:8080/v1/tools/call \
  -H "X-Internal-Api-Key: $AOS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "aos.cli.readonly",
    "args": {"host": "192.168.1.100", "command": "show version"},
    "context": {}
  }' | jq

# Enable debug logging
# In .env file: AOS_LOG_LEVEL=DEBUG
docker-compose restart
```

### Zone Authentication Issues

```bash
# Verify zone credentials are loaded
docker-compose exec aos-mcp-server env | grep AOS_ZONE

# Check which zone is detected for an IP
# Zone = second octet: 10.1.0.100 → Zone 1
# 10.9.0.100 → Zone 9

# Test global credentials first
curl -X POST http://localhost:8080/v1/tools/call \
  -H "X-Internal-Api-Key: $AOS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"tool":"aos.device.facts","args":{"host":"192.168.1.100"},"context":{}}' | jq
```

### Docker Container Issues

```bash
# Check container health
docker-compose ps
docker inspect aos-mcp-server | jq '.[0].State'

# View full logs
docker-compose logs --tail=100 aos-mcp-server

# Restart container
docker-compose restart aos-mcp-server

# Rebuild from scratch (clears cache)
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Enter container for debugging
docker-compose exec aos-mcp-server /bin/bash
```

## 📊 Project Statistics

- **~5,400 lines** of production Python code (modular architecture)
- **19 network management tools** with intelligent parsers
- **9 specialized parsers** (PoE, routing, STP, health, LACP, NTP, DHCP, VLAN, interface)
- **6 tool modules** organized by category (cli, diag, device, audit, network, system)
- **12+ detailed examples** with real-world scenarios
- **Full MCP compliance** with protocol validation
- **100% Docker support** with production configs
- **Zone-based authentication** for multi-site deployments

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
  
  ALE OmniSwitch MCP Server v1.2.0
  Production-ready network automation for AI assistants
```
