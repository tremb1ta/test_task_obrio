.PHONY: install dev lint format test run run-dashboard docker-up docker-down clean download-models

install:
	uv sync
	uv run python -m spacy download en_core_web_sm
	uv run python -c "import nltk; nltk.download('vader_lexicon', quiet=True)"

dev: install
	uv run pre-commit install

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

test:
	uv run pytest tests/ -v --tb=short

test-cov:
	uv run pytest tests/ -v --tb=short --cov=app --cov-report=term-missing

run:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

run-dashboard:
	uv run streamlit run dashboard/app.py --server.port 8501 --server.address 0.0.0.0

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

download-models:
	uv run python -m spacy download en_core_web_sm
	uv run python -c "import nltk; nltk.download('vader_lexicon', quiet=True)"
	uv run python -c "from transformers import pipeline; pipeline('sentiment-analysis', model='distilbert-base-uncased-finetuned-sst-2-english')"
	uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov dist build *.egg-info

pre-commit:
	uv run pre-commit run -a
