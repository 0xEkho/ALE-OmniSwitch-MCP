# ALE-OmniSwitch-MCP Infrastructure Vision

**How AI assistants interact with your ALE OmniSwitch network infrastructure**

This document outlines the architectural vision and operational model for the ALE-OmniSwitch-MCP server, explaining how it bridges AI assistants (Claude, ChatGPT, etc.) with enterprise ALE OmniSwitch devices through a secure, structured, and standardized MCP (Model Context Protocol) interface.

## 📐 Architectural Vision

### Core Philosophy

ALE-OmniSwitch-MCP is designed as a **secure gateway layer** between AI assistants and ALE OmniSwitch network infrastructure. Instead of giving AI direct SSH access to switches, the MCP server provides:

- **Structured Interface**: AI consumes typed, parsed data instead of raw CLI output
- **Policy Enforcement**: Commands are validated before execution
- **Audit Trail**: All operations are logged with correlation IDs
- **Abstraction**: AI doesn't need to understand CLI syntax or parsing logic

### Design Principles

1. **Read-Only by Default**: All operations are non-destructive except explicitly authorized write actions
2. **Fail-Safe**: Validation happens at multiple layers (policy, SSH, device)
3. **Observable**: Every action produces structured logs for auditing
4. **Stateless**: No session persistence required; each request is independent
5. **Extensible**: New tools can be added without modifying the core engine

## 🏗️ Infrastructure Model

```
┌─────────────────────────────────────────────────────────────────┐
│                         AI Assistant                             │
│                    (Claude, GPT, etc.)                           │
└────────────────────────┬────────────────────────────────────────┘
                         │ MCP Protocol
                         │ (JSON-RPC over HTTP)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ALE-OmniSwitch-MCP Server                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Tool Registry (20 production tools - v1.2.0)            │   │
│  │  ─────────────────────────────────────────────────────   │   │
│  │  Core Operations:                                        │   │
│  │  • aos.cli.readonly    - Execute read-only CLI commands  │   │
│  │  • aos.device.facts    - Gather device information       │   │
│  │  • aos.config.backup   - Backup running configuration    │   │
│  │                                                           │   │
│  │  Port & Interface Management:                            │   │
│  │  • aos.port.info       - Port status & statistics        │   │
│  │  • aos.port.discover   - Discover all switch ports       │   │
│  │  • aos.interfaces.discover - Interface details & LLDP    │   │
│  │  • aos.mac.lookup      - MAC/IP address lookup           │   │
│  │                                                           │   │
│  │  Power over Ethernet (PoE):                              │   │
│  │  • aos.diag.poe        - PoE power diagnostics           │   │
│  │  • aos.poe.restart     - Restart PoE on ports            │   │
│  │                                                           │   │
│  │  Network Auditing:                                       │   │
│  │  • aos.vlan.audit      - VLAN configuration audit        │   │
│  │  • aos.routing.audit   - Routing & OSPF audit            │   │
│  │  • aos.spantree.audit  - Spanning Tree audit             │   │
│  │                                                           │   │
│  │  Health & Monitoring:                                    │   │
│  │  • aos.health.monitor  - Complete health check           │   │
│  │  • aos.chassis.status  - Chassis hardware status         │   │
│  │  • aos.ntp.status      - NTP synchronization status      │   │
│  │  • aos.lacp.info       - Link Aggregation status         │   │
│  │  • aos.dhcp.relay.info - DHCP Relay configuration        │   │
│  │                                                           │   │
│  │  Diagnostics:                                            │   │
│  │  • aos.diag.ping       - Network connectivity test       │   │
│  │  • aos.diag.traceroute - Network path tracing            │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Security & Policy Engine                                │   │
│  │  • Command validation (allowlist/denylist)              │   │
│  │  • Zone-based authentication (global + zone fallback)   │   │
│  │  • Authorization checks                                  │   │
│  │  • Output redaction (passwords, SNMP communities)       │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  SSH Transport Layer                                     │   │
│  │  • Paramiko SSH client                                   │   │
│  │  • Host key verification                                 │   │
│  │  • Connection pooling & timeouts                         │   │
│  │  • Jump host support (bastion)                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Data Parsing & Normalization                            │   │
│  │  • AOS6/AOS8 CLI output parsing                         │   │
│  │  • Structured data extraction                            │   │
│  │  • Type validation (Pydantic models)                    │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────────┘
                         │ SSH
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│               ALE OmniSwitch Network Infrastructure              │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  Core    │  │  Aggr    │  │  Access  │  │  Access  │       │
│  │  Switch  │  │  Switch  │  │  Switch  │  │  Switch  │       │
│  │ 6900-X20 │  │ 6860-E24 │  │ 6360-24  │  │ 6360-48  │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
│                                                                  │
│  • VLANs configuration          • PoE management                │
│  • Routing (OSPF, static)       • Port discovery               │
│  • Spanning Tree topology       • LLDP neighbor info           │
│  • Interface statistics         • Configuration backup         │
└─────────────────────────────────────────────────────────────────┘
```

## 🎯 Usage Scenarios

### 1. Conversational Network Operations

**User**: "Check why port 1/1/5 is down on switch 192.168.10.50"

**Flow**:
```
AI Assistant
  → Calls: aos.port.info(host="192.168.10.50", port="1/1/5")
  → MCP validates request & authenticates (global or zone credentials)
  → SSH executes: "show interfaces 1/1/5"
  → Parser extracts status, speed, errors
  → AI receives structured data
  → AI responds: "Port is administratively down, no link detected"
```

### 2. Automated Diagnostics

**User**: "Show me all PoE ports using more than 20W"

**Flow**:
```
AI Assistant
  → Calls: aos.diag.poe(host="192.168.10.50")
  → MCP executes: "show lanpower"
  → Parser extracts all port power data
  → AI filters results > 20W
  → AI presents formatted table with high-power ports
```

### 3. Configuration Audits

**User**: "Find all VLANs without spanning tree enabled across building A"

**Flow**:
```
AI Assistant
  → Iterates through switch inventory
  → Calls: aos.vlan.audit(host=switch) for each device
  → MCP parses VLAN + STP configurations
  → AI correlates data across devices
  → AI reports VLANs with STP disabled
```

### 4. Troubleshooting Workflows

**User**: "Trace network path from 192.168.10.100 to 8.8.8.8"

**Flow**:
```
AI Assistant
  → Calls: aos.cli.readonly(host="...", command="ping 192.168.10.100")
  → Verifies connectivity
  → Calls: aos.routing.audit(host="...")
  → Analyzes routing table
  → Calls: aos.diag.traceroute(host="...", destination="8.8.8.8")
  → AI interprets hop-by-hop results
```

## 🔧 Deployment Models

### Standalone Deployment

**Use Case**: Small to medium networks (1-50 switches)

```yaml
Environment: Single server/container
Network: Direct connectivity to management VLAN
Authentication: Environment variables
Scaling: Vertical (CPU/memory)
```

**Characteristics**:
- Simple configuration
- Low latency
- Suitable for <100 concurrent requests/minute
- Direct SSH to switches

### Docker Deployment

**Use Case**: Production environments with containerization

```yaml
Environment: Docker Compose or Kubernetes
Network: Management VLAN access via overlay network
Authentication: Kubernetes secrets or Docker secrets
Scaling: Horizontal (multiple replicas)
```

**Characteristics**:
- Health checks and auto-restart
- Resource limits (CPU/memory)
- Log aggregation
- Config volume mounts
- Non-root execution

### Enterprise Integration

**Use Case**: Large networks with jump hosts and compliance requirements

```yaml
Environment: Behind bastion/jump host
Network: Segmented access through SSH proxy
Authentication: Vault integration, SSH key management
Scaling: Load-balanced, high availability
```

**Characteristics**:
- Jump host support for SSH
- Integration with IPAM/CMDB systems
- Audit log shipping (SIEM)
- Role-based access control
- Compliance reporting

## 🔐 Security Architecture

### Defense in Depth

```
Layer 1: Network Isolation
  ├─ MCP server in management network
  ├─ Firewall rules to switch management IPs
  └─ Optional: Jump host requirement

Layer 2: Authentication (Zone-Based System - v1.1.0)
  ├─ Primary: Global credentials (all switches)
  ├─ Fallback: Zone-specific credentials (per subnet)
  ├─ Zone detection: IP-based (e.g., 192.168.10.0/16 → Zone 10)
  ├─ SSH key-based authentication support
  └─ Known_hosts verification

Layer 3: Authorization
  ├─ Command policy (allowlist regex)
  ├─ Per-user subject validation
  └─ Tool-level permissions

Layer 4: Validation
  ├─ Input sanitization
  ├─ Command length limits
  └─ Parameter type checking

Layer 5: Auditing
  ├─ Request correlation IDs
  ├─ Structured logging
  └─ Output redaction (passwords/SNMP)
```

### Zone-Based Authentication

The v1.1.0 release introduces **zone-based authentication** for large-scale deployments with multiple network segments:

**How it works:**
1. **Global credentials** are tried first (defined in `AOS_GLOBAL_USERNAME` / `AOS_GLOBAL_PASSWORD`)
2. If global auth fails, **zone-specific credentials** are used based on target IP
3. Zones are identified by the **second octet** of the IP address:
   - `192.168.10.50` → Zone 10 → Uses `AOS_ZONE10_USERNAME` / `AOS_ZONE10_PASSWORD`
   - `192.168.25.100` → Zone 25 → Uses `AOS_ZONE25_USERNAME` / `AOS_ZONE25_PASSWORD`

**Configuration example:**
```bash
# Global credentials (priority 1)
AOS_GLOBAL_USERNAME="network_automation"
AOS_GLOBAL_PASSWORD="secure_global_password"

# Zone 10 credentials (192.168.10.0/16) - fallback
AOS_ZONE10_USERNAME="admin"
AOS_ZONE10_PASSWORD="zone10_password"

# Zone 25 credentials (192.168.25.0/16) - fallback  
AOS_ZONE25_USERNAME="admin"
AOS_ZONE25_PASSWORD="zone25_password"
```

**Use cases:**
- **Large enterprises** with 500+ switches across multiple sites
- **Credential rotation** per zone without affecting global access
- **Migration scenarios** where some zones use legacy credentials
- **Security isolation** between network segments

### Command Policy Example

```yaml
command_policy:
  allow_regex:
    - '^show\s+.*$'              # All show commands
    - '^vrf\s+\S+\s+show\s+.*$'  # VRF show commands
    - '^ping\s+.*$'               # Connectivity tests
    - '^traceroute\s+.*$'         # Path tracing
    - '^lanpower\s+port\s+.*\s+admin-state\s+(enable|disable)$'  # PoE control
    - '^write\s+terminal$'        # Config backup only
  
  strip_ansi: true
  
  redactions:
    - pattern: '(?i)(password\s+)(\S+)'
      replacement: '\1***'
    - pattern: '(?i)(snmp.*community\s+)(\S+)'
      replacement: '\1***'
```

## 📊 Data Flow & Processing

### Request Processing Pipeline

```
1. Request Ingestion
   ├─ HTTP POST to /v1/tools/call
   ├─ JSON payload validation
   └─ Correlation ID generation

2. Authorization
   ├─ Subject extraction (user identity)
   ├─ Tool permission check
   └─ Parameter validation

3. Command Construction
   ├─ Tool-specific command generation
   ├─ Policy validation (regex matching)
   └─ Timeout configuration

4. SSH Execution
   ├─ Connection establishment
   ├─ Host key verification
   ├─ Command execution
   └─ Output collection

5. Data Parsing
   ├─ CLI output normalization
   ├─ Pattern matching & extraction
   ├─ Structured data creation
   └─ Type validation (Pydantic)

6. Response Construction
   ├─ Result serialization
   ├─ Error handling
   ├─ Metadata attachment
   └─ HTTP response

7. Logging & Audit
   ├─ Operation logging
   ├─ Performance metrics
   └─ Error tracking
```

### Example: Port Information Flow

```python
# User request
{
  "tool": "aos.port.info",
  "args": {"host": "192.168.10.50", "port": "1/1/5"},
  "context": {"subject": "operator@company.com"}
}

# Internal processing
1. Validate: aos.port.info exists and subject authorized
2. Authenticate: Try global creds, fallback to Zone 10 creds (192.168.10.x)
3. Generate SSH command: "show interfaces 1/1/5 port"
4. Validate command against policy
5. Execute SSH → switch
6. Parse output:
   - Extract: admin_status, oper_status, speed, duplex
   - Extract: input_errors, output_errors, CRC
   - Extract: VLAN membership
7. Return structured JSON:
{
  "port": "1/1/5",
  "admin_status": "up",
  "oper_status": "up",
  "speed": "1000",
  "duplex": "full",
  "vlan": "100",
  "errors": {"input": 0, "output": 0, "crc": 0}
}
```

## 🔌 Integration Patterns

### 1. AI Assistant Integration (Primary)

```
AI Assistant ↔ MCP Protocol ↔ ALE-OmniSwitch-MCP
```

**Tools consumed**:
- Claude Desktop (via MCP config)
- Custom AI agents (API integration)
- ChatOps bots (Slack, Teams)

**Benefits**:
- Natural language interaction
- Multi-step reasoning
- Context retention across queries

### 2. IPAM/CMDB Integration

```
IPAM System → REST API → ALE-OmniSwitch-MCP → Switches
```

**Use cases**:
- Auto-discovery of switch inventory
- MAC address table synchronization
- LLDP neighbor population
- VLAN assignment validation

### Example: NetBox integration
```python
# NetBox webhook triggers on new switch discovery
switch_discovered = aos.device.facts(host=new_switch_ip)
interfaces = aos.interfaces.discover(host=new_switch_ip)
# Update NetBox device + interfaces automatically
```

### 3. Monitoring & Observability

```
Prometheus/Grafana → Metrics Endpoint → ALE-OmniSwitch-MCP
```

**Metrics exposed**:
- Request latency (per tool)
- SSH connection errors
- Policy validation failures
- Device availability

**Alerting scenarios**:
- High error rates
- Slow response times
- Authentication failures

### 4. CI/CD Integration

```
GitLab Pipeline → API Call → ALE-OmniSwitch-MCP → Config Validation
```

**Use cases:**
- Pre-deployment VLAN validation
- Configuration drift detection
- Automated compliance checks

**Example**: Pipeline stage for production validation
```yaml
validate_network:
  script:
    - curl -X POST $MCP_URL/v1/tools/call \
        -d '{"tool":"aos.vlan.audit","args":{"host":"192.168.10.1"}}'
    - jq '.result.issues | length == 0' response.json
```

## 🚀 Scaling Considerations

### Vertical Scaling

**Single instance optimization**:
- Connection pooling (reuse SSH sessions)
- Async I/O (multiple concurrent requests)
- Caching (device facts, stable data)
- Resource limits (CPU/memory)

**Suitable for**: <1000 switches, <500 req/min

### Horizontal Scaling

**Multi-instance deployment**:
- Load balancer (round-robin, least-conn)
- Stateless design (no session affinity needed)
- Shared configuration (volume mounts)
- Distributed logging (centralized)

**Suitable for**: >1000 switches, >1000 req/min

### High Availability

**Redundancy**:
- Active-active MCP servers
- Health checks and failover
- Multi-region deployment (edge cases)
- Database-backed inventory (optional)

## 🎓 Operational Model

### Day 1: Deployment

1. **Prepare infrastructure**:
   - Management network access
   - Global SSH credentials (mandatory)
   - Zone-specific credentials (optional, for fallback)
   - known_hosts file with switch fingerprints

2. **Deploy MCP server**:
   - Docker compose up or native Python
   - Configure config.yaml with policies
   - Set environment variables (global + zone credentials)

3. **Test connectivity**:
   - Health check endpoint: `curl http://localhost:8000/health`
   - Test tool: `aos.device.facts` on a known switch
   - Verify zone fallback authentication

### Day 2: Operations

**Routine tasks**:
- Monitor health endpoint (`/health`)
- Review audit logs for unauthorized attempts
- Update known_hosts for new switches
- Monitor zone authentication failures
- Rotate credentials per zone if needed

**Maintenance**:
- Update Docker images (new tool releases)
- Adjust command policies (add/remove patterns)
- Add new tools (as needed)
- Configure new zones (when network expands)

**Troubleshooting**:
- Check SSH connectivity per zone
- Review policy rejections in logs
- Analyze slow queries (SSH timeout issues)
- Verify zone credential configuration

### Day N: Evolution

**Enhancement opportunities**:
- Add custom tools (organization-specific)
- Integrate with IPAM/CMDB
- Implement caching layers
- Deploy additional instances

## 📈 Future Capabilities

### Near-Term (v1.4+)

- **Bulk operations**: Execute tools across multiple switches concurrently
- **Streaming output**: WebSocket support for real-time command output
- **Advanced parsing**: AOS8 SPB-M topology discovery

### Long-Term (v2.0+)

- **Change tracking**: Configuration diff and version control
- **Predictive analytics**: ML-based anomaly detection on port statistics
- **Self-service**: User-definable custom tools via YAML
- **Multi-vendor**: Support for Cisco, Aruba, Juniper switches

## 📚 Additional Resources

- **[README.md](README.md)**: Quick start guide and feature overview
- **[CHANGELOG.md](CHANGELOG.md)**: Version history and release notes
- **[examples/](examples/)**: Detailed usage examples for all 20 tools
- **[deploy/README.md](deploy/README.md)**: Docker deployment guide


---

**ALE-OmniSwitch-MCP v1.2.0** provides a production-ready, secure, and scalable foundation for AI-driven network operations on ALE OmniSwitch infrastructure, with zone-based authentication for enterprise-scale deployments.
