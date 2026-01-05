# aos.cli.readonly - Execute Read-Only Commands

## Purpose

Execute any allowlisted read-only command on an OmniSwitch device. This is the most flexible tool for running standard AOS show commands when no specialized tool exists.

## When to Use

- Execute custom show commands not covered by specialized tools
- Quick ad-hoc queries during troubleshooting
- Retrieve specific configuration sections
- Run diagnostic commands (ping, traceroute)

## Use Case

**Scenario**: Network operator needs to check the running directory to verify boot configuration and available images.

**User Prompt**: "Show me the running directory on switch 192.168.1.100"

## Request

```bash
curl -s \
  -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: $AOS_API_KEY" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "netops@company.com",
      "correlation_id": "cli-show-running-dir-001"
    },
    "tool": "aos.cli.readonly",
    "args": {
      "host": "192.168.1.100",
      "command": "show running-directory"
    }
  }' | jq
```

### Arguments

- **host** (required): Switch IP address or hostname
- **command** (required): AOS command to execute (must match allowlist policy)
- **port** (optional): SSH port, default: 22
- **username** (optional): SSH username, uses `AOS_DEVICE_USERNAME` env var if not specified
- **timeout_s** (optional): Command timeout in seconds, default: 30

## Expected Response

```json
{
  "status": "ok",
  "data": {
    "host": "192.168.1.100",
    "command": "show running-directory",
    "stdout": "Directory /flash\n\nSize(b) Type    Date       Time      Name\n------- ------  ------     ------    -------\n4096    Dir     02/15/25   10:23:45  working\n2048    Dir     01/10/25   08:15:30  certified\n8765432 File    01/10/25   08:15:30  boot.img\n\nTotal: 3 entries, 8771576 bytes\n",
    "stderr": "",
    "exit_status": 0,
    "duration_ms": 1250,
    "truncated": false,
    "redacted": false
  },
  "content": null,
  "warnings": [],
  "error": null,
  "meta": {
    "tool": "aos.cli.readonly"
  }
}
```

## Response Fields

- **stdout**: Command output
- **stderr**: Error output (if any)
- **exit_status**: Command exit code (0 = success)
- **duration_ms**: Execution time in milliseconds
- **truncated**: Whether output was truncated (if exceeds max_output_bytes)
- **redacted**: Whether sensitive data was redacted

## Additional Examples

### Ping Diagnostic

```bash
curl -s \
  -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: $AOS_API_KEY" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "netops@company.com",
      "correlation_id": "ping-gateway-check"
    },
    "tool": "aos.cli.readonly",
    "args": {
      "host": "192.168.1.100",
      "command": "ping 8.8.8.8 count 5"
    }
  }' | jq
```

### VRF-Scoped Command

```bash
curl -s \
  -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: $AOS_API_KEY" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "netops@company.com",
      "correlation_id": "vrf-routing-check"
    },
    "tool": "aos.cli.readonly",
    "args": {
      "host": "192.168.1.100",
      "command": "vrf MANAGEMENT show ip route"
    }
  }' | jq
```

### Check LLDP Neighbors

```bash
curl -s \
  -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: $AOS_API_KEY" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "netops@company.com",
      "correlation_id": "lldp-neighbor-discovery"
    },
    "tool": "aos.cli.readonly",
    "args": {
      "host": "192.168.1.100",
      "command": "show lldp remote-system"
    }
  }' | jq
```

## Error Handling

### Command Not Allowlisted

```json
{
  "status": "error",
  "data": null,
  "error": {
    "code": "policy_violation",
    "message": "Command 'write memory' not allowed by policy",
    "details": null
  }
}
```

### SSH Connection Failed

```json
{
  "status": "error",
  "data": null,
  "error": {
    "code": "ssh_error",
    "message": "Connection timeout after 10 seconds",
    "details": null
  }
}
```

## Tips

- Use `| jq '.data.stdout' -r` to get raw command output only
- Check `exit_status` field - non-zero indicates command failure
- Use correlation_id to trace requests in server logs
- Commands are validated against `command_policy` in config.yaml
