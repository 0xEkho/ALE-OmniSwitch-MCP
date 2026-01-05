# aos.port.info - Port Status Information

## Purpose

Get detailed information about a specific switch port including administrative state, operational state, speed, duplex mode, and VLAN assignment.

## When to Use

- Troubleshoot port connectivity issues
- Verify port configuration
- Check link speed and duplex negotiation
- Quick port status check

## Use Case

**Scenario**: User reports network connectivity issues on their workstation connected to port 1/1/5.

**User Prompt**: "Check the status of port 1/1/5 on switch 192.168.1.100 - user can't connect"

## Request

```bash
curl -s \
  -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: $AOS_API_KEY" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "helpdesk@company.com",
      "correlation_id": "ticket-12345-port-down"
    },
    "tool": "aos.port.info",
    "args": {
      "host": "192.168.1.100",
      "port_id": "1/1/5"
    }
  }' | jq
```

### Arguments

- **host** (required): Switch IP address
- **port_id** (required): Port identifier in format "chassis/slot/port" (e.g., "1/1/5")
- **port** (optional): SSH port, default: 22

## Expected Response

```json
{
  "status": "ok",
  "data": {
    "host": "192.168.1.100",
    "port_id": "1/1/5",
    "admin_state": "enabled",
    "oper_state": "up",
    "speed": "1000",
    "duplex": "full",
    "vlan": "100",
    "description": "User Workstation - John Doe",
    "mac_address": "aa:bb:cc:dd:ee:ff",
    "mtu": 1518,
    "errors": null,
    "raw_output": null,
    "duration_ms": 1423
  },
  "content": null,
  "warnings": [],
  "error": null,
  "meta": {
    "tool": "aos.port.info"
  }
}
```

## Response Fields

- **admin_state**: Administrative state (enabled/disabled)
- **oper_state**: Operational state (up/down)
- **speed**: Link speed in Mbps (10/100/1000/10000)
- **duplex**: Duplex mode (full/half)
- **vlan**: VLAN assignment
- **description**: Port description/alias
- **mac_address**: Connected device MAC address
- **mtu**: Maximum Transmission Unit

## Additional Examples

### Check Multiple Ports

```bash
for port in 1 2 3 4 5; do
  curl -s \
    -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: $AOS_API_KEY" \
    -X POST "http://localhost:8080/v1/tools/call" \
    -d "{
      \"context\": {
        \"subject\": \"netops@company.com\",
        \"correlation_id\": \"port-scan-floor2-$port\"
      },
      \"tool\": \"aos.port.info\",
      \"args\": {
        \"host\": \"192.168.1.100\",
        \"port_id\": \"1/1/$port\"
      }
    }" | jq -r '[.data.port_id, .data.oper_state, .data.speed] | @tsv'
done
```

### Extract Only Status

```bash
curl -s \
  -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: $AOS_API_KEY" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "monitoring@company.com",
      "correlation_id": "port-status-check"
    },
    "tool": "aos.port.info",
    "args": {
      "host": "192.168.1.100",
      "port_id": "1/1/5"
    }
  }' | jq '{port: .data.port_id, admin: .data.admin_state, oper: .data.oper_state}'
```

## Common Issues

### Port Down

```json
{
  "status": "ok",
  "data": {
    "admin_state": "enabled",
    "oper_state": "down",
    ...
  }
}
```
**Solution**: Check cable, verify remote device is powered on

### Admin Disabled

```json
{
  "status": "ok",
  "data": {
    "admin_state": "disabled",
    "oper_state": "down",
    ...
  }
}
```
**Solution**: Port is administratively shut down - enable if needed

## Tips

- Use this for quick status checks before deeper analysis
- For comprehensive port information, use `aos.port.discover` instead
- Combine with `aos.diag.poe` to check PoE status on same port
- Port ID format must match AOS notation (chassis/slot/port)
