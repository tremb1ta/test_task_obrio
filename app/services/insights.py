import logging

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class InsightsService:
    def __init__(self, settings: Settings):
        self._settings = settings

    def generate(
        self,
        sentiments: list[dict],
        keywords: list[dict],
        aspects: list[dict],
        metrics: dict,
    ) -> dict:
        insights = self._build_structured_insights(sentiments, keywords, aspects, metrics)
        return {"insights": insights, "narrative": None}

    @staticmethod
    def _build_structured_insights(
        sentiments: list[dict],
        keywords: list[dict],
        aspects: list[dict],
        metrics: dict,
    ) -> list[dict]:
        insights = []
        total = len(sentiments) if sentiments else 0

        if total > 0:
            negative_count = sum(
                1
                for s in sentiments
                if s.get("combined_label") == "negative"
                or s.get("vader", {}).get("label") == "negative"
            )
            negative_pct = negative_count / total * 100

            if negative_pct > 40:
                severity = "high"
            elif negative_pct > 20:
                severity = "medium"
            else:
                severity = "low"

            insights.append(
                {
                    "category": "overall_sentiment",
                    "severity": severity,
                    "message": f"{negative_pct:.0f}% of reviews express negative sentiment.",
                    "affected_aspect": "",
                }
            )

        avg_rating = metrics.get("average_rating", 0)
        if avg_rating < 3.0:
            insights.append(
                {
                    "category": "rating",
                    "severity": "high",
                    "message": f"Average rating is {avg_rating:.1f}/5, below threshold.",
                    "affected_aspect": "",
                }
            )
        elif avg_rating < 4.0:
            insights.append(
                {
                    "category": "rating",
                    "severity": "medium",
                    "message": f"Average rating is {avg_rating:.1f}/5, room for improvement.",
                    "affected_aspect": "",
                }
            )

        for kw in keywords[:5]:
            insights.append(
                {
                    "category": "negative_keywords",
                    "severity": "medium",
                    "message": f"Frequent complaint keyword: '{kw['keyword']}' "
                    f"(relevance: {kw['score']:.2f}).",
                    "affected_aspect": kw["keyword"],
                }
            )

        for aspect in aspects:
            if aspect.get("sentiment_label") == "negative" and aspect.get("mention_count", 0) >= 3:
                insights.append(
                    {
                        "category": "aspect_sentiment",
                        "severity": "high" if aspect["sentiment_score"] < -0.3 else "medium",
                        "message": f"Aspect '{aspect['category']}' has negative sentiment "
                        f"({aspect['sentiment_score']:.2f}) across "
                        f"{aspect['mention_count']} mentions.",
                        "affected_aspect": aspect["category"],
                    }
                )

        if not insights:
            insights.append(
                {
                    "category": "overall",
                    "severity": "low",
                    "message": "No significant issues detected in reviews.",
                    "affected_aspect": "",
                }
            )

        return insights

    async def generate_narrative(self, insights: list[dict], metrics: dict) -> str | None:
        if not self._settings.openrouter_api_key:
            return None

        insight_text = "\n".join(f"- [{i['severity']}] {i['message']}" for i in insights)
        prompt = (
            f"Based on an analysis of {metrics.get('total_reviews', 0)} app reviews "
            f"(avg rating: {metrics.get('average_rating', 0):.1f}/5), "
            f"here are the key findings:\n\n{insight_text}\n\n"
            "Write a concise 2-3 paragraph executive summary of these findings "
            "with actionable recommendations."
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self._settings.openrouter_base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._settings.openrouter_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self._settings.openrouter_model,
                        "messages": [
                            {"role": "system", "content": "You are a product analyst."},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": self._settings.openrouter_max_tokens,
                        "temperature": self._settings.openrouter_temperature,
                    },
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]
        except Exception:
            logger.exception("Narrative generation failed")
            return None
