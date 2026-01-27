#!/bin/bash

# Script para sincronizar código Python para pasta src (bind mount development)
# Copia apenas arquivos Python e pastas necessárias, ignorando Git e outros metadados

echo "Sincronizando código para ./src..."

# Criar pasta src se não existir
mkdir -p src

# Copiar arquivos Python e pastas necessárias
rsync -av --delete \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='.pytest_cache' \
    --exclude='logs' \
    --exclude='data' \
    --exclude='src' \
    --exclude='.vscode' \
    --exclude='.idea' \
    --exclude='.DS_Store' \
    --exclude='*.md' \
    --exclude='Dockerfile' \
    --exclude='docker-compose.yml' \
    --exclude='.dockerignore' \
    --exclude='*.sh' \
    --exclude='.env' \
    --exclude='venv' \
    --exclude='.venv' \
    --include='*.py' \
    --include='engine_entities/***' \
    --include='filters/***' \
    --include='config/***' \
    --include='requirements.txt' \
    --exclude='*' \
    ./ src/

echo "Sincronização concluída!"
echo "Arquivos copiados para ./src/"
