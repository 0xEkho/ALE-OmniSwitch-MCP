# aos.config.backup - Configuration Backup

## Purpose

Retrieve complete switch configuration (equivalent to `write terminal` command). Essential for backup, documentation, and disaster recovery.

## When to Use

- Daily/weekly configuration backups
- Before major configuration changes
- Disaster recovery planning
- Configuration version control
- Compliance documentation

## Use Case

**Scenario**: Automated nightly backup of all switch configurations for disaster recovery.

**User Prompt**: "Backup the configuration from switch 192.168.1.100"

## Request

```bash
curl -s \
  -H "Content-Type: application/json" \
  -X POST "http://localhost:8080/v1/tools/call" \
  -d '{
    "context": {
      "subject": "backup-system@company.com",
      "correlation_id": "nightly-backup-2025-01-15"
    },
    "tool": "aos.config.backup",
    "args": {
      "host": "192.168.1.100"
    }
  }' | jq
```

## Save to File

```bash
curl -s ... | jq -r '.data.config' > switch-192.168.1.100-$(date +%Y%m%d).cfg
```

## Automated Backup Script

```bash
#!/bin/bash
SWITCHES=("192.168.1.100" "192.168.1.101" "192.168.1.102")
BACKUP_DIR="/backups/switches"
DATE=$(date +%Y%m%d)

for switch in "${SWITCHES[@]}"; do
  echo "Backing up $switch..."
  curl -s \
    -H "Content-Type: application/json" \
    -X POST "http://localhost:8080/v1/tools/call" \
    -d "{
      \"context\": {
        \"subject\": \"backup-automation\",
        \"correlation_id\": \"backup-$switch-$DATE\"
      },
      \"tool\": \"aos.config.backup\",
      \"args\": {
        \"host\": \"$switch\"
      }
    }" | jq -r '.data.config' > "$BACKUP_DIR/$switch-$DATE.cfg"
done
```

## Tips

- Store backups in version control (Git)
- Encrypt backups containing sensitive data
- Test restore procedure regularly
- Keep multiple backup generations
- Include hostname in filename for clarity
- Schedule daily backups during maintenance windows
