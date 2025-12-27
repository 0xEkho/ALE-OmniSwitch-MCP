# IPAM Integration Guide

## Overview

AOS Server v0.2.0 is designed to work alongside your IPAM (IP Address Management) MCP service. This guide explains how to integrate both services for a complete device management solution.

## Division of Responsibilities

```
┌──────────────────────────────────────────────────────────────┐
│                    IPAM MCP Service                          │
│  ✓ Device discovery                                          │
│  ✓ IP address management                                     │
│  ✓ Device metadata (name, type, location, environment)       │
│  ✓ Network topology                                          │
│  ✓ Device relationships                                      │
└──────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌──────────────────────────────────────────────────────────────┐
│                    AOS MCP Service                           │
│  ✓ SSH command execution                                     │
│  ✓ Command policy enforcement                                │
│  ✓ Structured data parsing (PoE, etc.)                       │
│  ✓ Output redaction                                          │
└──────────────────────────────────────────────────────────────┘
```

## Typical Workflow

### Example: "Check PoE on switch RCK-XXX"

**Step 1: User Query**
```
User → LLM: "Check Power over Ethernet status on switch RCK-XXX"
```

**Step 2: LLM Decomposes**
```
LLM determines:
  1. Need to find device RCK-XXX
  2. Need to check PoE status on that device
```

**Step 3: Call IPAM**
```
LLM → Your MCP Platform → IPAM MCP

Request:
{
  "tool": "ipam.find_device",
  "args": {
    "query": "RCK-XXX"
  }
}

Response:
{
  "status": "ok",
  "data": {
    "name": "RCK-XXX",
    "ip": "10.9.0.1",
    "type": "Alcatel-Lucent OmniSwitch 6860",
    "location": "Building A, Floor 2",
    "environment": "TEST",
    "tags": ["access-switch", "poe-enabled"]
  }
}
```

**Step 4: Platform Validates Access**
```
Your Platform checks:
  - User authenticated? ✓
  - User can access TEST environment? ✓
  - OK to proceed
```

**Step 5: Call AOS MCP**
```
LLM → Your MCP Platform → AOS MCP

Request:
{
  "tool": "aos.diag.poe",
  "args": {
    "host": "10.9.0.1",
    "slot": "1"
  },
  "context": {
    "subject": "alice@company.com",
    "environment": "TEST",
    "correlation_id": "req-12345"
  }
}

Response:
{
  "status": "ok",
  "data": {
    "host": "10.9.0.1",
    "ports": [
      {
        "port_id": "1/1/1",
        "max_power_mw": 30000,
        "actual_used_mw": 15420,
        "status": "Powered",
        "priority": "High",
        "class": "4",
        "type": "802.3at"
      },
      // ... more ports
    ],
    "chassis_summary": {
      "chassis_id": 1,
      "slot_id": 1,
      "max_watts": 370,
      "actual_power_consumed_watts": 150,
      "power_budget_remaining_watts": 220
    }
  }
}
```

**Step 6: LLM Synthesizes Response**
```
LLM → User:
  "Switch RCK-XXX (10.9.0.1) in Building A, Floor 2 has:
   - 24 PoE ports
   - Total power consumption: 150W out of 370W available
   - 220W remaining budget (59% free)
   - Port 1/1/1 is consuming 15.4W (802.3at Class 4, High priority)"
```

## IPAM MCP Service Interface

### Recommended Tools

Your IPAM service should provide these tools:

#### 1. Find Device by Name
```json
{
  "tool": "ipam.find_device",
  "args": {
    "query": "RCK-XXX"
  }
}
```

**Returns:**
```json
{
  "name": "RCK-XXX",
  "ip": "10.9.0.1",
  "type": "OmniSwitch 6860",
  "environment": "TEST",
  "location": "...",
  "tags": ["..."]
}
```

#### 2. Find Device by IP
```json
{
  "tool": "ipam.find_by_ip",
  "args": {
    "ip": "10.9.0.1"
  }
}
```

#### 3. List Devices by Environment
```json
{
  "tool": "ipam.list_devices",
  "args": {
    "environment": "TEST",
    "device_type": "switch"
  }
}
```

#### 4. Search Devices
```json
{
  "tool": "ipam.search",
  "args": {
    "query": "building A floor 2",
    "types": ["switch"],
    "limit": 10
  }
}
```

### Required Fields

Your IPAM must return these fields for AOS integration:

**Mandatory:**
- `ip` - IP address (required by AOS)
- `name` - Device name

**Strongly Recommended:**
- `environment` - TEST or PROD (for audit logging)
- `type` - Device type (for LLM context)
- `location` - Physical location

**Optional:**
- `tags` - Device tags/labels
- `model` - Specific model
- `serial_number` - Serial number
- `management_vlan` - Management VLAN
- `snmp_community` - SNMP community (if used)

## Integration Patterns

### Pattern 1: Sequential Calls (Recommended)

```python
# Your MCP platform pseudo-code

async def handle_check_poe(device_name: str, user: User):
    # 1. Find device in IPAM
    device = await ipam.find_device(device_name)
    
    # 2. Validate user can access this environment
    if device.environment not in user.allowed_environments:
        raise PermissionDenied(f"Cannot access {device.environment}")
    
    # 3. Execute PoE check via AOS
    result = await aos.diag_poe(
        host=device.ip,
        context={
            "subject": user.email,
            "environment": device.environment,
            "correlation_id": generate_id()
        }
    )
    
    # 4. Return result
    return result
```

### Pattern 2: Parallel Calls (Advanced)

```python
# For multiple devices

async def check_poe_multiple(device_names: List[str], user: User):
    # 1. Find all devices in parallel
    devices = await asyncio.gather(*[
        ipam.find_device(name) for name in device_names
    ])
    
    # 2. Filter by user permissions
    allowed_devices = [
        d for d in devices 
        if d.environment in user.allowed_environments
    ]
    
    # 3. Execute PoE checks in parallel
    results = await asyncio.gather(*[
        aos.diag_poe(host=d.ip) for d in allowed_devices
    ])
    
    # 4. Combine results
    return list(zip(allowed_devices, results))
```

### Pattern 3: Cached Discovery

```python
# Cache device lookups for performance

from functools import lru_cache
from datetime import datetime, timedelta

class IPAMCache:
    def __init__(self, ttl_seconds=300):
        self.cache = {}
        self.ttl = timedelta(seconds=ttl_seconds)
    
    async def find_device(self, name: str):
        # Check cache
        if name in self.cache:
            cached_at, device = self.cache[name]
            if datetime.now() - cached_at < self.ttl:
                return device
        
        # Not in cache or expired - fetch from IPAM
        device = await ipam.find_device(name)
        
        # Update cache
        self.cache[name] = (datetime.now(), device)
        
        return device
```

## Error Handling

### IPAM Errors

```python
# Device not found
try:
    device = await ipam.find_device("UNKNOWN-XXX")
except DeviceNotFound:
    return "I couldn't find a device named UNKNOWN-XXX in the network."

# Multiple matches
try:
    device = await ipam.find_device("SW")  # Too vague
except MultipleMatches as e:
    return f"Found {len(e.matches)} devices matching 'SW': {e.matches}"

# IPAM service unavailable
try:
    device = await ipam.find_device("RCK-XXX")
except ServiceUnavailable:
    return "The network inventory service is currently unavailable."
```

### AOS Errors

```python
# SSH connection failed
try:
    result = await aos.diag_poe(host="10.9.0.1")
except SSHError as e:
    return f"Could not connect to switch at {e.host}: {e.message}"

# Command not allowed
try:
    result = await aos.cli_readonly(
        host="10.9.0.1",
        command="configure terminal"  # Not allowed!
    )
except PolicyViolation:
    return "That command is not allowed by the security policy."
```

## Environment Mapping

### TEST vs PROD Isolation

```python
class User:
    email: str
    allowed_environments: List[str]  # ["TEST"] or ["TEST", "PROD"]

# In your platform
def validate_access(user: User, device: Device):
    if device.environment not in user.allowed_environments:
        raise PermissionDenied(
            f"{user.email} cannot access {device.environment} environment"
        )
```

### Environment Tagging

**In IPAM:**
```json
{
  "name": "RCK-XXX",
  "ip": "10.9.0.1",
  "environment": "TEST"  ← Single source of truth
}
```

**Passed to AOS:**
```json
{
  "context": {
    "environment": "TEST"  ← For audit logging only
  }
}
```

## Complete Example Implementation

### Python FastAPI Platform

```python
from fastapi import FastAPI, HTTPException
from typing import Optional
import httpx

app = FastAPI()

# IPAM client
class IPAMClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient()
    
    async def find_device(self, name: str):
        response = await self.client.post(
            f"{self.base_url}/v1/tools/call",
            json={
                "tool": "ipam.find_device",
                "args": {"query": name}
            }
        )
        response.raise_for_status()
        return response.json()["data"]

# AOS client
class AOSClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient()
    
    async def diag_poe(self, host: str, context: dict):
        response = await self.client.post(
            f"{self.base_url}/v1/tools/call",
            json={
                "tool": "aos.diag.poe",
                "args": {"host": host, "slot": "1"},
                "context": context
            }
        )
        response.raise_for_status()
        return response.json()["data"]

# Initialize clients
ipam = IPAMClient("http://ipam-service:8080")
aos = AOSClient("http://aos-service:8080")

# Endpoint
@app.post("/api/check-poe")
async def check_poe(device_name: str, user_email: str):
    # 1. Find device
    try:
        device = await ipam.find_device(device_name)
    except httpx.HTTPStatusError:
        raise HTTPException(404, f"Device {device_name} not found")
    
    # 2. Validate permissions (simplified)
    # In real implementation, check user.allowed_environments
    
    # 3. Execute PoE check
    try:
        result = await aos.diag_poe(
            host=device["ip"],
            context={
                "subject": user_email,
                "environment": device.get("environment", "UNKNOWN"),
                "correlation_id": f"check-poe-{device_name}"
            }
        )
        return {
            "device": device,
            "poe_status": result
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(500, f"Failed to check PoE: {e}")
```

## Monitoring & Logging

### Correlated Logging

```python
import logging
import uuid

def generate_correlation_id():
    return f"req-{uuid.uuid4().hex[:12]}"

async def check_poe_with_logging(device_name: str, user: User):
    correlation_id = generate_correlation_id()
    
    logger.info(
        "Starting PoE check",
        extra={
            "correlation_id": correlation_id,
            "user": user.email,
            "device_name": device_name
        }
    )
    
    try:
        # Find device
        device = await ipam.find_device(device_name)
        logger.info(
            "Device found",
            extra={
                "correlation_id": correlation_id,
                "device_ip": device.ip,
                "environment": device.environment
            }
        )
        
        # Execute
        result = await aos.diag_poe(
            host=device.ip,
            context={"correlation_id": correlation_id}
        )
        
        logger.info(
            "PoE check completed",
            extra={
                "correlation_id": correlation_id,
                "power_used": result["chassis_summary"]["actual_power_consumed_watts"]
            }
        )
        
        return result
        
    except Exception as e:
        logger.error(
            "PoE check failed",
            extra={
                "correlation_id": correlation_id,
                "error": str(e)
            }
        )
        raise
```

## Testing Integration

### Unit Tests

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_check_poe_success():
    # Mock IPAM response
    mock_ipam = AsyncMock()
    mock_ipam.find_device.return_value = {
        "name": "RCK-XXX",
        "ip": "10.9.0.1",
        "environment": "TEST"
    }
    
    # Mock AOS response
    mock_aos = AsyncMock()
    mock_aos.diag_poe.return_value = {
        "ports": [],
        "chassis_summary": {"actual_power_consumed_watts": 150}
    }
    
    # Test
    with patch("myapp.ipam", mock_ipam), patch("myapp.aos", mock_aos):
        result = await check_poe("RCK-XXX", mock_user)
        
        assert result["device"]["ip"] == "10.9.0.1"
        assert result["poe_status"]["chassis_summary"]["actual_power_consumed_watts"] == 150
```

### Integration Tests

```bash
# Start services
docker-compose up -d ipam-service aos-service

# Run tests
pytest tests/integration/test_ipam_aos.py

# Check logs
docker-compose logs -f
```

## Best Practices

1. **Always use correlation IDs** for request tracing
2. **Cache IPAM lookups** (with TTL) for performance
3. **Validate environment access** before calling AOS
4. **Handle errors gracefully** with user-friendly messages
5. **Log all operations** with subject + environment
6. **Use async/await** for parallel operations
7. **Implement retries** for transient failures
8. **Monitor response times** for both services

## Troubleshooting

### Issue: Device not found in IPAM
**Solution**: Check device name spelling, verify device exists in IPAM database

### Issue: AOS connection timeout
**Solution**: Check network connectivity, verify IP address is reachable

### Issue: Permission denied
**Solution**: Verify user has access to device environment (TEST/PROD)

### Issue: Slow performance
**Solution**: Implement IPAM caching, use parallel calls for multiple devices
