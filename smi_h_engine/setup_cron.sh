#!/bin/bash

# Script para configurar execução automática diária do H Engine via cron
# Configura para execução todos os dias às 23:45 no horário de São Paulo (UTC-3)
# Ajusta automaticamente o horário do cron baseado no timezone do sistema

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Função para imprimir mensagens coloridas
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo "=== CONFIGURANDO CRON PARA H ENGINE ==="

# Verificar timezone do sistema e calcular offset
print_info "Verificando timezone do sistema..."
CURRENT_TZ=$(timedatectl show --property=Timezone --value 2>/dev/null || cat /etc/timezone 2>/dev/null || echo "unknown")
print_info "Timezone do sistema: $CURRENT_TZ"

# Obter offset UTC atual do sistema em segundos
SYSTEM_OFFSET_SECONDS=$(date +%z | awk '{
    sign = substr($1, 1, 1) == "-" ? -1 : 1
    hours = substr($1, 2, 2) + 0
    mins = substr($1, 4, 2) + 0
    print sign * (hours * 3600 + mins * 60)
}')

# Offset de São Paulo: UTC-3 = -10800 segundos
SAO_PAULO_OFFSET_SECONDS=-10800

# Calcular diferença em horas
OFFSET_DIFF_SECONDS=$((SYSTEM_OFFSET_SECONDS - SAO_PAULO_OFFSET_SECONDS))
OFFSET_DIFF_HOURS=$((OFFSET_DIFF_SECONDS / 3600))

print_info "Hora atual do sistema: $(date '+%Y-%m-%d %H:%M:%S %Z (UTC%:z)')"
print_info "Offset do sistema: UTC$(date +%:z) | São Paulo: UTC-03:00"
print_info "Diferença de timezone: $OFFSET_DIFF_HOURS horas"
echo ""

# Diretório do script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_SCRIPT="$SCRIPT_DIR/run_h_engine.sh"

# Verificar se o script existe
if [ ! -f "$RUN_SCRIPT" ]; then
    print_error "Script run_h_engine.sh não encontrado em: $RUN_SCRIPT"
    exit 1
fi

# Carregar horário de execução do .env
ENV_FILE="$SCRIPT_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    EXECUTION_TIME=$(grep "^EXECUTION_TIME=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'")
    if [ -z "$EXECUTION_TIME" ]; then
        print_warning "EXECUTION_TIME não encontrado no .env, usando padrão: 23:45"
        EXECUTION_TIME="23:45"
    else
        print_info "Horário carregado do .env: $EXECUTION_TIME (São Paulo UTC-3)"
    fi
else
    print_warning "Arquivo .env não encontrado, usando horário padrão: 23:45"
    EXECUTION_TIME="23:45"
fi

# Validar formato HH:MM
if ! echo "$EXECUTION_TIME" | grep -qE '^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$'; then
    print_error "Formato de EXECUTION_TIME inválido: $EXECUTION_TIME"
    print_error "Use o formato HH:MM (exemplo: 23:45)"
    exit 1
fi

# Extrair hora e minuto
SAO_PAULO_HOUR=$(echo "$EXECUTION_TIME" | cut -d':' -f1)
SAO_PAULO_MINUTE=$(echo "$EXECUTION_TIME" | cut -d':' -f2)

# Remover zeros à esquerda para cálculos
SAO_PAULO_HOUR=$((10#$SAO_PAULO_HOUR))
SAO_PAULO_MINUTE=$((10#$SAO_PAULO_MINUTE))

# Verificar se o script é executável
if [ ! -x "$RUN_SCRIPT" ]; then
    print_warning "Tornando run_h_engine.sh executável..."
    chmod +x "$RUN_SCRIPT"
fi

# Modo de teste (executa 1 minuto após o comando)
TEST_MODE=false
if [ "$1" == "--test" ] || [ "$1" == "-t" ]; then
    TEST_MODE=true
    print_warning "MODO DE TESTE ATIVADO - Execução em 1 minuto"
fi

# Configuração do cron job
if [ "$TEST_MODE" = true ]; then
    # Calcular horário de teste (próximo minuto) - compatível com Linux
    NEXT_MINUTE=$(date -d '+1 minute' '+%M' 2>/dev/null || date -v+1M '+%M')
    CURRENT_HOUR=$(date '+%H')
    CRON_TIME="$NEXT_MINUTE $CURRENT_HOUR * * *"
    DISPLAY_TIME="próximo minuto (teste)"
else
    # Ajustar hora para o timezone do sistema
    # Se sistema está em UTC (0) e SP em UTC-3, adicionar 3 horas: 23:45 + 3 = 02:45 (dia seguinte)
    # Se sistema está em UTC-3 e SP em UTC-3, manter: 23:45
    ADJUSTED_HOUR=$((SAO_PAULO_HOUR - OFFSET_DIFF_HOURS))
    ADJUSTED_MINUTE=$SAO_PAULO_MINUTE

    # Normalizar hora (tratar valores negativos e >= 24)
    while [ $ADJUSTED_HOUR -lt 0 ]; do
        ADJUSTED_HOUR=$((ADJUSTED_HOUR + 24))
    done
    while [ $ADJUSTED_HOUR -ge 24 ]; do
        ADJUSTED_HOUR=$((ADJUSTED_HOUR - 24))
    done

    CRON_TIME="$ADJUSTED_MINUTE $ADJUSTED_HOUR * * *"

    # Mensagem explicativa
    if [ $OFFSET_DIFF_HOURS -ne 0 ]; then
        DISPLAY_TIME="$ADJUSTED_HOUR:$(printf '%02d' $ADJUSTED_MINUTE) (hora local) = $EXECUTION_TIME São Paulo (UTC-3)"
    else
        DISPLAY_TIME="$EXECUTION_TIME (mesmo timezone de São Paulo)"
    fi
fi

LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/cron_h_engine.log"

# Criar diretório de logs se não existir
if [ ! -d "$LOG_DIR" ]; then
    print_info "Criando diretório de logs: $LOG_DIR"
    mkdir -p "$LOG_DIR"
fi

# Cron job completo com redirecionamento de logs
CRON_JOB="$CRON_TIME $RUN_SCRIPT >> $LOG_FILE 2>&1"

print_info "Configuração do cron job:"
print_info "Horário: $DISPLAY_TIME"
print_info "Cron: $CRON_TIME"
print_info "Script: $RUN_SCRIPT"
print_info "Logs: $LOG_FILE"

# Verificar se o cron job já existe
if crontab -l 2>/dev/null | grep -q "$RUN_SCRIPT"; then
    print_warning "Cron job já existe para este script"
    print_info "Removendo configuração anterior..."
    crontab -l 2>/dev/null | grep -v "$RUN_SCRIPT" | crontab -
fi

# Adicionar novo cron job
print_info "Adicionando novo cron job..."
(crontab -l 2>/dev/null || true; echo "$CRON_JOB") | crontab -

# Verificar se foi adicionado corretamente
if crontab -l 2>/dev/null | grep -q "$RUN_SCRIPT"; then
    print_info "Cron job configurado com sucesso!"
    echo ""
    print_info "=== CONFIGURAÇÃO ATUAL DO CRON ==="
    crontab -l | grep "$RUN_SCRIPT"
    echo ""
    if [ "$TEST_MODE" = true ]; then
        print_info "MODO DE TESTE: O H Engine será executado no próximo minuto"
        print_info "Aguardando execução para verificar funcionamento..."
        print_info "Monitorando log: $LOG_FILE"
        echo ""

        # Aguardar execução (65 segundos para garantir)
        sleep 65

        # Verificar se o log foi atualizado
        if [ -f "$LOG_FILE" ]; then
            LAST_LOG=$(tail -n 20 "$LOG_FILE")
            if echo "$LAST_LOG" | grep -q "INICIALIZANDO\|CONCLUÍDO\|engine_exec.py"; then
                print_info "✓ TESTE BEM-SUCEDIDO! O cron executou corretamente."
                echo ""
                print_info "=== ÚLTIMAS LINHAS DO LOG ==="
                tail -n 10 "$LOG_FILE"
                echo ""
                print_warning "Removendo configuração de teste..."
                crontab -l 2>/dev/null | grep -v "$RUN_SCRIPT" | crontab -
                print_info "Configure novamente sem --test para uso em produção:"
                print_info "./setup_cron.sh"
            else
                print_error "✗ O cron foi configurado mas não há evidência de execução no log"
                print_info "Verifique manualmente: tail -f $LOG_FILE"
            fi
        else
            print_error "✗ Log não foi criado. O cron pode não ter executado."
            print_info "Verifique o cron manualmente: crontab -l"
        fi
    else
        print_info "O H Engine será executado todos os dias às $EXECUTION_TIME (São Paulo UTC-3)"
        if [ $OFFSET_DIFF_HOURS -ne 0 ]; then
            print_info "No timezone local ($CURRENT_TZ), isso equivale a $ADJUSTED_HOUR:$(printf '%02d' $ADJUSTED_MINUTE)"
        fi
        print_info "Logs serão salvos em: $LOG_FILE"
        print_info ""
        print_info "Para testar o cron, execute: ./setup_cron.sh --test"
        print_info "Para remover a configuração, execute: ./remove_cron.sh"
    fi
else
    print_error "Erro ao configurar cron job"
    exit 1
fi

print_info "=== CONFIGURAÇÃO CONCLUÍDA ==="