from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

async_engine = None
async_session_factory = None


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(AsyncAttrs, DeclarativeBase):
    pass


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    app_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    review_id: Mapped[str] = mapped_column(String(64), nullable=False)

    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    author: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    author_uri: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    app_version: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    review_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")

    content_clean: Mapped[str | None] = mapped_column(Text, nullable=True)

    vader_compound: Mapped[float | None] = mapped_column(Float, nullable=True)
    vader_label: Mapped[str | None] = mapped_column(String(16), nullable=True)
    transformer_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    transformer_label: Mapped[str | None] = mapped_column(String(16), nullable=True)

    review_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        UniqueConstraint("app_id", "review_id", name="uq_app_review"),
        Index("ix_app_rating", "app_id", "rating"),
        Index("ix_app_date", "app_id", "review_date"),
    )

    def __repr__(self) -> str:
        return f"<Review {self.app_id}:{self.review_id} rating={self.rating}>"


async def init_db(database_url: str) -> None:
    global async_engine, async_session_factory
    async_engine = create_async_engine(
        database_url,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async_session_factory = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    global async_engine
    if async_engine:
        await async_engine.dispose()
