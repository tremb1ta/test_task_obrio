from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

import nltk
import spacy
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from sentence_transformers import SentenceTransformer
from transformers import pipeline as hf_pipeline

from app.api.middleware import RequestLoggingMiddleware
from app.api.routes.competitive import router as competitive_router
from app.api.routes.health import router as health_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.rag import router as rag_router
from app.api.routes.reviews import router as reviews_router
from app.config import settings
from app.models.database import close_db, init_db
from app.services.aspects import AspectService
from app.services.competitive import CompetitiveService
from app.services.insights import InsightsService
from app.services.keywords import KeywordService
from app.services.metrics import MetricsService
from app.services.preprocessing import PreprocessingService
from app.services.rag import RAGService
from app.services.scraper import ReviewScraper
from app.services.sentiment import SentimentService
from app.utils.logger import setup_logging


@dataclass
class ServiceRegistry:
    scraper: ReviewScraper = field(default_factory=ReviewScraper)
    preprocessing: PreprocessingService | None = None
    sentiment: SentimentService | None = None
    keywords: KeywordService | None = None
    metrics: MetricsService = field(default_factory=MetricsService)
    aspects: AspectService | None = None
    rag: RAGService | None = None
    competitive: CompetitiveService | None = None
    insights: InsightsService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()

    Path("data").mkdir(exist_ok=True)
    await init_db(settings.database_url)

    nltk.download("vader_lexicon", quiet=True)
    nlp = spacy.load(settings.spacy_model)
    vader = SentimentIntensityAnalyzer()
    transformer = hf_pipeline(
        "sentiment-analysis",  # type: ignore[call-overload]
        model=settings.sentiment_model,
        device=-1,
        truncation=True,
    )
    embedding_model = SentenceTransformer(settings.embedding_model)

    scraper = ReviewScraper()
    preprocessing = PreprocessingService(nlp)
    sentiment = SentimentService(vader, transformer)
    keywords = KeywordService(embedding_model)
    aspects = AspectService(nlp, vader)
    rag = RAGService(embedding_model, settings)
    insights = InsightsService(settings)
    competitive = CompetitiveService(scraper, preprocessing, sentiment, keywords, aspects)

    app.state.services = ServiceRegistry(
        scraper=scraper,
        preprocessing=preprocessing,
        sentiment=sentiment,
        keywords=keywords,
        metrics=MetricsService(),
        aspects=aspects,
        rag=rag,
        competitive=competitive,
        insights=insights,
    )
    app.state.models_loaded = {
        "spacy": True,
        "vader": True,
        "distilbert": True,
        "sentence_transformer": True,
    }

    logger.info("All models loaded, API ready")
    yield

    await close_db()


def create_app() -> FastAPI:
    application = FastAPI(
        title="Apple Store Review Analysis API",
        version="0.1.0",
        description="ML-powered review analysis with sentiment, aspects, and RAG",
        lifespan=lifespan,
    )

    application.add_middleware(RequestLoggingMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health_router)
    application.include_router(reviews_router, prefix=settings.api_prefix)
    application.include_router(metrics_router, prefix=settings.api_prefix)
    application.include_router(rag_router, prefix=settings.api_prefix)
    application.include_router(competitive_router, prefix=settings.api_prefix)

    return application


app = create_app()
