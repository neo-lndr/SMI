#!/bin/bash

# Script para executar saporder.py com ambiente virtual
# Autor: Script automatizado para execução do projeto sap orders

set -e  # Para o script se houver erro

# Sistema de lock para evitar execuções paralelas
LOCK_FILE="/tmp/arteris_saporder.lock"
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

echo "=== INICIALIZANDO SAPORDER.PY ==="

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

# Verificar e instalar python3-venv se necessário (Ubuntu/Debian)
if command -v apt &> /dev/null; then
    print_info "Verificando dependências do sistema..."
    
    # Verificar se python3-venv está instalado
    if ! dpkg -l | grep -q python3.*-venv; then
        print_warning "python3-venv não encontrado. Instalando..."
        if [ "$EUID" -eq 0 ]; then
            apt update && apt install -y python3-venv
        else
            print_info "Tentando instalar python3-venv com sudo..."
            sudo apt update && sudo apt install -y python3-venv
        fi
        
        if [ $? -ne 0 ]; then
            print_error "Falha ao instalar python3-venv"
            print_error "Execute manualmente: sudo apt install python3-venv"
            exit 1
        fi
        print_info "python3-venv instalado com sucesso"
    fi
fi

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

# Verificar se saporder.py existe
if [ ! -f "saporder.py" ]; then
    print_error "Arquivo saporder.py não encontrado"
    exit 1
fi

# Verificar se arquivo .env existe
if [ ! -f ".env" ]; then
    print_warning "Arquivo .env não encontrado"
    print_warning "Certifique-se de configurar as seguintes variáveis de ambiente:"
    print_warning "- ARTERIS_API_BASE_URL"
    print_warning "- ARTERIS_API_TOKEN"
    echo ""
    read -p "Deseja continuar mesmo sem o arquivo .env? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Execução cancelada"
        exit 0
    fi
fi

# Verificar se o arquivo CSV existe
CSV_PATH="/ftp/arteris/Saldo_Portal.csv"
if [ ! -f "$CSV_PATH" ]; then
    print_error "Arquivo CSV não encontrado: $CSV_PATH"
    exit 1
fi

print_info "Iniciando execução do saporder.py com arquivo: $CSV_PATH"
echo "=== EXECUÇÃO DO SAPORDER ==="

# Executar saporder.py com o path do arquivo CSV
python saporder.py "$CSV_PATH"

# Status da execução
if [ $? -eq 0 ]; then
    print_info "Saporder.py executado com sucesso!"
else
    print_error "Erro na execução do saporder.py"
    exit 1
fi

print_info "=== CONCLUÍDO ==="