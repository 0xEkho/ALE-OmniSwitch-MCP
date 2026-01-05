# aos.health.monitor - Health Monitoring

## Purpose

Monitor switch health including CPU usage, memory consumption, RX/TX errors, and module status. Provides automatic issue detection and threshold violations for proactive monitoring.

## When to Use

- Proactive health checks before maintenance
- Monitoring CPU/memory usage trends
- Detecting hardware errors early
- Automated health reporting
- Capacity planning

## Use Case

**Scenario**: Network operator needs to verify switch health before deploying new services.

**User Prompt**: "Check health status of switch 192.168.1.100"

## Request

```bash
curl -s \
  -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: $AOS_API_KEY" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "monitoring@company.com",
      "correlation_id": "health-check-001"
    },
    "tool": "aos.health.monitor",
    "args": {
      "host": "192.168.1.100",
      "detailed": false
    }
  }' | jq
```

### Arguments

- **host** (required): Switch IP address or hostname
- **port** (optional): SSH port, default: 22
- **detailed** (optional): Include detailed per-module info, default: false

## Expected Response

```json
{
  "status": "ok",
  "data": {
    "host": "192.168.1.100",
    "overall_status": "OK",
    "modules": [
      {
        "module_name": "CMM",
        "slot": "1",
        "status": "OK",
        "cpu_usage_percent": 12,
        "memory_usage_percent": 45,
        "rx_errors": 0,
        "tx_errors": 0
      },
      {
        "module_name": "NI",
        "slot": "1/1",
        "status": "OK",
        "cpu_usage_percent": 8,
        "memory_usage_percent": 38,
        "rx_errors": 125,
        "tx_errors": 0
      }
    ],
    "issues": [],
    "duration_ms": 1250,
    "commands_executed": ["show health"]
  },
  "content": [
    {
      "type": "text",
      "text": "✅ **Health Monitor: 192.168.1.100**\n\nOverall Status: OK\nModules Monitored: 2\n"
    }
  ],
  "meta": {
    "tool": "aos.health.monitor"
  }
}
```

## Response Fields

- **overall_status**: OK, WARNING, CRITICAL, or DOWN
- **modules**: Array of module health data
  - **module_name**: Module identifier (CMM, NI, etc.)
  - **slot**: Module slot location
  - **status**: Module operational status
  - **cpu_usage_percent**: CPU utilization percentage
  - **memory_usage_percent**: Memory usage percentage
  - **rx_errors**: Receive errors count
  - **tx_errors**: Transmit errors count
- **issues**: List of detected problems (threshold violations, errors)
- **duration_ms**: Execution time

## Additional Examples

### Detailed Health Check

```bash
curl -s \
  -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: $AOS_API_KEY" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "monitoring@company.com",
      "correlation_id": "health-detailed-001"
    },
    "tool": "aos.health.monitor",
    "args": {
      "host": "192.168.1.100",
      "detailed": true
    }
  }' | jq
```

### Filter High CPU Modules

```bash
curl -s ... | jq '.data.modules[] | select(.cpu_usage_percent > 70)'
```

### Check for Errors

```bash
curl -s ... | jq '.data.modules[] | select(.rx_errors > 100 or .tx_errors > 100)'
```

## Error Handling

### High Resource Usage

```json
{
  "status": "ok",
  "data": {
    "overall_status": "WARNING",
    "issues": [
      "CMM slot 1 CPU usage high: 85%",
      "NI slot 1/1 memory usage high: 92%"
    ]
  }
}
```

### Module Down

```json
{
  "status": "ok",
  "data": {
    "overall_status": "CRITICAL",
    "issues": [
      "NI slot 1/2 status: DOWN"
    ]
  }
}
```

## Tips

- Run health checks every 5-15 minutes for trending
- Alert on `overall_status != "OK"`
- CPU >80% or Memory >85% triggers warnings
- Combine with `aos.chassis.status` for complete hardware view
- Use `correlation_id` to track health checks over time
