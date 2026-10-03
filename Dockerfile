FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV OMP_NUM_THREADS=1
ENV MKL_NUM_THREADS=1
ENV FASTEMBED_CACHE_PATH=/srv/fastembed

WORKDIR /srv

RUN apt-get update \
    && apt-get install -y --no-install-recommends git git-lfs ca-certificates \
    && git lfs install --system \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements.txt

RUN pip install --no-cache-dir -r backend/requirements.txt

RUN python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/all-MiniLM-L6-v2')" \
    && ls -R /srv/fastembed | head -20

COPY backend backend
COPY evaluation evaluation

RUN git clone --no-checkout https://github.com/Al0kMishra/self-improving-rag-for-scientific-research.git /tmp/rag-data \
    && cd /tmp/rag-data \
    && git checkout main \
    && git lfs pull \
    && cp -a data /srv/data \
    && rm -rf /tmp/rag-data

WORKDIR /srv/backend

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]