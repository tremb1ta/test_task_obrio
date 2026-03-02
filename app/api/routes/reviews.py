import re

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session, get_services
from app.models.database import Review
from app.models.schemas import (
    CollectRequest,
    CollectResponse,
    ExportFormat,
    ReviewListResponse,
    ReviewResponse,
)
from app.utils.helpers import reviews_to_csv, reviews_to_json

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("/collect", response_model=CollectResponse)
async def collect_reviews(
    body: CollectRequest,
    session: AsyncSession = Depends(get_db_session),
    services=Depends(get_services),
):
    result = await services.scraper.collect(
        app_id=body.app_id,
        session=session,
        country=body.country,
        max_pages=body.max_pages,
        sort_by=body.sort_by,
    )
    await services.preprocessing.preprocess_reviews(body.app_id, session)
    logger.info(
        "Collected {collected} reviews for {app_id} ({new} new, {dupes} duplicates)",
        collected=result.collected,
        app_id=body.app_id,
        new=result.new,
        dupes=result.duplicates,
    )
    return CollectResponse(
        app_id=result.app_id,
        collected=result.collected,
        new=result.new,
        duplicates=result.duplicates,
        source=result.source,
    )


@router.get("/{app_id}", response_model=ReviewListResponse)
async def get_reviews(
    app_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    stmt = select(Review).where(Review.app_id == app_id).order_by(Review.review_date.desc())
    result = await session.execute(stmt)
    reviews = result.scalars().all()
    return ReviewListResponse(
        app_id=app_id,
        total=len(reviews),
        reviews=[ReviewResponse.model_validate(r) for r in reviews],
    )


@router.get("/{app_id}/download")
async def download_reviews(
    app_id: str,
    export_format: ExportFormat = Query(default=ExportFormat.JSON, alias="format"),
    session: AsyncSession = Depends(get_db_session),
):
    stmt = select(Review).where(Review.app_id == app_id)
    result = await session.execute(stmt)
    reviews = result.scalars().all()

    review_dicts = [
        {
            "review_id": r.review_id,
            "app_id": r.app_id,
            "title": r.title,
            "content": r.content,
            "rating": r.rating,
            "author": r.author,
            "app_version": r.app_version,
            "review_date": str(r.review_date),
        }
        for r in reviews
    ]

    safe_id = re.sub(r"[^\w\-]", "_", app_id)

    if export_format == ExportFormat.CSV:
        content = reviews_to_csv(review_dicts)
        return StreamingResponse(
            iter([content]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{safe_id}_reviews.csv"'},
        )

    content = reviews_to_json(review_dicts)
    return StreamingResponse(
        iter([content]),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{safe_id}_reviews.json"'},
    )
