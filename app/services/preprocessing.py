import re

from loguru import logger
from spacy.language import Language
from spacy.tokens import Doc
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Review

_PATTERNS = {
    "url": re.compile(r"https?://\S+"),
    "email": re.compile(r"\S+@\S+\.\S+"),
    "updated_prefix": re.compile(r"^updated\s*review[:\-\s]*", re.IGNORECASE),
    "repeated_chars": re.compile(r"(.)\1{3,}"),
    "extra_whitespace": re.compile(r"\s{2,}"),
}

NEGATION_WORDS = frozenset({"not", "no", "never", "neither", "nor", "hardly", "barely"})


class PreprocessingService:
    def __init__(self, nlp: Language):
        self._nlp = nlp

    def clean_text(self, text: str) -> str:
        if not text or not text.strip():
            return ""
        text = self._pre_spacy_clean(text)
        doc = self._nlp(text)
        tokens = self._post_spacy_filter(doc)
        return " ".join(tokens)

    def clean_batch(self, texts: list[str]) -> list[str]:
        pre_cleaned = [self._pre_spacy_clean(t) for t in texts]
        results = []
        for doc in self._nlp.pipe(pre_cleaned, batch_size=64):
            tokens = self._post_spacy_filter(doc)
            results.append(" ".join(tokens))
        return results

    @staticmethod
    def _pre_spacy_clean(text: str) -> str:
        text = _PATTERNS["updated_prefix"].sub("", text)
        text = _PATTERNS["url"].sub("", text)
        text = _PATTERNS["email"].sub("", text)
        text = _PATTERNS["repeated_chars"].sub(r"\1\1", text)
        text = _PATTERNS["extra_whitespace"].sub(" ", text)
        return text.strip()

    @staticmethod
    def _post_spacy_filter(doc: Doc) -> list[str]:
        tokens = []
        for token in doc:
            if token.is_space or token.is_punct:
                continue
            lemma = token.lemma_.lower().strip()
            if len(lemma) <= 1:
                continue
            if token.is_stop and lemma not in NEGATION_WORDS:
                continue
            tokens.append(lemma)
        return tokens

    async def preprocess_reviews(self, app_id: str, session: AsyncSession) -> int:
        stmt = select(Review).where(
            Review.app_id == app_id,
            Review.content_clean.is_(None),
        )
        result = await session.execute(stmt)
        reviews = result.scalars().all()
        if not reviews:
            return 0

        texts = [r.content for r in reviews]
        cleaned = self.clean_batch(texts)
        for review, clean_text in zip(reviews, cleaned, strict=True):
            review.content_clean = clean_text

        await session.commit()
        logger.info(
            "Preprocessed {count} reviews for app_id={app_id}", count=len(reviews), app_id=app_id
        )
        return len(reviews)
