# aos.diag.poe - PoE Diagnostics

## Purpose

Retrieve Power over Ethernet (PoE) status for all ports on a switch, including power consumption, status, device class, and total power budget. Essential for capacity planning and troubleshooting PoE devices.

## When to Use

- Check PoE power budget availability
- Identify ports consuming excessive power
- Troubleshoot PoE device connectivity (phones, APs, cameras)
- Capacity planning for PoE deployments
- Monitor power usage trends

## Use Case

**Scenario**: Planning to add 5 new IP cameras but need to verify available PoE capacity on the switch.

**User Prompt**: "Show me PoE power usage on switch 192.168.1.100 to see if we have capacity for new cameras"

## Request

```bash
curl -s \
  -H "Content-Type: application/json" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "facilities@company.com",
      "correlation_id": "poe-capacity-camera-expansion"
    },
    "tool": "aos.diag.poe",
    "args": {
      "host": "192.168.1.100",
      "slot": "1"
    }
  }' | jq
```

### Arguments

- **host** (required): Switch IP address
- **slot** (optional): Slot number (default: "1")
- **port** (optional): SSH port, default: 22

## Expected Response

```json
{
  "status": "ok",
  "data": {
    "host": "192.168.1.100",
    "command": "show lanpower slot 1/1",
    "ports": [
      {
        "port_id": "1/1/1",
        "admin_state": "ON",
        "status": "Delivering Power",
        "priority": "Low",
        "max_power_mw": 30000,
        "actual_used_mw": 15400,
        "voltage_v": 52.1,
        "current_ma": 295,
        "class_": "4",
        "detection": "802.3at"
      },
      {
        "port_id": "1/1/2",
        "admin_state": "ON",
        "status": "Searching",
        "priority": "Low",
        "max_power_mw": 30000,
        "actual_used_mw": 0,
        "voltage_v": 0.0,
        "current_ma": 0,
        "class_": null,
        "detection": null
      }
    ],
    "chassis_summary": {
      "total_power_available_w": 370,
      "total_power_used_w": 142,
      "total_power_remaining_w": 228,
      "power_consumption_percent": 38.4,
      "ports_delivering_power": 8,
      "ports_searching": 16,
      "ports_off": 0,
      "ports_fault": 0
    },
    "duration_ms": 1850,
    "raw_stdout": null
  },
  "content": null,
  "warnings": [],
  "error": null,
  "meta": {
    "tool": "aos.diag.poe"
  }
}
```

## Response Fields

### Chassis Summary
- **total_power_available_w**: Total PoE power budget in watts
- **total_power_used_w**: Current power consumption
- **total_power_remaining_w**: Available power for new devices
- **power_consumption_percent**: Percentage of budget used
- **ports_delivering_power**: Number of active PoE ports
- **ports_searching**: Ports looking for PoE devices
- **ports_off**: Administratively disabled ports
- **ports_fault**: Ports in fault state

### Per-Port Data
- **port_id**: Port identifier
- **admin_state**: ON/OFF
- **status**: Delivering Power, Searching, Fault, Off
- **priority**: Low, High, Critical
- **max_power_mw**: Maximum power allocation (milliwatts)
- **actual_used_mw**: Current power consumption (milliwatts)
- **voltage_v**: Voltage delivered
- **current_ma**: Current delivered (milliamps)
- **class_**: PoE device class (0-8)
- **detection**: 802.3af/802.3at/802.3bt

## Practical Examples

### Find High Power Consumers

```bash
curl -s \
  -H "Content-Type: application/json" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "monitoring@company.com",
      "correlation_id": "poe-high-consumption-alert"
    },
    "tool": "aos.diag.poe",
    "args": {
      "host": "192.168.1.100"
    }
  }' | jq '.data.ports[] | select(.actual_used_mw > 20000) | {port: .port_id, power_w: (.actual_used_mw / 1000)}'
```

### Check Available Capacity

```bash
curl -s \
  -H "Content-Type: application/json" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "planning@company.com",
      "correlation_id": "poe-capacity-planning"
    },
    "tool": "aos.diag.poe",
    "args": {
      "host": "192.168.1.100"
    }
  }' | jq '.data.chassis_summary | {available_w: .total_power_remaining_w, usage_percent: .power_consumption_percent}'
```

### List Active PoE Devices

```bash
curl -s \
  -H "Content-Type: application/json" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "inventory@company.com",
      "correlation_id": "poe-device-inventory"
    },
    "tool": "aos.diag.poe",
    "args": {
      "host": "192.168.1.100"
    }
  }' | jq '[.data.ports[] | select(.status == "Delivering Power") | {port: .port_id, power_w: (.actual_used_mw / 1000), class: .class_, type: .detection}]'
```

### Generate CSV Report

```bash
curl -s \
  -H "Content-Type: application/json" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "reporting@company.com",
      "correlation_id": "poe-monthly-report"
    },
    "tool": "aos.diag.poe",
    "args": {
      "host": "192.168.1.100"
    }
  }' | jq -r '.data.ports[] | select(.actual_used_mw > 0) | [.port_id, .status, (.actual_used_mw / 1000), .class_, .detection] | @csv'
```

## Troubleshooting

### Device Not Receiving Power

Check port status:
```json
{
  "port_id": "1/1/5",
  "status": "Searching",
  "actual_used_mw": 0
}
```
**Possible causes**: No PoE device connected, device fault, cable issue

### Power Budget Exceeded

```json
{
  "chassis_summary": {
    "total_power_used_w": 368,
    "total_power_available_w": 370,
    "power_consumption_percent": 99.5
  }
}
```
**Solution**: Reduce consumption or upgrade PoE budget

## Tips

- Check PoE budget before deploying new devices
- Monitor for "Fault" status ports - indicates wiring or device issues
- Class 4 devices (802.3at) can draw up to 30W
- Use correlation_id to track PoE restart operations
- Combine with `aos.port.discover` for complete port + PoE analysis
