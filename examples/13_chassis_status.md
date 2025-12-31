# aos.chassis.status - Chassis Hardware Status

## Purpose

Get comprehensive chassis hardware status including model, serial number, CMM status, temperature sensors, fan status, and power supply information. Essential for hardware monitoring and preventive maintenance.

## When to Use

- Hardware health checks
- Preventive maintenance planning
- Temperature monitoring
- Fan and PSU failure detection
- Hardware inventory and documentation

## Use Case

**Scenario**: Data center technician needs to check chassis hardware before replacing a fan.

**User Prompt**: "Show me complete hardware status of switch 192.168.1.100"

## Request

```bash
curl -s \
  -H "Content-Type: application/json" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "datacenter@company.com",
      "correlation_id": "chassis-hw-check-001"
    },
    "tool": "aos.chassis.status",
    "args": {
      "host": "192.168.1.100"
    }
  }' | jq
```

### Arguments

- **host** (required): Switch IP address
- **port** (optional): SSH port, default: 22
- **include_temperature** (optional): Include temp sensors, default: true
- **include_fans** (optional): Include fan status, default: true
- **include_power** (optional): Include PSU status, default: true

## Expected Response

```json
{
  "status": "ok",
  "data": {
    "host": "192.168.1.100",
    "chassis_type": "OS6860-P48",
    "serial_number": "ABC123456789",
    "hardware_revision": "AA",
    "mac_address": "00:1a:2b:3c:4d:5e",
    "cmm": {
      "primary": {
        "slot": 1,
        "role": "primary",
        "status": "running",
        "temperature_celsius": 42
      },
      "secondary": {
        "slot": 2,
        "role": "secondary",
        "status": "standby",
        "temperature_celsius": 38
      },
      "status": "running"
    },
    "temperature": {
      "sensors": [
        {
          "sensor": "Chassis",
          "location": "main",
          "current_celsius": 42,
          "threshold_celsius": 65,
          "status": "OK"
        },
        {
          "sensor": "CPU",
          "location": "CMM1",
          "current_celsius": 55,
          "threshold_celsius": 85,
          "status": "OK"
        }
      ],
      "overall_status": "OK",
      "issues": []
    },
    "fans": [
      {
        "fan_id": 1,
        "speed_rpm": 3500,
        "status": "OK"
      },
      {
        "fan_id": 2,
        "speed_rpm": 3480,
        "status": "OK"
      }
    ],
    "power_supplies": [
      {
        "psu_id": 1,
        "status": "present",
        "operational": true,
        "type": "AC",
        "watts": 370
      }
    ],
    "issues": [],
    "duration_ms": 2850,
    "commands_executed": [
      "show chassis",
      "show temperature",
      "show fan",
      "show power-supply",
      "show cmm"
    ]
  },
  "content": [
    {
      "type": "text",
      "text": "**Chassis Status: 192.168.1.100**\n\nModel: OS6860-P48\nSerial: ABC123456789\nMAC: 00:1a:2b:3c:4d:5e\nHardware Rev: AA\n"
    },
    {
      "type": "text",
      "text": "\n**CMM Status:**\n- Primary (Slot 1): running - 42°C\n- Secondary (Slot 2): standby - 38°C\n"
    }
  ]
}
```

## Response Fields

- **chassis_type**: Model name (e.g., OS6860-P48)
- **serial_number**: Chassis serial number
- **hardware_revision**: Hardware revision
- **mac_address**: Base MAC address
- **cmm**: CMM (Chassis Management Module) status
  - **primary/secondary**: Slot, status, temperature
- **temperature**: Temperature sensor readings
  - **sensors**: Array of sensor data (current, threshold, status)
- **fans**: Fan tray status (ID, RPM, status)
- **power_supplies**: PSU status (ID, operational, type, watts)
- **issues**: Detected hardware problems

## Practical Examples

### Quick Hardware Check (No Temperature/Fans)

```bash
curl -s \
  -H "Content-Type: application/json" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "tool": "aos.chassis.status",
    "args": {
      "host": "192.168.1.100",
      "include_temperature": false,
      "include_fans": false,
      "include_power": false
    },
    "context": {}
  }' | jq '{model: .data.chassis_type, serial: .data.serial_number}'
```

### Check Only Temperature

```bash
curl -s ... | jq '.data.temperature.sensors[] | select(.status != "OK")'
```

### Fan Status Check

```bash
curl -s ... | jq '.data.fans[] | select(.speed_rpm < 2000)'
```

## Error Detection

### High Temperature

```json
{
  "temperature": {
    "overall_status": "WARNING",
    "issues": [
      "Temperature sensor CPU at CMM1: 88°C (threshold: 85°C)"
    ]
  }
}
```

### Fan Failure

```json
{
  "fans": [
    {
      "fan_id": 2,
      "speed_rpm": 850,
      "status": "FAILED"
    }
  ],
  "issues": [
    "Fan 2 speed low: 850 RPM",
    "Fan 2 status: FAILED"
  ]
}
```

### PSU Issue

```json
{
  "power_supplies": [
    {
      "psu_id": 2,
      "status": "not_present",
      "operational": false
    }
  ],
  "issues": [
    "Power supply 2: not_present"
  ]
}
```

## Tips

- Check chassis status daily for preventive maintenance
- Alert on temperature >60°C chassis, >75°C CPU
- Fan speed <1500 RPM indicates potential failure
- Redundant PSU: both should be "operational"
- Combine with `aos.health.monitor` for software + hardware view
- Log serial numbers for warranty tracking
