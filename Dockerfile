FROM python:3.12-slim

# instalar ffmpeg para o yt-dlp funcionar
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# diretório da app
WORKDIR /app

# instalar dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copiar código
COPY . .

# Render injeta a variável PORT automaticamente
# usar "sh -c" para expandir $PORT
CMD ["sh", "-c", "gunicorn -w 2 -k gthread -t 600 -b 0.0.0.0:$PORT server:app"]
