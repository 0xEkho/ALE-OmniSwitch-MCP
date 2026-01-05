# Security Quick Start Guide

Guide rapide pour déployer le MCP avec les fonctionnalités de sécurité essentielles.

## 🚀 Configuration rapide (5 minutes)

### 1. Générer un Bearer Token

```bash
# Générer un token aléatoire sécurisé
openssl rand -hex 32

# Exemple de sortie:
# your-generated-api-key-from-openssl-rand-hex-32
```

### 2. Configurer les variables d'environnement

Éditer `deploy/.env` :

```bash
# === CREDENTIALS ===
AOS_GLOBAL_USERNAME=network_admin
AOS_GLOBAL_PASSWORD=your_secure_password

# === SECURITY (REQUIRED FOR PRODUCTION) ===
AOS_INTERNAL_API_KEY=your-generated-api-key-from-openssl-rand-hex-32

# IP whitelisting: remplacer par vos réseaux
AOS_ALLOWED_IPS=10.0.0.0/8,192.168.0.0/16,172.16.0.0/12,127.0.0.1/32

# Rate limiting
AOS_RATE_LIMIT_PER_MINUTE=60
```

### 3. Vérifier config.yaml

Éditer `config.yaml` :

```yaml
ssh:
  strict_host_key_checking: true  # ✅ Activer en production
  known_hosts_file: ./known_hosts
  max_output_bytes: 500000        # ✅ Augmenté pour grosses réponses
```

### 4. Ajouter les host keys SSH

```bash
# Scanner vos switches
ssh-keyscan 192.168.1.10 >> known_hosts
ssh-keyscan 192.168.1.11 >> known_hosts
# ... répéter pour tous les switches
```

### 5. Démarrer le serveur

```bash
cd deploy
docker-compose up -d --build
```

### 6. Tester la sécurité

```bash
# Test 1: Accès sans token (doit échouer avec 401)
curl -X POST http://localhost:8080/mcp/sse \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# Test 2: Accès avec token (doit réussir)
curl -X POST http://localhost:8080/mcp/sse \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-generated-api-key-from-openssl-rand-hex-32" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# Test 3: Health check
curl http://localhost:8080/healthz
```

## 🔧 Configuration Open WebUI

### Ajouter le MCP Server

1. **Admin Panel → Settings → External Tools**
2. **Add MCP Server** :
   - **Type** : `MCP (Streamable HTTP)`
   - **Server URL** : `http://your-mcp-server:8080/mcp/sse`
   - **Auth** : `Bearer`
   - **Token** : `your-generated-api-key-from-openssl-rand-hex-32`
   - **Name** : `ALE OmniSwitch Network Tools`
3. **Save** et redémarrer Open WebUI

### Vérifier l'intégration

Dans Open WebUI, taper :
```
Liste les tools disponibles pour ALE OmniSwitch
```

Le modèle devrait répondre avec les 20 tools disponibles.

## 📊 Monitoring

### Vérifier les logs

```bash
# Logs en temps réel
docker logs -f aos-mcp-server

# Rechercher les erreurs
docker logs aos-mcp-server | grep -i error

# Rechercher les accès bloqués
docker logs aos-mcp-server | grep -i "access denied"

# Rechercher rate limiting
docker logs aos-mcp-server | grep -i "rate limit"
```

### Logs d'audit

```bash
# Filtrer par utilisateur
docker logs aos-mcp-server | grep "User: admin@company.com"

# Filtrer par tool
docker logs aos-mcp-server | grep "Tool call: aos.device.facts"

# Filtrer les échecs
docker logs aos-mcp-server | grep "Tool call failed"
```

## 🔍 Troubleshooting

### Erreur 401 (Unauthorized)

**Cause** : Token manquant ou incorrect

**Solution** :
1. Vérifier que `AOS_INTERNAL_API_KEY` est défini dans `.env`
2. Vérifier que Open WebUI utilise le même token
3. Redémarrer le container : `docker-compose restart`

### Erreur 403 (Forbidden)

**Cause** : IP bloquée par le whitelisting

**Solution** :
1. Vérifier l'IP source : `docker logs aos-mcp-server | grep "Access denied"`
2. Ajouter l'IP/CIDR dans `AOS_ALLOWED_IPS`
3. Ou désactiver temporairement : `unset AOS_ALLOWED_IPS`

### Erreur 429 (Too Many Requests)

**Cause** : Rate limiting dépassé

**Solution** :
1. Augmenter le rate limit : `AOS_RATE_LIMIT_PER_MINUTE=120`
2. Ou identifier le client abusif dans les logs

### Erreur SSH Connection Timeout

**Cause** : Switch injoignable ou timeout trop court

**Solution** :
1. Vérifier connectivité : `ping 192.168.1.10`
2. Tester SSH : `ssh admin@192.168.1.10`
3. Augmenter timeout dans `config.yaml` :
   ```yaml
   ssh:
     connect_timeout_s: 20
     default_command_timeout_s: 60
   ```

## 📖 Documentation complète

Pour aller plus loin :
- **[SECURITY.md](SECURITY.md)** - Guide complet de sécurité (12 sections)
- **[README.md](README.md)** - Documentation générale
- **[OPEN_WEBUI.md](OPEN_WEBUI.md)** - Intégration Open WebUI

## ✅ Checklist production

- [ ] Bearer token généré (32+ caractères)
- [ ] IP whitelisting configuré
- [ ] Rate limiting configuré (60/min recommandé)
- [ ] SSH strict host key checking activé
- [ ] known_hosts rempli avec les switches
- [ ] max_output_bytes augmenté (500KB)
- [ ] Logs monitoring configuré
- [ ] Open WebUI configuré avec Bearer token
- [ ] Tests de sécurité effectués (401, 403, 429)
- [ ] Resource limits Docker configurés

---

**Version** : 1.2.0  
**Dernière mise à jour** : 2025-01-05
