FROM python:3.11-slim

# instala ffmpeg e dependências
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# define diretório de trabalho
WORKDIR /app

# copia requirements e instala
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copia o resto do projeto
COPY . .

# comando de start (Railway usa PORT automaticamente)
CMD ["gunicorn", "-b", "0.0.0.0:8000", "server:app"]
