#!/bin/bash
set -e

# Script de entrypoint para container Docker
# Suporta múltiplos modos de execução

echo "=== SMI Data Connector Docker Entrypoint ==="
echo "Mode: ${1:-api}"
echo "Python version: $(python --version)"
echo "Working directory: $(pwd)"
echo ""

# Verificar configuração de development.localhost
if grep -q "development.localhost" /etc/hosts; then
    DEV_LOCALHOST_IP=$(grep "development.localhost" /etc/hosts | head -1 | awk '{print $1}')
    echo "✓ development.localhost configurado -> $DEV_LOCALHOST_IP"
else
    echo "WARNING: development.localhost não encontrado em /etc/hosts"
fi
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
    mkdir -p logs data/temp
    echo "Diretórios criados com sucesso"
}


# Função para iniciar a API
start_api() {
    echo "Iniciando API REST na porta 8085..."
    validate_env
    setup_directories

    # Mudar para usuário appuser e iniciar API
    exec gosu appuser uvicorn api_import:app --host 0.0.0.0 --port 8085 --log-level info
}

# Função para executar tarefas diárias manualmente
run_daily() {
    echo "Executando tarefas diárias manualmente..."
    validate_env
    setup_directories

    exec gosu appuser /usr/local/bin/run_daily_tasks.sh
}

# Função para executar task específica
run_task() {
    echo "Executando task específica: ${2}"
    validate_env
    setup_directories

    case "${2}" in
        saporder)
            exec gosu appuser bash /app/run_saporder.sh
            ;;
        ftd)
            exec gosu appuser bash /app/run_ftd.sh
            ;;
        kartado)
            exec gosu appuser bash /app/run_kartado.sh
            ;;
        osiris)
            exec gosu appuser bash /app/run_osiris.sh
            ;;
        *)
            echo "Task desconhecida: ${2}"
            echo "Tasks disponíveis: saporder, ftd, kartado, osiris"
            exit 1
            ;;
    esac
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

    # Teste simples
    python -c "
import sys
print('Testing imports...')

try:
    from api_import import app
    print('✓ api_import OK')
except Exception as e:
    print(f'✗ api_import FAIL: {e}')
    sys.exit(1)

try:
    import kartado
    print('✓ kartado OK')
except Exception as e:
    print(f'✗ kartado FAIL: {e}')
    sys.exit(1)

try:
    import osiris
    print('✓ osiris OK')
except Exception as e:
    print(f'✗ osiris FAIL: {e}')
    sys.exit(1)

print('')
print('All tests passed!')
"
}

# Função para exibir ajuda
show_help() {
    cat << EOF
SMI Data Connector Docker Entrypoint

Uso: docker run smi-data-connector [MODE] [ARGS]

Modos disponíveis:
  api                    Inicia API REST (padrão)
  run-daily              Executa tarefas diárias manualmente
  run-task <task>        Executa task específica (saporder|ftd|kartado|osiris)
  shell                  Inicia shell bash para debug
  test                   Executa testes básicos
  help                   Exibe esta ajuda

Variáveis de ambiente:
  ARTERIS_API_TOKEN              Token de autenticação da API externa
  ARTERIS_API_BASE_URL           URL base da API externa
  AWS_REGION                     Região AWS
  AWS_ACCESS_KEY_ID              AWS Access Key
  AWS_SECRET_ACCESS_KEY          AWS Secret Key
  S3_OUTPUT_LOCATION             Localização S3 para output
  OSIRIS_LOGIN                   Login do Osiris
  OSIRIS_PASSWORD                Senha do Osiris
  LOG_LEVEL                      Nível de log (DEBUG/INFO/WARNING/ERROR)

Exemplos:
  docker run smi-data-connector
  docker run smi-data-connector api
  docker run smi-data-connector run-daily
  docker run smi-data-connector run-task kartado
  docker run smi-data-connector shell
  docker run -it smi-data-connector test

EOF
}

# Roteamento para o modo apropriado
case "${1:-api}" in
    api)
        start_api
        ;;
    run-daily)
        run_daily
        ;;
    run-task)
        run_task "$@"
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
