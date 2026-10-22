FROM python:3.12-slim

# tzdata: para que "hace 14 días" y las horas se calculen en hora de Chile
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=America/Santiago \
    PYTHONUNBUFFERED=1 \
    JT_DB=/datos/ofertas.db \
    JT_HOST=0.0.0.0 \
    JT_PUERTO=8765

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Chromium sin ventana para Laborum (laborum.py), con sus librerías del sistema
RUN python -m playwright install --with-deps --only-shell chromium \
    && rm -rf /var/lib/apt/lists/*

COPY *.py ./
COPY web/ ./web/
RUN mkdir -p /datos
VOLUME ["/datos"]
EXPOSE 8765

HEALTHCHECK --interval=60s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/estado', timeout=4)"

CMD ["python", "servidor.py", "--no-abrir"]
