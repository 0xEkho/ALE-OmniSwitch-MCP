# Open WebUI LLM Optimization Guide

This guide explains how to optimize the MCP server for LLM token efficiency in Open WebUI.

## Problem: LLM Token Overload

When Open WebUI calls `/v1/tools/list`, it can overwhelm the LLM context with tool schemas, causing:
- Timeouts without response
- Excessive token consumption
- Slow responses

## Solution: Compact Response Modes

The server provides **3 response formats** for `/v1/tools/list`:

| Mode | Lines | Size | Use Case |
|------|-------|------|----------|
| **ultra_compact** | 23 | 400 bytes | ⭐ Best for LLM discovery |
| **compact** (default) | 80 | 2KB | Balanced (name + description) |
| **full** | 518 | 8KB | Developer/debugging only |

### Mode 1: Ultra Compact (Recommended for LLMs)

**Returns:** Tool names only

```json
{
  "tools": [
    "aos.chassis.status",
    "aos.cli.readonly",
    "aos.config.backup",
    ...
  ]
}
```

**23 lines** - Minimal token usage, perfect for LLM tool discovery.

### Mode 2: Compact (Default)

**Returns:** Names + short descriptions

```json
{
  "tools": [
    {
      "name": "aos.chassis.status",
      "description": "Get chassis hardware status including temperature, fans, and power supplies."
    },
    ...
  ]
}
```

**80 lines** - Provides context without overwhelming tokens.

### Mode 3: Full (Developers Only)

**Returns:** Complete schemas with input/output definitions

**518 lines** - Use only when you need to see exact parameter schemas.

---

## How to Configure

### Method 1: Body JSON (Recommended)

Send mode flags in the POST body:

```bash
# Ultra compact (best for LLMs)
curl -X POST http://localhost:8080/v1/tools/list \
  -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: YOUR_KEY" \
  -d '{"ultra_compact": true}'

# Compact (default)
curl -X POST http://localhost:8080/v1/tools/list \
  -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: YOUR_KEY" \
  -d '{}'

# Full schemas
curl -X POST http://localhost:8080/v1/tools/list \
  -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: YOUR_KEY" \
  -d '{"compact": false}'
```

### Method 2: Query Parameters

Add flags to URL:

```bash
# Ultra compact
curl -X POST 'http://localhost:8080/v1/tools/list?ultra_compact=true' \
  -H "X-Internal-Api-Key: YOUR_KEY"

# Compact (default)
curl -X POST http://localhost:8080/v1/tools/list \
  -H "X-Internal-Api-Key: YOUR_KEY"

# Full schemas
curl -X POST 'http://localhost:8080/v1/tools/list?compact=false' \
  -H "X-Internal-Api-Key: YOUR_KEY"
```

---

## Open WebUI Configuration

### For MCP SSE Endpoint

If you're using `/mcp/sse`, the compact mode is already optimized. No changes needed.

### For OpenAPI Integration

If you configured Open WebUI to use `/v1/tools/list` directly:

1. Open your Open WebUI configuration
2. Find the tool server settings
3. If possible, add query parameter to URL:
   ```
   http://your-server:8080/v1/tools/list?ultra_compact=true
   ```

**Note:** Most Open WebUI setups use `/mcp/sse` which handles this automatically.

---

## Performance Comparison

| Mode | Lines | Bytes | Tokens (est.) | LLM Impact |
|------|-------|-------|---------------|------------|
| ultra_compact | 23 | 400 | ~100 | ✅ Minimal |
| compact | 80 | 2,000 | ~500 | ✅ Low |
| full | 518 | 8,300 | ~2,000 | ⚠️ High |

**Recommendation:** Use `ultra_compact=true` if your LLM times out on tool discovery.

---

## Troubleshooting

### LLM Still Times Out

1. **Verify compact mode is active:**
   ```bash
   curl -X POST http://localhost:8080/v1/tools/list \
     -H "X-Internal-Api-Key: YOUR_KEY" \
     -d '{"ultra_compact": true}' | jq '.'
   ```

2. **Check response size:**
   ```bash
   curl -X POST http://localhost:8080/v1/tools/list \
     -H "X-Internal-Api-Key: YOUR_KEY" \
     -d '{"ultra_compact": true}' | wc -l
   # Should show: 23 lines
   ```

3. **Check server logs:**
   ```bash
   docker logs aos-mcp-server --tail 50
   ```

### LLM Needs More Context

If the LLM needs descriptions, switch to compact mode:

```json
{"compact": true}
```

This provides 80 lines with descriptions instead of just names.

---

## Best Practices

✅ **DO:**
- Use `ultra_compact=true` for initial tool discovery
- Use `compact=true` if LLM needs descriptions
- Use `compact=false` only for development/debugging

❌ **DON'T:**
- Use full mode in production with LLMs
- Send tool list on every request (cache if possible)
- Hardcode large responses in prompts

---

## Related Documentation

- [OPEN_WEBUI.md](OPEN_WEBUI.md) - Full integration guide
- [OPEN_WEBUI_QUICKSTART.md](OPEN_WEBUI_QUICKSTART.md) - Quick setup
- [README.md](README.md) - General documentation

---

**Version:** 1.2.0  
**Last Updated:** 2025-01-05
