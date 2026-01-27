#!/bin/bash

# Script para fazer backup do site msi.arteris.com.br
SITE_NAME="msi.arteris.com.br"
RETENTION_DAYS=${1:-7}
BACKUP_DIR="/home/azureuser/frappe_docker/gitops/backup"
CONTAINER_NAME="msi-backend-1"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "=== Frappe Backup Script - MSI Arteris ==="
echo "🕐 Timestamp: $TIMESTAMP"
echo "🌐 Site: $SITE_NAME"
echo "🗂️  Container: $CONTAINER_NAME"
echo "📅 Retenção: $RETENTION_DAYS dias"
echo

# Verificar se o container está rodando
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "❌ Container $CONTAINER_NAME não está rodando!"
    echo "Execute: docker-compose up -d"
    exit 1
fi

# Verificar espaço em disco disponível
AVAILABLE_SPACE=$(df ~/frappe_docker/gitops/backup | awk 'NR==2 {print $4}')
if [ "$AVAILABLE_SPACE" -lt 1048576 ]; then  # Menos que 1GB
    echo "⚠️  Aviso: Pouco espaço em disco disponível ($(($AVAILABLE_SPACE/1024))MB)"
    echo "Considere limpar backups antigos ou aumentar o espaço"
    echo
fi

echo "🚀 Iniciando backup..."
echo "⏳ Este processo pode demorar alguns minutos..."
echo

# Verificar se o site msi.arteris.com.br existe
echo "🔍 Verificando site $SITE_NAME..."
if ! docker exec -w /home/frappe/frappe-bench "$CONTAINER_NAME" bench --site "$SITE_NAME" version >/dev/null 2>&1; then
    echo "❌ Site '$SITE_NAME' não encontrado!"
    echo "Sites disponíveis:"
    docker exec -w /home/frappe/frappe-bench "$CONTAINER_NAME" ls sites/ | grep -v "^apps.txt$" | grep -v "^assets$" | grep -v "^common_site_config.json$"
    exit 1
fi

echo "✅ Site $SITE_NAME encontrado!"
echo

# Fazer backup do site msi.arteris.com.br
echo "📦 Iniciando backup do site: $SITE_NAME"

# Executar backup
if docker exec -w /home/frappe/frappe-bench "$CONTAINER_NAME" \
    bench --site "$SITE_NAME" backup --with-files --backup-path /tmp/backup; then
    
    echo "✅ Backup do $SITE_NAME concluído com sucesso!"
    BACKUP_SUCCESS=1
    BACKUP_FAILED=0
else
    echo "❌ Erro no backup do $SITE_NAME!"
    BACKUP_SUCCESS=0
    BACKUP_FAILED=1
fi
echo

# Verificar arquivos criados
echo "📋 Verificando arquivos de backup criados..."
cd /home/azureuser/frappe_docker/gitops/backup/ || exit 1

LATEST_FILES=$(find . -name "*$(date +%Y%m%d)*" -type f 2>/dev/null | wc -l)
if [ "$LATEST_FILES" -gt 0 ]; then
    echo "✅ $LATEST_FILES arquivos de backup criados hoje:"
    find . -name "*$(date +%Y%m%d)*" -type f -exec ls -lh {} \; | awk '{print "   📄 " $9 " (" $5 ")"}'
else
    echo "⚠️  Nenhum arquivo de backup encontrado para hoje!"
fi
echo

# Limpeza de arquivos antigos
echo "🧹 Removendo backups com mais de $RETENTION_DAYS dias..."

OLD_FILES_COUNT=$(find . -type f -mtime +$RETENTION_DAYS 2>/dev/null | wc -l)

if [ "$OLD_FILES_COUNT" -gt 0 ]; then
    echo "🗑️  Encontrados $OLD_FILES_COUNT arquivos antigos para remoção:"
    find . -type f -mtime +$RETENTION_DAYS -exec ls -lh {} \; | awk '{print "   🗑️  " $9 " (" $5 ")"}'
    
    # Confirmar antes de deletar se for interativo
    if [ -t 0 ]; then  # Verifica se está rodando em terminal interativo
        echo
        read -p "Confirma a remoção destes arquivos? [y/N]: " -r
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            find . -type f -mtime +$RETENTION_DAYS -delete
            echo "✅ Arquivos antigos removidos!"
        else
            echo "⏸️  Limpeza cancelada pelo usuário"
        fi
    else
        # Se não for interativo, remove automaticamente
        find . -type f -mtime +$RETENTION_DAYS -delete
        echo "✅ $OLD_FILES_COUNT arquivos antigos removidos!"
    fi
else
    echo "✨ Nenhum arquivo antigo encontrado para remoção"
fi

echo

# Calcular espaço total usado pelos backups
TOTAL_SIZE=$(du -sh . 2>/dev/null | awk '{print $1}')
TOTAL_FILES=$(find . -type f | wc -l)

# Resumo final
echo "=== Resumo do Backup - MSI Arteris ==="
if [ "$BACKUP_SUCCESS" -eq 1 ]; then
    echo "✅ Backup do $SITE_NAME: Sucesso"
else
    echo "❌ Backup do $SITE_NAME: Falhou"
fi
echo "📊 Total de arquivos: $TOTAL_FILES"
echo "💾 Espaço total usado: $TOTAL_SIZE"
echo "📁 Localização: ~/frappe_docker/gitops/backup/"
echo "🕐 Concluído em: $(date)"

# Verificar saúde geral
if [ "$BACKUP_FAILED" -gt 0 ]; then
    echo
    echo "⚠️  Backup falhou! Verifique os logs:"
    echo "   docker-compose logs backend"
    exit 1
else
    echo
    echo "🎉 Backup do site $SITE_NAME concluído com sucesso!"
fi

echo "=== Backup Finalizado ==="