# aos.poe.restart - Restart PoE Port

## Purpose

⚠️ **WRITE OPERATION** - Power cycle a PoE port by disabling and re-enabling power delivery. Used to remotely reboot PoE-powered devices like IP phones, wireless access points, and cameras.

## When to Use

- Reboot unresponsive PoE device (IP phone frozen, AP not responding)
- Troubleshoot device connectivity without physical access
- Scheduled maintenance reboots
- Remote power cycling as first troubleshooting step

## Use Case

**Scenario**: Wireless access point on floor 3 is not responding to management. Onsite visit would take 30 minutes.

**User Prompt**: "The WiFi AP on port 1/1/12 at switch 192.168.1.100 is frozen - restart its PoE power"

## Request

```bash
curl -s \
  -H "Content-Type: application/json" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "netops@company.com",
      "correlation_id": "ticket-67890-wifi-ap-reboot"
    },
    "tool": "aos.poe.restart",
    "args": {
      "host": "192.168.1.100",
      "port_id": "1/1/12",
      "wait_seconds": 10
    }
  }' | jq
```

### Arguments

- **host** (required): Switch IP address
- **port_id** (required): Port identifier (e.g., "1/1/12")
- **wait_seconds** (optional): Time to wait between disable/enable, default: 5 seconds
- **port** (optional): SSH port, default: 22
- **username** (optional): SSH username

## Expected Response

```json
{
  "status": "ok",
  "data": {
    "host": "192.168.1.100",
    "port_id": "1/1/12",
    "action": "restart_completed",
    "commands_executed": [
      "lanpower port 1/1/12 admin-state disable",
      "lanpower port 1/1/12 admin-state enable"
    ],
    "wait_seconds": 10,
    "total_duration_ms": 11250,
    "disable_result": {
      "stdout": "",
      "stderr": "",
      "exit_status": 0
    },
    "enable_result": {
      "stdout": "",
      "stderr": "",
      "exit_status": 0
    }
  },
  "content": null,
  "warnings": [],
  "error": null,
  "meta": {
    "tool": "aos.poe.restart"
  }
}
```

## Response Fields

- **action**: Operation status (restart_completed, restart_failed)
- **commands_executed**: List of commands sent to switch
- **wait_seconds**: Actual wait time between disable/enable
- **total_duration_ms**: Total operation time
- **disable_result**: Result of disable command
- **enable_result**: Result of enable command

## Wait Time Recommendations

Different devices require different reboot times:

```bash
# IP Phones (short boot time)
{
  "wait_seconds": 5
}

# Wireless APs (medium boot time)
{
  "wait_seconds": 10
}

# IP Cameras (variable boot time)
{
  "wait_seconds": 15
}

# Complex devices (long boot time)
{
  "wait_seconds": 20
}
```

## Additional Examples

### Quick Restart (IP Phone)

```bash
curl -s \
  -H "Content-Type: application/json" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "helpdesk@company.com",
      "correlation_id": "phone-reboot-user-request"
    },
    "tool": "aos.poe.restart",
    "args": {
      "host": "192.168.1.100",
      "port_id": "1/1/8",
      "wait_seconds": 5
    }
  }' | jq
```

### Extended Wait (Security Camera)

```bash
curl -s \
  -H "Content-Type: application/json" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "security@company.com",
      "correlation_id": "camera-reboot-no-video"
    },
    "tool": "aos.poe.restart",
    "args": {
      "host": "192.168.1.100",
      "port_id": "1/1/20",
      "wait_seconds": 15
    }
  }' | jq
```

### Batch Restart Multiple Ports

```bash
#!/bin/bash
# Restart PoE on multiple ports (e.g., weekly AP maintenance)

PORTS=("1/1/10" "1/1/11" "1/1/12" "1/1/13")

for port in "${PORTS[@]}"; do
  echo "Restarting PoE on port $port..."
  curl -s \
    -H "Content-Type: application/json" \
    -X POST "http://localhost:8080/v1/tools/call" \
    -d "{
      \"context\": {
        \"subject\": \"maintenance-automation\",
        \"correlation_id\": \"weekly-ap-restart-$port\"
      },
      \"tool\": \"aos.poe.restart\",
      \"args\": {
        \"host\": \"192.168.1.100\",
        \"port_id\": \"$port\",
        \"wait_seconds\": 10
      }
    }" | jq -r '.status'
  
  # Wait between restarts to avoid overwhelming switch
  sleep 5
done
```

## Error Handling

### Port Not PoE Capable

```json
{
  "status": "error",
  "error": {
    "code": "internal_error",
    "message": "Command failed - port may not support PoE"
  }
}
```

### Command Not Allowed

```json
{
  "status": "error",
  "error": {
    "code": "policy_violation",
    "message": "lanpower admin-state command not allowed by policy"
  }
}
```

**Solution**: Update `command_policy.allow_regex` in config.yaml to include:
```yaml
- '^lanpower\s+port\s+.*\s+admin-state\s+(enable|disable)$'
```

## Safety Considerations

⚠️ **Important Safety Notes**:

1. **Production Impact**: Restarting PoE will disconnect the device
2. **User Impact**: IP phones will lose active calls during restart
3. **Security**: Cameras will have recording gaps during reboot
4. **Network**: APs will cause WiFi interruption during restart
5. **Verification**: Confirm correct port before executing
6. **Timing**: Consider maintenance windows for non-urgent restarts

## Verification After Restart

Check if device came back online:

```bash
# Wait for device to boot
sleep 30

# Then check PoE status
curl -s \
  -H "Content-Type: application/json" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "netops@company.com",
      "correlation_id": "verify-poe-restart"
    },
    "tool": "aos.diag.poe",
    "args": {
      "host": "192.168.1.100"
    }
  }' | jq '.data.ports[] | select(.port_id == "1/1/12") | {port, status, power_mw: .actual_used_mw}'
```

## Tips

- Always verify the port number before restart
- Use descriptive correlation_id for audit trails
- Start with shortest reasonable wait time
- Check PoE status after restart to confirm device powered back on
- Document restarts in ticketing system using correlation_id
- For planned maintenance, notify users in advance
- Consider scheduled restarts during off-hours for non-urgent issues
