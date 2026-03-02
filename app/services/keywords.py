from keybert import KeyBERT
from sentence_transformers import SentenceTransformer

GENERIC_PHRASES = frozenset(
    {
        "the app",
        "this app",
        "the application",
        "i think",
        "i feel",
        "really good",
        "very good",
        "very bad",
        "really bad",
    }
)


class KeywordService:
    def __init__(self, embedding_model: SentenceTransformer):
        self._kw_model = KeyBERT(model=embedding_model)  # type: ignore[arg-type]

    def extract_keywords(
        self,
        texts: list[str],
        top_n: int = 15,
        ngram_range: tuple[int, int] = (1, 3),
        diversity: float = 0.5,
    ) -> list[dict]:
        if not texts:
            return []

        combined_text = " ".join(texts)
        if len(combined_text.strip()) < 10:
            return []

        raw_keywords: list[tuple[str, float]] = self._kw_model.extract_keywords(  # type: ignore[assignment]
            combined_text,
            keyphrase_ngram_range=ngram_range,
            stop_words="english",
            top_n=top_n + 10,
            use_mmr=True,
            diversity=diversity,
        )
        results = []
        for keyword, score in raw_keywords:
            if keyword.lower() in GENERIC_PHRASES:
                continue
            results.append({"keyword": keyword, "score": round(score, 4)})
            if len(results) >= top_n:
                break
        return results

    def extract_from_negative_reviews(
        self,
        reviews: list[dict],
        top_n: int = 15,
    ) -> list[dict]:
        negative_texts = []
        for r in reviews:
            is_negative = (
                r.get("vader_label") == "negative"
                or r.get("combined_label") == "negative"
                or r.get("rating", 5) <= 2
            )
            if is_negative:
                negative_texts.append(r.get("content", ""))

        if len(negative_texts) < 3:
            rating_based = [r.get("content", "") for r in reviews if r.get("rating", 5) <= 2]
            negative_texts = list(dict.fromkeys(negative_texts + rating_based))

        return self.extract_keywords(negative_texts, top_n=top_n)
