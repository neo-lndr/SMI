#!/bin/bash

# Script para remover execução automática do H Engine do cron

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

echo "=== REMOVENDO CRON DO H ENGINE ==="

# Diretório do script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_SCRIPT="$SCRIPT_DIR/run_h_engine.sh"

print_info "Procurando por cron jobs do H Engine..."

# Verificar se existe algum cron job configurado
if ! crontab -l 2>/dev/null | grep -q "$RUN_SCRIPT"; then
    print_warning "Nenhum cron job encontrado para o H Engine"
    print_info "Script: $RUN_SCRIPT"
    exit 0
fi

# Mostrar configuração atual
print_info "=== CONFIGURAÇÃO ATUAL DO CRON ==="
crontab -l 2>/dev/null | grep "$RUN_SCRIPT"
echo ""

# Confirmar remoção
read -p "Deseja remover esta configuração do cron? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_info "Remoção cancelada pelo usuário"
    exit 0
fi

# Remover cron job
print_info "Removendo cron job do H Engine..."
crontab -l 2>/dev/null | grep -v "$RUN_SCRIPT" | crontab -

# Verificar se foi removido
if crontab -l 2>/dev/null | grep -q "$RUN_SCRIPT"; then
    print_error "Erro ao remover cron job"
    exit 1
else
    print_info "Cron job removido com sucesso!"
fi

# Mostrar cron atual (se houver)
if crontab -l 2>/dev/null | wc -l | grep -q "^0$"; then
    print_info "Nenhum cron job configurado no momento"
else
    print_info "=== CRON JOBS RESTANTES ==="
    crontab -l 2>/dev/null
fi

print_info "=== REMOÇÃO CONCLUÍDA ==="