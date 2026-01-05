# Security Guide - ALE OmniSwitch MCP Server

Ce guide détaille les fonctionnalités de sécurité et les bonnes pratiques pour déployer le serveur MCP en production.

## 🔒 Vue d'ensemble des couches de sécurité

Le serveur MCP implémente plusieurs couches de sécurité complémentaires :

1. **Authentification** - Bearer token sur l'endpoint MCP SSE
2. **Contrôle d'accès réseau** - Whitelisting IP/CIDR
3. **Rate limiting** - Protection contre le DoS par IP
4. **Audit logging** - Traçabilité complète avec correlation_id
5. **Command policy** - Validation des commandes SSH
6. **SSH security** - Host key verification et credentials isolés

---

## 1. Authentification Bearer Token

### Configuration

Activer l'authentification sur l'endpoint `/mcp/sse` :

```bash
# Générer un token aléatoire
export AOS_INTERNAL_API_KEY=$(openssl rand -hex 32)

# Ou définir manuellement dans .env
AOS_INTERNAL_API_KEY=your-secure-random-token-here
```

### Intégration Open WebUI

Configurer le Bearer token dans Open WebUI :

1. **Admin Panel → Settings → External Tools**
2. **Add MCP Server** :
   - Type : `MCP (Streamable HTTP)`
   - Server URL : `http://your-mcp-server:8080/mcp/sse`
   - **Auth** : `Bearer`
   - **Token** : `your-secure-random-token-here`
3. Save et redémarrer Open WebUI

### Test manuel

```bash
# Sans token (échoue avec 401)
curl -X POST http://localhost:8080/mcp/sse \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'

# Avec token (succès)
curl -X POST http://localhost:8080/mcp/sse \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secure-random-token-here" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

---

## 2. Whitelisting IP/CIDR

### Configuration

Limiter l'accès aux réseaux de confiance uniquement :

```bash
# Dans .env ou variables d'environnement
AOS_ALLOWED_IPS=10.0.0.0/8,192.168.0.0/16,172.16.0.0/12,127.0.0.1/32

# Format : CIDRs séparés par des virgules
# Exemples :
# - RFC1918 privé : 10.0.0.0/8, 192.168.0.0/16, 172.16.0.0/12
# - Localhost : 127.0.0.1/32
# - Subnet spécifique : 192.168.1.0/24
```

### Cas d'usage

**Scénario 1 : Open WebUI et MCP sur le même hôte**
```bash
AOS_ALLOWED_IPS=127.0.0.1/32
```

**Scénario 2 : Open WebUI sur réseau interne**
```bash
AOS_ALLOWED_IPS=10.0.0.0/8,127.0.0.1/32
```

**Scénario 3 : Accès depuis plusieurs réseaux (Docker inclus)**
```bash
AOS_ALLOWED_IPS=10.0.0.0/8,192.168.0.0/16,172.16.0.0/12,127.0.0.1/32
```

### Comportement

- Si `AOS_ALLOWED_IPS` n'est **pas défini** → Pas de restriction IP
- Si `AOS_ALLOWED_IPS` est **défini** → Seules les IPs dans les CIDRs autorisés peuvent accéder
- Requête bloquée → HTTP 403 Forbidden + log warning

### Logs

```
2026-01-05 10:15:23 WARNING aos_server.mcp_sse Access denied for IP: 203.0.113.50
```

---

## 3. Rate Limiting

### Configuration

Limiter le nombre de requêtes par minute par adresse IP :

```bash
# Par défaut : 60 requêtes/minute/IP
AOS_RATE_LIMIT_PER_MINUTE=60

# Pour un environnement avec peu d'utilisateurs :
AOS_RATE_LIMIT_PER_MINUTE=120

# Pour un environnement public (restrictif) :
AOS_RATE_LIMIT_PER_MINUTE=30
```

### Comportement

- Rate limit appliqué **par IP source**
- Fenêtre glissante d'**1 minute**
- Dépassement → HTTP 429 Too Many Requests

### Headers de réponse

```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1704447600
```

### Protection DoS

Le rate limiting protège contre :
- **Flood** d'un seul client malveillant
- **Brute force** sur l'API
- **Consommation excessive** de ressources SSH

**Important** : Si Open WebUI et MCP sont derrière le même reverse proxy, tous les utilisateurs partageront la même IP (celle du proxy). Dans ce cas :
- Augmenter `AOS_RATE_LIMIT_PER_MINUTE`
- Ou configurer le proxy pour transmettre `X-Forwarded-For`

---

## 4. Audit Logging Enrichi

### Traçabilité complète

Chaque appel de tool est loggé avec :
- **User** : `subject` extrait du contexte Open WebUI
- **CorrelationID** : `requestId` pour tracer la requête bout-en-bout
- **Tool** : Nom du tool appelé
- **Arguments** : Paramètres passés
- **Status** : Success/Failure
- **Error** : Message d'erreur si échec

### Format de log

```
2026-01-05 10:30:45 INFO aos_server.mcp_sse Tool call: aos.device.facts | User: admin@company.com | CorrelationID: req-001-abc123
2026-01-05 10:30:47 INFO aos_server.mcp_sse Tool call success: aos.device.facts | User: admin@company.com
```

### Logs d'erreur

```
2026-01-05 10:35:12 ERROR aos_server.mcp_sse Tool call failed: aos.cli.readonly | User: operator@company.com | Error: SSH connection timeout
```

### Analyse des logs

Exemples de requêtes utiles :

```bash
# Filtrer par utilisateur
grep "User: admin@company.com" /app/logs/aos-server.log

# Filtrer par tool
grep "Tool call: aos.poe.restart" /app/logs/aos-server.log

# Filtrer les erreurs
grep "Tool call failed" /app/logs/aos-server.log

# Filtrer par correlation ID
grep "CorrelationID: req-001-abc123" /app/logs/aos-server.log
```

### Intégration SIEM

Les logs peuvent être envoyés à un SIEM (Splunk, ELK, etc.) via :
- Docker log driver (syslog, fluentd, etc.)
- Montage de volume `/app/logs` vers un collecteur
- Parser JSON structuré (`structlog` activé)

---

## 5. Command Policy Enforcement

### Validation des commandes

Seules les commandes **explicitement autorisées** dans `config.yaml` peuvent être exécutées :

```yaml
command_policy:
  allow_regex:
    - '^show\s+.*$'                     # Toutes les commandes "show"
    - '^vrf\s+\S+\s+show\s+.*$'        # Show commands dans un VRF
    - '^ping\s+.*$'                     # Diagnostics ping
    - '^traceroute\s+.*$'               # Diagnostics traceroute
    - '^lanpower\s+port\s+.*\s+admin-state\s+(enable|disable)$'  # PoE restart uniquement
    - '^write\s+terminal$'              # Backup config uniquement
  
  deny_regex: []                        # Blocage explicite (optionnel)
  max_command_length: 512               # Limite injection
  deny_multiline: true                  # Bloque les commandes multi-lignes
  strip_ansi: true                      # Nettoie les codes ANSI
  
  redactions:                           # Masquage automatique
    - pattern: '(?i)(password\s+)(\S+)'
      replacement: '\1***'
    - pattern: '(?i)(community\s+)(\S+)'
      replacement: '\1***'
```

### Principe de moindre privilège

**Read-only par défaut** : 18 tools sur 19 sont en lecture seule. Seul `aos.poe.restart` effectue une écriture.

Pour désactiver le seul tool avec écriture, supprimer la ligne :
```yaml
    - '^lanpower\s+port\s+.*\s+admin-state\s+(enable|disable)$'
```

---

## 6. SSH Security

### Host Key Verification

**Production (recommandé)** :
```yaml
ssh:
  strict_host_key_checking: true
  known_hosts_file: ./known_hosts
```

Ajouter les fingerprints SSH des switches :
```bash
ssh-keyscan 192.168.1.10 >> known_hosts
ssh-keyscan 192.168.1.11 >> known_hosts
# Répéter pour tous les switches
```

**Test/Dev uniquement** :
```yaml
ssh:
  strict_host_key_checking: false  # ⚠️ Ne PAS utiliser en production
```

### Zone-Based Authentication

Isolation des credentials par zone réseau :

```yaml
zone_auth:
  global:
    username_env: AOS_GLOBAL_USERNAME      # Essayé en premier
    password_env: AOS_GLOBAL_PASSWORD
  zones:
    9:  # 10.9.0.0/16
      username_env: AOS_ZONE9_USERNAME     # Fallback pour zone 9
      password_env: AOS_ZONE9_PASSWORD
    1:  # 10.1.0.0/16
      username_env: AOS_ZONE1_USERNAME
      password_env: AOS_ZONE1_PASSWORD
```

**Avantages** :
- Credentials globaux centralisés
- Fallback par site si nécessaire
- Isolation des zones (compromission limitée)
- Support 500+ switches multi-sites

### Timeouts & Limites

```yaml
ssh:
  connect_timeout_s: 10          # Timeout connexion SSH
  auth_timeout_s: 10             # Timeout authentification
  default_command_timeout_s: 30  # Timeout exécution commande
  max_output_bytes: 500000       # Limite taille réponse (500KB)
  keepalive_s: 30                # Keepalive SSH
```

**Augmenter `max_output_bytes`** : Si certaines commandes retournent beaucoup de données (ex: `show running-directory`), augmenter la limite :

```yaml
  max_output_bytes: 1000000  # 1MB
```

---

## 7. Docker Security

### Non-root execution

Le container s'exécute avec un utilisateur **non-root** :
```dockerfile
USER appuser:10001
```

### Read-only volumes

Configuration montée en lecture seule :
```yaml
volumes:
  - ../config.yaml:/app/config.yaml:ro
  - ../known_hosts:/app/known_hosts:ro
  - ../logs:/app/logs  # Seul volume writable
```

### Resource limits

Limite les ressources Docker pour éviter l'épuisement :
```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 1G
    reservations:
      cpus: '0.5'
      memory: 256M
```

### Health checks

Monitoring automatique avec restart si échec :
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/healthz"]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 10s
```

---

## 8. Reverse Proxy (Nginx/Traefik)

### Nginx avec SSE support

Configuration pour désactiver le buffering (requis pour SSE) :

```nginx
location /mcp/sse {
    proxy_pass http://aos-mcp-server:8080;
    
    # Désactiver le buffering pour SSE
    proxy_buffering off;
    proxy_cache off;
    proxy_set_header X-Accel-Buffering no;
    proxy_set_header Connection '';
    proxy_http_version 1.1;
    chunked_transfer_encoding off;
    
    # Transmettre l'IP client (pour rate limiting)
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Real-IP $remote_addr;
    
    # Timeouts
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 300s;  # Long timeout pour SSE
}
```

### IP whitelisting Nginx (couche supplémentaire)

```nginx
location /mcp/sse {
    # Whitelisting au niveau Nginx
    allow 10.0.0.0/8;
    allow 192.168.0.0/16;
    allow 127.0.0.1;
    deny all;
    
    proxy_pass http://aos-mcp-server:8080;
    # ... reste de la config
}
```

---

## 9. Checklist de déploiement sécurisé

### ✅ Configuration minimale (production)

```bash
# 1. Authentification Bearer token
AOS_INTERNAL_API_KEY=$(openssl rand -hex 32)

# 2. Whitelisting IP
AOS_ALLOWED_IPS=10.0.0.0/8,192.168.0.0/16,127.0.0.1/32

# 3. Rate limiting
AOS_RATE_LIMIT_PER_MINUTE=60

# 4. SSH strict mode
strict_host_key_checking: true
known_hosts_file: ./known_hosts

# 5. Logs structurés
AOS_LOG_LEVEL=INFO

# 6. Resource limits (docker-compose.yaml)
deploy.resources.limits.memory: 1G
```

### ✅ Vérifications post-déploiement

```bash
# 1. Health check
curl http://localhost:8080/healthz
# Attendu: {"status":"ok"}

# 2. Test Bearer token (doit échouer sans token)
curl -X POST http://localhost:8080/mcp/sse \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
# Attendu: 401 Unauthorized

# 3. Test IP whitelisting (depuis IP non autorisée)
# Attendu: 403 Forbidden

# 4. Vérifier logs
docker logs aos-mcp-server | tail -50

# 5. Test rate limiting (100 requêtes rapides)
for i in {1..100}; do
  curl -s http://localhost:8080/healthz > /dev/null
done
# Attendu: 429 Too Many Requests après 60 requêtes
```

---

## 10. Bonnes pratiques

### ✅ À FAIRE

- ✅ Utiliser Bearer token en production
- ✅ Activer IP whitelisting pour réseaux internes
- ✅ Activer strict host key checking
- ✅ Monitorer les logs avec SIEM/ELK
- ✅ Utiliser zone-based auth pour multi-sites
- ✅ Rate limiting ajusté selon votre charge
- ✅ Credentials en variables d'environnement uniquement
- ✅ Backup réguliers de `known_hosts`
- ✅ Resource limits Docker

### ❌ À ÉVITER

- ❌ Hardcoder credentials dans config.yaml
- ❌ Désactiver strict_host_key_checking en production
- ❌ Exposer port 8080 directement sur Internet
- ❌ Utiliser Bearer token faible (< 32 chars)
- ❌ Ignorer les logs d'erreur SSH
- ❌ Rate limit trop élevé (> 200/min)
- ❌ Désactiver IP whitelisting sans reverse proxy
- ❌ Partager credentials entre environnements (dev/prod)

---

## 11. Gestion des secrets (roadmap future)

Pour une sécurité maximale, intégrer un gestionnaire de secrets :

### HashiCorp Vault

```yaml
zone_auth:
  global:
    username_vault_path: secret/aos/global/username
    password_vault_path: secret/aos/global/password
```

### AWS Secrets Manager

```bash
# Rotation automatique des credentials
aws secretsmanager rotate-secret \
  --secret-id aos-global-credentials \
  --rotation-lambda-arn arn:aws:lambda:...
```

### Azure Key Vault

```bash
# Récupération sécurisée
az keyvault secret show --name aos-global-password --vault-name myvault
```

**Note** : Cette fonctionnalité n'est pas encore implémentée mais est dans la roadmap.

---

## 12. Monitoring & Alerting

### Métriques à surveiller

1. **Rate limit exceeded** → Potentielle attaque DoS
2. **IP blocked (403)** → Scan/attaque réseau
3. **Auth failures (401)** → Tentative d'accès non autorisée
4. **SSH timeouts** → Problème réseau/switches
5. **Tool failures** → Erreurs applicatives

### Exemple Prometheus metrics

```python
# À implémenter dans une version future
mcp_requests_total{status="200"} 1024
mcp_requests_total{status="401"} 5
mcp_requests_total{status="403"} 12
mcp_requests_total{status="429"} 3
mcp_tool_calls_total{tool="aos.device.facts",status="success"} 450
mcp_ssh_connection_duration_seconds{quantile="0.95"} 2.3
```

---

## Support

Pour toute question de sécurité :
- **GitHub Issues** : [Security label](https://github.com/0xEkho/ALE-OmniSwitch-MCP/issues?q=label%3Asecurity)
- **Email** : security@example.com (à configurer)
- **Documentation** : [README.md](README.md)

---

**Version** : 1.2.0  
**Dernière mise à jour** : 2025-01-05
