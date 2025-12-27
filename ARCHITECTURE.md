# Architecture - AOS Server v0.2.0

## Design Philosophy

**Single Responsibility**: Pure SSH command executor for OmniSwitch devices.

**Core Principle**: Trust but verify
- Trust your MCP platform for authentication and authorization
- Verify commands against policy before execution
- Execute safely with proper error handling

## System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Your MCP Platform                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │     Auth     │  │     IPAM     │  │   AOS MCP    │     │
│  │   Service    │  │     MCP      │  │  (this proj) │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│         │                 │                   │             │
└─────────┼─────────────────┼───────────────────┼─────────────┘
          │                 │                   │
          ↓                 ↓                   ↓
    Authenticates      Discovers IP      Executes SSH
    Users              Addresses         Commands


Flow Example:
─────────────

User: "Check PoE on switch RCK-XXX"
  ↓
LLM decomposes:
  1. Find RCK-XXX location
  2. Check PoE status on that switch
  ↓
MCP Platform authenticates user
  ↓
Call 1: IPAM MCP
  Input: find_device("RCK-XXX")
  Output: {ip: "10.9.0.1", environment: "TEST"}
  ↓
Platform validates: Can user access TEST environment?
  ↓
Call 2: AOS MCP (this service)
  Input: diag_poe(host="10.9.0.1")
  Output: {ports: [...], chassis_summary: {...}}
  ↓
LLM synthesizes response:
  "Switch RCK-XXX (10.9.0.1) has 24 ports with PoE.
   Total consumption: 150W / 370W available.
   Port 1/1/1: 15.4W (802.3at, Class 4)"
```

## Security Architecture

### Three-Layer Security Model

**Layer 1: MCP Platform (External)**
- User authentication (OAuth, SAML, etc.)
- Role-based access control
- Environment permissions (TEST vs PROD)
- Audit logging

**Layer 2: AOS Server (This Service)**
- Command policy enforcement (allowlist/denylist)
- SSH credential management
- Output redaction (passwords, secrets)
- Connection security (host key verification)

**Layer 3: Network Device**
- SSH authentication
- Command authorization (device-level)
- AOS operating system security

### Why No Authorization in AOS Server?

**Problem with dual authorization:**
```
Platform checks: Can Alice call AOS? → Yes
AOS checks:      Does Alice have scope X? → Redundant!
```

**Simplified model:**
```
Platform checks: Can Alice execute on 10.9.0.1? → Yes/No
AOS executes:    Command (if platform said yes)
```

**Benefits:**
- Single source of truth (your platform)
- No duplication of security logic
- Simpler to test and maintain
- Clearer separation of concerns
- Platform controls everything

**Trade-offs:**
- Less "defense in depth"
- Must trust platform completely
- Platform compromise = full access

**Mitigation:**
- Command policy still enforced (allowlist)
- Network isolation (private network only)
- Audit logging (subject + environment)
- Read-only SSH credentials

## Data Flow

### Request Processing

```
1. HTTP Request arrives
   ├─ Validate JSON structure
   ├─ Extract tool + args + context
   └─ Route to tool handler

2. Tool Handler
   ├─ Parse and validate args (Pydantic)
   ├─ Create dynamic Device object from host
   └─ Prepare SSH command

3. Command Policy Check
   ├─ Match against allow_regex patterns
   ├─ Check deny_regex patterns
   ├─ Reject if multi-line or control chars
   └─ Pass if valid

4. SSH Execution
   ├─ Connect to host:port
   ├─ Authenticate with credentials
   ├─ Execute command with timeout
   ├─ Capture stdout + stderr
   └─ Disconnect

5. Post-Processing
   ├─ Strip ANSI codes (if configured)
   ├─ Apply redaction patterns
   ├─ Parse output (for structured tools)
   └─ Build response model

6. HTTP Response
   ├─ Serialize to JSON
   ├─ Add MCP content blocks (optional)
   └─ Return to caller
```

### Error Handling

```
Validation Error → 400 Bad Request
  {
    "status": "error",
    "error": {
      "code": "invalid_request",
      "message": "..."
    }
  }

Policy Violation → 403 Forbidden
  {
    "status": "error",
    "error": {
      "code": "invalid_request",
      "message": "Command not allowed"
    }
  }

SSH Error → 500 Internal Server Error
  {
    "status": "error",
    "error": {
      "code": "ssh_error",
      "message": "Connection timeout"
    }
  }

Unknown Tool → 404 Not Found
  {
    "status": "error",
    "error": {
      "code": "unknown_tool",
      "message": "..."
    }
  }
```

## Tool Design

### Tool Structure

Each tool follows this pattern:

```python
# 1. Input Model (Pydantic)
class ArgsToolName(BaseModel):
    host: str = Field(description="Target IP")
    param1: str
    param2: Optional[int] = None

# 2. Output Model (Pydantic)
class OutToolName(BaseModel):
    host: str
    result: Dict[str, Any]
    duration_ms: int

# 3. Handler Function
def handle_tool(args, runner, config):
    # Parse args
    parsed = ArgsToolName.model_validate(args)
    
    # Create device
    device = create_device(parsed.host)
    
    # Execute
    result = runner.run(device, command)
    
    # Return structured data
    return OutToolName(
        host=device.host,
        result=parse_result(result.stdout),
        duration_ms=result.duration_ms
    ).model_dump()
```

### Why Structured Data?

**Before (raw CLI output):**
```json
{
  "stdout": "Port Max Actual Status...\n1/1/1 30000 15420 Powered...",
  "stderr": ""
}
```
- Hard to parse
- Error-prone
- Depends on CLI format
- No type safety

**After (structured):**
```json
{
  "ports": [
    {
      "port_id": "1/1/1",
      "max_power_mw": 30000,
      "actual_used_mw": 15420,
      "status": "Powered",
      "priority": "High",
      "class": "4",
      "type": "802.3at"
    }
  ],
  "chassis_summary": {
    "max_watts": 370,
    "actual_power_consumed_watts": 150
  }
}
```
- Easy to consume
- Type-safe
- Version-stable
- Self-documenting

## Scalability

### Stateless Design

**No shared state:**
- No inventory database
- No session management
- No caching (except SSH connections)
- Each request is independent

**Benefits:**
- Horizontal scaling (add more instances)
- No synchronization needed
- Resilient to failures (no state loss)
- Simple deployment

### Performance Considerations

**SSH Connection Pooling:**
```python
# Per-request connections (current)
connect → execute → disconnect

# Future: Connection pooling
pool.get(host) → execute → pool.return(host)
```

**Concurrent Requests:**
- FastAPI handles concurrency automatically
- Each SSH session is independent
- No blocking operations

**Bottlenecks:**
- SSH handshake latency (~100-500ms)
- Network latency to switches
- Command execution time (device-dependent)

**Optimization Strategies:**
- Connection pooling (future)
- Batch operations (future)
- Caching for read-heavy workloads (future)

## Integration Patterns

### Pattern 1: Direct IP from IPAM

```
LLM → IPAM (get IP) → AOS (execute)
```

**Best for:**
- Simple queries
- Single-device operations
- Real-time data

### Pattern 2: Platform Middleware

```
LLM → Platform API → AOS
         ↓
    Validation
    Enrichment
    Logging
```

**Best for:**
- Complex authorization
- Multi-system coordination
- Compliance requirements

### Pattern 3: Batch Operations (Future)

```
LLM → Platform → AOS (bulk request)
```

**Best for:**
- Multiple devices
- Parallel execution
- Efficiency

## Configuration Management

### Layered Configuration

```
1. Built-in Defaults
   ├─ Timeouts: 10s
   ├─ Max output: 200KB
   └─ Allow patterns: show*

2. Config File (config.yaml)
   ├─ SSH settings
   ├─ Command policy
   └─ Templates

3. Environment Variables
   ├─ Credentials (NEVER in config file)
   ├─ Optional: API keys
   └─ Runtime overrides

4. Runtime Parameters (per-request)
   ├─ Timeouts
   └─ Other overrides
```

### Credential Management

**Best Practices:**
- ✅ Environment variables
- ✅ Secret management systems (Vault, AWS Secrets Manager)
- ✅ Kubernetes secrets
- ❌ Never in config files
- ❌ Never in code
- ❌ Never in version control

## Monitoring & Observability

### Logging

**What to log:**
- All command executions (subject + environment + command)
- Failed authentications
- Policy violations
- SSH errors
- Performance metrics (duration)

**Log format:**
```json
{
  "timestamp": "2025-12-27T11:40:00Z",
  "level": "INFO",
  "subject": "alice@company.com",
  "environment": "TEST",
  "host": "10.9.0.1",
  "tool": "aos.diag.poe",
  "duration_ms": 1234,
  "status": "success"
}
```

### Metrics (Future)

- Request rate (per tool, per environment)
- Error rate (per error code)
- Latency (p50, p95, p99)
- SSH connection failures
- Policy violations

### Health Checks

```bash
# Basic health
GET /healthz

# Detailed (future)
GET /healthz/detailed
{
  "status": "ok",
  "ssh_pool": {"available": 10, "in_use": 2},
  "config_valid": true
}
```

## Design Decisions

### Why Host Instead of Device ID?

**Old way:**
```json
{"device_id": "sw-core-1"}
→ Lookup in inventory → Get IP → Connect
```

**New way:**
```json
{"host": "10.9.0.1"}
→ Connect directly
```

**Reasons:**
- IPAM is source of truth for IPs
- No inventory synchronization
- Simpler, faster, stateless
- Scales better

### Why No Inventory?

**Problems with inventory:**
- Synchronization with IPAM
- Stale data
- State management
- Deployment complexity

**Benefits of no inventory:**
- IPAM is single source of truth
- Always current data
- Stateless service
- Simple deployment

### Why Minimal Context?

**Old context:**
```json
{
  "subject": "...",
  "tenant": "...",
  "scopes": ["..."],
  "allowed_tags": ["..."],
  "allowed_device_ids": ["..."]
}
```

**New context:**
```json
{
  "subject": "...",
  "environment": "...",
  "correlation_id": "..."
}
```

**Reasons:**
- Platform handles authorization
- Context only for audit logging
- Simpler integration
- Less data to manage

## Future Enhancements

### Planned

1. **Connection Pooling**
   - Reuse SSH connections
   - Reduce latency
   - Configurable pool size

2. **Batch Operations**
   - Execute on multiple devices
   - Parallel execution
   - Aggregated results

3. **Enhanced Observability**
   - Prometheus metrics
   - Distributed tracing
   - Detailed health checks

### Under Consideration

1. **Webhook Support**
   - Async command execution
   - Long-running commands
   - Result notifications

2. **Command Templates**
   - User-defined templates
   - Parameter validation
   - Reusable patterns

3. **Output Parsing Extensions**
   - Plugin system
   - Custom parsers
   - Format converters
