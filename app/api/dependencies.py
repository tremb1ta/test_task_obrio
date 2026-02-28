from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import database as db


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with db.async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


def get_services(request: Request):
    return request.app.state.services
