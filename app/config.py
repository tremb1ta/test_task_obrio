from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:8501"]

    database_url: str = "sqlite+aiosqlite:///./data/reviews.db"

    openrouter_api_key: str = ""
    openrouter_model: str = "moonshotai/kimi-k2.5"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_max_tokens: int = 2048
    openrouter_temperature: float = 0.3

    sentiment_model: str = "distilbert-base-uncased-finetuned-sst-2-english"
    embedding_model: str = "all-MiniLM-L6-v2"
    spacy_model: str = "en_core_web_sm"

    chroma_persist_dir: str = "./data/chroma"

    apple_rss_base_url: str = "https://itunes.apple.com"
    scraper_timeout: float = 30.0
    scraper_max_pages: int = 10

    basic_auth_user: str
    basic_auth_pass: str

    log_level: str = "info"


settings = Settings()  # type: ignore[call-arg]
