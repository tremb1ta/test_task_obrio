import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Review

logger = logging.getLogger(__name__)


class CompetitiveService:
    def __init__(self, scraper, preprocessing, sentiment, keywords, aspects):
        self._scraper = scraper
        self._preprocessing = preprocessing
        self._sentiment = sentiment
        self._keywords = keywords
        self._aspects = aspects

    async def compare(self, app_ids: list[str], country: str, session: AsyncSession) -> dict:
        app_summaries = []

        for app_id in app_ids:
            stmt = select(Review).where(Review.app_id == app_id)
            result = await session.execute(stmt)
            reviews = result.scalars().all()

            if not reviews:
                await self._scraper.collect(app_id, session, country=country, max_pages=2)
                await self._preprocessing.preprocess_reviews(app_id, session)
                await self._sentiment.analyze_reviews(app_id, session)

                result = await session.execute(stmt)
                reviews = result.scalars().all()

            if not reviews:
                app_summaries.append(
                    {
                        "app_id": app_id,
                        "average_rating": 0.0,
                        "average_sentiment": 0.0,
                        "top_keywords": [],
                        "top_complaints": [],
                    }
                )
                continue

            review_dicts = [
                {
                    "content": r.content,
                    "rating": r.rating,
                    "vader_label": r.vader_label,
                    "vader_compound": r.vader_compound,
                    "review_id": r.review_id,
                }
                for r in reviews
            ]

            ratings = [r.rating for r in reviews]
            avg_rating = sum(ratings) / len(ratings) if ratings else 0.0

            sentiments = [r.vader_compound or 0.0 for r in reviews]
            avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0

            kw_results = self._keywords.extract_from_negative_reviews(review_dicts)
            top_keywords = [k["keyword"] for k in kw_results[:5]]

            complaints = [k["keyword"] for k in kw_results[:3]]

            app_summaries.append(
                {
                    "app_id": app_id,
                    "average_rating": round(avg_rating, 2),
                    "average_sentiment": round(avg_sentiment, 4),
                    "top_keywords": top_keywords,
                    "top_complaints": complaints,
                }
            )

        insights = self._generate_insights(app_summaries)

        return {"apps": app_summaries, "insights": insights}

    @staticmethod
    def _generate_insights(summaries: list[dict]) -> list[str]:
        if len(summaries) < 2:
            return []

        insights = []
        sorted_by_rating = sorted(summaries, key=lambda x: x["average_rating"], reverse=True)
        best = sorted_by_rating[0]
        worst = sorted_by_rating[-1]

        if best["average_rating"] != worst["average_rating"]:
            diff = best["average_rating"] - worst["average_rating"]
            insights.append(
                f"App {best['app_id']} leads in ratings ({best['average_rating']}) "
                f"over {worst['app_id']} ({worst['average_rating']}) by {diff:.1f} stars."
            )

        sorted_by_sentiment = sorted(summaries, key=lambda x: x["average_sentiment"], reverse=True)
        best_sent = sorted_by_sentiment[0]
        worst_sent = sorted_by_sentiment[-1]

        if best_sent["average_sentiment"] > worst_sent["average_sentiment"]:
            insights.append(
                f"App {best_sent['app_id']} has more positive sentiment "
                f"({best_sent['average_sentiment']:.3f}) vs "
                f"{worst_sent['app_id']} ({worst_sent['average_sentiment']:.3f})."
            )

        all_complaints = set()
        for s in summaries:
            all_complaints.update(s.get("top_complaints", []))

        for s in summaries:
            unique = set(s.get("top_complaints", [])) - set().union(
                *(set(o.get("top_complaints", [])) for o in summaries if o != s)
            )
            if unique:
                insights.append(f"Unique complaints for {s['app_id']}: {', '.join(unique)}.")

        return insights
