from fastapi import APIRouter, Depends
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session, get_services
from app.models.schemas import CompareRequest, CompareResponse

router = APIRouter(prefix="/competitive", tags=["competitive"])


@router.post("/compare", response_model=CompareResponse)
async def compare_apps(
    body: CompareRequest,
    session: AsyncSession = Depends(get_db_session),
    services=Depends(get_services),
):
    logger.info("Competitive comparison for {app_ids}", app_ids=body.app_ids)
    result = await services.competitive.compare(body.app_ids, body.country, session)
    return CompareResponse(**result)
