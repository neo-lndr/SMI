# Configuração de Rede Docker

## Conectando com development.localhost

O container está configurado para acessar serviços na máquina host, incluindo `development.localhost:8000`.

## Configuração Atual

### docker-compose.yml

```yaml
smi-h-engine-api:
  network_mode: host  # Usa a rede do host diretamente
  extra_hosts:
    - "development.localhost:host-gateway"  # Mapeia para IP do host
```

### Funcionamento

1. **network_mode: host**
   - Container compartilha a rede do host
   - Pode acessar `localhost`, `127.0.0.1` e `development.localhost`
   - Porta 8084 fica disponível diretamente no host

2. **extra_hosts**
   - Adiciona entrada em `/etc/hosts` do container
   - `host-gateway` resolve para o IP do host Docker
   - Funciona quando `network_mode: host` não é usado

## Teste de Conectividade

### Verificar Mapeamento
```bash
docker exec smi-h-engine-api cat /etc/hosts | grep development
# Saída: 0.250.250.254	development.localhost
```

### Testar Conexão HTTP
```bash
docker exec smi-h-engine-api gosu appuser python -c \
  "import requests; print(requests.get('http://development.localhost:8000/').status_code)"
# Saída: 200 (se servidor estiver rodando)
```

### Testar com curl (se disponível)
```bash
docker exec smi-h-engine-api curl -s http://development.localhost:8000/ | head -10
```

## Configurações Alternativas

### Opção 1: network_mode: host (Atual - Desenvolvimento)

**Vantagens:**
- ✅ Acesso direto a todos os serviços do host
- ✅ Sem necessidade de port mapping
- ✅ Performance máxima
- ✅ Ideal para desenvolvimento local

**Desvantagens:**
- ❌ Não funciona no Docker Desktop para Mac/Windows (funciona apenas no Linux)
- ❌ Não isola rede do container
- ❌ Não recomendado para produção

```yaml
# docker-compose.yml
services:
  smi-h-engine-api:
    network_mode: host
```

### Opção 2: extra_hosts com Bridge Network (Recomendado para Produção)

**Vantagens:**
- ✅ Funciona em todas as plataformas
- ✅ Isolamento de rede
- ✅ Port mapping explícito
- ✅ Compatível com Docker Compose networks

**Desvantagens:**
- ❌ Requer configuração de portas
- ❌ Levemente mais lento que host mode

```yaml
# docker-compose.yml
services:
  smi-h-engine-api:
    ports:
      - "8084:8084"
    extra_hosts:
      - "development.localhost:host-gateway"
      - "api.exemplo.com:192.168.1.100"
    networks:
      - msi-network

networks:
  msi-network:
    driver: bridge
```

### Opção 3: Usar IP Direto do Host

Se `host-gateway` não funcionar, use o IP real:

```bash
# Descobrir IP do host (Mac/Linux)
ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -1

# Ou no Mac especificamente
ipconfig getifaddr en0
```

```yaml
# docker-compose.yml
services:
  smi-h-engine-api:
    extra_hosts:
      - "development.localhost:192.168.1.10"  # IP real do host
```

### Opção 4: Conectar a Outro Container

Se `development.localhost` for outro container:

```yaml
# docker-compose.yml
services:
  development-api:
    image: frappe/frappe:latest
    container_name: development-api
    networks:
      - msi-network

  smi-h-engine-api:
    depends_on:
      - development-api
    environment:
      - ARTERIS_API_BASE_URL=http://development-api:8000/api
    networks:
      - msi-network

networks:
  msi-network:
    driver: bridge
```

## Troubleshooting

### Erro: Connection refused

```bash
# 1. Verificar se serviço está rodando no host
curl http://development.localhost:8000/

# 2. Verificar firewall
# Mac: System Preferences > Security & Privacy > Firewall

# 3. Verificar mapeamento de hosts
docker exec smi-h-engine-api cat /etc/hosts | grep development

# 4. Testar com IP direto
docker exec smi-h-engine-api gosu appuser python -c \
  "import requests; print(requests.get('http://192.168.1.10:8000/').status_code)"
```

### Erro: Name resolution failed

```bash
# 1. Verificar DNS do container
docker exec smi-h-engine-api cat /etc/resolv.conf

# 2. Adicionar DNS explícito no docker-compose.yml
dns:
  - 8.8.8.8
  - 8.8.4.4
```

### network_mode: host não funciona no Mac/Windows

Docker Desktop usa VM, então `host` não funciona como no Linux.

**Soluções:**
- Usar `extra_hosts` com `host-gateway`
- Usar IP direto do host
- Usar Docker nativo no Linux

## Validação

Execute este script para validar a conectividade:

```bash
#!/bin/bash
echo "=== TESTE DE CONECTIVIDADE ==="

echo "1. Mapeamento de hosts:"
docker exec smi-h-engine-api cat /etc/hosts | grep development

echo -e "\n2. Teste de conexão:"
docker exec smi-h-engine-api gosu appuser python -c \
  "import requests; r=requests.get('http://development.localhost:8000/', timeout=5); print(f'Status: {r.status_code}')" \
  2>&1 && echo "✓ Conexão OK" || echo "✗ Falha na conexão"

echo -e "\n3. Teste de API específica:"
docker exec smi-h-engine-api gosu appuser python -c \
  "import requests; r=requests.get('http://development.localhost:8000/api/method/ping', timeout=5); print(f'API: {r.status_code}')" \
  2>&1 || echo "API não disponível ou endpoint diferente"

echo -e "\n=== FIM DOS TESTES ==="
```

## Configuração para Diferentes Ambientes

### Desenvolvimento Local (.env)
```bash
ARTERIS_API_BASE_URL=http://development.localhost:8000/api
DISABLE_SSL_VERIFY=true
```

### Staging (.env.staging)
```bash
ARTERIS_API_BASE_URL=https://staging-api.exemplo.com/api
DISABLE_SSL_VERIFY=false
```

### Produção (.env.production)
```bash
ARTERIS_API_BASE_URL=https://api.exemplo.com/api
DISABLE_SSL_VERIFY=false
```

## Deploy com docker-compose.override.yml

Para não modificar o `docker-compose.yml` principal:

```yaml
# docker-compose.override.yml (automático)
version: '3.8'

services:
  smi-h-engine-api:
    extra_hosts:
      - "development.localhost:192.168.1.50"  # IP do seu ambiente
```

Docker Compose automaticamente mescla `docker-compose.yml` + `docker-compose.override.yml`.

## Múltiplos Hosts

Se precisar conectar com vários hosts:

```yaml
extra_hosts:
  - "development.localhost:host-gateway"
  - "staging.localhost:192.168.1.100"
  - "database.local:192.168.1.101"
  - "redis.local:192.168.1.102"
```

## VPN e Redes Complexas

Se estiver usando VPN ou rede corporativa:

```yaml
services:
  smi-h-engine-api:
    network_mode: host  # Usa configuração de rede do host, incluindo VPN
```

Ou configure rotas específicas:

```yaml
services:
  smi-h-engine-api:
    cap_add:
      - NET_ADMIN  # Permite modificar rotas de rede
    extra_hosts:
      - "vpn-server.corp:10.0.1.1"
```

## Referências

- [Docker Networking](https://docs.docker.com/network/)
- [Docker Compose Networking](https://docs.docker.com/compose/networking/)
- [Extra Hosts](https://docs.docker.com/compose/compose-file/compose-file-v3/#extra_hosts)

## Status Atual

✅ **Configurado e Testado**
- Container pode conectar com `development.localhost:8000`
- Mapeamento: `development.localhost` → `host-gateway` (IP do host)
- Testado com sucesso: Status HTTP 200

```bash
# Teste rápido
docker exec smi-h-engine-api gosu appuser python -c \
  "import requests; print(requests.get('http://development.localhost:8000/').status_code)"
# Saída: 200 ✓
```
