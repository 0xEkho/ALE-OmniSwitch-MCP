# Open WebUI Integration via OpenAPI (Alternative Method)

Si Open WebUI demande une "API base URL" et "OpenAPI Spec", utilisez cette méthode.

## Configuration Open WebUI

### Dans Open WebUI → Admin Panel → Settings → External Tools

**Ajouter un outil OpenAPI :**

```
Name: ALE OmniSwitch Tools
API Base URL: http://your-server:8080
OpenAPI Spec URL: http://your-server:8080/openapi.json
Auth: None (ou Bearer si API key configurée)
```

## Endpoints Disponibles

Une fois le serveur démarré, FastAPI génère automatiquement :

- **OpenAPI Spec** : `http://localhost:8080/openapi.json`
- **Swagger UI** : `http://localhost:8080/docs`
- **ReDoc** : `http://localhost:8080/redoc`

## Test Rapide

```bash
# 1. Démarrer le serveur
cd deploy
cp .env.example .env
# Edit .env: set credentials and AOS_INTERNAL_API_KEY
docker-compose up -d

# 2. Vérifier health (pas d'auth requise)
curl http://localhost:8080/healthz

# 3. Accéder à Swagger UI
open http://localhost:8080/docs

# 4. Tester un endpoint (auth requise)
curl -X POST http://localhost:8080/v1/tools/call \
  -H "X-Internal-Api-Key: $AOS_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "tool": "aos.device.facts",
    "args": {"host": "192.168.1.100"},
    "context": {}
  }'
```

## Configuration dans Open WebUI

### Méthode 1 : OpenAPI Direct (Recommandé)

1. Aller dans **Admin Panel → Settings → External Tools**
2. Cliquer **"+ Add Tool"**
3. Sélectionner **"OpenAPI Server"**
4. Remplir :
   ```
   Name: ALE OmniSwitch
   API Base URL: http://your-mcp-server:8080
   OpenAPI Spec URL: http://your-mcp-server:8080/openapi.json
   Auth: API Key (X-Internal-Api-Key: your-api-key)
   ```
5. Cliquer **Save**

### Méthode 2 : Via MCPO (Pour MCP natif)

Si vous voulez utiliser le protocole MCP SSE natif via MCPO :

1. **Installer MCPO** :
   ```bash
   pip install mcpo
   ```

2. **Configurer MCPO** - Deux options :

   **Option A: Connexion à Docker (production)**
   ```json
   {
     "mcpServers": {
       "ale-omniswitch": {
         "type": "sse",
         "url": "http://localhost:8080/mcp/sse",
         "headers": {
           "Authorization": "Bearer your_api_key"
         }
       }
     }
   }
   ```

   **Option B: Lancement local (développement)**
   ```json
   {
     "mcpServers": {
       "ale-omniswitch": {
         "command": "python",
         "args": ["-m", "uvicorn", "aos_server.main:create_app", "--factory", "--port", "8080"],
         "env": {
           "AOS_GLOBAL_USERNAME": "admin",
           "AOS_GLOBAL_PASSWORD": "password"
         }
       }
     }
   }
   ```

3. **Démarrer MCPO** :
   ```bash
   mcpo --config mcpo-config.json --port 8000
   ```

4. **Configurer Open WebUI** :
   ```
   Type: MCP Server
   URL: http://localhost:8000/ale-omniswitch
   ```

## Endpoints Exposés via OpenAPI

### Core Endpoints

```
POST /v1/tools/list       - Liste tous les outils (19 outils)
POST /v1/tools/call       - Exécute un outil
GET  /healthz             - Health check
GET  /mcp/metadata        - MCP metadata
```

### Format de Requête pour tools/call

```json
{
  "tool": "aos.device.facts",
  "args": {
    "host": "192.168.1.100"
  },
  "context": {
    "subject": "user@example.com",
    "correlation_id": "request-123"
  }
}
```

### Format de Réponse

```json
{
  "status": "ok",
  "data": {
    "host": "192.168.1.100",
    "hostname": "CORE-SW-01",
    "model": "OS6900-X20",
    "software_version": "8.9.221.R01"
  },
  "warnings": [],
  "meta": {
    "tool": "aos.device.facts"
  }
}
```

## Liste des 19 Outils Disponibles

### Core Operations
- `aos.cli.readonly` - Execute read-only commands
- `aos.device.facts` - Device information
- `aos.config.backup` - Backup configuration

### Port Management
- `aos.port.info` - Single port status
- `aos.interfaces.discover` - All interfaces
- `aos.port.discover` - Comprehensive port analysis

### Power over Ethernet
- `aos.diag.poe` - PoE diagnostics
- `aos.poe.restart` - Restart PoE (write)

### Network Audits
- `aos.vlan.audit` - VLAN audit
- `aos.routing.audit` - Routing audit
- `aos.spantree.audit` - STP audit

### Diagnostics
- `aos.diag.ping` - Ping from switch
- `aos.diag.traceroute` - Traceroute
- `aos.mac.lookup` - MAC lookup

### Health
- `aos.health.monitor` - Health check
- `aos.chassis.status` - Chassis status

### Protocols
- `aos.lacp.info` - LACP/LAG info
- `aos.ntp.status` - NTP status
- `aos.dhcp.relay.info` - DHCP Relay configuration

## Utilisation dans Open WebUI

Une fois configuré, vous pouvez poser des questions en langage naturel :

```
"Liste tous les outils réseau disponibles"
→ Open WebUI appelle GET /v1/tools/list

"Affiche les infos du switch 192.168.1.100"
→ Open WebUI appelle POST /v1/tools/call avec aos.device.facts

"Quelle est la consommation PoE ?"
→ Open WebUI appelle POST /v1/tools/call avec aos.diag.poe
```

## Troubleshooting

### Health check

```bash
# Health endpoint (pas d'auth requise)
curl http://localhost:8080/healthz
```

### Open WebUI ne voit pas les outils

1. Vérifier que l'URL est correcte dans la config Open WebUI
2. Tester manuellement avec authentification :
   ```bash
   curl -X POST http://localhost:8080/v1/tools/list \
     -H "X-Internal-Api-Key: $AOS_API_KEY" \
     -H 'Content-Type: application/json' \
     -d '{}'
   ```
3. Vérifier les logs :
   ```bash
   docker-compose logs -f aos-mcp-server
   ```

### Erreur "Missing or invalid X-Internal-Api-Key"

L'API requiert une authentification. Configurer dans Open WebUI :

```
Auth Type: API Key
Header: X-Internal-Api-Key
Value: votre_api_key
```

Ou pour SSE :
```
Auth: Bearer
Token: votre_api_key
```

## Différences MCP SSE vs OpenAPI

| Feature | MCP SSE (/mcp/sse) | OpenAPI (/v1/tools/*) |
|---------|-------------------|----------------------|
| Protocol | JSON-RPC 2.0 | REST |
| Transport | Server-Sent Events | HTTP JSON |
| Open WebUI Support | v0.6.31+ natif | Toutes versions |
| Setup | Direct ou MCPO | Direct |
| Recommandé | Open WebUI récent | Open WebUI standard |

**Pour la plupart des cas, utilisez la méthode OpenAPI (cette page) car elle est plus simple et universelle.**

## Support

- Documentation complète : [OPEN_WEBUI.md](OPEN_WEBUI.md)
- Quick start : [OPEN_WEBUI_QUICKSTART.md](OPEN_WEBUI_QUICKSTART.md)
- API docs : http://localhost:8080/docs
