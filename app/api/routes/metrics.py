import asyncio

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session, get_services
from app.models.database import Review
from app.models.schemas import (
    AspectsResponse,
    InsightsResponse,
    MetricsResponse,
    NarrativeResponse,
    SentimentLabel,
    SentimentResponse,
    SentimentResult,
    SentimentSummary,
)

router = APIRouter(tags=["metrics"])


async def _get_reviews(app_id: str, session: AsyncSession) -> list[Review]:
    stmt = select(Review).where(Review.app_id == app_id)
    result = await session.execute(stmt)
    reviews = result.scalars().all()
    if not reviews:
        raise HTTPException(status_code=404, detail=f"No reviews found for app_id={app_id}")
    return list(reviews)


@router.get("/metrics/{app_id}", response_model=MetricsResponse)
async def get_metrics(
    app_id: str,
    session: AsyncSession = Depends(get_db_session),
    services=Depends(get_services),
):
    reviews = await _get_reviews(app_id, session)
    review_dicts = [{"rating": r.rating} for r in reviews]
    result = services.metrics.calculate(review_dicts)
    return MetricsResponse(app_id=app_id, **result)


@router.get("/sentiment/{app_id}", response_model=SentimentResponse)
async def get_sentiment(
    app_id: str,
    session: AsyncSession = Depends(get_db_session),
    services=Depends(get_services),
):
    reviews = await _get_reviews(app_id, session)

    logger.info("Sentiment analysis requested for {app_id}", app_id=app_id)
    unanalyzed = [r for r in reviews if r.vader_compound is None]
    if unanalyzed:
        await services.sentiment.analyze_reviews(app_id, session)
        stmt = select(Review).where(Review.app_id == app_id)
        result = await session.execute(stmt)
        reviews = list(result.scalars().all())

    results = []
    vader_scores = []
    transformer_scores = []

    for r in reviews:
        results.append(
            SentimentResult(
                review_id=r.review_id,
                content=r.content,
                vader_compound=r.vader_compound or 0.0,
                vader_label=SentimentLabel(r.vader_label or "neutral"),
                transformer_score=r.transformer_score or 0.0,
                transformer_label=SentimentLabel(r.transformer_label or "neutral"),
            )
        )
        vader_scores.append(r.vader_compound or 0.0)
        transformer_scores.append(r.transformer_score or 0.0)

    def _summary(method: str, labels: list[str], scores: list[float]) -> SentimentSummary:
        return SentimentSummary(
            method=method,
            positive=sum(1 for label in labels if label == "positive"),
            negative=sum(1 for label in labels if label == "negative"),
            neutral=sum(1 for label in labels if label == "neutral"),
            average_score=round(sum(scores) / len(scores), 4) if scores else 0.0,
        )

    vader_labels = [r.vader_label or "neutral" for r in reviews]
    transformer_labels = [r.transformer_label or "neutral" for r in reviews]

    return SentimentResponse(
        app_id=app_id,
        total_analyzed=len(reviews),
        summaries={
            "vader": _summary("vader", vader_labels, vader_scores),
            "transformer": _summary("transformer", transformer_labels, transformer_scores),
        },
        results=results,
    )


@router.get("/aspects/{app_id}", response_model=AspectsResponse)
async def get_aspects(
    app_id: str,
    session: AsyncSession = Depends(get_db_session),
    services=Depends(get_services),
):
    reviews = await _get_reviews(app_id, session)
    review_dicts = [{"content": r.content, "rating": r.rating} for r in reviews]
    aspects = await asyncio.to_thread(services.aspects.analyze_reviews, review_dicts)
    return AspectsResponse(app_id=app_id, total_aspects=len(aspects), aspects=aspects)


@router.get("/insights/{app_id}", response_model=InsightsResponse)
async def get_insights(
    app_id: str,
    session: AsyncSession = Depends(get_db_session),
    services=Depends(get_services),
):
    reviews = await _get_reviews(app_id, session)
    logger.info("Insights generation requested for {app_id}", app_id=app_id)
    review_dicts = [
        {
            "content": r.content,
            "rating": r.rating,
            "review_id": r.review_id,
            "vader_label": r.vader_label,
            "vader_compound": r.vader_compound,
            "combined_label": r.vader_label,
        }
        for r in reviews
    ]

    metrics_result = services.metrics.calculate(review_dicts)

    texts = [r.content for r in reviews]
    sentiments = await asyncio.to_thread(services.sentiment.analyze_batch, texts)

    keywords = await asyncio.to_thread(
        services.keywords.extract_from_negative_reviews, review_dicts
    )
    aspects = await asyncio.to_thread(services.aspects.analyze_reviews, review_dicts)

    result = services.insights.generate(
        sentiments=sentiments,
        keywords=keywords,
        aspects=aspects,
        metrics=metrics_result,
    )
    return InsightsResponse(app_id=app_id, **result)


@router.post("/insights/{app_id}/narrative", response_model=NarrativeResponse)
async def generate_narrative(
    app_id: str,
    session: AsyncSession = Depends(get_db_session),
    services=Depends(get_services),
):
    reviews = await _get_reviews(app_id, session)
    review_dicts = [
        {
            "content": r.content,
            "rating": r.rating,
            "review_id": r.review_id,
            "vader_label": r.vader_label,
            "vader_compound": r.vader_compound,
            "combined_label": r.vader_label,
        }
        for r in reviews
    ]

    metrics_result = services.metrics.calculate(review_dicts)

    texts = [r.content for r in reviews]
    sentiments = await asyncio.to_thread(services.sentiment.analyze_batch, texts)

    keywords = await asyncio.to_thread(
        services.keywords.extract_from_negative_reviews, review_dicts
    )
    aspects = await asyncio.to_thread(services.aspects.analyze_reviews, review_dicts)

    result = services.insights.generate(
        sentiments=sentiments,
        keywords=keywords,
        aspects=aspects,
        metrics=metrics_result,
    )

    narrative = await services.insights.generate_narrative(result["insights"], metrics_result)
    return NarrativeResponse(app_id=app_id, narrative=narrative)
