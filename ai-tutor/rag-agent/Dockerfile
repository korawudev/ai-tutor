FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./

RUN pip install --no-cache-dir -e .

COPY shared/ ./shared/
COPY rag-agent/ ./rag-agent/

EXPOSE 8002

CMD ["uvicorn", "rag-agent.app.main:app", "--host", "0.0.0.0", "--port", "8002"]
