#!/bin/bash
set -e

# Script de entrypoint para container Docker
# Suporta múltiplos modos de execução

echo "=== SMI H-Engine Docker Entrypoint ==="
echo "Mode: ${1:-api}"
echo "Python version: $(python --version)"
echo "Working directory: $(pwd)"
echo ""

# Função para validar variáveis de ambiente obrigatórias
validate_env() {
    if [ -z "$ARTERIS_API_TOKEN" ]; then
        echo "WARNING: ARTERIS_API_TOKEN não definido. Algumas funcionalidades podem não funcionar."
    fi

    if [ -z "$ARTERIS_API_BASE_URL" ]; then
        echo "WARNING: ARTERIS_API_BASE_URL não definido. Usando padrão."
    fi
}

# Função para criar diretórios necessários
setup_directories() {
    echo "Configurando diretórios..."
    mkdir -p logs data/temp engine_entities/temp
    echo "Diretórios criados com sucesso"
}


# Função para iniciar a API
start_api() {
    echo "Iniciando API REST na porta 8084..."
    validate_env
    setup_directories

    # Mudar para usuário appuser e iniciar API
    exec gosu appuser uvicorn api_engine:app --host 0.0.0.0 --port 8084 --log-level info
}

# Função para executar processamento único
run_once() {
    echo "Executando processamento único..."
    validate_env
    setup_directories

    MEASUREMENT=${2:-}

    if [ -n "$MEASUREMENT" ]; then
        echo "Processando medição específica: $MEASUREMENT"
        exec python engine_exec.py "$MEASUREMENT"
    else
        echo "Processando todas as medições"
        exec python engine_exec.py
    fi
}

# Função para modo shell/debug
run_shell() {
    echo "Iniciando modo shell para debug..."
    exec /bin/bash
}

# Função para executar testes
run_tests() {
    echo "Executando testes..."
    setup_directories

    # Exemplo de teste simples
    python -c "
from engine_parser import FormulaParser
from engine_eval import EngineEval

print('Testing FormulaParser...')
parser = FormulaParser()
result = parser.parse_formula('sum(e00001v) + avg(e00002v)')
print(f'Parser test: OK - {result}')

print('Testing EngineEval...')
engine = EngineEval()
print('EngineEval test: OK')

print('All tests passed!')
"
}

# Função para exibir ajuda
show_help() {
    cat << EOF
SMI H-Engine Docker Entrypoint

Uso: docker run smi-h-engine [MODE] [ARGS]

Modos disponíveis:
  api                    Inicia API REST (padrão)
  run-once [MEASUREMENT] Executa processamento único e finaliza
  shell                  Inicia shell bash para debug
  test                   Executa testes básicos
  help                   Exibe esta ajuda

Variáveis de ambiente:
  ARTERIS_API_TOKEN              Token de autenticação da API externa
  ARTERIS_API_BASE_URL           URL base da API externa
  ARTERIS_API_URL_UPDATE_DOCKTYPE URL para atualização de doctypes
  DISABLE_SSL_VERIFY             Desabilitar verificação SSL (true/false)
  LOG_LEVEL                      Nível de log (DEBUG/INFO/WARNING/ERROR)
  WORKER_INTERVAL                Intervalo entre processamentos (segundos)

Exemplos:
  docker run smi-h-engine
  docker run smi-h-engine api
  docker run smi-h-engine run-once BM-CW40566-001
  docker run smi-h-engine shell
  docker run -it smi-h-engine test

EOF
}

# Roteamento para o modo apropriado
case "${1:-api}" in
    api)
        start_api
        ;;
    run-once)
        run_once "$@"
        ;;
    shell|bash|sh)
        run_shell
        ;;
    test|tests)
        run_tests
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "Modo desconhecido: $1"
        echo "Use 'help' para ver modos disponíveis"
        exit 1
        ;;
esac
