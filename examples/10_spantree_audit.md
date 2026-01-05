# aos.spantree.audit - Spanning Tree Audit

## Purpose

Audit Spanning Tree Protocol configuration, topology, and port states. Identifies potential loops, forwarding issues, and STP misconfigurations.

## When to Use

- Troubleshoot network loops
- Verify STP topology
- Audit STP configuration
- Check root bridge placement

## Use Case

**Scenario**: Network experiencing intermittent loops - need STP configuration review.

**User Prompt**: "Check STP configuration on 192.168.1.100 for potential loop issues"

## Request

```bash
curl -s \
  -H "Content-Type: application/json" \
  -H "X-Internal-Api-Key: $AOS_API_KEY" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "netops@company.com",
      "correlation_id": "stp-audit-loop-troubleshooting"
    },
    "tool": "aos.spantree.audit",
    "args": {
      "host": "192.168.1.100"
    }
  }' | jq
```

## Tips

- Check for ports in blocking state
- Verify root bridge is correct switch
- Look for topology changes in logs
- Audit STP priorities and port costs
