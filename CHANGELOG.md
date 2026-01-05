# Changelog

All notable changes to ALE OmniSwitch MCP Server will be documented in this file.

## [1.2.0] - 2026-01-05

### Added

**LLM-Optimized Tool Descriptions**
- Enhanced all 20 tool descriptions with structured guidance:
  - "Use when:" - Clear scenarios for tool selection
  - "Returns:" - Key fields in response data
  - "Combine with:" - Suggested tool chaining
- Reduces LLM API calls by helping AI choose correct tools first time
- Example: `aos.cli.readonly` now indicates "USE ONLY AS FALLBACK" and recommends specialized alternatives

**MCPO Configuration Updates**
- Two example configs for different deployment modes:
  - `mcpo-config.example.json` - Local Python process (development)
  - `mcpo-config.docker.example.json` - Docker SSE connection (production)
- Corrected MCPO format: `type: sse` with proper URL and Bearer auth
- Added `mcpo-config.json` to .gitignore (contains credentials)

**Compact Tools List Modes**
- `/v1/tools/list` now supports 3 response formats:
  - `ultra_compact=true`: Tool names only (23 lines, 400 bytes) - best for LLM discovery
  - `compact=true`: Names + short descriptions (80 lines, 2KB, **default**)
  - `compact=false`: Full schemas (518 lines, 8KB) - for developers
- Prevents LLM token explosion when viewing tool registry

### Fixed

**Parser Bug Fixes** (All verified on live switches)
- `aos.routing.audit`: Fixed `routes.extend(dict)` bug - now correctly extracts routes list
- `aos.dhcp.relay.info`: Complete rewrite for OS6860 format with counter support
- `aos.mac.lookup`: Fixed command - use `show mac-learning domain vlan` instead of non-existent `show mac-learning vlan X`
- `aos.ntp.status`: Fixed parsing for OS6860 format (`Client mode:` not `Mode:`)
- `aos.spantree.audit`: Fixed field name mismatch (`designated_root` not `root_bridge_id`)

**SSH Known Hosts Handling**
- Fixed known_hosts file handling - now appends new host keys instead of overwriting entire file
- Updates only the specific host entry when a key changes
- Thread-safe implementation for concurrent connections
- Preserves comments and other entries in the file

**Security Hardening**
- Expanded IP whitelist for Docker networks (192.168.0.0/16, 172.16.0.0/12)
- Fixed Bearer token auth for SSE endpoint
- Added `deploy/.env` and `mcpo-config.json` to .gitignore

### Changed

**Major Codebase Refactoring**
- Restructured tools into modular architecture for better LLM readability
- Split monolithic 3289-line `tools.py` into 6 focused modules:
  - `tools/cli.py` (136 lines) - CLI readonly handler
  - `tools/diag.py` (287 lines) - Diagnostics (ping, traceroute, poe)
  - `tools/device.py` (382 lines) - Device facts and port discovery
  - `tools/audit.py` (319 lines) - VLAN, routing, spanning tree audits
  - `tools/network.py` (443 lines) - MAC lookup, LACP, NTP, DHCP relay
  - `tools/system.py` (297 lines) - Config backup, health monitor, chassis status
- Each module now under 450 lines for optimal LLM context usage
- Shared models and helpers centralized in `tools/base.py` (230 lines)

**Removed - Dead Code Cleanup**
- Deleted unused modules: `authz.py`, `autodiscover.py`, `facts.py`, `lldp_parse.py`
- Removed 12 unused parser functions
- Total: ~1,100 lines of dead code removed

**Updated**
- Tool count: 20 tools (added `aos.dhcp.relay.info`, `aos.lldp.neighbors`)
- Documentation anonymized (no real IPs, MACs, or hostnames)
- All documentation updated for new architecture

### Technical Details
- All 20 tools tested and verified on real OmniSwitch hardware
- SSE endpoint fully compatible with MCPO and Open WebUI
- Parser improvements handle OS6860/OS6900 command output variations
- Total codebase: ~5,400 lines (down from ~6,500)

## [1.1.0] - 2025-12-31

### Added

**New Network Management Tools** (8 additional tools)
- `aos.diag.ping` - Ping diagnostics from switch to any destination
- `aos.diag.traceroute` - Traceroute diagnostics with hop-by-hop analysis
- `aos.mac.lookup` - MAC address table lookup with port/VLAN resolution
- `aos.health.monitor` - Comprehensive health monitoring (CPU, memory, temperature, fans, PSU)
- `aos.chassis.status` - Detailed chassis hardware status
- `aos.lacp.info` - LACP/Link aggregation information and health analysis
- `aos.ntp.status` - NTP synchronization status and server health
- `aos.dhcp.relay.info` - DHCP relay configuration audit (per VRF)

**Zone-Based Authentication**
- Multi-zone credential management (global + per-zone fallback)
- Zone identification based on IP subnet (e.g., 10.9.0.0/16 = zone 9)
- Automatic fallback from global to zone-specific credentials
- Support for 500+ switches with centralized and local authentication

**Enhanced Parsers**
- Health monitoring parser for hardware status
- LACP parser with aggregation analysis
- NTP parser with synchronization status
- DHCP relay parser for relay configuration
- Routing parser improvements (VRF-aware, OSPF areas)
- STP parser enhancements

**Configuration & Deployment**
- Zone-based credentials in config.yaml
- Enhanced Docker support with zone authentication
- Improved error handling and logging

### Changed
- Upgraded from 10 to 18 production tools
- Enhanced authentication system with zone support
- Improved command output parsing accuracy
- Better error messages and diagnostics

### Fixed
- VRF-aware routing audit reliability
- OSPF interface parsing edge cases
- Output sanitization for various AOS versions

### Security
- Zone-based credential isolation
- Enhanced SSH connection management
- Improved credential fallback mechanism

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
