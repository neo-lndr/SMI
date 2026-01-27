#!/bin/bash

# Script para restaurar o backup mais recente no Frappe

SITE_NAME="msi.arteris.com.br"
BACKUP_DIR="/home/azureuser/frappe_docker/gitops/backup"
CONTAINER_NAME="msi-backend-1"

echo "=== Frappe Restore Script ==="
echo "Site: $SITE_NAME"
echo "Container: $CONTAINER_NAME"
echo

# Navegar para o diretório de backup
cd /home/azureuser/frappe_docker/gitops/backup/ || exit 1

# Verificar se existem arquivos de backup
if [ ! "$(ls -A .)" ]; then
    echo "❌ Nenhum arquivo de backup encontrado!"
    exit 1
fi

# Encontrar os arquivos mais recentes automaticamente
echo "🔍 Procurando arquivos de backup mais recentes..."

DATABASE=$(ls -t *-database.sql.gz 2>/dev/null | head -1)
PUBLIC_FILES=$(ls -t *-files.tar 2>/dev/null | head -1)
PRIVATE_FILES=$(ls -t *-private-files.tar 2>/dev/null | head -1)

# Verificar se todos os arquivos foram encontrados
if [ -z "$DATABASE" ] || [ -z "$PUBLIC_FILES" ] || [ -z "$PRIVATE_FILES" ]; then
    echo "❌ Arquivos de backup incompletos!"
    echo "Database: $DATABASE"
    echo "Public Files: $PUBLIC_FILES"
    echo "Private Files: $PRIVATE_FILES"
    exit 1
fi

echo "✅ Arquivos mais recentes encontrados:"
echo "📊 Database: $DATABASE"
echo "📁 Public Files: $PUBLIC_FILES"
echo "🔒 Private Files: $PRIVATE_FILES"
echo

# Verificar se o container está rodando
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "❌ Container $CONTAINER_NAME não está rodando!"
    echo "Execute: docker-compose up -d"
    exit 1
fi

echo "📁 Usando arquivos via bind mount (/tmp/backup)..."
echo

# Verificar se o site existe, se não, criar
echo "🔧 Verificando site $SITE_NAME..."
if ! docker exec -w /home/frappe/frappe-bench "$CONTAINER_NAME" bench --site "$SITE_NAME" version >/dev/null 2>&1; then
    echo "⚠️  Site $SITE_NAME não existe. Criando..."
    docker exec -w /home/frappe/frappe-bench "$CONTAINER_NAME" \
        bench new-site "$SITE_NAME" --admin-password admin --install-app arteris_app
fi

echo "🚀 Iniciando restore do backup..."
echo "⏳ Este processo pode demorar alguns minutos..."

# Executar restore (arquivos via bind mount)
if docker exec -w /home/frappe/frappe-bench "$CONTAINER_NAME" \
    bench --site "$SITE_NAME" restore \
        "/tmp/backup/$DATABASE" \
        --with-private-files "/tmp/backup/$PRIVATE_FILES" \
        --with-public-files "/tmp/backup/$PUBLIC_FILES" \
        --db-root-username root \
        --db-root-password BtQEprm1Re5QDjY; then
    
    echo
    echo "✅ Restore concluído com sucesso!"
    echo "🌐 Site: $SITE_NAME"
    echo "🔗 URL: https://msi.arteris.com.br (se $SITE_NAME for o site principal)"
    
    # Não há arquivos temporários para limpar (usando bind mount)
    
else
    echo
    echo "❌ Erro durante o restore!"
    echo "📋 Verifique os logs do container:"
    echo "   docker-compose logs backend"
    exit 1
fi

echo
echo "=== Restore Finalizado ==="