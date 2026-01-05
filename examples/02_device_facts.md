# aos.device.facts - Device Information

## Purpose

Collect comprehensive device information including hostname, model, AOS version, serial number, uptime, MAC address, and hardware details. Essential for inventory management and device identification.

## When to Use

- Building device inventory
- Verifying device specifications before configuration changes
- Collecting data for asset management systems
- Troubleshooting hardware or software version issues
- Automated documentation generation

## Use Case

**Scenario**: IT team needs to document all network switches for compliance audit, including model, software version, and serial numbers.

**User Prompt**: "Get all device information for switch 192.168.1.100 for our inventory database"

## Request

```bash
curl -s \
  -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: $AOS_API_KEY" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "inventory-system@company.com",
      "correlation_id": "device-facts-inventory-audit"
    },
    "tool": "aos.device.facts",
    "args": {
      "host": "192.168.1.100"
    }
  }' | jq
```

### Arguments

- **host** (required): Switch IP address or hostname
- **port** (optional): SSH port, default: 22
- **username** (optional): SSH username, uses `AOS_DEVICE_USERNAME` env var if not specified

## Expected Response

```json
{
  "status": "ok",
  "data": {
    "host": "192.168.1.100",
    "hostname": "SW-CORE-01",
    "model": "OS6900-X20",
    "aos_version": "8.9.221.R02",
    "serial_number": "AB1234567890",
    "uptime": "127 days, 14 hours, 23 minutes",
    "mac_address": "00:1a:2b:3c:4d:5e",
    "facts": {
      "platform": "ALE OmniSwitch",
      "chassis_type": "OS6900-X20",
      "description": "Alcatel-Lucent OS6900-X20 Gigabit Ethernet Switch",
      "hardware": {
        "cpu": "ARM Cortex-A9 Dual Core @ 1.2GHz",
        "memory": "4096 MB",
        "flash": "8192 MB"
      },
      "software": {
        "aos_version": "8.9.221.R02",
        "boot_version": "8.9.221.R02",
        "kernel_version": "4.4.179"
      },
      "chassis": {
        "serial": "AB1234567890",
        "part_number": "OS6900-X20-E",
        "manufacture_date": "2023-06-15"
      }
    },
    "duration_ms": 2150
  },
  "content": null,
  "warnings": [],
  "error": null,
  "meta": {
    "tool": "aos.device.facts"
  }
}
```

## Response Fields

### Basic Info
- **hostname**: Device hostname
- **model**: Hardware model
- **aos_version**: AOS software version
- **serial_number**: Chassis serial number
- **uptime**: System uptime
- **mac_address**: Base MAC address

### Detailed Facts
- **facts.platform**: Platform identifier
- **facts.chassis_type**: Chassis model
- **facts.hardware**: CPU, memory, flash specifications
- **facts.software**: Detailed version information
- **facts.chassis**: Manufacturing details

## Use Cases & Examples

### Inventory Collection

Extract only essential inventory fields:

```bash
curl -s \
  -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: $AOS_API_KEY" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "inventory-automation",
      "correlation_id": "nightly-inventory-scan"
    },
    "tool": "aos.device.facts",
    "args": {
      "host": "192.168.1.100"
    }
  }' | jq '{host: .data.host, hostname: .data.hostname, model: .data.model, version: .data.aos_version, serial: .data.serial_number}'
```

### Version Compliance Check

Check if device meets minimum version requirements:

```bash
curl -s \
  -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: $AOS_API_KEY" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "compliance-checker",
      "correlation_id": "version-compliance-check"
    },
    "tool": "aos.device.facts",
    "args": {
      "host": "192.168.1.100"
    }
  }' | jq 'if (.data.aos_version | split(".")[0] | tonumber) >= 8 then "✓ Compliant" else "✗ Upgrade needed" end'
```

### Hardware Specifications

Get detailed hardware info:

```bash
curl -s \
  -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: $AOS_API_KEY" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "capacity-planning@company.com",
      "correlation_id": "hardware-specs-review"
    },
    "tool": "aos.device.facts",
    "args": {
      "host": "192.168.1.100"
    }
  }' | jq '.data.facts.hardware'
```

### Export to CSV

Generate CSV for spreadsheet import:

```bash
curl -s \
  -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: $AOS_API_KEY" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "reporting-system",
      "correlation_id": "csv-export-devices"
    },
    "tool": "aos.device.facts",
    "args": {
      "host": "192.168.1.100"
    }
  }' | jq -r '[.data.hostname, .data.model, .data.aos_version, .data.serial_number, .data.uptime] | @csv'
```

## Error Handling

### SSH Authentication Failed

```json
{
  "status": "error",
  "data": null,
  "error": {
    "code": "ssh_error",
    "message": "Authentication failed for user",
    "details": null
  }
}
```

### Device Unreachable

```json
{
  "status": "error",
  "data": null,
  "error": {
    "code": "ssh_error",
    "message": "Connection timeout - host unreachable",
    "details": null
  }
}
```

## Integration Examples

### Bash Script for Multiple Devices

```bash
#!/bin/bash
# Collect facts from multiple switches

SWITCHES=("192.168.1.100" "192.168.1.101" "192.168.1.102")

for switch in "${SWITCHES[@]}"; do
  echo "Collecting facts from $switch..."
  curl -s \
    -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: $AOS_API_KEY" \
    -X POST "http://localhost:8080/v1/tools/call" \
    -d "{
      \"context\": {
        \"subject\": \"batch-inventory\",
        \"correlation_id\": \"facts-$switch-$(date +%s)\"
      },
      \"tool\": \"aos.device.facts\",
      \"args\": {
        \"host\": \"$switch\"
      }
    }" | jq -r '[.data.hostname, .data.model, .data.aos_version] | @tsv'
done
```

## Tips

- Cache device facts to avoid repeated SSH connections
- Use correlation_id to track inventory runs across logs
- Parse `uptime` field to alert on recent reboots
- Compare serial numbers to detect hardware replacements
- Monitor version fields for patch management compliance
