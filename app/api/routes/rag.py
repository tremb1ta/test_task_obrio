import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session, get_services
from app.models.database import Review
from app.models.schemas import RAGQueryRequest, RAGQueryResponse

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(
    body: RAGQueryRequest,
    session: AsyncSession = Depends(get_db_session),
    services=Depends(get_services),
):
    stmt = select(Review).where(Review.app_id == body.app_id)
    result = await session.execute(stmt)
    reviews = result.scalars().all()
    if not reviews:
        raise HTTPException(
            status_code=404,
            detail=f"No reviews found for app_id={body.app_id}. Collect reviews first.",
        )

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

    result = await services.rag.query(body.app_id, body.question, body.top_k)
    return RAGQueryResponse(**result)
