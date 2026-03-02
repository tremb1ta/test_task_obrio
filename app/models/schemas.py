from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ExportFormat(StrEnum):
    CSV = "csv"
    JSON = "json"


class ReviewSortOrder(StrEnum):
    MOST_HELPFUL = "mosthelpful"
    MOST_RECENT = "mostrecent"


class SentimentLabel(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class ReviewBase(BaseModel):
    app_id: str
    review_id: str
    title: str
    content: str
    rating: int = Field(ge=1, le=5)
    author: str
    author_uri: str = ""
    app_version: str = ""
    review_url: str = ""
    review_date: datetime


class ReviewResponse(ReviewBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content_clean: str | None = None
    vader_compound: float | None = None
    vader_label: str | None = None
    transformer_score: float | None = None
    transformer_label: str | None = None
    collected_at: datetime
    updated_at: datetime


class ReviewListResponse(BaseModel):
    app_id: str
    total: int
    reviews: list[ReviewResponse]


class CollectRequest(BaseModel):
    app_id: str = Field(
        description="Apple App Store numeric application ID",
        examples=["389801252"],
    )
    country: str = Field(default="us", max_length=2)
    max_pages: int = Field(default=10, ge=1, le=10)
    sort_by: ReviewSortOrder = ReviewSortOrder.MOST_RECENT


class CollectResponse(BaseModel):
    app_id: str
    collected: int
    new: int
    duplicates: int
    source: str


class DownloadParams(BaseModel):
    format: ExportFormat = ExportFormat.JSON


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    models_loaded: dict[str, bool]


class RatingDistribution(BaseModel):
    rating: int
    count: int
    percentage: float


class MetricsResponse(BaseModel):
    app_id: str
    total_reviews: int
    average_rating: float
    rating_distribution: list[RatingDistribution]


class SentimentResult(BaseModel):
    review_id: str
    content: str
    vader_compound: float
    vader_label: SentimentLabel
    transformer_score: float
    transformer_label: SentimentLabel


class SentimentSummary(BaseModel):
    method: str
    positive: int
    negative: int
    neutral: int
    average_score: float


class SentimentResponse(BaseModel):
    app_id: str
    total_analyzed: int
    summaries: dict[str, SentimentSummary]
    results: list[SentimentResult]


class SuggestQuestionsRequest(BaseModel):
    app_id: str
    num_questions: int = Field(default=5, ge=1, le=20)


class SuggestQuestionsResponse(BaseModel):
    app_id: str
    questions: list[str]
    model_used: str | None


class RAGQueryRequest(BaseModel):
    app_id: str
    question: str = Field(min_length=5, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)


class RAGSourceReview(BaseModel):
    review_id: str
    content: str
    rating: int
    similarity_score: float


class RAGQueryResponse(BaseModel):
    app_id: str
    question: str
    answer: str | None
    model_used: str | None
    mode: str
    sources: list[RAGSourceReview]


class AspectSentiment(BaseModel):
    aspect: str
    category: str
    sentiment_score: float
    sentiment_label: SentimentLabel
    mention_count: int
    sample_phrases: list[str]


class AspectsResponse(BaseModel):
    app_id: str
    total_aspects: int
    aspects: list[AspectSentiment]


class CompareRequest(BaseModel):
    app_ids: list[str] = Field(min_length=2, max_length=5)
    country: str = "us"


class AppSummary(BaseModel):
    app_id: str
    average_rating: float
    average_sentiment: float
    top_keywords: list[str]
    top_complaints: list[str]


class CompareResponse(BaseModel):
    apps: list[AppSummary]
    insights: list[str]


class InsightItem(BaseModel):
    category: str
    severity: str
    message: str
    affected_aspect: str = ""


class InsightsResponse(BaseModel):
    app_id: str
    insights: list[InsightItem]
    narrative: str | None = None
