from app.services.scraper import ReviewScraper

SAMPLE_RSS_RESPONSE = {
    "feed": {
        "entry": [
            {
                "id": {"label": "app_metadata"},
                "title": {"label": "App Name"},
            },
            {
                "id": {"label": "12345"},
                "title": {"label": "Great app"},
                "content": {"label": "Really enjoying this application"},
                "im:rating": {"label": "5"},
                "author": {
                    "name": {"label": "testuser"},
                    "uri": {"label": "https://example.com"},
                },
                "im:version": {"label": "2.0"},
                "link": {"attributes": {"href": "https://example.com/review"}},
                "updated": {"label": "2026-01-15T12:00:00-07:00"},
            },
            {
                "id": {"label": "12346"},
                "title": {"label": "Needs work"},
                "content": {"label": "The app crashes frequently"},
                "im:rating": {"label": "2"},
                "author": {
                    "name": {"label": "anotheruser"},
                    "uri": {"label": "https://example.com"},
                },
                "im:version": {"label": "2.0"},
                "link": {"attributes": {"href": "https://example.com/review2"}},
                "updated": {"label": "2026-01-14T10:00:00-07:00"},
            },
        ]
    }
}


def test_parse_rss_response():
    reviews = ReviewScraper._parse_rss_response(SAMPLE_RSS_RESPONSE, "test_app")
    assert len(reviews) == 2
    assert reviews[0]["review_id"] == "12345"
    assert reviews[0]["rating"] == 5
    assert reviews[1]["review_id"] == "12346"
    assert reviews[1]["rating"] == 2


def test_skip_app_metadata_entry():
    reviews = ReviewScraper._parse_rss_response(SAMPLE_RSS_RESPONSE, "test_app")
    review_ids = [r["review_id"] for r in reviews]
    assert "app_metadata" not in review_ids


def test_parse_empty_feed():
    reviews = ReviewScraper._parse_rss_response({"feed": {}}, "test_app")
    assert reviews == []


def test_parse_malformed_entry():
    data = {
        "feed": {
            "entry": [
                {"im:rating": {"label": "5"}},
            ]
        }
    }
    reviews = ReviewScraper._parse_rss_response(data, "test_app")
    assert len(reviews) == 0
