from unittest.mock import MagicMock

from app.services.sentiment import SentimentService, _vader_label


def test_vader_label_positive():
    assert _vader_label(0.5) == "positive"


def test_vader_label_negative():
    assert _vader_label(-0.5) == "negative"


def test_vader_label_neutral():
    assert _vader_label(0.01) == "neutral"


def test_analyze_vader():
    vader = MagicMock()
    vader.polarity_scores.return_value = {"compound": 0.8, "pos": 0.6, "neg": 0.0, "neu": 0.4}
    service = SentimentService(vader, MagicMock())
    result = service.analyze_vader("great app")
    assert result["label"] == "positive"
    assert result["compound"] == 0.8


def test_analyze_transformer():
    transformer = MagicMock()
    transformer.return_value = [{"label": "NEGATIVE", "score": 0.95}]
    service = SentimentService(MagicMock(), transformer)
    result = service.analyze_transformer("terrible app")
    assert result["label"] == "negative"
    assert result["sentiment_score"] == -0.95


def test_analyze_batch_empty():
    service = SentimentService(MagicMock(), MagicMock())
    assert service.analyze_batch([]) == []
