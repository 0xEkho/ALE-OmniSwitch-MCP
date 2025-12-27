# aos.vlan.audit - VLAN Configuration Audit

## Purpose

Audit VLAN configurations with automatic issue detection. Checks for inactive VLANs, missing names, MTU inconsistencies, and other configuration problems.

## When to Use

- Regular configuration audits
- Verify VLAN setup after changes
- Identify unused or misconfigured VLANs
- Compliance checks

## Use Case

**Scenario**: Quarterly network audit requires VLAN configuration review.

**User Prompt**: "Audit all VLAN configurations on switch 192.168.1.100"

## Request

```bash
curl -s \
  -H "Content-Type: application/json" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "audit@company.com",
      "correlation_id": "quarterly-vlan-audit-q1"
    },
    "tool": "aos.vlan.audit",
    "args": {
      "host": "192.168.1.100"
    }
  }' | jq
```

## Audit Specific VLAN

```bash
curl -s ... -d '{"args": {"host": "192.168.1.100", "vlan_id": 100}}' | jq
```

## Tips

- Review `issues` array for configuration problems
- Check `summary` for VLAN statistics
- Filter VLANs by admin/oper state
- Export for compliance documentation
