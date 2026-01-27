#!/bin/bash

# Script para remover cron job do arteris_kartado
# Autor: Script de remoção do cron para arteris_kartado

echo "=== REMOVENDO CRON JOB ==="

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

# Verificar se existem entradas do cron
DAILY_EXISTS=$(crontab -l 2>/dev/null | grep -q "run_daily.sh" && echo "yes" || echo "no")
ADOBE_EXISTS=$(crontab -l 2>/dev/null | grep -q "run_adobe.sh" && echo "yes" || echo "no")

if [ "$DAILY_EXISTS" = "yes" ] || [ "$ADOBE_EXISTS" = "yes" ]; then
    print_warning "Encontradas entradas do cron:"

    # Mostrar entradas atuais
    print_info "Entradas atuais:"
    if [ "$DAILY_EXISTS" = "yes" ]; then
        echo "  Tarefas Diárias (SAP Order→FTD→Kartado→Osiris):"
        crontab -l 2>/dev/null | grep "run_daily.sh" | sed 's/^/    /'
    fi
    if [ "$ADOBE_EXISTS" = "yes" ]; then
        echo "  Adobe:"
        crontab -l 2>/dev/null | grep "run_adobe.sh" | sed 's/^/    /'
    fi
    echo
    
    # Confirmar remoção
    read -p "Deseja remover estas entradas do cron? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Fazer backup
        print_info "Fazendo backup do crontab atual..."
        crontab -l > /tmp/crontab_backup_removal_$(date +%Y%m%d_%H%M%S) 2>/dev/null
        
        # Remover entradas
        print_info "Removendo entradas do cron..."
        NEW_CRONTAB=$(crontab -l 2>/dev/null)

        # Remover entradas atuais
        if [ "$DAILY_EXISTS" = "yes" ]; then
            NEW_CRONTAB=$(echo "$NEW_CRONTAB" | grep -v "run_daily.sh")
        fi
        if [ "$ADOBE_EXISTS" = "yes" ]; then
            NEW_CRONTAB=$(echo "$NEW_CRONTAB" | grep -v "run_adobe.sh")
        fi

        echo "$NEW_CRONTAB" | crontab -

        # Verificar se foram removidas
        DAILY_REMOVED=$(crontab -l 2>/dev/null | grep -q "run_daily.sh" && echo "no" || echo "yes")
        ADOBE_REMOVED=$(crontab -l 2>/dev/null | grep -q "run_adobe.sh" && echo "no" || echo "yes")

        if ([ "$DAILY_EXISTS" = "no" ] || [ "$DAILY_REMOVED" = "yes" ]) &&
           ([ "$ADOBE_EXISTS" = "no" ] || [ "$ADOBE_REMOVED" = "yes" ]); then
            print_info "✅ Entradas do cron removidas com sucesso!"
        else
            print_error "❌ Falha ao remover algumas entradas do cron"
            if [ "$DAILY_EXISTS" = "yes" ] && [ "$DAILY_REMOVED" = "no" ]; then
                print_error "  - Falha ao remover entrada das Tarefas Diárias"
            fi
            if [ "$ADOBE_EXISTS" = "yes" ] && [ "$ADOBE_REMOVED" = "no" ]; then
                print_error "  - Falha ao remover entrada do Adobe"
            fi
            exit 1
        fi
    else
        print_info "Operação cancelada"
        exit 0
    fi
else
    print_info "Nenhuma entrada do cron encontrada"
fi

print_info "=== REMOÇÃO CONCLUÍDA ==="