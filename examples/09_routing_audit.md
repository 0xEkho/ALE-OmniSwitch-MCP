# aos.routing.audit - Routing Configuration Audit

## Purpose

Comprehensive routing audit including VRFs, OSPF configuration, static routes, and IP interfaces. Detects misconfigurations, missing neighbors, and routing issues.

## When to Use

- Audit routing configurations
- Verify OSPF neighbor relationships
- Check for routing loops or black holes
- Document routing topology

## Use Case

**Scenario**: OSPF adjacencies are flapping - need complete routing configuration review.

**User Prompt**: "Show me complete routing configuration on 192.168.1.100 including OSPF neighbors"

## Request

```bash
curl -s \
  -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: $AOS_API_KEY" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "neteng@company.com",
      "correlation_id": "routing-troubleshoot-ospf-flap"
    },
    "tool": "aos.routing.audit",
    "args": {
      "host": "192.168.1.100"
    }
  }' | jq
```

## Tips

- Check OSPF neighbor states for adjacency issues
- Verify router IDs are unique
- Review static routes for conflicts
- Audit VRF configurations separately
