FROM python:3.12-slim

# Evita que o Python gere arquivos .pyc e obriga o log a sair no console
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependências de sistema necessárias para o psycopg2 e criptografia
RUN apt-get update \
    && apt-get install -y libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Copia apenas o requirements primeiro (para cache do Docker)
COPY requirements.txt /app/

# Instala as dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia o resto do código da aplicação
COPY . /app/

# O CMD será sobrescrito pelo docker-compose.yml dependendo de qual serviço é (API ou Frontend)
