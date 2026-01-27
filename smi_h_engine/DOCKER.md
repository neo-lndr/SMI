# Docker - SMI H-Engine

Documentação completa para implantação do SMI H-Engine usando Docker e Docker Compose.

## Índice

- [Visão Geral](#visão-geral)
- [Arquivos Docker](#arquivos-docker)
- [Construindo a Imagem](#construindo-a-imagem)
- [Executando com Docker Run](#executando-com-docker-run)
- [Executando com Docker Compose](#executando-com-docker-compose)
- [Modos de Execução](#modos-de-execução)
- [Variáveis de Ambiente](#variáveis-de-ambiente)
- [Volumes e Persistência](#volumes-e-persistência)
- [Redes](#redes)
- [Health Checks](#health-checks)
- [Integração com Outros Compose](#integração-com-outros-compose)
- [Troubleshooting](#troubleshooting)
- [Produção](#produção)

## Visão Geral

O projeto fornece suporte completo para containerização:

- **Dockerfile multi-stage**: Build otimizado com imagem mínima
- **docker-compose.yml**: Orquestração completa com múltiplos serviços
- **docker-entrypoint.sh**: Script flexível com múltiplos modos
- **Health checks**: Monitoramento automático de saúde
- **Perfis opcionais**: Redis e Worker podem ser ativados sob demanda

## Arquivos Docker

```
smi_h_engine_/
├── Dockerfile              # Definição da imagem
├── docker-compose.yml      # Orquestração de serviços
├── docker-entrypoint.sh    # Script de inicialização
└── .dockerignore          # Arquivos ignorados no build
```

## Construindo a Imagem

### Build Básico

```bash
docker build -t smi-h-engine:latest .
```

### Build com Tag de Versão

```bash
docker build -t smi-h-engine:1.0.0 -t smi-h-engine:latest .
```

### Build com BuildKit (Recomendado)

```bash
DOCKER_BUILDKIT=1 docker build -t smi-h-engine:latest .
```

## Executando com Docker Run

### Modo API (Padrão)

```bash
docker run -d \
  --name smi-h-engine-api \
  -p 8084:8084 \
  -e ARTERIS_API_TOKEN="seu_token_aqui" \
  -e LOG_LEVEL=INFO \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  smi-h-engine:latest
```

### Processamento Único

```bash
# Todas as medições
docker run --rm \
  -e ARTERIS_API_TOKEN="seu_token_aqui" \
  -v $(pwd)/logs:/app/logs \
  smi-h-engine:latest run-once

# Medição específica
docker run --rm \
  -e ARTERIS_API_TOKEN="seu_token_aqui" \
  -v $(pwd)/logs:/app/logs \
  smi-h-engine:latest run-once BM-CW40566-001
```

### Modo Shell (Debug)

```bash
docker run -it --rm \
  -v $(pwd):/app \
  smi-h-engine:latest shell
```

### Executar Testes

```bash
docker run --rm smi-h-engine:latest test
```

## Executando com Docker Compose

### Iniciar Apenas API

```bash
docker-compose up -d
```

### Ver Logs

```bash
# Todos os serviços
docker-compose logs -f

# Apenas API
docker-compose logs -f smi-h-engine-api

# Últimas 100 linhas
docker-compose logs --tail=100 -f
```

### Parar Serviços

```bash
docker-compose down
```

### Parar e Remover Volumes

```bash
docker-compose down -v
```

### Rebuild e Restart

```bash
docker-compose up -d --build
```

## Modos de Execução

O `docker-entrypoint.sh` suporta múltiplos modos:

### 1. API (Padrão)

```bash
docker run smi-h-engine:latest api
```

**Uso**: Produção, desenvolvimento com API REST

### 2. Run-Once

Executa processamento único e finaliza.

```bash
# Todas as medições
docker run smi-h-engine:latest run-once

# Medição específica
docker run smi-h-engine:latest run-once BM-CW40566-001
```

**Uso**: Jobs únicos, cron jobs externos, CI/CD

### 3. Shell

Abre shell bash para debug.

```bash
docker run -it smi-h-engine:latest shell
```

**Uso**: Debug, inspeção, troubleshooting

### 4. Test

Executa testes básicos.

```bash
docker run smi-h-engine:latest test
```

**Uso**: Validação pós-build, CI/CD

### 5. Help

Exibe ajuda do entrypoint.

```bash
docker run smi-h-engine:latest help
```

## Variáveis de Ambiente

### Obrigatórias

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `ARTERIS_API_TOKEN` | Token de autenticação da API externa | `"abc123xyz..."` |

### API Externa

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `ARTERIS_API_BASE_URL` | `https://smi.arteris.com.br/api` | URL base da API |
| `ARTERIS_API_URL_UPDATE_DOCKTYPE` | - | URL para atualização de doctypes |
| `DISABLE_SSL_VERIFY` | `false` | Desabilitar verificação SSL |

### Logging

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `LOG_LEVEL` | `INFO` | Nível de log (DEBUG/INFO/WARNING/ERROR) |
| `LOG_TO_CONSOLE` | `true` | Logar para console |
| `LOG_TO_FILE` | `true` | Logar para arquivo |
| `LOG_DIR` | `/app/logs` | Diretório de logs |
| `LOG_FILE` | `engine.log` | Nome do arquivo de log |
| `LOG_FILE_MAX_SIZE_BYTES` | `1048576` | Tamanho máximo do log (1MB) |
| `LOG_FILE_BACKUP_COUNT` | `3` | Número de backups de log |

### Worker

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `WORKER_INTERVAL` | `3600` | Intervalo entre processamentos (segundos) |

### Python

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `PYTHONUNBUFFERED` | `1` | Saída não bufferizada |
| `PYTHONDONTWRITEBYTECODE` | `1` | Não criar arquivos .pyc |

## Volumes e Persistência

### Volumes Recomendados

```yaml
volumes:
  - ./logs:/app/logs              # Logs persistentes
  - ./data:/app/data              # Cache de dados
  - ./.env:/app/.env:ro           # Variáveis de ambiente (somente leitura)
```

### Estrutura de Diretórios

```
logs/
├── engine.log              # Log principal
├── worker.log              # Log do worker
└── *.log                   # Outros logs

data/
├── temp/                   # Arquivos temporários
└── contract_data_*.json    # Cache de contratos
```

### Permissões

O container roda como usuário `appuser` (não-root). Certifique-se de que os volumes montados têm permissões adequadas:

```bash
# Criar diretórios locais
mkdir -p logs data/temp

# Ajustar permissões (se necessário)
chmod 755 logs data
```

## Redes

### Rede Padrão

O docker-compose cria uma rede bridge chamada `smi-network`:

```yaml
networks:
  smi-network:
    driver: bridge
    name: smi-network
```

### Conectar Outros Serviços

Outros containers podem se conectar à mesma rede:

```bash
docker run --network smi-network outro-servico
```

## Health Checks

### Health Check do Container

O Dockerfile define um health check:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8084/', timeout=5)" || exit 1
```

### Verificar Status

```bash
docker ps
docker inspect --format='{{.State.Health.Status}}' smi-h-engine-api
```

### Health Check Manual

```bash
docker exec smi-h-engine-api curl -f http://localhost:8084/ || exit 1
```

## Integração com Outros Compose

### Método 1: Anexar ao Compose Existente

Adicione o serviço ao seu `docker-compose.yml` existente:

```yaml
version: '3.8'

services:
  # Seus serviços existentes
  meu-app:
    image: meu-app:latest
    # ...

  # Adicionar SMI H-Engine
  smi-h-engine-api:
    image: smi-h-engine:latest
    restart: unless-stopped
    ports:
      - "8084:8084"
    environment:
      - ARTERIS_API_TOKEN=${ARTERIS_API_TOKEN}
      - LOG_LEVEL=INFO
    volumes:
      - ./smi-logs:/app/logs
      - ./smi-data:/app/data
    networks:
      - default
```

### Método 2: Usar Rede Externa

**docker-compose.yml do SMI H-Engine:**

```yaml
networks:
  smi-network:
    external: true
    name: minha-rede-externa
```

**Criar rede externa:**

```bash
docker network create minha-rede-externa
```

**Seu compose conecta à mesma rede:**

```yaml
networks:
  default:
    external: true
    name: minha-rede-externa
```

### Método 3: Docker Compose com Múltiplos Arquivos

```bash
# Seu compose + SMI H-Engine
docker-compose -f docker-compose.yml -f smi-h-engine/docker-compose.yml up -d
```

### Método 4: Arquivo de Override

Crie `docker-compose.override.yml`:

```yaml
version: '3.8'

services:
  smi-h-engine-api:
    environment:
      - CUSTOM_VAR=custom_value
    volumes:
      - ./custom-config:/app/config
```

Execute normalmente:

```bash
docker-compose up -d
```

Docker Compose automaticamente mescla `docker-compose.yml` + `docker-compose.override.yml`.

## Troubleshooting

### Container não inicia

```bash
# Ver logs
docker logs smi-h-engine-api

# Verificar configurações
docker inspect smi-h-engine-api
```

### Problemas de permissão

```bash
# Rodar como root temporariamente (debug apenas)
docker run --user root -it smi-h-engine:latest shell

# Verificar permissões
ls -la /app/logs /app/data
```

### Health check falha

```bash
# Testar manualmente
docker exec smi-h-engine-api curl http://localhost:8084/

# Ver logs do health check
docker inspect --format='{{json .State.Health}}' smi-h-engine-api | jq
```

### Erro de conexão com API externa

```bash
# Verificar variáveis de ambiente
docker exec smi-h-engine-api env | grep ARTERIS

# Testar conectividade
docker exec smi-h-engine-api curl -v https://smi.arteris.com.br/api
```

### Build falha

```bash
# Build com output detalhado
docker build --progress=plain -t smi-h-engine:latest .

# Verificar requirements.txt
docker run --rm python:3.9-slim pip install -r requirements.txt
```

### Logs não aparecem

```bash
# Verificar se volume está montado corretamente
docker inspect -f '{{ .Mounts }}' smi-h-engine-api

# Ver logs direto do container
docker exec smi-h-engine-api cat /app/logs/engine.log
```

## Produção

### Checklist de Produção

- [ ] **Usar variáveis de ambiente seguras**
  ```bash
  # Usar Docker secrets ou vault
  docker secret create arteris_token token.txt
  ```

- [ ] **Configurar SSL/TLS**
  ```yaml
  # Adicionar proxy reverso (nginx/traefik)
  ```

- [ ] **Limitar recursos**
  ```yaml
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 4G
      reservations:
        cpus: '1'
        memory: 2G
  ```

- [ ] **Habilitar restart automático**
  ```yaml
  restart: unless-stopped
  ```

- [ ] **Configurar logs externos**
  ```yaml
  logging:
    driver: "json-file"
    options:
      max-size: "10m"
      max-file: "3"
  ```

- [ ] **Usar Redis para cache**
  ```bash
  docker-compose --profile with-redis up -d
  ```

- [ ] **Monitoramento**
  - Prometheus + Grafana
  - Health checks externos
  - Alertas

- [ ] **Backup de volumes**
  ```bash
  docker run --rm -v smi-h-engine-redis-data:/data -v $(pwd):/backup \
    alpine tar czf /backup/redis-backup.tar.gz /data
  ```

### Exemplo de Stack Completo (Produção)

```yaml
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./certs:/etc/nginx/certs
    depends_on:
      - smi-h-engine-api

  smi-h-engine-api:
    image: smi-h-engine:1.0.0
    restart: always
    environment:
      - ARTERIS_API_TOKEN_FILE=/run/secrets/api_token
      - LOG_LEVEL=WARNING
    secrets:
      - api_token
    volumes:
      - logs:/app/logs
      - data:/app/data
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '2'
          memory: 4G
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  redis:
    image: redis:7-alpine
    restart: always
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes

  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana

secrets:
  api_token:
    external: true

volumes:
  logs:
  data:
  redis-data:
  prometheus-data:
  grafana-data:
```

### Deploy em Produção

```bash
# Build
docker build -t registry.example.com/smi-h-engine:1.0.0 .

# Push para registry
docker push registry.example.com/smi-h-engine:1.0.0

# Pull no servidor
docker pull registry.example.com/smi-h-engine:1.0.0

# Deploy
docker-compose -f docker-compose.prod.yml up -d
```

## Comandos Úteis

```bash
# Ver uso de recursos
docker stats smi-h-engine-api

# Limpar recursos não utilizados
docker system prune -a --volumes

# Exportar imagem
docker save smi-h-engine:latest | gzip > smi-h-engine.tar.gz

# Importar imagem
gunzip -c smi-h-engine.tar.gz | docker load

# Ver histórico da imagem
docker history smi-h-engine:latest

# Executar comando no container
docker exec -it smi-h-engine-api python -c "from engine_parser import FormulaParser; print('OK')"
```

## Referências

- [Documentação Principal](README.md)
- [API REST](API_REST.md)
- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
