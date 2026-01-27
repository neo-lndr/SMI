# SMI H-Engine - Motor de Cálculo de Fórmulas Hierárquicas

Sistema de processamento e avaliação de fórmulas hierárquicas para cálculos de medições em contratos. O motor processa fórmulas com agregações, variáveis e filtros, aplicando-as sobre estruturas de dados hierárquicas de forma segura e eficiente.

## Índice

- [Visão Geral](#visão-geral)
- [Arquitetura](#arquitetura)
- [Instalação](#instalação)
- [Configuração](#configuração)
- [Uso](#uso)
- [API REST](#api-rest)
- [Módulos Principais](#módulos-principais)
- [Desenvolvimento](#desenvolvimento)

## Visão Geral

O SMI H-Engine é um sistema completo para:

- **Parsing de fórmulas**: Extração e análise de expressões matemáticas com funções de agregação
- **Classificação de dependências**: Ordenação topológica de fórmulas baseada em dependências
- **Avaliação segura**: Execução controlada usando `asteval` com sandbox de segurança
- **Processamento hierárquico**: Aplicação de cálculos em estruturas de dados em árvore
- **Integração via API**: Interface REST para execução assíncrona e monitoramento

## Arquitetura

### Componentes Principais

```
smi_h_engine_/
├── engine_exec.py          # Orquestrador principal do processamento
├── engine_parser.py        # Parser de fórmulas e extração de dependências
├── engine_eval.py          # Avaliador seguro de fórmulas (asteval + NumPy)
├── formula_classifier.py   # Classificador de ordem de execução (DAG)
├── update_tree.py          # Atualizador de árvore com resultados
├── api_engine.py           # API REST para execução assíncrona
├── config/
│   └── config.py           # Configurações de segurança e funções permitidas
├── engine_entities/
│   ├── engine_data.py      # Construtor de árvore de dados
│   ├── get_doctypes.py     # Processador de entidades e fórmulas
│   ├── api_smi.py          # Cliente API externa (SMI/Frappe)
│   ├── file_manager.py     # Gerenciador de arquivos temporários
│   └── hierarchical_tree.py # Estruturas hierárquicas
└── filters/
    ├── filters_paths.py    # Filtros e buscas na árvore
    └── variable_filter.py  # Extração de variáveis de filtros
```

### Fluxo de Processamento

1. **Carregamento de Dados**: Obtenção de contratos, medições e fórmulas via API
2. **Construção da Árvore**: Montagem da estrutura hierárquica de dados
3. **Parsing de Fórmulas**: Análise e extração de variáveis/agregações/dependências
4. **Classificação**: Ordenação topológica em grupos de execução
5. **Enriquecimento**: Extração de valores de variáveis da árvore
6. **Avaliação**: Execução segura das fórmulas com asteval
7. **Atualização**: Aplicação dos resultados de volta na árvore
8. **Persistência**: Sincronização com API externa

## Instalação

### Requisitos

- Python 3.8+
- pip

### Instalação de Dependências

```bash
pip install -r requirements.txt
```

### Dependências Principais

- `networkx` - Manipulação de grafos (dependências)
- `pydantic` - Validação de dados
- `numpy` - Operações numéricas e estatísticas
- `asteval` - Avaliação segura de expressões
- `fastapi` - Framework para API REST
- `uvicorn` - Servidor ASGI
- `requests` - Cliente HTTP
- `python-dotenv` - Gerenciamento de variáveis de ambiente

## Configuração

### Variáveis de Ambiente

Crie um arquivo `.env` baseado em `.env.example`:

```bash
cp .env.example .env
```

Configurações disponíveis:

```bash
# Logging
LOG_LEVEL=DEBUG                           # DEBUG, INFO, WARNING, ERROR
LOG_TO_CONSOLE=true
LOG_TO_FILE=true
LOG_DIR=logs
LOG_FILE=engine.log
LOG_FILE_MAX_SIZE_BYTES=1048576          # 1MB
LOG_FILE_BACKUP_COUNT=3

# API Externa (SMI/Frappe)
ARTERIS_API_TOKEN=seu_token_aqui
ARTERIS_API_BASE_URL=https://smi.arteris.com.br/api
ARTERIS_API_URL_UPDATE_DOCKTYPE=https://smi.arteris.com.br/api/method/arteris_app.api.engine.update_doctype

# Segurança
DISABLE_SSL_VERIFY=true                   # Apenas para desenvolvimento
```

### Configuração de Segurança

O arquivo `config/config.py` define:

- **Funções de agregação permitidas**: `sum`, `avg`, `count`, `max`, `min`, etc.
- **Funções NumPy permitidas**: operações matemáticas, estatísticas e trigonométricas
- **Nós AST bloqueados**: `Import`, `Exec`, `Eval`, `Attribute`, etc.

## Uso

### Execução via Linha de Comando

#### Processar todas as medições:

```bash
python engine_exec.py
```

#### Processar medição específica:

```bash
python engine_exec.py BM-CW40566-001
```

#### Com dados em cache:

```python
from engine_exec import EngineProcessor

processor = EngineProcessor(debug=True)
processor.calculate_measurements(use_cached_data=True, measurement='BM-CW40566-001')
```

### Execução via Script

```bash
./run_h_engine.sh                    # Todas as medições
./run_h_engine.sh BM-CW40566-001     # Medição específica
```

### Execução via API REST

Veja a documentação completa em [API_REST.md](API_REST.md)

```bash
# Iniciar servidor
python api_engine.py
# ou
uvicorn api_engine:app --host 0.0.0.0 --port 8084

# Executar processamento
curl -X POST "http://localhost:8084/calculate" \
  -H "Content-Type: application/json" \
  -d '{"measurement": "BM-CW40566-001", "use_cached_data": true, "debug": true}'
```

## API REST

O módulo `api_engine.py` fornece uma API REST completa para:

- Iniciar processamentos assíncronos
- Consultar status de execução
- Visualizar logs em tempo real
- Gerenciar tarefas

Documentação completa: [API_REST.md](API_REST.md)

Swagger UI disponível em: `http://localhost:8084/docs`

## Módulos Principais

### engine_exec.py - Processador Principal

Orquestra todo o fluxo de processamento de fórmulas:

```python
processor = EngineProcessor(debug=True)
processor.calculate_measurements(
    use_cached_data=True,
    measurement='BM-CW40566-001'
)
```

**Responsabilidades:**
- Carregamento e cache de dados de contratos
- Coordenação entre parser, classificador e avaliador
- Gestão de logs e tratamento de erros
- Integração com API externa

### engine_parser.py - Parser de Fórmulas

Analisa expressões matemáticas e extrai metadados:

```python
parser = FormulaParser(debug=True)
result = parser.parse_formula("sum(e00001v, e00002v > 0) + avg(e00003v)")
```

**Extrai:**
- Funções de agregação (`sum`, `avg`, `count`, etc.)
- Variáveis (formato `eNNNNNv`)
- Filtros e condições
- Dependências entre fórmulas (DAG)

### formula_classifier.py - Classificador de Execução

Ordena fórmulas em grupos baseado em dependências:

```python
classifier = FormulaExecutionClassifier(formulas)
execution_groups = classifier.get_execution_order()
# {1: ['formula_a', 'formula_b'], 2: ['formula_c'], ...}
```

**Características:**
- Ordenação topológica (DAG)
- Detecção de ciclos
- Grupos de execução paralela

### engine_eval.py - Avaliador Seguro

Executa fórmulas em ambiente controlado:

```python
engine = EngineEval(debug=True)
results = engine.eval_formula(enriched_formulas, formulas, data_tree)
```

**Segurança:**
- Sandbox com `asteval`
- Funções restritas (whitelist)
- Bloqueio de operações perigosas
- Suporte a NumPy para cálculos numéricos

### update_tree.py - Atualizador de Árvore

Aplica resultados calculados de volta na estrutura:

```python
updater = UpdateTreeData(tree_data, formulas, results)
updated_tree = updater.update_tree()
```

## Desenvolvimento

### Estrutura de Fórmulas

Fórmulas suportam:

#### Variáveis simples:
```
e00001v + e00002v
```

#### Agregações locais:
```
sum(e00001v) + avg(e00002v, e00003v > 0)
```

#### Agregações globais:
```
sum_node(e00001v) + count(e00002v, e00003v == 'X')
```

#### Funções NumPy:
```
sqrt(sum(e00001v)) + round(avg(e00002v), 2)
```

### Logs e Debugging

```python
# Modo debug ativa logs detalhados
processor = EngineProcessor(debug=True)

# Logs são salvos em:
# - logs/engine.log (arquivo)
# - Console (stdout)
# - API REST (via endpoint /logs/{task_id})
```

### Testes

```bash
# Processar com dados em cache (mais rápido para testes)
python engine_exec.py --cached

# Validar parsing de fórmula específica
python -c "from engine_parser import FormulaParser; \
           p = FormulaParser(); \
           print(p.parse_formula('sum(e00001v)'))"
```

### Cache de Dados

Arquivos de cache são salvos em `data/`:

- `contract_data_{contract_id}.json` - Dados do contrato
- `enriched_data_{contract_id}-{group}.json` - Fórmulas enriquecidas
- `engine_result_g{group}_{contract_id}.json` - Resultados por grupo

## Segurança

### Sandboxing

- **asteval**: Interpretador Python restrito
- **Whitelist de funções**: Apenas funções aprovadas
- **Bloqueio de AST nodes**: Import, Exec, Eval, Attribute bloqueados
- **Validação de entrada**: Sanitização de expressões

### Considerações

- Não executar código não confiável
- Validar todas as entradas de usuário
- Usar HTTPS em produção
- Proteger tokens de API
- Revisar logs regularmente

## Automação

### Cron Jobs

```bash
# Configurar execução agendada
./setup_cron.sh

# Remover cron job
./remove_cron.sh
```

## Troubleshooting

### Erro de conexão com API

Verifique:
- Token de API em `.env`
- URL base da API
- Conectividade de rede
- Certificados SSL (se `DISABLE_SSL_VERIFY=false`)

### Erros de avaliação de fórmulas

- Verificar sintaxe da fórmula
- Validar variáveis existem na árvore
- Revisar logs detalhados (`debug=True`)
- Consultar `config/config.py` para funções permitidas

### Performance

- Usar `use_cached_data=True` para testes
- Limpar arquivos temporários: `data/temp/`
- Verificar tamanho dos logs
- Considerar processamento paralelo de contratos

## Licença

Projeto proprietário - Arteris/SMI

## Suporte

Para questões e suporte, contate a equipe de desenvolvimento SMI.
