from collections import Counter


class MetricsService:
    @staticmethod
    def calculate(reviews: list[dict]) -> dict:
        if not reviews:
            return {
                "total_reviews": 0,
                "average_rating": 0.0,
                "rating_distribution": [],
            }

        ratings = [r["rating"] for r in reviews]
        total = len(ratings)
        avg = sum(ratings) / total

        counts = Counter(ratings)
        distribution = []
        for star in range(1, 6):
            count = counts.get(star, 0)
            distribution.append(
                {
                    "rating": star,
                    "count": count,
                    "percentage": round(count / total * 100, 1),
                }
            )

        return {
            "total_reviews": total,
            "average_rating": round(avg, 2),
            "rating_distribution": distribution,
        }
