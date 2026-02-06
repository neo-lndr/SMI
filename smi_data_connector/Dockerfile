# Multi-stage build para otimizar tamanho da imagem
FROM python:3.14.3-slim AS builder

# Definir diretório de trabalho
WORKDIR /app

# Instalar dependências de sistema necessárias para compilação
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copiar arquivos de requisitos
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Stage final - imagem mínima
FROM python:3.14.3-slim

# Instalar cron e gosu
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Criar usuário não-root para segurança
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Definir diretório de trabalho
ENV APP_HOME=/app
WORKDIR ${APP_HOME}

# Copiar dependências Python do stage builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copiar código da aplicação com permissões de escrita
COPY --chown=appuser:appuser . .
RUN chmod -R 755 ${APP_HOME}

# Criar diretórios necessários com permissões apropriadas
RUN mkdir -p logs data/temp ssl-certs && \
    chown -R appuser:appuser logs data ssl-certs && \
    chmod -R 755 logs data ssl-certs

# Copiar e configurar scripts
COPY --chown=appuser:appuser docker-entrypoint.sh /usr/local/bin/
COPY --chown=appuser:appuser run_daily_tasks.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh /usr/local/bin/run_daily_tasks.sh

# Expor porta da API
EXPOSE 8085

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8085/', timeout=5)" || exit 1

# Entrypoint (não mudar para appuser aqui, o entrypoint gerencia isso)
ENTRYPOINT ["docker-entrypoint.sh"]

# Comando padrão: iniciar API
CMD ["api"]
