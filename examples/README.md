# Examples - ALE OmniSwitch MCP Server

This directory contains practical examples for all available MCP tools.

## 📚 Available Examples

| Tool | Purpose | Example File |
|------|---------|--------------|
| `aos.cli.readonly` | Execute read-only commands | [01_cli_readonly.md](01_cli_readonly.md) |
| `aos.device.facts` | Get device information | [02_device_facts.md](02_device_facts.md) |
| `aos.port.info` | Port status details | [03_port_info.md](03_port_info.md) |
| `aos.diag.poe` | PoE diagnostics | [04_diag_poe.md](04_diag_poe.md) |
| `aos.poe.restart` | Restart PoE port | [05_poe_restart.md](05_poe_restart.md) |
| `aos.interfaces.discover` | Discover all interfaces | [06_interfaces_discover.md](06_interfaces_discover.md) |
| `aos.port.discover` | Deep dive single port | [07_port_discover.md](07_port_discover.md) |
| `aos.vlan.audit` | VLAN configuration audit | [08_vlan_audit.md](08_vlan_audit.md) |
| `aos.routing.audit` | Routing configuration audit | [09_routing_audit.md](09_routing_audit.md) |
| `aos.spantree.audit` | Spanning tree audit | [10_spantree_audit.md](10_spantree_audit.md) |
| `aos.config.backup` | Configuration backup | [11_config_backup.md](11_config_backup.md) |

## 🚀 Quick Start

Each example follows the same structure:

1. **Purpose** - What the tool does and when to use it
2. **Use Case** - Real-world scenario
3. **Request** - Complete curl command with context
4. **Expected Response** - Sample output

## 💡 Request Format

All tools use this standard format:

```bash
curl -s \
  -H "Content-Type: application/json" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "operator@company.com",
      "correlation_id": "unique-request-id"
    },
    "tool": "aos.tool.name",
    "args": {
      "host": "switch-ip-address",
      ...
    }
  }' | jq
```

### Context Fields

- **subject**: User or system making the request (for audit trails)
- **correlation_id**: Unique identifier to track requests across logs

### Common Arguments

- **host**: Switch IP address or hostname (required for all tools)
- **port**: SSH port (optional, default: 22)
- **username**: SSH username (optional, uses `AOS_DEVICE_USERNAME` env var)

## 📊 Response Format

All tools return standardized responses:

```json
{
  "status": "ok",           // "ok" or "error"
  "data": { ... },          // Tool-specific data
  "content": [ ... ],       // Optional: Formatted content for AI
  "warnings": [],           // Optional: Non-fatal warnings
  "error": null,            // Error details if status is "error"
  "meta": {
    "tool": "aos.tool.name"
  }
}
```

## 🔧 jq Filtering Tips

Extract specific fields:
```bash
# Get only status and data
curl ... | jq '{status, data}'

# Get specific nested field
curl ... | jq '.data.hostname'

# Filter arrays
curl ... | jq '.data.ports[] | select(.actual_used_mw > 10000)'

# Export to CSV
curl ... | jq -r '.data.vlans[] | [.vlan_id, .name, .admin_state] | @csv'
```

## 🎯 Common Use Cases

### Network Troubleshooting
- Check port status: `aos.port.info`
- Find down ports: `aos.interfaces.discover` with filtering
- Trace connectivity: `aos.cli.readonly` with ping/traceroute

### Capacity Planning
- PoE budget analysis: `aos.diag.poe`
- Port utilization: `aos.interfaces.discover` with statistics
- VLAN usage: `aos.vlan.audit`

### Configuration Audits
- Routing configuration: `aos.routing.audit`
- STP topology: `aos.spantree.audit`
- VLAN setup: `aos.vlan.audit`

### Documentation & Backup
- Device inventory: `aos.device.facts`
- Configuration backup: `aos.config.backup`
- Network topology: `aos.interfaces.discover` with LLDP

## 🔐 Security Notes

- Never commit real IP addresses or credentials to version control
- Use environment variables for sensitive data: `AOS_DEVICE_USERNAME`, `AOS_DEVICE_PASSWORD`
- Always include proper `subject` in context for audit trails
- Use unique `correlation_id` for request tracking

## 📝 Testing

Replace placeholder values before testing:
- `switch-ip-address` → Your switch IP (e.g., `192.168.1.100`)
- `operator@company.com` → Your user identifier
- `unique-request-id` → Generate unique IDs (e.g., `$(uuidgen)`)

Example with real values:
```bash
export SWITCH_IP="192.168.1.100"
export OPERATOR="john.doe@company.com"

curl -s \
  -H "Content-Type: application/json" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d "{
    \"context\": {
      \"subject\": \"$OPERATOR\",
      \"correlation_id\": \"device-facts-$(date +%s)\"
    },
    \"tool\": \"aos.device.facts\",
    \"args\": {
      \"host\": \"$SWITCH_IP\"
    }
  }" | jq
```
