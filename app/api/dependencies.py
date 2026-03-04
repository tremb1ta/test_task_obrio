import base64
import secrets as secrets_mod
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import database as db
from app.models.database import Review

security = HTTPBasic(auto_error=False)


async def ensure_reviews_exist(app_id: str, session: AsyncSession, services) -> None:
    count = await session.execute(
        select(func.count()).select_from(Review).where(Review.app_id == app_id)
    )
    if count.scalar_one() > 0:
        return
    logger.info("No reviews for {app_id}, auto-collecting", app_id=app_id)
    await services.scraper.collect(app_id, session, country="us", max_pages=10)
    await services.preprocessing.preprocess_reviews(app_id, session)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with db.async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


def get_services(request: Request):
    return request.app.state.services


def _check_credentials(username: str, password: str) -> bool:
    username_ok = secrets_mod.compare_digest(username, settings.basic_auth_user)
    password_ok = secrets_mod.compare_digest(password, settings.basic_auth_pass)
    return username_ok and password_ok


def _parse_x_auth(header_value: str) -> tuple[str, str] | None:
    """Parse X-Auth header in format 'Basic base64(user:pass)'."""
    try:
        scheme, _, encoded = header_value.partition(" ")
        if scheme.lower() != "basic":
            return None
        decoded = base64.b64decode(encoded).decode("utf-8")
        username, _, password = decoded.partition(":")
        return username, password
    except Exception:
        return None


def verify_basic_auth(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(security),
) -> None:
    if credentials and _check_credentials(credentials.username, credentials.password):
        return

    x_auth = request.headers.get("x-auth")
    if x_auth:
        parsed = _parse_x_auth(x_auth)
        if parsed and _check_credentials(*parsed):
            return

    raise HTTPException(
        status_code=401,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Basic"},
    )
