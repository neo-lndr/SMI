#!/bin/bash

# Script para sincronizar código Python para pasta src (bind mount development)
# Copia apenas arquivos Python e pastas necessárias, ignorando Git e outros metadados

echo "Sincronizando código para ./src..."

# Criar pasta src se não existir
mkdir -p src

# Copiar arquivos Python da raiz
rsync -av --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.pytest_cache' \
    --exclude='logs' \
    --exclude='data' \
    --exclude='src' \
    --include='*.py' \
    --include='athena/***' \
    --exclude='*' \
    ./ src/

echo "Sincronização concluída!"
echo "Arquivos copiados para ./src/"
