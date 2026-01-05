# Open WebUI Quick Start

Get your ALE OmniSwitch MCP Server integrated with Open WebUI in 5 minutes.

## Prerequisites

- Docker and Docker Compose installed
- Open WebUI v0.6.31+ running
- Network switches accessible from MCP server

## Step 1: Deploy MCP Server (2 minutes)

```bash
# Clone repository
git clone https://github.com/0xEkho/ALE-OmniSwitch-MCP.git
cd ALE-OmniSwitch-MCP

# Configure credentials
cd deploy
cp .env.example .env
nano .env  # Add your network credentials

# Required:
AOS_GLOBAL_USERNAME=network_admin
AOS_GLOBAL_PASSWORD=your_secure_password
AOS_INTERNAL_API_KEY=$(openssl rand -hex 32)

# Start server
cd ..
cd deploy && docker-compose up -d

# Verify (health check doesn't require auth)
curl http://localhost:8080/healthz
# Expected: {"status":"ok"}
```

## Step 2: Configure Open WebUI (2 minutes)

1. Open your **Open WebUI** interface
2. Go to: **Admin Panel → Settings → External Tools**
3. Click: **"+" (Add MCP Server)**
4. Enter:
   ```
   Type: MCP (Streamable HTTP)
   Server URL: http://your-server-ip:8080/mcp/sse
   Auth: Bearer
   Token: <your AOS_INTERNAL_API_KEY value>
   ID: ale-omniswitch
   Name: ALE OmniSwitch Network Tools
   ```
5. Click **Save**
6. Restart Open WebUI if prompted

## Step 3: Test Integration (1 minute)

Open a chat in Open WebUI and try:

```
"List all available network tools"
```

You should see 20 ALE OmniSwitch tools discovered.

Then try a real query:

```
"Get device facts for switch 192.168.1.100"
```

## Example Queries

Once integrated, ask natural language questions:

- **Device Info**: "What's the model and software version of switch 192.168.1.100?"
- **Port Status**: "Show me all ports with errors on switch 192.168.1.100"
- **PoE**: "What's the total PoE consumption on switch 192.168.1.100?"
- **Health**: "Check CPU, memory and temperature on switch 192.168.1.100"
- **Audit**: "Audit VLANs on switch 192.168.1.100"
- **Troubleshoot**: "Trace route from switch 192.168.1.100 to 8.8.8.8"

## Troubleshooting

**Tools not appearing?**

```bash
# Test SSE endpoint (requires auth)
curl -X POST http://localhost:8080/mcp/sse \
  -H "Authorization: Bearer $AOS_INTERNAL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

**"Invalid or missing Bearer token" error?**

Ensure you've set the Bearer token in Open WebUI's Auth settings.

**Authentication errors?**

```bash
# Verify credentials loaded
docker exec aos-mcp-server env | grep AOS_
```

**Connection issues?**

```bash
# Check server logs
docker-compose logs -f aos-mcp-server
```

## Next Steps

- Read [OPEN_WEBUI.md](OPEN_WEBUI.md) for advanced configuration
- Check [examples/](examples/) for detailed tool usage
- Configure zone-based auth for multi-site deployments

---

**Need help?** Open an issue at https://github.com/0xEkho/ALE-OmniSwitch-MCP/issues
