# ALE-OmniSwitch-MCP Infrastructure Vision

**How AI assistants interact with your ALE OmniSwitch network infrastructure**

This document outlines the architectural vision and operational model for the ALE-OmniSwitch-MCP server, explaining how it bridges AI assistants with enterprise network devices through a secure, structured, and standardized interface.

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
│  │  Tool Registry (10 production tools)                     │   │
│  │  • aos.cli.readonly    • aos.device.facts               │   │
│  │  • aos.port.info       • aos.diag.poe                   │   │
│  │  • aos.poe.restart     • aos.interfaces.discover        │   │
│  │  • aos.port.discover   • aos.vlan.audit                 │   │
│  │  • aos.routing.audit   • aos.spantree.audit             │   │
│  │  • aos.config.backup                                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Security & Policy Engine                                │   │
│  │  • Command validation (allowlist/denylist)              │   │
│  │  • Authorization checks                                  │   │
│  │  • Output redaction (passwords, SNMP)                   │   │
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

**User**: "Check why port 1/1/5 is down on switch 192.168.1.100"

**Flow**:
```
AI Assistant
  → Calls: aos.port.info(host="192.168.1.100", port="1/1/5")
  → MCP validates request
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
  → Calls: aos.diag.poe(host="192.168.1.100")
  → MCP executes: "show lanpower"
  → Parser extracts all port power data
  → AI filters results > 20W
  → AI presents formatted table with ports
```

### 3. Configuration Audits

**User**: "Find all VLANs without spanning tree enabled across building A"

**Flow**:
```
AI Assistant
  → Iterates through switch inventory
  → Calls: aos.vlan.audit(host=switch) for each
  → MCP parses VLAN + STP configurations
  → AI correlates data across devices
  → AI reports VLANs with STP disabled
```

### 4. Troubleshooting Workflows

**User**: "Trace network path from 10.1.1.100 to 8.8.8.8"

**Flow**:
```
AI Assistant
  → Calls: aos.cli.readonly(host="...", command="ping 10.1.1.100")
  → Verifies connectivity
  → Calls: aos.routing.audit(host="...")
  → Analyzes routing table
  → Calls: aos.cli.readonly(host="...", command="traceroute 8.8.8.8")
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

Layer 2: Authentication
  ├─ SSH key-based authentication
  ├─ Known_hosts verification
  └─ Credential management (env vars, secrets)

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
  "args": {"host": "192.168.1.100", "port": "1/1/5"},
  "context": {"subject": "operator@company.com"}
}

# Internal processing
1. Validate: aos.port.info exists and subject authorized
2. Generate SSH command: "show interfaces 1/1/5 port"
3. Validate command against policy
4. Execute SSH → switch
5. Parse output:
   - Extract: admin_status, oper_status, speed, duplex
   - Extract: input_errors, output_errors, CRC
   - Extract: VLAN membership
6. Return structured JSON:
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

**Example**: NetBox integration
```python
# NetBox webhook triggers
switch_discovered = aos.device.facts(host=new_switch_ip)
interfaces = aos.interfaces.discover(host=new_switch_ip)
# Update NetBox device + interfaces
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

**Use cases**:
- Pre-deployment VLAN validation
- Configuration drift detection
- Automated compliance checks

**Example**: Pipeline stage
```yaml
validate_vlans:
  script:
    - curl -X POST $MCP_URL/v1/tools/call \
        -d '{"tool":"aos.vlan.audit","args":{"host":"prod-core-01"}}'
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
   - SSH credentials
   - known_hosts file

2. **Deploy MCP server**:
   - Docker compose up or native Python
   - Configure config.yaml
   - Set environment variables

3. **Test connectivity**:
   - Health check endpoint
   - Single tool test (aos.device.facts)

### Day 2: Operations

**Routine tasks**:
- Monitor health endpoint
- Review audit logs
- Update known_hosts (new switches)
- Rotate credentials (if needed)

**Maintenance**:
- Update Docker images
- Adjust command policies
- Add new tools (as needed)

**Troubleshooting**:
- Check SSH connectivity
- Review policy rejections
- Analyze slow queries

### Day N: Evolution

**Enhancement opportunities**:
- Add custom tools (organization-specific)
- Integrate with IPAM/CMDB
- Implement caching layers
- Deploy additional instances

## 📈 Future Capabilities

### Near-Term

- **Bulk operations**: Execute tools across multiple switches concurrently
- **Streaming**: WebSocket support for real-time output
- **Advanced parsing**: AOS8 SPB-M topology discovery

### Long-Term

- **Change tracking**: Configuration diff and version control
- **Predictive analytics**: ML-based anomaly detection
- **Self-service**: User-definable custom tools
- **Multi-vendor**: Support for other switch vendors

## 📚 Additional Resources

- **[README.md](README.md)**: Quick start and feature overview
- **[CHANGELOG.md](CHANGELOG.md)**: Version history
- **[examples/](examples/)**: 12 detailed usage examples
- **[deploy/README.md](deploy/README.md)**: Docker deployment guide

---

**ALE-OmniSwitch-MCP** is designed to be the foundational layer for AI-driven network operations, providing a secure, scalable, and maintainable interface to your ALE OmniSwitch infrastructure.
