# Usa uma imagem Python
FROM python:3.11-slim

# Instala ffmpeg e dependências
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Cria pasta de trabalho
WORKDIR /app

# Copia requirements e instala dependências do Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código
COPY . .

# Expõe a porta
EXPOSE 5000

# Comando para iniciar o servidor Flask
CMD ["python", "server.py"]
