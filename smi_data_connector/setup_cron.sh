#!/bin/bash

# Script para configurar cron job para execução diária às 22:00 (Horário de São Paulo UTC-3)
# Autor: Script de configuração do cron para arteris_kartado
# Uso: ./setup_cron.sh [--test]
#   --test: Configura execuções de teste em 1 minuto com countdown

echo "=== CONFIGURANDO CRON JOB ==="

# Verificar modo de teste
TEST_MODE=false
if [ "$1" = "--test" ]; then
    TEST_MODE=true
    echo "🧪 MODO DE TESTE ATIVADO - Execuções configuradas para 1 minuto"
fi

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ==========================================
# VERIFICAR TIMEZONE
# ==========================================
print_info "Verificando timezone do sistema..."

# Obter timezone atual
CURRENT_TZ=$(timedatectl show -p Timezone --value 2>/dev/null || cat /etc/timezone 2>/dev/null || echo "Desconhecido")
CURRENT_OFFSET=$(date +%z)

print_info "Timezone atual: $CURRENT_TZ (UTC$CURRENT_OFFSET)"

# Verificar se está em São Paulo (UTC-3 ou UTC-2 durante horário de verão)
if [[ "$CURRENT_TZ" == "America/Sao_Paulo" ]] || [[ "$CURRENT_TZ" == "America/São_Paulo" ]]; then
    print_info "✅ Timezone correto: America/Sao_Paulo"
elif [[ "$CURRENT_OFFSET" == "-0300" ]] || [[ "$CURRENT_OFFSET" == "-0200" ]]; then
    print_warning "⚠️  Timezone não é America/Sao_Paulo, mas o offset está correto ($CURRENT_OFFSET)"
else
    print_warning "⚠️  ATENÇÃO: Timezone pode não estar configurado para São Paulo!"
    print_warning "   Timezone detectado: $CURRENT_TZ (UTC$CURRENT_OFFSET)"
    print_warning "   Os cron jobs executarão no horário do sistema atual."
    echo
    print_info "Para configurar timezone de São Paulo no Ubuntu, execute:"
    echo "  sudo timedatectl set-timezone America/Sao_Paulo"
    echo
    read -t 10 -p "Deseja continuar mesmo assim? (y/N): " -n 1 -r || REPLY="y"
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]] && [ -t 0 ]; then
        print_error "Configuração cancelada. Configure o timezone primeiro."
        exit 1
    fi
fi

echo

# Diretório do script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DAILY_SCRIPT="$SCRIPT_DIR/run_daily.sh"
ADOBE_SCRIPT="$SCRIPT_DIR/run_adobe.sh"
ENV_FILE="$SCRIPT_DIR/.env"

print_info "Diretório do projeto: $SCRIPT_DIR"

# ==========================================
# CARREGAR CONFIGURAÇÕES DO .ENV
# ==========================================
print_info "Carregando configurações do .env..."

# Valores padrão
DEFAULT_DAILY_HOUR=22
DEFAULT_DAILY_MINUTE=0
DEFAULT_ADOBE_INTERVAL=60

CRON_DAILY_HOUR=$DEFAULT_DAILY_HOUR
CRON_DAILY_MINUTE=$DEFAULT_DAILY_MINUTE
CRON_ADOBE_INTERVAL=$DEFAULT_ADOBE_INTERVAL

if [ -f "$ENV_FILE" ]; then
    print_info "✅ Arquivo .env encontrado"

    # Função para ler variável do .env (ignora comentários e espaços)
    read_env_var() {
        local var_name=$1
        local value=$(grep "^${var_name}=" "$ENV_FILE" | cut -d '=' -f2- | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | sed 's/#.*//')
        echo "$value"
    }

    # Ler variáveis
    CRON_DAILY_HOUR=$(read_env_var "CRON_DAILY_HOUR")
    CRON_DAILY_MINUTE=$(read_env_var "CRON_DAILY_MINUTE")
    CRON_ADOBE_INTERVAL=$(read_env_var "CRON_ADOBE_INTERVAL")

    # Usar valores padrão se não estiverem definidos
    [ -z "$CRON_DAILY_HOUR" ] && CRON_DAILY_HOUR=$DEFAULT_DAILY_HOUR
    [ -z "$CRON_DAILY_MINUTE" ] && CRON_DAILY_MINUTE=$DEFAULT_DAILY_MINUTE
    [ -z "$CRON_ADOBE_INTERVAL" ] && CRON_ADOBE_INTERVAL=$DEFAULT_ADOBE_INTERVAL

    # Validar valores
    if ! [[ "$CRON_DAILY_HOUR" =~ ^[0-9]+$ ]] || [ "$CRON_DAILY_HOUR" -lt 0 ] || [ "$CRON_DAILY_HOUR" -gt 23 ]; then
        print_warning "⚠️  CRON_DAILY_HOUR inválido ($CRON_DAILY_HOUR). Usando padrão: $DEFAULT_DAILY_HOUR"
        CRON_DAILY_HOUR=$DEFAULT_DAILY_HOUR
    fi

    if ! [[ "$CRON_DAILY_MINUTE" =~ ^[0-9]+$ ]] || [ "$CRON_DAILY_MINUTE" -lt 0 ] || [ "$CRON_DAILY_MINUTE" -gt 59 ]; then
        print_warning "⚠️  CRON_DAILY_MINUTE inválido ($CRON_DAILY_MINUTE). Usando padrão: $DEFAULT_DAILY_MINUTE"
        CRON_DAILY_MINUTE=$DEFAULT_DAILY_MINUTE
    fi

    if ! [[ "$CRON_ADOBE_INTERVAL" =~ ^[0-9]+$ ]] || [ "$CRON_ADOBE_INTERVAL" -lt 0 ] || [ "$CRON_ADOBE_INTERVAL" -gt 1440 ]; then
        print_warning "⚠️  CRON_ADOBE_INTERVAL inválido ($CRON_ADOBE_INTERVAL). Usando padrão: $DEFAULT_ADOBE_INTERVAL"
        CRON_ADOBE_INTERVAL=$DEFAULT_ADOBE_INTERVAL
    fi

    print_info "📋 Configurações carregadas do .env:"
    print_info "   Tarefas Diárias: ${CRON_DAILY_HOUR}:$(printf "%02d" $CRON_DAILY_MINUTE) (horário de SP)"
    print_info "   Adobe: A cada $CRON_ADOBE_INTERVAL minutos"
else
    print_warning "⚠️  Arquivo .env não encontrado em: $ENV_FILE"
    print_warning "   Usando valores padrão:"
    print_warning "   - Tarefas Diárias: ${DEFAULT_DAILY_HOUR}:$(printf "%02d" $DEFAULT_DAILY_MINUTE) (horário de SP)"
    print_warning "   - Adobe: A cada $DEFAULT_ADOBE_INTERVAL minutos"
    echo
    print_info "Para personalizar os horários, copie .env.example para .env e ajuste:"
    echo "  cp .env.example .env"
    echo "  nano .env"
fi

echo

# Verificar se o script diário existe
if [ ! -f "$DAILY_SCRIPT" ]; then
    print_error "Script run_daily.sh não encontrado em: $DAILY_SCRIPT"
    exit 1
fi

# Verificar se o script adobe existe
if [ ! -f "$ADOBE_SCRIPT" ]; then
    print_error "Script run_adobe.sh não encontrado em: $ADOBE_SCRIPT"
    exit 1
fi

# Verificar se os scripts são executáveis
if [ ! -x "$DAILY_SCRIPT" ]; then
    print_warning "Tornando run_daily.sh executável..."
    chmod +x "$DAILY_SCRIPT"
fi

if [ ! -x "$ADOBE_SCRIPT" ]; then
    print_warning "Tornando run_adobe.sh executável..."
    chmod +x "$ADOBE_SCRIPT"
fi

# Criar diretório de logs se não existir
print_info "Criando diretórios de logs..."
sudo mkdir -p /var/log/arteris_kartado
sudo mkdir -p /var/log/arteris_adobe
sudo chown $(whoami):$(whoami) /var/log/arteris_kartado
sudo chown $(whoami):$(whoami) /var/log/arteris_adobe

# Backup do crontab atual
print_info "Fazendo backup do crontab atual..."
crontab -l > /tmp/crontab_backup_$(date +%Y%m%d_%H%M%S) 2>/dev/null || echo "# Novo crontab" > /tmp/crontab_backup_$(date +%Y%m%d_%H%M%S)

# ==========================================
# CALCULAR HORÁRIO AJUSTADO PARA SÃO PAULO
# ==========================================

# Horário desejado em São Paulo (UTC-3) - vem do .env
SP_DAILY_HOUR=$CRON_DAILY_HOUR
SP_DAILY_MINUTE=$CRON_DAILY_MINUTE

# Calcular diferença entre UTC e horário atual do sistema
# Formato: +0000, -0300, +0530, etc
CURRENT_OFFSET_RAW=$(date +%z)
SIGN=${CURRENT_OFFSET_RAW:0:1}
HOURS=${CURRENT_OFFSET_RAW:1:2}
MINUTES=${CURRENT_OFFSET_RAW:3:2}

# Converter para inteiro usando base 10 (remover zeros à esquerda)
CURRENT_OFFSET_HOURS=$((10#$HOURS))

# Aplicar sinal negativo se necessário
if [ "$SIGN" = "-" ]; then
    CURRENT_OFFSET_HOURS=$((-1 * CURRENT_OFFSET_HOURS))
fi

# Avisar se timezone tem minutos (raro, mas existe - ex: Índia +05:30)
if [ "$MINUTES" != "00" ]; then
    print_warning "⚠️  Timezone com minutos detectado: ${CURRENT_OFFSET_RAW}"
    print_warning "   O ajuste considerará apenas as horas completas."
fi

# São Paulo está em UTC-3 (offset -03:00 = -3 horas)
SP_OFFSET=-3

# Calcular ajuste necessário
# Se sistema está em UTC (0), e queremos SP (-3), precisamos adicionar 3 horas
# Se sistema está em SP (-3), e queremos SP (-3), não ajusta
HOUR_ADJUSTMENT=$((SP_OFFSET - CURRENT_OFFSET_HOURS))

# Calcular horário local do sistema para executar às 22:00 de SP
ADJUSTED_DAILY_HOUR=$((SP_DAILY_HOUR - HOUR_ADJUSTMENT))

# Normalizar horário (0-23)
if [ $ADJUSTED_DAILY_HOUR -lt 0 ]; then
    ADJUSTED_DAILY_HOUR=$((ADJUSTED_DAILY_HOUR + 24))
elif [ $ADJUSTED_DAILY_HOUR -ge 24 ]; then
    ADJUSTED_DAILY_HOUR=$((ADJUSTED_DAILY_HOUR - 24))
fi

print_info "🕐 Ajuste de horário:"
print_info "  Timezone do sistema: UTC$CURRENT_OFFSET (offset: $CURRENT_OFFSET_HOURS horas)"
print_info "  Timezone de São Paulo: UTC-3 (offset: -3 horas)"
print_info "  Ajuste necessário: $HOUR_ADJUSTMENT horas"
print_info "  Horário desejado (SP): ${SP_DAILY_HOUR}:$(printf "%02d" $SP_DAILY_MINUTE)"
print_info "  Horário ajustado (sistema): ${ADJUSTED_DAILY_HOUR}:$(printf "%02d" $SP_DAILY_MINUTE)"
echo

# Criar entradas do cron
if [ "$TEST_MODE" = true ]; then
    # Modo teste: execuções em 1 minuto
    CURRENT_HOUR=$(date "+%H")
    MIN1=$(date -d "+1 minute" "+%M" 2>/dev/null || date -v+1M "+%M")
    MIN2=$(date -d "+2 minutes" "+%M" 2>/dev/null || date -v+2M "+%M")

    HOUR1=$CURRENT_HOUR
    HOUR2=$CURRENT_HOUR

    if [ "$MIN2" -lt "$MIN1" ]; then HOUR2=$((CURRENT_HOUR + 1)); fi

    DAILY_CRON_ENTRY="$MIN1 $HOUR1 * * * cd $SCRIPT_DIR && ./run_daily.sh >> /var/log/arteris_kartado/cron.log 2>&1"
    ADOBE_CRON_ENTRY="$MIN2 $HOUR2 * * * cd $SCRIPT_DIR && ./run_adobe.sh >> /var/log/arteris_adobe/cron.log 2>&1"

    print_info "⏰ Execuções programadas para teste (horário do sistema):"
    print_info "  1. Tarefas Diárias (SAP Order→FTD→Kartado→Osiris): $HOUR1:$MIN1"
    print_info "  2. Adobe: $HOUR2:$MIN2"
else
    # Configurar entrada daily com minutos do .env
    DAILY_CRON_ENTRY="$SP_DAILY_MINUTE $ADJUSTED_DAILY_HOUR * * * cd $SCRIPT_DIR && ./run_daily.sh >> /var/log/arteris_kartado/cron.log 2>&1"

    # Configurar Adobe baseado no intervalo
    if [ "$CRON_ADOBE_INTERVAL" -eq 60 ]; then
        # A cada hora (padrão)
        ADOBE_CRON_ENTRY="0 * * * * cd $SCRIPT_DIR && ./run_adobe.sh >> /var/log/arteris_adobe/cron.log 2>&1"
        ADOBE_DESC="A cada hora"
    elif [ "$CRON_ADOBE_INTERVAL" -eq 0 ]; then
        # Desabilitado
        ADOBE_CRON_ENTRY=""
        ADOBE_DESC="Desabilitado"
        print_warning "⚠️  Adobe está desabilitado (CRON_ADOBE_INTERVAL=0)"
    elif [ "$CRON_ADOBE_INTERVAL" -le 59 ]; then
        # Intervalo em minutos
        ADOBE_CRON_ENTRY="*/$CRON_ADOBE_INTERVAL * * * * cd $SCRIPT_DIR && ./run_adobe.sh >> /var/log/arteris_adobe/cron.log 2>&1"
        ADOBE_DESC="A cada $CRON_ADOBE_INTERVAL minutos"
    else
        # Intervalo maior que 1 hora (converter para horas)
        HOURS=$((CRON_ADOBE_INTERVAL / 60))
        ADOBE_CRON_ENTRY="0 */$HOURS * * * cd $SCRIPT_DIR && ./run_adobe.sh >> /var/log/arteris_adobe/cron.log 2>&1"
        ADOBE_DESC="A cada $HOURS horas"
    fi

    print_info "⏰ Cron configurado para executar:"
    print_info "  Tarefas Diárias: ${ADJUSTED_DAILY_HOUR}:$(printf "%02d" $SP_DAILY_MINUTE) (sistema) = ${SP_DAILY_HOUR}:$(printf "%02d" $SP_DAILY_MINUTE) (SP)"
    print_info "  Adobe: $ADOBE_DESC"
fi

print_info "Configurando cron jobs..."
print_info "Entrada do cron daily: $DAILY_CRON_ENTRY"
print_info "Entrada do cron adobe: $ADOBE_CRON_ENTRY"

# Verificar se as entradas já existem e remover antigas
if crontab -l 2>/dev/null | grep -q "run_daily.sh"; then
    print_warning "Entrada do cron daily já existe. Removendo entrada antiga..."
    crontab -l 2>/dev/null | grep -v "run_daily.sh" | crontab -
fi

if crontab -l 2>/dev/null | grep -q "run_adobe.sh"; then
    print_warning "Entrada do cron adobe já existe. Removendo entrada antiga..."
    crontab -l 2>/dev/null | grep -v "run_adobe.sh" | crontab -
fi

# Adicionar novas entradas
print_info "Adicionando novas entradas do cron..."

if [ -n "$ADOBE_CRON_ENTRY" ]; then
    # Adobe habilitado - adicionar ambas entradas
    (crontab -l 2>/dev/null; echo "$DAILY_CRON_ENTRY"; echo "$ADOBE_CRON_ENTRY") | crontab -
else
    # Adobe desabilitado - adicionar apenas daily
    (crontab -l 2>/dev/null; echo "$DAILY_CRON_ENTRY") | crontab -
fi

# Verificar se foram adicionados com sucesso
DAILY_ADDED=$(crontab -l | grep -q "run_daily.sh" && echo "yes" || echo "no")
ADOBE_ADDED=$(crontab -l | grep -q "run_adobe.sh" && echo "yes" || echo "no")

if [ "$DAILY_ADDED" = "yes" ] && ([ -z "$ADOBE_CRON_ENTRY" ] || [ "$ADOBE_ADDED" = "yes" ]); then
    print_info "✅ Cron jobs configurados com sucesso!"
    echo
    print_info "Configuração dos cron jobs:"
    echo "  📅 Tarefas Diárias"
    echo "      ├─ Horário (SP): ${SP_DAILY_HOUR}:$(printf "%02d" $SP_DAILY_MINUTE) (horário de São Paulo)"
    echo "      ├─ Horário (Sistema): ${ADJUSTED_DAILY_HOUR}:$(printf "%02d" $SP_DAILY_MINUTE) (UTC$CURRENT_OFFSET)"
    echo "      ├─ SAP Order (1º)"
    echo "      ├─ FTD (2º)"
    echo "      ├─ Kartado (3º)"
    echo "      └─ Osiris (4º)"
    echo "  📂 Diretório: $SCRIPT_DIR"
    echo "  📝 Script: run_daily.sh"
    echo "  📋 Log do cron: /var/log/arteris_kartado/cron.log"
    echo "  📊 Logs detalhados: /var/log/arteris_kartado/daily_execution_AAAAMMDD.log"
    echo

    if [ -n "$ADOBE_CRON_ENTRY" ]; then
        echo "  📅 Adobe"
        echo "      ├─ Intervalo: $ADOBE_DESC"
        echo "      └─ Timezone: Horário do sistema (UTC$CURRENT_OFFSET)"
        echo "  📂 Diretório: $SCRIPT_DIR"
        echo "  📝 Script: run_adobe.sh"
        echo "  📋 Log do cron: /var/log/arteris_adobe/cron.log"
        echo
    else
        echo "  📅 Adobe: ❌ Desabilitado (CRON_ADOBE_INTERVAL=0 no .env)"
        echo
    fi

    echo "  🌎 Sistema: $CURRENT_TZ (UTC$CURRENT_OFFSET)"
    echo "  🕐 Ajuste aplicado: $HOUR_ADJUSTMENT horas para compensar diferença de timezone"
    echo "  ⚙️  Configuração: Carregada de $ENV_FILE"
    echo
    print_info "Para visualizar o crontab:"
    echo "  crontab -l"
    echo
    print_info "Para monitorar os logs:"
    echo "  tail -f /var/log/arteris_kartado/cron.log"
    echo "  tail -f /var/log/arteris_adobe/cron.log"
    echo
    print_info "Para testar manualmente:"
    echo "  cd $SCRIPT_DIR && ./run_daily.sh"
    echo "  cd $SCRIPT_DIR && ./run_adobe.sh"
    echo

    # Countdown se modo de teste
    if [ "$TEST_MODE" = true ]; then
        print_info "🕐 INICIANDO COUNTDOWN PARA EXECUÇÃO SEQUENCIAL"
        echo

        # Calcular segundos até a primeira execução (run_daily.sh)
        CURRENT_TIME=$(date "+%s")
        NEXT_TIME=$(date -d "$HOUR1:$MIN1:00" "+%s" 2>/dev/null || date -v${HOUR1}H -v${MIN1}M -v0S "+%s")
        SECONDS_LEFT=$((NEXT_TIME - CURRENT_TIME))

        # Se o tempo já passou, adicionar 60 segundos
        if [ $SECONDS_LEFT -lt 0 ]; then
            SECONDS_LEFT=$((SECONDS_LEFT + 60))
        fi

        print_info "⏰ Primeira execução (Tarefas Diárias) em $SECONDS_LEFT segundos"
        print_info "⏰ Segunda execução (Adobe) em aproximadamente $((SECONDS_LEFT + 60)) segundos"
        echo
        print_info "📊 Monitore os logs em OUTRA JANELA do terminal:"
        echo "  tail -f /var/log/arteris_kartado/cron.log"
        echo "  tail -f /var/log/arteris_adobe/cron.log"
        echo

        # Countdown visual para primeira execução
        for ((i=SECONDS_LEFT; i>0; i--)); do
            MIN=$((i/60))
            SEC=$((i%60))
            printf "\r⏳ Tempo para execução das Tarefas Diárias: %02d:%02d " $MIN $SEC
            sleep 1
        done

        echo
        echo
        print_info "✅ 1/2 - Tarefas Diárias iniciadas (SAP Order→FTD→Kartado→Osiris)!"
        print_info "⏰ Aguardando 1 minuto para Adobe..."

        # Countdown para segunda execução
        for ((i=60; i>0; i--)); do
            printf "\r⏳ Próxima execução (Adobe): %02d segundos " $i
            sleep 1
        done

        echo
        echo
        print_info "✅ 2/2 - Adobe iniciado!"
        echo

        # ==========================================
        # VALIDAÇÃO AUTOMÁTICA DOS LOGS
        # ==========================================
        print_info "🔍 VALIDANDO EXECUÇÃO DOS CRON JOBS..."
        echo

        # Aguardar mais 30 segundos para garantir que os logs foram escritos
        print_info "Aguardando 30 segundos para os scripts iniciarem..."
        sleep 30

        echo
        print_info "📋 Verificando logs de execução:"
        echo

        # Verificar log do run_daily.sh
        DAILY_LOG="/var/log/arteris_kartado/cron.log"
        DAILY_SUCCESS=false

        if [ -f "$DAILY_LOG" ]; then
            # Verificar se houve execução recente (últimos 5 minutos)
            RECENT_DAILY=$(find "$DAILY_LOG" -mmin -5 2>/dev/null)
            if [ -n "$RECENT_DAILY" ]; then
                DAILY_LINES=$(tail -20 "$DAILY_LOG" 2>/dev/null)
                if echo "$DAILY_LINES" | grep -q "INICIANDO EXECUÇÃO DIÁRIA\|INICIALIZANDO\|SAP ORDER"; then
                    print_info "✅ run_daily.sh: EXECUTADO"
                    DAILY_SUCCESS=true
                    echo "   Últimas linhas do log:"
                    tail -5 "$DAILY_LOG" | sed 's/^/   /'
                else
                    print_warning "⚠️  run_daily.sh: Log encontrado mas sem evidência de execução"
                fi
            else
                print_warning "⚠️  run_daily.sh: Log não foi atualizado recentemente"
            fi
        else
            print_error "❌ run_daily.sh: Log não encontrado em $DAILY_LOG"
        fi

        echo

        # Verificar log do run_adobe.sh
        ADOBE_LOG="/var/log/arteris_adobe/cron.log"
        ADOBE_SUCCESS=false

        if [ -f "$ADOBE_LOG" ]; then
            # Verificar se houve execução recente (últimos 5 minutos)
            RECENT_ADOBE=$(find "$ADOBE_LOG" -mmin -5 2>/dev/null)
            if [ -n "$RECENT_ADOBE" ]; then
                ADOBE_LINES=$(tail -20 "$ADOBE_LOG" 2>/dev/null)
                if echo "$ADOBE_LINES" | grep -q "INICIALIZANDO ADOBE\|Adobe"; then
                    print_info "✅ run_adobe.sh: EXECUTADO"
                    ADOBE_SUCCESS=true
                    echo "   Últimas linhas do log:"
                    tail -5 "$ADOBE_LOG" | sed 's/^/   /'
                else
                    print_warning "⚠️  run_adobe.sh: Log encontrado mas sem evidência de execução"
                fi
            else
                print_warning "⚠️  run_adobe.sh: Log não foi atualizado recentemente"
            fi
        else
            print_error "❌ run_adobe.sh: Log não encontrado em $ADOBE_LOG"
        fi

        echo
        echo "========================================"
        print_info "RESULTADO DA VALIDAÇÃO"
        echo "========================================"

        if [ "$DAILY_SUCCESS" = true ] && [ "$ADOBE_SUCCESS" = true ]; then
            print_info "🎉 SUCESSO! Todos os cron jobs foram executados corretamente!"
        elif [ "$DAILY_SUCCESS" = true ] || [ "$ADOBE_SUCCESS" = true ]; then
            print_warning "⚠️  PARCIAL: Apenas alguns jobs foram executados."
            print_warning "   Verifique os logs acima para mais detalhes."
        else
            print_error "❌ FALHA: Nenhum job foi executado."
            print_error "   Possíveis causas:"
            echo "   - Cron daemon não está rodando (serviço cron/crond)"
            echo "   - Permissões incorretas nos scripts"
            echo "   - Erro nos scripts de execução"
        fi

        echo
        print_info "Para verificar se o cron está rodando:"
        echo "  sudo systemctl status cron     # Debian/Ubuntu"
        echo "  sudo systemctl status crond    # RedHat/CentOS"
        echo
        print_info "Para ver logs completos:"
        echo "  tail -100 /var/log/arteris_kartado/cron.log"
        echo "  tail -100 /var/log/arteris_adobe/cron.log"
        echo
        print_info "⚠️  LEMBRE-SE: Este é um teste. Execute './remove_cron.sh' e depois './setup_cron.sh' sem --test para configuração normal."
    fi

else
    print_error "❌ Falha ao configurar cron jobs"
    exit 1
fi

print_info "=== CONFIGURAÇÃO CONCLUÍDA ==="