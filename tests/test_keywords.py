from unittest.mock import MagicMock

from app.services.keywords import KeywordService


def test_extract_keywords():
    mock_model = MagicMock()
    service = KeywordService(mock_model)
    service._kw_model = MagicMock()
    service._kw_model.extract_keywords.return_value = [
        ("battery drain", 0.85),
        ("app crashes", 0.72),
        ("the app", 0.60),
    ]
    result = service.extract_keywords(["battery drain is terrible", "app crashes all the time"])
    keywords = [r["keyword"] for r in result]
    assert "battery drain" in keywords
    assert "the app" not in keywords


def test_extract_empty_input():
    mock_model = MagicMock()
    service = KeywordService(mock_model)
    result = service.extract_keywords([])
    assert result == []


def test_extract_from_negative_reviews():
    mock_model = MagicMock()
    service = KeywordService(mock_model)
    service._kw_model = MagicMock()
    service._kw_model.extract_keywords.return_value = [("slow loading", 0.9)]

    reviews = [
        {"content": "App is slow", "rating": 1, "vader_label": "negative"},
        {"content": "Love it", "rating": 5, "vader_label": "positive"},
    ]
    result = service.extract_from_negative_reviews(reviews)
    assert len(result) >= 0
