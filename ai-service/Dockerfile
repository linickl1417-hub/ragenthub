FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 RAGENTHUB_CONFIG_DIR=/config \
    HF_ENDPOINT=https://hf-mirror.com

COPY ai-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 预下载 Chroma onnx embedding 模型（build 阶段单进程下载，避免运行时 ingest/uvicorn 两进程抢文件）
RUN python -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction; ef = DefaultEmbeddingFunction(); ef(['warmup'])" || echo "pre-download skipped"

COPY ai-service/app ./app
COPY config /config
COPY examples /examples
COPY web /app/web

EXPOSE 8000

CMD ["sh", "-c", "python -m app.scripts.ingest --domain medical & uvicorn app.main:app --host 0.0.0.0 --port 8000"]