FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render injeta $PORT automaticamente
CMD ["gunicorn", "-w", "2", "-k", "gthread", "-t", "600", "-b", "0.0.0.0:${PORT}", "server:app"]
