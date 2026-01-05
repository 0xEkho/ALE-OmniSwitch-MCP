# Open WebUI Integration Guide

This guide explains how to integrate the ALE OmniSwitch MCP Server with Open WebUI for AI-assisted network management.

## Prerequisites

- **Open WebUI** v0.6.31 or higher (for native MCP support)
- **ALE OmniSwitch MCP Server** deployed and accessible
- Network connectivity between Open WebUI and MCP server

## Integration Methods

There are two ways to integrate with Open WebUI:

### Method 1: Native HTTP Streamable (Recommended)

Open WebUI v0.6.31+ supports native MCP over HTTP using Server-Sent Events (SSE).

#### Configuration Steps

1. **Deploy ALE OmniSwitch MCP Server**
   ```bash
   # Using Docker (recommended)
   cd deploy
   cp .env.example .env
   # Edit .env: set AOS_GLOBAL_USERNAME, AOS_GLOBAL_PASSWORD, AOS_INTERNAL_API_KEY
   docker-compose up -d
   
   # Verify server is running (healthz doesn't require auth)
   curl http://localhost:8080/healthz
   # Expected: {"status":"ok"}
   ```

2. **Configure Open WebUI**
   - Navigate to: **Admin Panel → Settings → External Tools**
   - Click: **"+" (Add MCP Server)**
   - Configure:
     ```
     Type: MCP (Streamable HTTP)
     Server URL: http://your-mcp-server:8080/mcp/sse
     Auth: Bearer <your-AOS_INTERNAL_API_KEY>
     ID: ale-omniswitch
     Name: ALE OmniSwitch Network Tools
     ```
   - Click **Save**

3. **Restart Open WebUI** (if prompted)

4. **Verify Integration**
   - Open a chat in Open WebUI
   - Type: "List available network tools"
   - The AI should discover and list the 20 ALE OmniSwitch tools

#### Native Integration Architecture

```
┌─────────────────┐         HTTP/SSE          ┌──────────────────────┐
│   Open WebUI    │ ────────────────────────> │  ALE OmniSwitch MCP  │
│  (v0.6.31+)     │   /mcp/sse endpoint       │      Server          │
└─────────────────┘                           └──────────────────────┘
                                                        │
                                                        │ SSH
                                                        ▼
                                              ┌──────────────────┐
                                              │  OmniSwitch      │
                                              │  Devices         │
                                              └──────────────────┘
```

---

### Method 2: MCPO Proxy (For stdio/SSE servers)

If you're running the MCP server via stdio or need to aggregate multiple MCP servers, use **MCPO** (MCP-to-OpenAPI proxy).

⚠️ **Note:** The current implementation uses HTTP/SSE, so MCPO is optional. Use it if you want to:
- Run the server via stdio
- Aggregate multiple MCP servers
- Add additional authentication layers

#### MCPO Configuration

1. **Install MCPO**
   ```bash
   # Using uvx (recommended)
   uvx mcpo --version
   
   # Or with pip
   pip install mcpo
   ```

2. **Create MCPO Config** - Choose ONE of these modes:

   **Option A: Connect to Docker container (recommended for production)**
   ```json
   {
     "mcpServers": {
       "ale-omniswitch": {
         "type": "sse",
         "url": "http://localhost:8080/mcp/sse",
         "headers": {
           "Authorization": "Bearer your_api_key_here"
         }
       }
     }
   }
   ```
   
   **Option B: Launch local Python process (for development)**
   ```json
   {
     "mcpServers": {
       "ale-omniswitch": {
         "command": "python",
         "args": [
           "-m",
           "uvicorn",
           "aos_server.main:create_app",
           "--factory",
           "--host",
           "127.0.0.1",
           "--port",
           "8080"
         ],
         "env": {
           "AOS_GLOBAL_USERNAME": "admin",
           "AOS_GLOBAL_PASSWORD": "your_password",
           "AOS_API_KEY": "your_api_key_here"
         }
       }
     }
   }
   ```

3. **Start MCPO**
   ```bash
   mcpo --config mcpo-config.json --port 8000 --api-key "your_secret_key"
   ```

4. **Configure Open WebUI**
   - Server URL: `http://localhost:8000/ale-omniswitch`
   - Auth: Bearer token with MCPO API key

---

## Available Tools

Once integrated, Open WebUI will have access to 20 production-ready network tools:

**Note:** The `/v1/tools/list` endpoint supports 3 response modes to prevent LLM token overload:
- **ultra_compact** (23 lines): Tool names only - best for initial discovery
- **compact** (80 lines, default): Names + short descriptions - recommended for LLMs
- **full** (518 lines): Complete schemas with input/output - for developers only

Configure in body: `{"ultra_compact": true}` or `{"compact": false}`

### Core Operations
- `aos.cli.readonly` - Execute read-only show commands
- `aos.device.facts` - Get device information
- `aos.config.backup` - Backup configurations

### Port & Interface Management
- `aos.port.info` - Single port status
- `aos.interfaces.discover` - Discover all interfaces
- `aos.port.discover` - Comprehensive port analysis

### Power over Ethernet
- `aos.diag.poe` - PoE diagnostics
- `aos.poe.restart` - Restart PoE (write operation)

### Network Audits
- `aos.vlan.audit` - VLAN configuration audit
- `aos.routing.audit` - Routing audit
- `aos.spantree.audit` - STP audit

### Diagnostics
- `aos.diag.ping` - Ping from switch
- `aos.diag.traceroute` - Traceroute
- `aos.mac.lookup` - MAC address lookup

### Health Monitoring
- `aos.health.monitor` - Health check
- `aos.chassis.status` - Chassis status

### Advanced Protocols
- `aos.lacp.info` - LACP/LAG information
- `aos.ntp.status` - NTP status
- `aos.dhcp.relay.info` - DHCP Relay configuration

---

## Example Queries in Open WebUI

Once integrated, you can ask Open WebUI natural language questions:

### Basic Device Information
```
"What's the model and software version of switch 192.168.1.100?"
→ Uses: aos.device.facts
```

### Port Diagnostics
```
"Show me all ports with errors on switch 192.168.1.100"
→ Uses: aos.interfaces.discover
```

### PoE Management
```
"What's the total PoE consumption on switch 192.168.1.100?"
→ Uses: aos.diag.poe
```

### Network Audits
```
"Audit VLANs on switch 192.168.1.100 and find any issues"
→ Uses: aos.vlan.audit
```

### Health Monitoring
```
"Check CPU, memory, and temperature on switch 192.168.1.100"
→ Uses: aos.health.monitor
```

### Troubleshooting
```
"Trace route from switch 192.168.1.100 to 8.8.8.8"
→ Uses: aos.diag.traceroute
```

---

## Authentication & Security

### Environment Variables

Required credentials must be set before starting the MCP server:

```bash
# Global credentials (required)
export AOS_GLOBAL_USERNAME="network_admin"
export AOS_GLOBAL_PASSWORD="secure_password"

# Zone-specific credentials (optional)
export AOS_ZONE1_USERNAME="zone1_admin"
export AOS_ZONE1_PASSWORD="zone1_password"
```

### Zone-Based Authentication

The server supports multi-site deployments with zone-specific credentials:

- **Global credentials** are tried first
- **Zone credentials** are used as fallback (detected from IP)
- Supports unlimited zones for large infrastructures

Example: `192.168.1.100` → Zone 1 → Uses `AOS_ZONE1_USERNAME/PASSWORD`

### Security Features

- ✅ **Read-only by design** (only 1 write operation: PoE restart)
- ✅ **Command policy enforcement** with allowlist
- ✅ **SSH host key verification**
- ✅ **Password redaction** in logs
- ✅ **Non-root Docker execution**

---

## Troubleshooting

### Issue: Tools not appearing in Open WebUI

**Solution:**
1. Check MCP server health:
   ```bash
   # Health check (no auth required)
   curl http://localhost:8080/healthz
   
   # Test SSE endpoint (requires auth)
   curl http://localhost:8080/mcp/sse -X POST \
     -H "Authorization: Bearer $AOS_INTERNAL_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
   ```

2. Check Open WebUI logs:
   ```bash
   docker logs open-webui
   ```

3. Verify server URL and Bearer token are correct in Open WebUI settings

### Issue: Authentication failures

**Solution:**
1. Verify credentials are set:
   ```bash
   docker exec aos-mcp-server env | grep AOS_
   ```

2. Test direct SSH connection:
   ```bash
   ssh admin@192.168.1.100
   ```

3. Check known_hosts file if strict checking enabled

### Issue: "Invalid or missing Bearer token"

**Solution:**
1. Ensure `AOS_INTERNAL_API_KEY` is set in your `.env` file
2. Add the Bearer token in Open WebUI: `Bearer your-api-key-here`
3. Test manually:
   ```bash
   curl -X POST http://localhost:8080/mcp/sse \
     -H "Authorization: Bearer your-api-key-here" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
   ```

### Issue: Connection timeout

**Solution:**
1. Verify network connectivity:
   ```bash
   curl -v http://your-mcp-server:8080/healthz
   ```

2. Check firewall rules between Open WebUI and MCP server

3. Increase timeout in Open WebUI settings

### Issue: SSE stream errors

**Solution:**
1. Check server logs:
   ```bash
   docker-compose logs -f aos-mcp-server
   ```

2. Verify Open WebUI version ≥ 0.6.31

3. Test SSE endpoint manually:
   ```bash
   curl -N http://localhost:8080/mcp/sse -X POST \
     -H "Authorization: Bearer $AOS_INTERNAL_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
   ```

---

## Advanced Configuration

### API Key Authentication (Required for Production)

1. Set environment variable:
   ```bash
   export INTERNAL_API_KEY="your_secret_key"
   ```

2. Configure Open WebUI with Bearer token:
   ```
   Auth: Bearer
   Token: your_secret_key
   ```

### Nginx Reverse Proxy

If using Nginx, disable buffering for SSE:

```nginx
location /mcp/sse {
    proxy_pass http://aos-mcp-server:8080;
    proxy_buffering off;
    proxy_cache off;
    proxy_set_header X-Accel-Buffering no;
    proxy_set_header Connection '';
    proxy_http_version 1.1;
    chunked_transfer_encoding off;
}
```

### Resource Limits

Adjust Docker resource limits in `deploy/docker-compose.yaml`:

```yaml
services:
  aos-mcp-server:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 256M
```

---

## Performance Considerations

- **Concurrent Requests**: Server handles multiple simultaneous tool calls
- **SSH Connection Pooling**: Reuses connections when possible
- **Timeout Configuration**: Adjust in `config.yaml` for slow networks
- **Output Limits**: `max_output_bytes` prevents memory exhaustion

---

## Support & Resources

- **Documentation**: [README.md](README.md)
- **Examples**: [examples/](examples/) directory
- **Issues**: [GitHub Issues](https://github.com/0xEkho/ALE-OmniSwitch-MCP/issues)
- **Open WebUI Docs**: https://docs.openwebui.com/features/mcp/

---

## License

This project is released into the public domain under the [Unlicense](LICENSE).
