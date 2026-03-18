FROM python:3.11-slim

LABEL org.opencontainers.image.title="A.R.I.E. Resume Intelligence Engine"
LABEL org.opencontainers.image.version="3.1.0"
LABEL org.opencontainers.image.description="Deterministic resume parser — no LLM required"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpoppler-cpp-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data/output

RUN useradd -m -u 1000 aria && chown -R aria:aria /app
USER aria

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
