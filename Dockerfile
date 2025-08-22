FROM python:3.12-slim

# Instala dependências do sistema (ffmpeg pro yt-dlp)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Define diretório de trabalho
WORKDIR /app

# Copia requirements e instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código
COPY . .

# Render injeta a PORT automaticamente
# Gunicorn vai escutar nela
CMD ["gunicorn", "-w", "2", "-k", "gthread", "-t", "600", "-b", "0.0.0.0:${PORT}", "server:app"]
