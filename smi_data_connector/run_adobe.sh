#!/bin/bash

# Script para executar adobe.py
# Autor: Script automatizado para verificação de assinaturas Adobe

set -e  # Para o script se houver erro

# Sistema de lock para evitar execuções paralelas
LOCK_FILE="/tmp/arteris_adobe.lock"
LOCK_TIMEOUT=3600  # 1 hora

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

echo "=== INICIALIZANDO ADOBE.PY ==="

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

# Verificar se Python3 está instalado
if ! command -v python3 &> /dev/null; then
    print_error "Python3 não encontrado. Instale o Python3 primeiro."
    exit 1
fi

print_info "Python3 encontrado: $(python3 --version)"

# Diretório do script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

print_info "Diretório de trabalho: $SCRIPT_DIR"

# Verificar se o ambiente virtual existe e está íntegro
if [ ! -d "venv" ] || [ ! -f "venv/bin/activate" ]; then
    if [ -d "venv" ]; then
        print_warning "Ambiente virtual corrompido. Removendo..."
        rm -rf venv
    fi
    print_info "Criando ambiente virtual..."
    python3 -m venv venv
    if [ $? -eq 0 ]; then
        print_info "Ambiente virtual criado com sucesso"
    else
        print_error "Falha ao criar ambiente virtual"
        exit 1
    fi
else
    print_info "Ambiente virtual já existe"
fi

# Ativar ambiente virtual
print_info "Ativando ambiente virtual..."
source venv/bin/activate

# Verificar se requirements.txt existe
if [ ! -f "requirements.txt" ]; then
    print_error "Arquivo requirements.txt não encontrado"
    exit 1
fi

# Instalar/atualizar dependências
print_info "Verificando e instalando dependências..."
pip install --upgrade pip
pip install -r requirements.txt

# Verificar se adobe.py existe
if [ ! -f "adobe.py" ]; then
    print_error "Arquivo adobe.py não encontrado"
    exit 1
fi

# Verificar se arquivo .env existe
if [ ! -f ".env" ]; then
    print_warning "Arquivo .env não encontrado"
    print_warning "Certifique-se de configurar as seguintes variáveis de ambiente:"
    print_warning "- ARTERIS_API_BASE_URL"
    print_warning "- ARTERIS_API_TOKEN"
    echo ""
fi

print_info "Iniciando execução do adobe.py"
echo "=== EXECUÇÃO DO ADOBE ==="

# Executar adobe.py (sem parâmetros)
python adobe.py

# Status da execução
if [ $? -eq 0 ]; then
    print_info "adobe.py executado com sucesso!"
else
    print_error "Erro na execução do adobe.py"
    exit 1
fi

print_info "=== CONCLUÍDO ==="