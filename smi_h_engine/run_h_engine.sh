#!/bin/bash

# Script para executar engine_processor_v2.py com ambiente virtual
# Autor: Script automatizado para execução do projeto msi_h_engine
#
# Uso: ./run_h_engine.sh [measurement]
#
# Exemplos:
#   ./run_h_engine.sh                    # Executa para todos os measurements
#   ./run_h_engine.sh BM-CW33039-003     # Executa apenas para o measurement específico

set -e  # Para o script se houver erro

echo "=== INICIALIZANDO ENGINE_EXEC.PY ==="

set -e

# Configurar PATH para encontrar pacotes Python do appuser
export PATH="/home/appuser/.local/bin:$PATH"
export PYTHONPATH="/home/appuser/.local/lib/python3.12/site-packages:$PYTHONPATH"

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

# Verificar se engine_exec.py existe
if [ ! -f "engine_exec.py" ]; then
    print_error "Arquivo engine_exec.py não encontrado"
    exit 1
fi

# Verificar se arquivo .env existe
if [ ! -f ".env" ]; then
    print_warning "Arquivo .env não encontrado"
    print_warning "Certifique-se de configurar as seguintes variáveis de ambiente:"
    print_warning "- Configurações da API e banco de dados necessárias"
    echo ""
    read -p "Deseja continuar mesmo sem o arquivo .env? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Execução cancelada"
        exit 0
    fi
fi


print_info "Iniciando execução do engine_exec.py..."
echo "=== EXECUÇÃO DO H ENGINE ==="

# Executar engine_exec.py
if [ "$1" != "" ]; then
    print_info "Executando com measurement específico: $1"
    python engine_exec.py "$1"
else
    print_info "Executando para todos os measurements"
    python engine_exec.py
fi

# Status da execução
if [ $? -eq 0 ]; then
    print_info "engine_exec.py executado com sucesso!"
else
    print_error "Erro na execução do engine_exec.py"
    exit 1
fi

print_info "=== CONCLUÍDO ==="