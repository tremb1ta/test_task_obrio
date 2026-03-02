import secrets
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import database as db

security = HTTPBasic()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with db.async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


def get_services(request: Request):
    return request.app.state.services


def verify_basic_auth(credentials: HTTPBasicCredentials = Depends(security)) -> None:
    username_ok = secrets.compare_digest(credentials.username, settings.basic_auth_user)
    password_ok = secrets.compare_digest(credentials.password, settings.basic_auth_pass)
    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
