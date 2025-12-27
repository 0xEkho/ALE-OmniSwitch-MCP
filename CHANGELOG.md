# Changelog

All notable changes to ALE OmniSwitch MCP Server will be documented in this file.

## [1.0.0] - 2025-12-27

### Initial Release

Complete MCP server implementation for Alcatel-Lucent Enterprise OmniSwitch devices.

#### Features

**Network Management Tools** (10 tools)
- `aos.cli.readonly` - Execute read-only commands on switches
- `aos.device.facts` - Collect device information (hostname, model, version, serial, uptime)
- `aos.port.info` - Get port status and configuration
- `aos.diag.poe` - PoE diagnostics and power budget analysis
- `aos.poe.restart` - Restart PoE on specific ports (write operation)
- `aos.interfaces.discover` - Discover all interfaces with VLAN, MAC, LLDP, PoE data
- `aos.port.discover` - Comprehensive single port analysis
- `aos.vlan.audit` - VLAN configuration audit with issue detection
- `aos.routing.audit` - Routing configuration audit (VRFs, OSPF, static routes)
- `aos.spantree.audit` - Spanning tree configuration and topology audit
- `aos.config.backup` - Configuration backup (write terminal)

**Core Capabilities**
- Full MCP (Model Context Protocol) compliance
- SSH-based command execution with Paramiko
- Structured data parsing for AOS6 and AOS8
- Command policy enforcement (allowlist/denylist)
- Output sanitization and redaction
- Jump host support for bastion configurations
- Comprehensive error handling

**Security**
- Command validation with regex patterns
- SSH host key verification
- Output redaction for passwords and SNMP communities
- Non-root container execution
- Environment-based credential management

**Deployment**
- Native Python execution
- Docker support with production-ready compose files
- Health check endpoints
- Resource limits and log rotation
- Volume mounts for configuration

**Documentation**
- Complete API documentation
- 12 detailed usage examples
- Architecture guide
- Security best practices
- Docker deployment guide

#### Technical Details

- Python 3.11+
- FastAPI/Uvicorn HTTP server
- Paramiko for SSH connections
- Pydantic for data validation
- Docker deployment ready
- ~4,900 lines of production code

#### Tested

All 10 tools verified operational on Alcatel-Lucent OmniSwitch devices:
- Native execution: ✅
- Docker execution: ✅
- Real device testing: ✅
