FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/appuser/.cache/huggingface \
    NLTK_DATA=/home/appuser/.cache/nltk_data

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml .
RUN uv pip install --system .

RUN python -m spacy download en_core_web_sm && \
    python -c "import nltk; nltk.download('vader_lexicon', quiet=True, download_dir='/home/appuser/.cache/nltk_data')"

RUN python -c "from transformers import pipeline; pipeline('sentiment-analysis', model='distilbert-base-uncased-finetuned-sst-2-english')" && \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid 1000 --create-home appuser && \
    mkdir -p /home/appuser/.cache && \
    cp -r /root/.cache/huggingface /home/appuser/.cache/huggingface 2>/dev/null || true && \
    cp -r /root/.cache/nltk_data /home/appuser/.cache/nltk_data 2>/dev/null || true && \
    chown -R appuser:appuser /home/appuser/.cache

COPY app/ app/
RUN mkdir -p data

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
