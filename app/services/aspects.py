from collections import defaultdict

from nltk.sentiment.vader import SentimentIntensityAnalyzer
from spacy.language import Language

ASPECT_CATEGORIES: dict[str, list[str]] = {
    "battery": ["battery", "battery life", "power", "charging", "battery drain", "charge"],
    "performance": [
        "speed",
        "slow",
        "fast",
        "lag",
        "crash",
        "freeze",
        "loading",
        "performance",
        "responsive",
        "hang",
    ],
    "ui": [
        "ui",
        "interface",
        "design",
        "layout",
        "screen",
        "display",
        "look",
        "theme",
        "dark mode",
        "ux",
    ],
    "price": [
        "price",
        "cost",
        "expensive",
        "cheap",
        "subscription",
        "payment",
        "in-app purchase",
        "ads",
        "ad",
        "premium",
    ],
    "support": ["support", "customer service", "help", "response", "team"],
    "features": ["feature", "update", "functionality", "option", "setting", "tool"],
    "stability": ["crash", "bug", "error", "glitch", "issue", "problem", "fix"],
    "usability": [
        "easy",
        "intuitive",
        "confusing",
        "complicated",
        "user friendly",
        "simple",
        "hard to use",
    ],
}

_CATEGORY_LOOKUP: dict[str, str] = {}
for cat, keywords in ASPECT_CATEGORIES.items():
    for kw in keywords:
        _CATEGORY_LOOKUP[kw] = cat


class AspectService:
    def __init__(self, nlp: Language, vader: SentimentIntensityAnalyzer):
        self._nlp = nlp
        self._vader = vader

    def extract_aspects(self, text: str) -> list[dict]:
        doc = self._nlp(text)
        pairs = []

        for token in doc:
            if token.pos_ == "ADJ":
                aspect = None
                opinion = token.text

                for child in token.children:
                    if child.dep_ == "neg":
                        opinion = f"not {opinion}"

                head = token.head
                if token.dep_ == "amod" and head.pos_ in ("NOUN", "PROPN"):
                    aspect = self._get_noun_chunk(head)
                elif token.dep_ in ("acomp", "attr") and head.dep_ == "ROOT":
                    for child in head.children:
                        if child.dep_ == "nsubj" and child.pos_ in ("NOUN", "PROPN"):
                            aspect = self._get_noun_chunk(child)
                            break

                if aspect:
                    sentiment = self._vader.polarity_scores(opinion)
                    pairs.append(
                        {
                            "aspect": aspect.lower(),
                            "opinion": opinion.lower(),
                            "category": self._map_category(aspect.lower()),
                            "sentiment_score": sentiment["compound"],
                        }
                    )

            if token.pos_ == "VERB" and token.dep_ in ("ROOT", "conj"):
                for child in token.children:
                    if child.dep_ == "dobj" and child.pos_ in ("NOUN", "PROPN"):
                        aspect = self._get_noun_chunk(child)
                        opinion = token.text.lower()
                        sentiment = self._vader.polarity_scores(opinion)
                        pairs.append(
                            {
                                "aspect": aspect.lower(),
                                "opinion": opinion,
                                "category": self._map_category(aspect.lower()),
                                "sentiment_score": sentiment["compound"],
                            }
                        )

        return pairs

    @staticmethod
    def _get_noun_chunk(token) -> str:
        for chunk in token.doc.noun_chunks:
            if token in chunk:
                return chunk.text
        return token.text

    @staticmethod
    def _map_category(aspect: str) -> str:
        if aspect in _CATEGORY_LOOKUP:
            return _CATEGORY_LOOKUP[aspect]
        for word in aspect.split():
            if word in _CATEGORY_LOOKUP:
                return _CATEGORY_LOOKUP[word]
        return aspect

    def analyze_reviews(self, reviews: list[dict]) -> list[dict]:
        all_pairs = defaultdict(list)

        for review in reviews:
            text = review.get("content", "")
            if not text:
                continue
            pairs = self.extract_aspects(text)
            for pair in pairs:
                all_pairs[pair["category"]].append(pair)

        aggregated = []
        for category, pairs in sorted(all_pairs.items(), key=lambda x: -len(x[1])):
            scores = [p["sentiment_score"] for p in pairs]
            avg_score = sum(scores) / len(scores) if scores else 0.0

            if avg_score >= 0.05:
                label = "positive"
            elif avg_score <= -0.05:
                label = "negative"
            else:
                label = "neutral"

            sample_phrases = list({p["opinion"] for p in pairs})[:5]

            aggregated.append(
                {
                    "aspect": category,
                    "category": category,
                    "sentiment_score": round(avg_score, 4),
                    "sentiment_label": label,
                    "mention_count": len(pairs),
                    "sample_phrases": sample_phrases,
                }
            )

        return aggregated
