#!/bin/bash

# Script para executar tarefas diárias sequencialmente às 22:00
# Ordem: SAP Order → FTD → Kartado → Osiris
# Autor: Script automatizado para execução diária do projeto arteris_kartado

# Para o script se houver erro crítico (mas permite continuar em alguns casos)
set -e

# Sistema de lock para evitar execuções paralelas
LOCK_FILE="/tmp/arteris_daily_tasks.lock"
LOCK_TIMEOUT=7200  # 2 horas (para todas as 4 tarefas)

# Verificar se existe lock ativo
if [ -f "$LOCK_FILE" ]; then
    LOCK_PID=$(cat "$LOCK_FILE")
    LOCK_AGE=$(($(date +%s) - $(stat -c %Y "$LOCK_FILE" 2>/dev/null || stat -f %m "$LOCK_FILE")))

    # Verificar se o processo ainda existe
    if kill -0 "$LOCK_PID" 2>/dev/null; then
        if [ $LOCK_AGE -lt $LOCK_TIMEOUT ]; then
            echo "Script já em execução (PID: $LOCK_PID). Abortando."
            exit 1
        else
            echo "Lock expirado (>1h). Removendo e continuando..."
            rm -f "$LOCK_FILE"
        fi
    else
        echo "Lock órfão detectado. Removendo..."
        rm -f "$LOCK_FILE"
    fi
fi

# Criar lock
echo $$ > "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

# Configurar logging
LOG_DIR="/var/log/arteris_kartado"
LOG_FILE="$LOG_DIR/daily_execution_$(date +%Y%m%d).log"

# Criar diretório de log se não existir
mkdir -p "$LOG_DIR"

# Função de log
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Redirecionar toda saída para o arquivo de log também
exec > >(tee -a "$LOG_FILE") 2>&1

echo "========================================"
log "INICIANDO EXECUÇÃO DIÁRIA - ARTERIS KARTADO"
echo "========================================"

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Função para imprimir mensagens coloridas
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
    log "INFO: $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
    log "WARNING: $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    log "ERROR: $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
    log "SUCCESS: $1"
}

# Diretório do script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

print_info "Diretório de trabalho: $SCRIPT_DIR"
print_info "Arquivo de log: $LOG_FILE"

# Verificar se os scripts existem
REQUIRED_SCRIPTS=("run_saporder.sh" "run_ftd.sh" "run_kartado.sh" "run_osiris.sh")
for script in "${REQUIRED_SCRIPTS[@]}"; do
    if [ ! -f "$script" ]; then
        print_error "Script $script não encontrado"
        exit 1
    fi
    if [ ! -x "$script" ]; then
        print_warning "Tornando $script executável..."
        chmod +x "$script"
    fi
done

# Variáveis de controle
SAPORDER_SUCCESS=false
FTD_SUCCESS=false
KARTADO_SUCCESS=false
OSIRIS_SUCCESS=false

SAPORDER_EXIT_CODE=0
FTD_EXIT_CODE=0
KARTADO_EXIT_CODE=0
OSIRIS_EXIT_CODE=0

# Função auxiliar para executar uma tarefa
execute_task() {
    local task_name=$1
    local script_path=$2
    local success_var=$3
    local exit_code_var=$4

    echo "========================================"
    print_info "=== TAREFA $task_name ==="
    echo "========================================"
    log "Iniciando $task_name às $(date)"

    local start_time=$(date +%s)

    # Desabilitar set -e temporariamente para capturar erros
    set +e

    # Executar script
    ./"$script_path"
    local exit_code=$?

    # Reabilitar set -e
    set -e

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    if [ $exit_code -eq 0 ]; then
        eval "$success_var=true"
        print_success "$task_name executado com sucesso! (${duration}s)"
        log "$task_name concluído com sucesso às $(date) - Duração: ${duration}s"
    else
        print_error "$task_name falhou com código de saída: $exit_code (${duration}s)"
        log "$task_name falhou às $(date) - Exit code: $exit_code - Duração: ${duration}s"
        eval "$exit_code_var=$exit_code"

        # Em modo cron, continua com próxima tarefa
        if [ ! -t 0 ]; then
            print_warning "Modo não-interativo: continuando com próxima tarefa"
            log "Continuando execução em modo não-interativo"
        fi
    fi

    # Pausa entre tarefas
    sleep 3
}

# ==========================================
# TAREFA 1: SAP ORDER
# ==========================================
execute_task "SAP ORDER" "run_saporder.sh" "SAPORDER_SUCCESS" "SAPORDER_EXIT_CODE"

# ==========================================
# TAREFA 2: FTD
# ==========================================
execute_task "FTD" "run_ftd.sh" "FTD_SUCCESS" "FTD_EXIT_CODE"

# ==========================================
# TAREFA 3: KARTADO
# ==========================================
execute_task "KARTADO" "run_kartado.sh" "KARTADO_SUCCESS" "KARTADO_EXIT_CODE"

# ==========================================
# TAREFA 4: OSIRIS
# ==========================================
execute_task "OSIRIS" "run_osiris.sh" "OSIRIS_SUCCESS" "OSIRIS_EXIT_CODE"

# ==========================================
# RELATÓRIO FINAL
# ==========================================
echo ""
echo "========================================"
print_info "RELATÓRIO FINAL DA EXECUÇÃO DIÁRIA"
echo "========================================"
echo ""

# Contador de tarefas
TOTAL_TASKS=4
SUCCESS_COUNT=0
FAILED_COUNT=0

# SAP Order
if [ "$SAPORDER_SUCCESS" = true ]; then
    print_success "✅ SAP Order: SUCESSO"
    ((SUCCESS_COUNT++))
else
    print_error "❌ SAP Order: FALHA (Exit code: $SAPORDER_EXIT_CODE)"
    ((FAILED_COUNT++))
fi

# FTD
if [ "$FTD_SUCCESS" = true ]; then
    print_success "✅ FTD: SUCESSO"
    ((SUCCESS_COUNT++))
else
    print_error "❌ FTD: FALHA (Exit code: $FTD_EXIT_CODE)"
    ((FAILED_COUNT++))
fi

# Kartado
if [ "$KARTADO_SUCCESS" = true ]; then
    print_success "✅ Kartado: SUCESSO"
    ((SUCCESS_COUNT++))
else
    print_error "❌ Kartado: FALHA (Exit code: $KARTADO_EXIT_CODE)"
    ((FAILED_COUNT++))
fi

# Osiris
if [ "$OSIRIS_SUCCESS" = true ]; then
    print_success "✅ Osiris: SUCESSO"
    ((SUCCESS_COUNT++))
else
    print_error "❌ Osiris: FALHA (Exit code: $OSIRIS_EXIT_CODE)"
    ((FAILED_COUNT++))
fi

echo ""
echo "========================================"
print_info "Total: $SUCCESS_COUNT/$TOTAL_TASKS tarefas concluídas com sucesso"
echo "========================================"

# Status final
if [ $SUCCESS_COUNT -eq $TOTAL_TASKS ]; then
    print_success "🎉 EXECUÇÃO DIÁRIA CONCLUÍDA COM SUCESSO!"
    log "Execução diária concluída com sucesso às $(date) - $SUCCESS_COUNT/$TOTAL_TASKS"
    exit 0
elif [ $SUCCESS_COUNT -gt 0 ]; then
    print_warning "⚠️  EXECUÇÃO PARCIALMENTE CONCLUÍDA ($SUCCESS_COUNT/$TOTAL_TASKS)"
    log "Execução diária parcialmente concluída às $(date) - $SUCCESS_COUNT/$TOTAL_TASKS"
    exit 1
else
    print_error "💥 EXECUÇÃO DIÁRIA FALHOU COMPLETAMENTE (0/$TOTAL_TASKS)"
    log "Execução diária falhou completamente às $(date)"
    exit 2
fi