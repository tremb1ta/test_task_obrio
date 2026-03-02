from loguru import logger
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from transformers import Pipeline

from app.models.database import Review

POSITIVE_THRESHOLD = 0.05
NEGATIVE_THRESHOLD = -0.05


def _vader_label(compound: float) -> str:
    if compound >= POSITIVE_THRESHOLD:
        return "positive"
    if compound <= NEGATIVE_THRESHOLD:
        return "negative"
    return "neutral"


class SentimentService:
    def __init__(self, vader: SentimentIntensityAnalyzer, transformer: Pipeline):
        self._vader = vader
        self._transformer = transformer

    def analyze_vader(self, text: str) -> dict:
        scores = self._vader.polarity_scores(text)
        return {
            "compound": scores["compound"],
            "positive": scores["pos"],
            "negative": scores["neg"],
            "neutral": scores["neu"],
            "label": _vader_label(scores["compound"]),
        }

    def analyze_transformer(self, text: str) -> dict:
        result = self._transformer(text, truncation=True, max_length=512)[0]
        label = result["label"].lower()
        score = result["score"]
        sentiment_score = score if label == "positive" else -score
        return {
            "label": label,
            "score": score,
            "sentiment_score": sentiment_score,
        }

    def analyze_batch(self, texts: list[str]) -> list[dict]:
        if not texts:
            return []

        vader_results = [self.analyze_vader(t) for t in texts]

        transformer_outputs = self._transformer(
            texts, truncation=True, max_length=512, batch_size=32
        )
        transformer_results = []
        for out in transformer_outputs:
            label = out["label"].lower()
            score = out["score"]
            sentiment_score = score if label == "positive" else -score
            transformer_results.append(
                {"label": label, "score": score, "sentiment_score": sentiment_score}
            )

        combined = []
        for vader, transformer in zip(vader_results, transformer_results, strict=True):
            combined_score = 0.6 * transformer["sentiment_score"] + 0.4 * vader["compound"]
            if combined_score >= POSITIVE_THRESHOLD:
                combined_label = "positive"
            elif combined_score <= NEGATIVE_THRESHOLD:
                combined_label = "negative"
            else:
                combined_label = "neutral"

            combined.append(
                {
                    "vader": vader,
                    "transformer": transformer,
                    "combined_label": combined_label,
                    "combined_score": combined_score,
                }
            )
        return combined

    async def analyze_reviews(self, app_id: str, session: AsyncSession) -> int:
        stmt = select(Review).where(
            Review.app_id == app_id,
            Review.vader_compound.is_(None),
        )
        result = await session.execute(stmt)
        reviews = result.scalars().all()
        if not reviews:
            return 0

        texts = [r.content for r in reviews]
        results = self.analyze_batch(texts)
        for review, sentiment in zip(reviews, results, strict=True):
            review.vader_compound = sentiment["vader"]["compound"]
            review.vader_label = sentiment["vader"]["label"]
            review.transformer_score = sentiment["transformer"]["sentiment_score"]
            review.transformer_label = sentiment["transformer"]["label"]

        await session.commit()
        logger.info(
            "Analyzed sentiment for {count} reviews, app_id={app_id}",
            count=len(reviews),
            app_id=app_id,
        )
        return len(reviews)
