# Apple Store Review Analysis API

ML-powered REST API for collecting, analyzing, and querying Apple App Store reviews. Dual sentiment pipeline (VADER + distilBERT), aspect-based analysis, RAG Q&A, and competitive intelligence.

## Quick Start

```bash
# Install dependencies + download NLP models
make install

# Copy .env.example to .env and set credentials
cp .env.example .env

# Run API (port 8000)
make run

# Run dashboard (port 8501)
make run-dashboard
```

Or with Docker:

```bash
docker compose up --build
```

## Authentication

All API endpoints (except `/health`) require HTTP Basic Auth. The dashboard has its own login page using the same credentials.

Set credentials via environment variables (required, no defaults):
- `BASIC_AUTH_USER`
- `BASIC_AUTH_PASS`

## Models & Storage

| Model | Used By | Purpose |
|-------|---------|---------|
| spaCy (en_core_web_sm) | Preprocessing, Aspects | Text cleaning, lemmatization, dependency-based aspect extraction |
| VADER | Sentiment | Rule-based sentiment scoring |
| distilBERT | Sentiment | Transformer-based sentiment classification |
| SentenceTransformer (all-MiniLM-L6-v2) | Keywords, RAG | KeyBERT keyword extraction, ChromaDB vector embeddings |
| OpenRouter LLM | RAG | Natural language answer generation over retrieved reviews |
| SQLite (aiosqlite) | All services | Async review storage with upsert deduplication |
| ChromaDB | RAG | Persistent vector store for semantic search over reviews |

**Key design choices:**
- Dual sentiment pipeline: VADER (rule-based, fast) + distilBERT (transformer, accurate) with weighted combination (0.4/0.6) for robust scoring
- Single `SentenceTransformer` instance shared across KeyBERT and ChromaDB to minimize memory footprint
- Single `spaCy` instance shared between preprocessing and aspect extraction
- All models preloaded at startup via FastAPI lifespan handler — no cold-start latency on first request
- `ServiceRegistry` dataclass on `app.state` for clean dependency injection across all routes
- Fully async I/O: async SQLAlchemy sessions, async HTTP client for scraping, `asyncio.to_thread` for CPU-bound NLP operations
- RAG gracefully degrades to retrieval-only mode when no OpenRouter API key is configured

## API Endpoints

### Core

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/reviews/collect` | Collect reviews from Apple RSS Feed (sort: most_recent/most_helpful) |
| GET | `/api/v1/reviews/{app_id}` | Retrieve stored reviews |
| GET | `/api/v1/reviews/{app_id}/download?format=csv` | Export as CSV or JSON |
| GET | `/api/v1/metrics/{app_id}` | Rating stats + structured insights |
| GET | `/api/v1/sentiment/{app_id}` | Dual sentiment analysis (VADER + transformer) |

### Differentiators

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/aspects/{app_id}` | Aspect-based sentiment breakdown |
| POST | `/api/v1/rag/query` | Natural language Q&A over reviews |
| POST | `/api/v1/rag/suggest-questions` | Auto-suggest relevant questions |
| POST | `/api/v1/competitive/compare` | Cross-app comparison |
| GET | `/api/v1/insights/{app_id}` | Structured insights |
| POST | `/api/v1/insights/{app_id}/narrative` | LLM-generated actionable recommendations |

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/docs` | Swagger UI |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/reviews.db` | Database connection string |
| `OPENROUTER_API_KEY` | _(empty)_ | OpenRouter API key for RAG generation |
| `OPENROUTER_MODEL` | `moonshotai/kimi-k2.5` | LLM model for RAG answers |
| `CHROMA_PERSIST_DIR` | `./data/chroma` | ChromaDB storage directory |
| `BASIC_AUTH_USER` | _(required)_ | Username for API and dashboard auth |
| `BASIC_AUTH_PASS` | _(required)_ | Password for API and dashboard auth |
| `LOG_LEVEL` | `info` | Logging level |

Copy `.env.example` to `.env` and fill in your values.

## Development

```bash
# Install with dev dependencies
make install

# Run linter + formatter
make lint
make format

# Run tests
make test

# Run tests with coverage
make test-cov

# Run pre-commit hooks
make pre-commit
```

## Project Structure

```
app/
├── main.py              # FastAPI entry point, lifespan, service registry
├── config.py            # Pydantic BaseSettings
├── api/
│   ├── dependencies.py  # DB session, service injection, Basic Auth
│   ├── middleware.py     # Request logging middleware
│   └── routes/          # health, reviews, metrics, rag, competitive
├── constants/
│   └── app_groups.py    # Predefined app groups for dashboard
├── models/
│   ├── database.py      # SQLAlchemy async models
│   └── schemas.py       # Pydantic request/response schemas
├── services/
│   ├── scraper.py       # Apple RSS Feed collector
│   ├── preprocessing.py # spaCy text cleaning + Unicode normalization
│   ├── sentiment.py     # VADER + distilBERT dual pipeline
│   ├── keywords.py      # KeyBERT extraction
│   ├── aspects.py       # spaCy dependency-based aspect extraction
│   ├── rag.py           # ChromaDB + OpenRouter RAG + question suggestions
│   ├── competitive.py   # Multi-app comparison
│   ├── insights.py      # Structured insights + LLM narrative generation
│   └── metrics.py       # Rating statistics
└── utils/
    ├── helpers.py       # CSV/JSON export utilities
    └── logger.py        # Loguru structured logging setup
dashboard/
└── app.py               # Streamlit UI with login, app selector, tabs
scripts/
└── renormalize_reviews.py  # One-off Unicode normalization migration
tests/                   # pytest test suite
```

## NLP Pipeline

1. **Collection**: Apple RSS Feed (paginated, ~50 reviews/page, configurable sort order)
2. **Preprocessing**: Unicode normalization (NFKC), URL/email removal, repeated char normalization, spaCy lemmatization
3. **Sentiment**: VADER (rule-based, 0.4 weight) + distilBERT (transformer, 0.6 weight) combined score
4. **Keywords**: KeyBERT with MMR diversity, filtered for generic phrases
5. **Aspects**: spaCy dependency parsing (ADJ→noun, VERB→dobj patterns), category mapping, per-aspect VADER scoring
6. **RAG**: ChromaDB vector retrieval + OpenRouter LLM generation (falls back to retrieval-only without API key)

## Docker

Two containers:
- **api** (port 8000): FastAPI + all NLP models + ChromaDB embedded
- **dashboard** (port 8501): Streamlit + Plotly

```bash
docker compose up --build    # Start both
docker compose down          # Stop
```

Volumes: `sqlite-data` and `chroma-data` persist between restarts.
