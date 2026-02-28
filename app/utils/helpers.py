import csv
import io
import json


def reviews_to_csv(reviews: list[dict]) -> str:
    if not reviews:
        return ""
    output = io.StringIO()
    fields = [
        "review_id",
        "app_id",
        "title",
        "content",
        "rating",
        "author",
        "app_version",
        "review_date",
    ]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(reviews)
    return output.getvalue()


def reviews_to_json(reviews: list[dict]) -> str:
    return json.dumps(reviews, default=str, indent=2)
