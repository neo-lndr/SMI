# Docker - SMI Data Connector

Documentação para execução do projeto em container Docker.

## 📋 Pré-requisitos

- Docker Engine 20.10+
- Docker Compose 2.0+
- 2GB de RAM livre
- Acesso à API Arteris
- Credenciais AWS (para Kartado)
- Credenciais Osiris

## 🚀 Quick Start

### 1. Configurar variáveis de ambiente

Copie o arquivo de exemplo e preencha com suas credenciais:

```bash
cp .env.example .env
nano .env
```

### 2. Build da imagem

```bash
docker-compose build
```

### 3. Iniciar o serviço

```bash
docker-compose up -d
```

A API estará disponível em: `http://localhost:8085`

### 4. Configurar Timezone (Ubuntu)

**IMPORTANTE:** Os cron jobs executam no horário do sistema. Para garantir execução no horário de São Paulo (UTC-3):

```bash
# Verificar timezone atual
timedatectl

# Configurar timezone de São Paulo
sudo timedatectl set-timezone America/Sao_Paulo

# Verificar se está correto
date
```

O sistema deve mostrar: `... -03 2025` (UTC-3)

## 📦 Estrutura do Container

### Diretórios montados

- `./logs` - Logs da aplicação e cron
- `./data` - Dados e cache
- `./.env` - Variáveis de ambiente
- `/ftp/arteris` - Acesso ao diretório FTP (read-only)

### Portas expostas

- `8085` - API REST de importação

## ⚙️ Configuração

### Variáveis de ambiente obrigatórias

```env
# API Arteris
ARTERIS_API_BASE_URL=https://development.localhost
ARTERIS_API_TOKEN=your_token_here

# AWS (para Kartado)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
S3_OUTPUT_LOCATION=s3://your-bucket/path/

# Osiris
OSIRIS_LOGIN=your_email@example.com
OSIRIS_PASSWORD=your_password
```

### Variáveis opcionais

```env
# Cron - Execução diária
CRON_SCHEDULE=0 21 * * *  # 21:00 diariamente
ENABLE_CRON=true

# Logging
LOG_LEVEL=INFO
LOG_TO_CONSOLE=true
LOG_TO_FILE=true

# FTP
FTP_PATH=/ftp/arteris
```

## 🎯 Modos de Execução

### Modo API (padrão)

Inicia a API REST com cron habilitado:

```bash
docker-compose up -d
```

### Executar tarefas diárias manualmente

```bash
docker-compose exec smi-data-connector-api run-daily
```

### Executar task específica

```bash
# SAP Order
docker-compose exec smi-data-connector-api run-task saporder

# FTD
docker-compose exec smi-data-connector-api run-task ftd

# Kartado
docker-compose exec smi-data-connector-api run-task kartado

# Osiris
docker-compose exec smi-data-connector-api run-task osiris
```

### Modo shell (debug)

```bash
docker-compose exec smi-data-connector-api shell
```

### Executar testes

```bash
docker-compose exec smi-data-connector-api test
```

## 📅 Agendamento (Cron)

Por padrão, o container executa automaticamente às **21:00** (horário do container) as seguintes tarefas em sequência:

1. `run_saporder.sh` - Importação de SAP Orders
2. `run_ftd.sh` - Importação de FTD
3. `run_kartado.sh` - Importação de dados Kartado
4. `run_osiris.sh` - Importação de dados Osiris

### Personalizar horário

Edite a variável `CRON_SCHEDULE` no `.env`:

```env
# Executar às 23:00
CRON_SCHEDULE=0 23 * * *

# Executar às 21:00 de segunda a sexta
CRON_SCHEDULE=0 21 * * 1-5

# Executar a cada 6 horas
CRON_SCHEDULE=0 */6 * * *
```

### Desabilitar cron

```env
ENABLE_CRON=false
```

## 🔍 Monitoramento

### Ver logs em tempo real

```bash
# Todos os logs
docker-compose logs -f

# Apenas logs do cron
docker-compose exec smi-data-connector-api tail -f /app/logs/cron.log

# Logs da aplicação
docker-compose exec smi-data-connector-api tail -f /app/logs/connector.log
```

### Verificar status

```bash
# Status do container
docker-compose ps

# Health check
docker inspect smi-data-connector-api --format='{{.State.Health.Status}}'

# Verificar crontab
docker-compose exec smi-data-connector-api crontab -l
```

### API de status

```bash
# Verificar API
curl http://localhost:8085/

# Listar tarefas
curl http://localhost:8085/tasks

# Status de uma tarefa específica
curl http://localhost:8085/status/{task_id}

# Logs de uma tarefa
curl http://localhost:8085/logs/{task_id}
```

## 🛠️ Comandos Úteis

### Iniciar serviço

```bash
docker-compose up -d
```

### Parar serviço

```bash
docker-compose down
```

### Reiniciar serviço

```bash
docker-compose restart
```

### Rebuild completo

```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Ver logs

```bash
docker-compose logs -f
```

### Acessar shell do container

```bash
docker-compose exec smi-data-connector-api bash
```

### Limpar volumes e reconstruir

```bash
docker-compose down -v
docker-compose up -d --build
```

## 🐛 Troubleshooting

### Container não inicia

1. Verificar logs: `docker-compose logs`
2. Verificar variáveis de ambiente no `.env`
3. Verificar permissões dos diretórios montados

### Cron não executa

1. Verificar se cron está habilitado: `ENABLE_CRON=true`
2. Verificar crontab: `docker-compose exec smi-data-connector-api crontab -l`
3. Verificar logs do cron: `tail -f ./logs/cron.log`
4. Verificar timezone do container: `docker-compose exec smi-data-connector-api date`

### Erros de permissão

```bash
# Ajustar permissões dos diretórios
sudo chown -R 1000:1000 logs data
```

### API não responde

1. Verificar health check: `docker inspect smi-data-connector-api`
2. Verificar porta: `netstat -tlnp | grep 8085`
3. Testar API: `curl http://localhost:8085/`

### Arquivos CSV não encontrados

1. Verificar montagem do FTP: `docker-compose exec smi-data-connector-api ls -la /ftp/arteris/`
2. Verificar variável `FTP_PATH` no `.env`
3. Verificar permissões do diretório FTP no host

## 📊 Uso da API REST

### Iniciar importação

```bash
curl -X POST "http://localhost:8085/import_data" \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2025-09-01",
    "end_date": "2025-09-18",
    "contract_code": "CW082025",
    "source_system": "both",
    "ignore_check": false,
    "only_images": false
  }'
```

### Verificar status da importação

```bash
curl "http://localhost:8085/status/{task_id}"
```

### Ver logs da importação

```bash
curl "http://localhost:8085/logs/{task_id}?limit=100"
```

## 🔒 Segurança

- Container roda como usuário não-root (`appuser`)
- Variáveis sensíveis via `.env` (não commitado)
- Volumes read-only onde apropriado
- Health checks configurados
- SSL verify habilitado por padrão

## 📈 Performance

- Multi-stage build para imagem otimizada
- Cache de dependências Python
- Execução assíncrona via FastAPI
- Logs com rotação automática

## 🆘 Suporte

Para problemas ou dúvidas:

1. Verificar logs: `docker-compose logs -f`
2. Verificar health: `docker inspect smi-data-connector-api`
3. Abrir issue no repositório

## 📝 Notas

- Timezone do container: UTC (ajustar `CRON_SCHEDULE` conforme necessário)
- Logs são persistidos em `./logs`
- Dados de cache em `./data`
- Container reinicia automaticamente em caso de falha (`restart: unless-stopped`)
