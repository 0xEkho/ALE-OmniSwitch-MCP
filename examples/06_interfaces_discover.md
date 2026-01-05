# aos.interfaces.discover - Discover All Interfaces

## Purpose

Discover all network interfaces on a switch with comprehensive data: status, VLANs, MAC addresses, LLDP neighbors, PoE info, and optional traffic statistics. Ideal for network topology mapping and capacity planning.

## When to Use

- Network topology discovery and documentation
- Find all active ports and their connections
- Identify LLDP neighbors for device mapping
- Capacity planning and utilization analysis
- Audit VLAN assignments across all ports

## Use Case

**Scenario**: Create network topology map showing all active ports, connected devices, and LLDP neighbor information.

**User Prompt**: "Show me all active ports on switch 192.168.1.100 with their LLDP neighbors"

## Request

```bash
curl -s \
  -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: $AOS_API_KEY" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "network-mapping@company.com",
      "correlation_id": "topology-discovery-building-a"
    },
    "tool": "aos.interfaces.discover",
    "args": {
      "host": "192.168.1.100",
      "include_inactive": false,
      "include_statistics": false
    }
  }' | jq
```

### Arguments

- **host** (required): Switch IP address
- **include_inactive** (optional): Include down ports, default: true
- **include_statistics** (optional): Include traffic stats (slower), default: false

## Expected Response

```json
{
  "status": "ok",
  "data": {
    "host": "192.168.1.100",
    "total_interfaces": 24,
    "active_interfaces": 18,
    "interfaces": [
      {
        "port_id": "1/1/1",
        "admin_state": "enabled",
        "oper_state": "up",
        "speed": "1000",
        "duplex": "full",
        "auto_neg": true,
        "interface_type": "Copper",
        "vlan": {
          "untagged": 100,
          "tagged": [200, 300],
          "status": "forwarding"
        },
        "mac_addresses": [
          {"mac": "aa:bb:cc:dd:ee:ff", "vlan": 100, "type": "dynamic"}
        ],
        "lldp_neighbor": {
          "system_name": "SW-ACCESS-02",
          "port_id": "1/1/24",
          "chassis_id": "00:11:22:33:44:55"
        },
        "poe": {
          "enabled": true,
          "status": "Delivering Power",
          "power_used_mw": 15400,
          "max_power_mw": 30000
        }
      }
    ],
    "duration_ms": 8500
  }
}
```

## Filtering Examples

### Find Uplinks (LLDP neighbors)

```bash
curl -s ... | jq '.data.interfaces[] | select(.lldp_neighbor != null) | {port: .port_id, neighbor: .lldp_neighbor.system_name, neighbor_port: .lldp_neighbor.port_id}'
```

### List All VLANs in Use

```bash
curl -s ... | jq '[.data.interfaces[].vlan.untagged] | unique'
```

### Find Ports with Multiple MACs

```bash
curl -s ... | jq '.data.interfaces[] | select((.mac_addresses | length) > 1) | {port: .port_id, mac_count: (.mac_addresses | length)}'
```

### Active PoE Ports Only

```bash
curl -s ... | jq '.data.interfaces[] | select(.poe.status == "Delivering Power") | {port: .port_id, power_w: (.poe.power_used_mw / 1000)}'
```

## With Statistics

```bash
curl -s \
  -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: $AOS_API_KEY" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "monitoring@company.com",
      "correlation_id": "interface-stats-utilization"
    },
    "tool": "aos.interfaces.discover",
    "args": {
      "host": "192.168.1.100",
      "include_inactive": false,
      "include_statistics": true
    }
  }' | jq '.data.interfaces[] | {port: .port_id, tx_bytes: .statistics.tx_bytes, rx_bytes: .statistics.rx_bytes, errors: (.statistics.tx_errors + .statistics.rx_errors)}'
```

## Tips

- Set `include_inactive: false` for faster results
- Enable statistics only when needed (adds ~5s per switch)
- Use LLDP data to automatically build network topology
- Filter by VLAN to audit specific network segments
- Export to CSV for documentation or spreadsheets
