from fastapi import APIRouter, Request

from app.models.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request) -> HealthResponse:
    models_loaded = getattr(request.app.state, "models_loaded", {})
    return HealthResponse(
        status="ok",
        version="0.1.0",
        models_loaded=models_loaded,
    )
