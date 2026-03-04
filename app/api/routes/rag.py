import asyncio

from fastapi import APIRouter, Depends
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import ensure_reviews_exist, get_db_session, get_services
from app.models.database import Review
from app.models.schemas import (
    RAGQueryRequest,
    RAGQueryResponse,
    SuggestQuestionsRequest,
    SuggestQuestionsResponse,
)

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(
    body: RAGQueryRequest,
    session: AsyncSession = Depends(get_db_session),
    services=Depends(get_services),
):
    await ensure_reviews_exist(body.app_id, session, services)
    stmt = select(Review).where(Review.app_id == body.app_id)
    result = await session.execute(stmt)
    reviews = result.scalars().all()

    review_dicts = [
        {
            "content": r.content,
            "rating": r.rating,
            "review_id": r.review_id,
            "vader_label": r.vader_label or "",
        }
        for r in reviews
    ]
    await asyncio.to_thread(services.rag.index_reviews, body.app_id, review_dicts)

    logger.info("RAG query for {app_id}: {question}", app_id=body.app_id, question=body.question)
    result = await services.rag.query(body.app_id, body.question, body.top_k)
    return RAGQueryResponse(**result)


@router.post("/suggest-questions", response_model=SuggestQuestionsResponse)
async def suggest_questions(
    body: SuggestQuestionsRequest,
    session: AsyncSession = Depends(get_db_session),
    services=Depends(get_services),
):
    await ensure_reviews_exist(body.app_id, session, services)
    stmt = select(Review).where(Review.app_id == body.app_id)
    result = await session.execute(stmt)
    reviews = list(result.scalars().all())

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

    insights_result = services.insights.generate(
        sentiments=sentiments,
        keywords=keywords,
        aspects=aspects,
        metrics=metrics_result,
    )

    parts = [
        f"Average rating: {metrics_result['average_rating']:.2f}/5 "
        f"({metrics_result['total_reviews']} reviews)"
    ]
    for insight in insights_result.get("insights", []):
        parts.append(f"[{insight['severity']}] {insight['message']}")

    insights_summary = "\n".join(parts)
    suggestion = await services.rag.suggest_questions(insights_summary, body.num_questions)

    return SuggestQuestionsResponse(
        app_id=body.app_id,
        questions=suggestion["questions"],
        model_used=suggestion["model_used"],
    )
