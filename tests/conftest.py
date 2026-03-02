from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.database import Base


@pytest.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def sample_reviews():
    return [
        {
            "app_id": "389801252",
            "review_id": f"review_{i}",
            "title": f"Test Review {i}",
            "content": content,
            "rating": rating,
            "author": f"user_{i}",
            "author_uri": "",
            "app_version": "1.0",
            "review_url": "",
            "review_date": datetime.now(UTC).isoformat(),
        }
        for i, (content, rating) in enumerate(
            [
                ("This app is amazing, I love the new design and features!", 5),
                ("Terrible experience, the app crashes every time I open it.", 1),
                ("Pretty good but the ads are really annoying.", 3),
                ("Battery drain is insane with this app running in background.", 2),
                ("Best social media app out there, highly recommend!", 5),
                ("The latest update broke everything, can't even log in now.", 1),
                ("Decent app with some useful features but could be better.", 3),
                ("Love it", 5),
                ("Customer support is very helpful and responsive.", 4),
                ("Slow loading times and constant freezing on my phone.", 2),
            ]
        )
    ]


@pytest.fixture
def mock_services():
    services = MagicMock()
    services.scraper.collect = AsyncMock()
    services.preprocessing.preprocess_reviews = AsyncMock(return_value=0)
    services.sentiment.analyze_reviews = AsyncMock(return_value=0)
    services.sentiment.analyze_batch = MagicMock(return_value=[])
    services.metrics.calculate = MagicMock(
        return_value={
            "total_reviews": 10,
            "average_rating": 3.1,
            "rating_distribution": [
                {"rating": i, "count": 2, "percentage": 20.0} for i in range(1, 6)
            ],
        }
    )
    services.keywords.extract_from_negative_reviews = MagicMock(return_value=[])
    services.aspects.analyze_reviews = MagicMock(return_value=[])
    services.insights.generate = MagicMock(return_value={"insights": [], "narrative": None})
    services.rag.index_reviews = MagicMock(return_value=0)
    services.rag.suggest_questions = AsyncMock(
        return_value={"questions": ["What are the top complaints?"], "model_used": "test-model"}
    )
    services.rag.query = AsyncMock(
        return_value={
            "app_id": "test",
            "question": "test",
            "answer": "test answer",
            "model_used": "test-model",
            "mode": "rag",
            "sources": [],
        }
    )
    services.competitive.compare = AsyncMock(return_value={"apps": [], "insights": []})
    return services


@pytest.fixture
async def test_client(mock_services, async_session):
    from app.api.dependencies import get_db_session
    from app.main import create_app

    application = create_app()

    async def override_db():
        yield async_session

    application.dependency_overrides[get_db_session] = override_db
    application.state.services = mock_services
    application.state.models_loaded = {"spacy": True, "vader": True}

    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        yield client
