from unittest.mock import MagicMock

import pytest
import spacy

from app.services.aspects import _CATEGORY_LOOKUP, AspectService


@pytest.fixture(scope="module")
def nlp():
    try:
        return spacy.load("en_core_web_sm")
    except OSError:
        pytest.skip("spaCy model en_core_web_sm not installed")


def test_category_mapping():
    assert _CATEGORY_LOOKUP.get("battery") == "battery"
    assert _CATEGORY_LOOKUP.get("crash") in ("performance", "stability")
    assert _CATEGORY_LOOKUP.get("design") == "ui"


def test_extract_aspects_basic(nlp):
    vader = MagicMock()
    vader.polarity_scores.return_value = {"compound": -0.8, "pos": 0.0, "neg": 0.8, "neu": 0.2}
    service = AspectService(nlp, vader)

    aspects = service.extract_aspects("The interface is terrible")
    assert len(aspects) > 0


def test_analyze_reviews_empty():
    nlp_mock = MagicMock()
    vader_mock = MagicMock()
    service = AspectService(nlp_mock, vader_mock)
    result = service.analyze_reviews([])
    assert result == []
