import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import Review

logger = logging.getLogger(__name__)


@dataclass
class ScrapeResult:
    app_id: str
    collected: int
    new: int
    duplicates: int
    source: str


class ReviewScraper:
    RSS_URL_TEMPLATE = (
        "{base_url}/{country}/rss/customerreviews/page={page}/id={app_id}/sortby=mostrecent/json"
    )

    def __init__(
        self,
        base_url: str = settings.apple_rss_base_url,
        timeout: float = settings.scraper_timeout,
    ):
        self._base_url = base_url
        self._timeout = timeout

    async def collect(
        self,
        app_id: str,
        session: AsyncSession,
        country: str = "us",
        max_pages: int = 2,
    ) -> ScrapeResult:
        try:
            raw_reviews = await self._fetch_all_pages(app_id, country, max_pages)
        except Exception:
            logger.exception("RSS feed failed for app_id=%s", app_id)
            raise

        result = await self._persist_reviews(app_id, raw_reviews, session)
        return ScrapeResult(
            app_id=app_id,
            collected=len(raw_reviews),
            new=result["new"],
            duplicates=result["duplicates"],
            source="rss_feed",
        )

    async def _fetch_all_pages(self, app_id: str, country: str, max_pages: int) -> list[dict]:
        all_reviews: list[dict] = []
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for page in range(1, max_pages + 1):
                url = self.RSS_URL_TEMPLATE.format(
                    base_url=self._base_url,
                    country=country,
                    page=page,
                    app_id=app_id,
                )
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    reviews = self._parse_rss_response(response.json(), app_id)
                    if not reviews:
                        break
                    all_reviews.extend(reviews)
                except httpx.HTTPStatusError as exc:
                    logger.warning(
                        "RSS page %d returned %d, stopping", page, exc.response.status_code
                    )
                    break
                except httpx.RequestError:
                    logger.warning("Request error on page %d, stopping", page)
                    break
        return all_reviews

    @staticmethod
    def _parse_rss_response(data: dict, app_id: str) -> list[dict]:
        entries = data.get("feed", {}).get("entry", [])
        reviews = []
        for entry in entries:
            if "im:rating" not in entry:
                continue
            try:
                reviews.append(
                    {
                        "app_id": app_id,
                        "review_id": entry["id"]["label"],
                        "title": entry.get("title", {}).get("label", ""),
                        "content": entry.get("content", {}).get("label", ""),
                        "rating": int(entry["im:rating"]["label"]),
                        "author": entry.get("author", {}).get("name", {}).get("label", ""),
                        "author_uri": entry.get("author", {}).get("uri", {}).get("label", ""),
                        "app_version": entry.get("im:version", {}).get("label", ""),
                        "review_url": entry.get("link", {}).get("attributes", {}).get("href", ""),
                        "review_date": datetime.fromisoformat(entry["updated"]["label"])
                        .astimezone(UTC)
                        .replace(tzinfo=None),
                    }
                )
            except (KeyError, ValueError):
                logger.warning("Skipping malformed entry: %s", entry.get("id", "unknown"))
        return reviews

    @staticmethod
    async def _persist_reviews(
        app_id: str, reviews: list[dict], session: AsyncSession
    ) -> dict[str, int]:
        new_count = 0
        for review in reviews:
            stmt = (
                sqlite_upsert(Review)
                .values(**review)
                .on_conflict_do_nothing(index_elements=["app_id", "review_id"])
            )
            result = await session.execute(stmt)
            if result.rowcount > 0:  # type: ignore[union-attr]
                new_count += 1
        await session.commit()
        return {"new": new_count, "duplicates": len(reviews) - new_count}
