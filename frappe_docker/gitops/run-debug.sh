#!/bin/bash
#
## Script de deploy para SMI
## Executa restart do docker compose e comandos bench no container
#

# Função de cleanup
cleanup() {
    echo "🛑 Interrompido pelo usuário"
    docker compose --project-name smi -f docker-compose.msi.ssl.v1.yml down
    exit 0
}

# Captura Ctrl+C
trap cleanup SIGINT SIGTERM

echo "📥 Atualizando código da aplicação..."
docker exec smi-backend-1 bash -c "cd /home/frappe/frappe-bench/apps/arteris_app && git pull" 2>/dev/null || true

set -e

echo "🔄 Parando containers do projeto SMI..."
docker compose --project-name smi -f docker-compose.msi.ssl.v1.yml down

echo "🚀 Iniciando containers do projeto SMI..."
docker compose --project-name smi -f docker-compose.msi.ssl.v1.yml up -d

echo "⏳ Aguardando containers iniciarem..."
sleep 10

echo "🔧 Executando comandos bench no container smi-backend-1..."

echo "  📦 Executando migrate..."
docker exec smi-backend-1 bench --site smi.arteris.com.br migrate

echo "  🔨 Executando build..."
docker exec smi-backend-1 bench --site smi.arteris.com.br build

echo "  🧹 Limpando cache..."
docker exec smi-backend-1 bench --site smi.arteris.com.br clear-cache

echo "  🌐 Limpando cache do website..."
docker exec smi-backend-1 bench --site smi.arteris.com.br clear-website-cache

echo "✅ Deploy concluído com sucesso!"
echo "📋 Mostrando logs dos containers (Ctrl+C para parar)..."

# Mantém os logs visíveis
docker compose --project-name smi -f docker-compose.msi.ssl.v1.yml logs -f