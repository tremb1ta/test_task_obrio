import pytest

from app.services.metrics import MetricsService


def test_average_rating():
    reviews = [{"rating": 5}, {"rating": 3}, {"rating": 1}]
    result = MetricsService.calculate(reviews)
    assert result["average_rating"] == 3.0


def test_rating_distribution():
    reviews = [{"rating": 5}, {"rating": 5}, {"rating": 1}]
    result = MetricsService.calculate(reviews)
    dist = {d["rating"]: d for d in result["rating_distribution"]}
    assert dist[5]["count"] == 2
    assert dist[5]["percentage"] == pytest.approx(66.7, abs=0.1)
    assert dist[1]["count"] == 1


def test_empty_reviews():
    result = MetricsService.calculate([])
    assert result["total_reviews"] == 0
    assert result["average_rating"] == 0.0


def test_all_same_rating():
    reviews = [{"rating": 4}] * 10
    result = MetricsService.calculate(reviews)
    assert result["average_rating"] == 4.0
    dist = {d["rating"]: d for d in result["rating_distribution"]}
    assert dist[4]["percentage"] == 100.0
