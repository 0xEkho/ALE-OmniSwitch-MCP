# aos.mac.lookup - MAC Address Lookup

## Purpose

Lookup devices by MAC address, IP address, or VLAN. Returns location (port, VLAN) and type (dynamic/static/ARP) of learned addresses. Essential for device troubleshooting and network inventory.

## When to Use

- Finding physical location of a device by MAC
- Resolving IP to MAC and port location
- Auditing devices on a specific VLAN
- Troubleshooting "where is this device?"
- Network device inventory

## Use Case

**Scenario**: Help desk received complaint about slow network. Need to find which port the user's device is connected to.

**User Prompt**: "Find device with MAC address a4:83:e7:12:34:56"

## Request

```bash
curl -s \
  -H "Content-Type: application/json" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "helpdesk@company.com",
      "correlation_id": "mac-lookup-ticket-12345"
    },
    "tool": "aos.mac.lookup",
    "args": {
      "host": "192.168.1.100",
      "mac_address": "a4:83:e7:12:34:56"
    }
  }' | jq
```

### Arguments

- **host** (required): Switch IP address
- **mac_address** (optional): MAC to lookup (formats: `aa:bb:cc:dd:ee:ff` or `aa-bb-cc-dd-ee-ff`)
- **ip_address** (optional): IP to lookup via ARP
- **vlan_id** (optional): List all MACs in VLAN
- **port** (optional): SSH port, default: 22

**Note**: Provide at least one of: `mac_address`, `ip_address`, or `vlan_id`

## Expected Response

### Lookup by MAC

```json
{
  "status": "ok",
  "data": {
    "host": "192.168.1.100",
    "entries": [
      {
        "mac_address": "a4:83:e7:12:34:56",
        "vlan": 100,
        "port": "1/1/8",
        "type": "dynamic"
      }
    ],
    "total_found": 1,
    "duration_ms": 850,
    "commands_executed": ["show mac-learning mac a4:83:e7:12:34:56"]
  },
  "content": [
    {
      "type": "text",
      "text": "**MAC Lookup Results: 192.168.1.100**\n\nFound: 1 entries\n"
    },
    {
      "type": "text",
      "text": "\n- MAC: a4:83:e7:12:34:56 | VLAN: 100 | Port: 1/1/8"
    }
  ]
}
```

### Lookup by IP (via ARP)

```json
{
  "status": "ok",
  "data": {
    "host": "192.168.1.100",
    "entries": [
      {
        "ip_address": "10.1.0.25",
        "mac_address": "a4:83:e7:12:34:56",
        "vlan": 100,
        "port": "1/1/8",
        "type": "arp"
      }
    ],
    "total_found": 1,
    "duration_ms": 920,
    "commands_executed": ["show arp 10.1.0.25"]
  }
}
```

### Lookup by VLAN

```json
{
  "status": "ok",
  "data": {
    "host": "192.168.1.100",
    "entries": [
      {
        "mac_address": "a4:83:e7:12:34:56",
        "vlan": 100,
        "port": "1/1/8",
        "type": "dynamic"
      },
      {
        "mac_address": "b8:27:eb:ab:cd:ef",
        "vlan": 100,
        "port": "1/1/12",
        "type": "dynamic"
      },
      {
        "mac_address": "00:1a:2b:3c:4d:5e",
        "vlan": 100,
        "port": "1/1/25",
        "type": "static"
      }
    ],
    "total_found": 3,
    "duration_ms": 1250,
    "commands_executed": ["show mac-learning vlan 100"]
  }
}
```

## Response Fields

- **entries**: Array of found MAC/IP entries
  - **mac_address**: MAC address
  - **ip_address**: IP address (if ARP lookup)
  - **vlan**: VLAN ID
  - **port**: Switch port location
  - **type**: Entry type (dynamic, static, arp)
- **total_found**: Number of entries found
- **duration_ms**: Execution time

## Additional Examples

### Find Device by IP

```bash
curl -s \
  -H "Content-Type: application/json" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "network-ops@company.com"
    },
    "tool": "aos.mac.lookup",
    "args": {
      "host": "192.168.1.100",
      "ip_address": "10.1.0.25"
    }
  }' | jq
```

### List All Devices in VLAN 100

```bash
curl -s \
  -H "Content-Type: application/json" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "tool": "aos.mac.lookup",
    "args": {
      "host": "192.168.1.100",
      "vlan_id": 100
    },
    "context": {}
  }' | jq '.data.entries'
```

### Export to CSV

```bash
curl -s ... | jq -r '.data.entries[] | [.mac_address, .vlan, .port, .type] | @csv'
```

### Filter Static Entries

```bash
curl -s ... | jq '.data.entries[] | select(.type == "static")'
```

## Use Cases

### Troubleshooting: "Where is this device?"

**Question**: User reports "My device MAC a4:83:e7:12:34:56 can't connect"

```bash
# Find the port
curl ... -d '{"tool": "aos.mac.lookup", "args": {"host": "192.168.1.100", "mac_address": "a4:83:e7:12:34:56"}}'

# Then check port status
curl ... -d '{"tool": "aos.port.discover", "args": {"host": "192.168.1.100", "port_id": "1/1/8"}}'
```

### Security: Unauthorized Device

**Question**: "Is MAC aa:bb:cc:dd:ee:ff on the network?"

```bash
curl ... | jq 'if .data.total_found > 0 then "FOUND on port " + .data.entries[0].port else "NOT FOUND" end'
```

### Inventory: VLAN Occupancy

**Question**: "How many devices in VLAN 200?"

```bash
curl ... -d '{"tool": "aos.mac.lookup", "args": {"vlan_id": 200}}' | jq '.data.total_found'
```

## Error Handling

### Not Found

```json
{
  "status": "ok",
  "data": {
    "entries": [],
    "total_found": 0
  },
  "content": [
    {
      "type": "text",
      "text": "**MAC Lookup: 192.168.1.100**\n\nNo entries found."
    }
  ]
}
```

### Invalid MAC Format

The tool accepts both colon and hyphen formats:
- ✅ `a4:83:e7:12:34:56`
- ✅ `a4-83-e7-12-34-56`
- ✅ `A4:83:E7:12:34:56` (case insensitive)

## Tips

- MAC lookups are instant (<1s typically)
- ARP entries may be transient (use MAC learning for persistent tracking)
- Static entries indicate manual configuration
- Use with `aos.port.discover` for complete device context
- For VLAN lookups, results may be large (100s of entries)
- Combine with LLDP (`aos.interfaces.discover`) for device identification
