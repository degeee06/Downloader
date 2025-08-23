# Usa Python 3.10
FROM python:3.10-slim

# Instala dependências do sistema (ffmpeg incluso)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Define diretório de trabalho
WORKDIR /app

# Copia dependências primeiro (para cache eficiente)
COPY requirements.txt .

# Instala dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante dos arquivos do app
COPY . .

# Expõe a porta do Flask
EXPOSE 5000

# Comando para iniciar o servidor
CMD ["python", "server.py"]
