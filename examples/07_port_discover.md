# aos.port.discover - Single Port Deep Dive

## Purpose

Comprehensive analysis of a single port with all available information: status, VLAN, MAC table, LLDP, PoE, and statistics. More detailed than `aos.port.info` and faster than `aos.interfaces.discover` for single-port queries.

## When to Use

- Troubleshoot specific port issues with complete context
- Get all information about a port in one request
- Verify port configuration and connected devices
- Document port details for troubleshooting tickets

## Use Case

**Scenario**: User reports network issues on their desk port - need complete port analysis for troubleshooting.

**User Prompt**: "Give me all information about port 1/1/15 on switch 192.168.1.100 - user having intermittent connectivity"

## Request

```bash
curl -s \
  -H "Content-Type: application/json" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "helpdesk@company.com",
      "correlation_id": "ticket-99999-connectivity-issue"
    },
    "tool": "aos.port.discover",
    "args": {
      "host": "192.168.1.100",
      "port_id": "1/1/15"
    }
  }' | jq
```

## Expected Response

Complete port analysis including status, VLANs, MACs, LLDP, PoE, and statistics in a single response.

## Tips

- Faster than full interface discovery for single port
- Use for troubleshooting tickets - includes all relevant data
- Check LLDP to identify connected device
- Verify VLAN configuration matches expected
- Review statistics for errors or high utilization
