# API REST - SMI H-Engine

Documentação completa da API REST para execução assíncrona do processador de fórmulas.

## Índice

- [Visão Geral](#visão-geral)
- [Iniciando o Servidor](#iniciando-o-servidor)
- [Autenticação](#autenticação)
- [Endpoints](#endpoints)
- [Modelos de Dados](#modelos-de-dados)
- [Exemplos de Uso](#exemplos-de-uso)
- [Códigos de Status HTTP](#códigos-de-status-http)
- [Tratamento de Erros](#tratamento-de-erros)
- [Boas Práticas](#boas-práticas)

## Visão Geral

A API REST fornece uma interface para:

- ✅ Executar processamentos de forma assíncrona
- ✅ Consultar status de execução em tempo real
- ✅ Visualizar logs gerados durante o processamento
- ✅ Gerenciar tarefas (listar, remover)
- ✅ Identificação única via UUID para cada execução

**Base URL**: `http://localhost:8084`

**Documentação Interativa (Swagger)**: `http://localhost:8084/docs`

**ReDoc**: `http://localhost:8084/redoc`

## Iniciando o Servidor

### Opção 1: Execução Direta

```bash
python api_engine.py
```

### Opção 2: Via Uvicorn (Recomendado para Produção)

```bash
# Desenvolvimento (com reload automático)
uvicorn api_engine:app --reload --host 0.0.0.0 --port 8084

# Produção (múltiplos workers)
uvicorn api_engine:app --host 0.0.0.0 --port 8084 --workers 4
```

### Opção 3: Docker (Exemplo)

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "api_engine:app", "--host", "0.0.0.0", "--port", "8084"]
```

## Autenticação

**Versão Atual**: Nenhuma autenticação configurada (desenvolvimento)

**Produção**: Recomenda-se implementar:
- OAuth2 / JWT tokens
- API Keys
- Rate limiting
- HTTPS obrigatório

## Endpoints

### 📋 GET / - Informações da API

Retorna informações sobre a API e endpoints disponíveis.

**Request:**
```bash
curl http://localhost:8084/
```

**Response:**
```json
{
  "name": "Engine Processor API",
  "version": "1.0.0",
  "endpoints": {
    "POST /calculate": "Inicia processamento de medições",
    "GET /status/{task_id}": "Consulta status de uma tarefa",
    "GET /tasks": "Lista todas as tarefas",
    "GET /logs/{task_id}": "Consulta logs de uma tarefa",
    "DELETE /tasks/{task_id}": "Remove uma tarefa",
    "DELETE /logs/{task_id}": "Remove logs de uma tarefa"
  }
}
```

---

### 🚀 POST /calculate - Iniciar Processamento

Inicia uma nova execução assíncrona do processador de fórmulas.

**Request:**
```bash
curl -X POST "http://localhost:8084/calculate" \
  -H "Content-Type: application/json" \
  -d '{
    "measurement": "BM-CW40566-001",
    "use_cached_data": true,
    "debug": true
  }'
```

**Request Body:**
```json
{
  "measurement": "BM-CW40566-001",  // Opcional: ID da medição específica
  "use_cached_data": true,          // Padrão: true
  "debug": false                    // Padrão: false
}
```

**Response (201 Created):**
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "pending",
  "created_at": "2025-09-30T15:30:00.123456",
  "started_at": null,
  "completed_at": null,
  "measurement": "BM-CW40566-001",
  "use_cached_data": true,
  "error": null,
  "result": null
}
```

**Parâmetros:**

| Campo | Tipo | Obrigatório | Padrão | Descrição |
|-------|------|-------------|--------|-----------|
| `measurement` | string | Não | null | ID da medição específica (ex: BM-CW40566-001). Se omitido, processa todas as medições |
| `use_cached_data` | boolean | Não | true | Se `true`, usa dados em cache para contratos |
| `debug` | boolean | Não | false | Se `true`, ativa logs detalhados (DEBUG level) |

---

### 📊 GET /status/{task_id} - Consultar Status

Retorna o status atual de uma tarefa específica.

**Request:**
```bash
curl http://localhost:8084/status/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**Response (200 OK):**

**Tarefa em Execução:**
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "running",
  "created_at": "2025-09-30T15:30:00.123456",
  "started_at": "2025-09-30T15:30:01.234567",
  "completed_at": null,
  "measurement": "BM-CW40566-001",
  "use_cached_data": true,
  "error": null,
  "result": null
}
```

**Tarefa Concluída:**
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "completed",
  "created_at": "2025-09-30T15:30:00.123456",
  "started_at": "2025-09-30T15:30:01.234567",
  "completed_at": "2025-09-30T15:45:23.456789",
  "measurement": "BM-CW40566-001",
  "use_cached_data": true,
  "error": null,
  "result": {
    "message": "Processamento concluído com sucesso"
  }
}
```

**Tarefa com Erro:**
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "error",
  "created_at": "2025-09-30T15:30:00.123456",
  "started_at": "2025-09-30T15:30:01.234567",
  "completed_at": "2025-09-30T15:32:15.789012",
  "measurement": "BM-CW40566-001",
  "use_cached_data": true,
  "error": "ConnectionError: Failed to connect to API",
  "result": null
}
```

**Response (404 Not Found):**
```json
{
  "detail": "Tarefa não encontrada"
}
```

---

### 📝 GET /tasks - Listar Todas as Tarefas

Retorna todas as tarefas registradas no sistema.

**Request:**
```bash
curl http://localhost:8084/tasks
```

**Response (200 OK):**
```json
{
  "a1b2c3d4-e5f6-7890-abcd-ef1234567890": {
    "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "status": "completed",
    "created_at": "2025-09-30T15:30:00.123456",
    "started_at": "2025-09-30T15:30:01.234567",
    "completed_at": "2025-09-30T15:45:23.456789",
    "measurement": "BM-CW40566-001",
    "use_cached_data": true,
    "error": null,
    "result": {"message": "Processamento concluído com sucesso"}
  },
  "b2c3d4e5-f6g7-8901-bcde-f12345678901": {
    "task_id": "b2c3d4e5-f6g7-8901-bcde-f12345678901",
    "status": "running",
    "created_at": "2025-09-30T16:00:00.123456",
    "started_at": "2025-09-30T16:00:01.234567",
    "completed_at": null,
    "measurement": null,
    "use_cached_data": true,
    "error": null,
    "result": null
  }
}
```

---

### 📜 GET /logs/{task_id} - Consultar Logs

Retorna os logs gerados durante a execução de uma tarefa.

**Request:**
```bash
# Logs padrão (primeiras 100 linhas)
curl http://localhost:8084/logs/a1b2c3d4-e5f6-7890-abcd-ef1234567890

# Com paginação
curl "http://localhost:8084/logs/a1b2c3d4-e5f6-7890-abcd-ef1234567890?offset=100&limit=50"

# Ver apenas últimas 10 linhas (requer calcular offset)
curl "http://localhost:8084/logs/a1b2c3d4-e5f6-7890-abcd-ef1234567890" | jq '.total_lines'
# Supondo total_lines = 500
curl "http://localhost:8084/logs/a1b2c3d4-e5f6-7890-abcd-ef1234567890?offset=490&limit=10"
```

**Query Parameters:**

| Parâmetro | Tipo | Obrigatório | Padrão | Min | Max | Descrição |
|-----------|------|-------------|--------|-----|-----|-----------|
| `offset` | integer | Não | 0 | 0 | - | Número de linhas para pular |
| `limit` | integer | Não | 100 | 1 | 10000 | Máximo de linhas para retornar |

**Response (200 OK):**
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "logs": [
    "2025-09-30 15:30:01 - engine_exec - INFO - Iniciando o processamento de fórmulas",
    "2025-09-30 15:30:02 - engine_entities.get_doctypes - INFO - Carregando fórmulas do sistema",
    "2025-09-30 15:30:03 - engine_parser - DEBUG - Processando grupo de fórmulas 1/5",
    "2025-09-30 15:30:05 - engine_eval - INFO - Avaliação das fórmulas concluída. Com sucesso: 145, Erros: 0"
  ],
  "total_lines": 1247
}
```

**Response (404 Not Found - Tarefa não existe):**
```json
{
  "detail": "Tarefa não encontrada"
}
```

**Response (200 OK - Sem logs):**
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "logs": [],
  "total_lines": 0
}
```

---

### 🗑️ DELETE /tasks/{task_id} - Remover Tarefa

Remove uma tarefa do registro do sistema.

**Request:**
```bash
curl -X DELETE http://localhost:8084/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**Response (200 OK):**
```json
{
  "message": "Tarefa a1b2c3d4-e5f6-7890-abcd-ef1234567890 removida com sucesso"
}
```

**Response (404 Not Found):**
```json
{
  "detail": "Tarefa não encontrada"
}
```

---

### 🗑️ DELETE /logs/{task_id} - Remover Logs

Remove os logs de uma tarefa específica (mantém a tarefa).

**Request:**
```bash
curl -X DELETE http://localhost:8084/logs/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**Response (200 OK):**
```json
{
  "message": "Logs da tarefa a1b2c3d4-e5f6-7890-abcd-ef1234567890 removidos com sucesso"
}
```

**Response (404 Not Found):**
```json
{
  "detail": "Logs da tarefa não encontrados"
}
```

---

## Modelos de Dados

### TaskStatus (Enum)

Estados possíveis de uma tarefa:

| Status | Descrição |
|--------|-----------|
| `pending` | Tarefa criada, aguardando início da execução |
| `running` | Tarefa em execução |
| `completed` | Tarefa concluída com sucesso |
| `error` | Tarefa finalizada com erro |

### TaskInfo

```typescript
{
  task_id: string,              // UUID da tarefa
  status: TaskStatus,           // Status atual
  created_at: datetime,         // Timestamp de criação
  started_at?: datetime,        // Timestamp de início (null se pending)
  completed_at?: datetime,      // Timestamp de conclusão (null se running/pending)
  measurement?: string,         // ID da medição (null se processar todas)
  use_cached_data: boolean,     // Se usa cache
  error?: string,               // Mensagem de erro (null se sucesso)
  result?: object               // Resultado (null se erro/running/pending)
}
```

### ProcessRequest

```typescript
{
  measurement?: string,         // Opcional: ID da medição
  use_cached_data?: boolean,    // Padrão: true
  debug?: boolean               // Padrão: false
}
```

### LogResponse

```typescript
{
  task_id: string,              // UUID da tarefa
  logs: string[],               // Array de linhas de log
  total_lines: integer          // Total de linhas disponíveis
}
```

---

## Exemplos de Uso

### Exemplo 1: Processar Medição Específica e Monitorar

```bash
#!/bin/bash

# 1. Iniciar processamento
RESPONSE=$(curl -s -X POST "http://localhost:8084/calculate" \
  -H "Content-Type: application/json" \
  -d '{"measurement": "BM-CW40566-001", "debug": true}')

# 2. Extrair task_id
TASK_ID=$(echo $RESPONSE | jq -r '.task_id')
echo "Task ID: $TASK_ID"

# 3. Monitorar status até conclusão
while true; do
  STATUS=$(curl -s "http://localhost:8084/status/$TASK_ID" | jq -r '.status')
  echo "Status: $STATUS"

  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "error" ]; then
    break
  fi

  sleep 5
done

# 4. Ver resultado final
curl -s "http://localhost:8084/status/$TASK_ID" | jq

# 5. Ver logs
curl -s "http://localhost:8084/logs/$TASK_ID" | jq
```

### Exemplo 2: Processar Todas as Medições

```bash
curl -X POST "http://localhost:8084/calculate" \
  -H "Content-Type: application/json" \
  -d '{"use_cached_data": true, "debug": false}'
```

### Exemplo 3: Streaming de Logs (Python)

```python
import requests
import time

# Iniciar processamento
response = requests.post('http://localhost:8084/calculate', json={
    'measurement': 'BM-CW40566-001',
    'debug': True
})
task_id = response.json()['task_id']
print(f"Task ID: {task_id}")

# Monitorar logs em tempo real
offset = 0
while True:
    # Verificar status
    status_resp = requests.get(f'http://localhost:8084/status/{task_id}')
    status = status_resp.json()['status']

    # Obter novos logs
    logs_resp = requests.get(f'http://localhost:8084/logs/{task_id}', params={
        'offset': offset,
        'limit': 100
    })
    logs_data = logs_resp.json()

    # Imprimir novos logs
    for log_line in logs_data['logs']:
        print(log_line)

    offset += len(logs_data['logs'])

    # Se concluído, parar
    if status in ['completed', 'error']:
        print(f"\nStatus final: {status}")
        break

    time.sleep(2)
```

### Exemplo 4: Gerenciamento de Tarefas

```bash
# Listar todas as tarefas
curl http://localhost:8084/tasks | jq

# Filtrar tarefas em execução (usando jq)
curl -s http://localhost:8084/tasks | jq 'to_entries[] | select(.value.status == "running")'

# Filtrar tarefas com erro
curl -s http://localhost:8084/tasks | jq 'to_entries[] | select(.value.status == "error")'

# Remover tarefas antigas (concluídas há mais de 1 dia)
# Requer script adicional para calcular timestamp
```

---

## Códigos de Status HTTP

| Código | Descrição |
|--------|-----------|
| 200 | OK - Requisição bem-sucedida |
| 201 | Created - Tarefa criada com sucesso |
| 404 | Not Found - Tarefa ou logs não encontrados |
| 422 | Unprocessable Entity - Erro de validação nos dados |
| 500 | Internal Server Error - Erro interno do servidor |

---

## Tratamento de Erros

### Erro de Validação (422)

```json
{
  "detail": [
    {
      "loc": ["body", "use_cached_data"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### Tarefa Não Encontrada (404)

```json
{
  "detail": "Tarefa não encontrada"
}
```

### Erro Interno (500)

```json
{
  "detail": "Internal server error"
}
```

---

## Boas Práticas

### 1. Polling de Status

**Evite polling excessivo:**

```python
# ❌ Ruim - polling muito frequente
while True:
    status = get_status(task_id)
    time.sleep(0.5)  # Muito frequente!

# ✅ Bom - intervalo razoável
while True:
    status = get_status(task_id)
    if status in ['completed', 'error']:
        break
    time.sleep(5)  # Intervalo apropriado
```

### 2. Paginação de Logs

Para tarefas grandes com muitos logs:

```python
# ✅ Usar paginação para logs grandes
offset = 0
limit = 100

while True:
    response = requests.get(f'/logs/{task_id}', params={
        'offset': offset,
        'limit': limit
    })
    data = response.json()

    process_logs(data['logs'])

    if offset + limit >= data['total_lines']:
        break

    offset += limit
```

### 3. Timeout

Configure timeouts adequados:

```python
# ✅ Definir timeouts
response = requests.post(
    'http://localhost:8084/calculate',
    json={'measurement': 'BM-CW40566-001'},
    timeout=30  # 30 segundos
)
```

### 4. Limpeza de Tarefas

Implemente limpeza periódica:

```python
# ✅ Remover tarefas antigas
def cleanup_old_tasks(max_age_hours=24):
    tasks = requests.get('http://localhost:8084/tasks').json()

    for task_id, task in tasks.items():
        if task['status'] in ['completed', 'error']:
            created_at = datetime.fromisoformat(task['created_at'])
            age = datetime.now() - created_at

            if age.total_seconds() > max_age_hours * 3600:
                requests.delete(f'http://localhost:8084/tasks/{task_id}')
```

### 5. Tratamento de Erros

Sempre trate possíveis erros:

```python
# ✅ Tratamento robusto
try:
    response = requests.post('http://localhost:8084/calculate', json=payload)
    response.raise_for_status()
    task_id = response.json()['task_id']
except requests.exceptions.ConnectionError:
    print("Erro: Não foi possível conectar ao servidor")
except requests.exceptions.Timeout:
    print("Erro: Timeout na requisição")
except requests.exceptions.HTTPError as e:
    print(f"Erro HTTP: {e.response.status_code}")
```

---

## Limitações Conhecidas

### Armazenamento em Memória

**Versão Atual**: Tarefas e logs são armazenados em memória.

**Implicações**:
- Dados são perdidos ao reiniciar o servidor
- Limitado pela RAM disponível

**Solução para Produção**:
- Usar Redis para cache de tarefas
- Usar banco de dados (PostgreSQL) para persistência
- Implementar TTL (Time To Live) automático

### Concorrência

**Versão Atual**: Execução sequencial de tarefas em background.

**Solução para Produção**:
- Usar Celery + Redis para fila de tarefas
- Implementar worker pools
- Adicionar rate limiting

### Segurança

**Versão Atual**: Sem autenticação.

**Solução para Produção**:
- Implementar OAuth2 / JWT
- Adicionar API keys
- Rate limiting por IP/usuário
- CORS configurado adequadamente

---

## Migração para Produção

### Checklist

- [ ] Implementar autenticação (OAuth2/JWT)
- [ ] Configurar HTTPS/TLS
- [ ] Adicionar rate limiting
- [ ] Usar Redis para cache de tarefas
- [ ] Implementar banco de dados para persistência
- [ ] Configurar logging centralizado
- [ ] Adicionar monitoramento (Prometheus/Grafana)
- [ ] Implementar health checks
- [ ] Configurar CORS adequadamente
- [ ] Adicionar testes automatizados
- [ ] Documentar políticas de retenção de logs
- [ ] Implementar backup de dados

---

## Suporte

Para questões sobre a API REST, contate a equipe de desenvolvimento SMI.

**Documentação Adicional**:
- [README.md](README.md) - Visão geral do projeto
- Swagger UI: `http://localhost:8084/docs`
- ReDoc: `http://localhost:8084/redoc`
