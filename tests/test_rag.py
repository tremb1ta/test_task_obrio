import tempfile
from unittest.mock import MagicMock

import numpy as np
import pytest

from app.services.rag import RAGService


@pytest.fixture
def rag_service():
    embedding_model = MagicMock()
    embedding_model.encode.return_value = np.random.rand(3, 384).astype(np.float32)

    settings = MagicMock()
    settings.chroma_persist_dir = tempfile.mkdtemp()
    settings.openrouter_api_key = ""
    settings.openrouter_model = "test-model"
    settings.openrouter_base_url = "https://openrouter.ai/api/v1"
    settings.openrouter_max_tokens = 100
    settings.openrouter_temperature = 0.3

    return RAGService(embedding_model, settings)


def test_index_reviews(rag_service):
    reviews = [
        {"content": "Great app", "rating": 5, "review_id": "1", "vader_label": "positive"},
        {"content": "Terrible", "rating": 1, "review_id": "2", "vader_label": "negative"},
        {"content": "It's okay", "rating": 3, "review_id": "3", "vader_label": "neutral"},
    ]
    count = rag_service.index_reviews("test_app", reviews)
    assert count == 3


def test_index_empty(rag_service):
    assert rag_service.index_reviews("test_app", []) == 0


@pytest.mark.asyncio
async def test_fallback_without_api_key(rag_service):
    result = await rag_service.generate_answer("test question", [])
    assert result["mode"] == "retrieval_only"
    assert result["answer"] is None
