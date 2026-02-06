# Multi-stage build para otimizar tamanho da imagem
FROM python:3.14.3-slim AS builder

# Definir diretório de trabalho
WORKDIR /app

# Instalar dependências de sistema necessárias
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copiar arquivos de requisitos
COPY requirements.txt .

# Instalar dependências Python globalmente
RUN pip install --no-cache-dir -r requirements.txt

# Stage final - imagem mínima
FROM python:3.14.3-slim

# Instalar cron e gosu
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Criar usuário não-root para segurança
RUN groupadd -r appuser && useradd -r -g appuser -m appuser

# Definir diretório de trabalho
ENV APP_HOME=/app
WORKDIR ${APP_HOME}

# Garantir permissões do diretório de trabalho
RUN chown -R appuser:appuser ${APP_HOME} && \
    chmod -R 755 ${APP_HOME}

# Copiar dependências Python do stage builder (globalmente)
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copiar código da aplicação
COPY --chown=appuser:appuser . .

# Criar diretórios necessários com permissões completas
RUN mkdir -p logs data/temp engine_entities/temp ssl-certs && \
    chown -R appuser:appuser logs data engine_entities ssl-certs && \
    chmod -R 755 logs data engine_entities ssl-certs

# Copiar scripts
COPY --chown=appuser:appuser docker-entrypoint.sh /usr/local/bin/
COPY --chown=appuser:appuser run_h_engine.sh /usr/local/bin/run_h_engine.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh /usr/local/bin/run_h_engine.sh

# Expor porta da API
EXPOSE 8084

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8084/', timeout=5)" || exit 1

# Entrypoint (não mudar para appuser aqui, o entrypoint gerencia isso)
ENTRYPOINT ["docker-entrypoint.sh"]

# Comando padrão: iniciar API
CMD ["api"]
