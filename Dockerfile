FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/srv/data/hf

WORKDIR /srv

# Install Git LFS
RUN apt-get update \
    && apt-get install -y --no-install-recommends git git-lfs ca-certificates \
    && git lfs install --system \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements.txt

RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu torch \
    && pip install --no-cache-dir -r backend/requirements.txt

COPY backend backend
COPY evaluation evaluation

# Copy repository data.
# Git LFS files may arrive as pointer files during the Render checkout.
COPY data data

WORKDIR /srv/backend

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]