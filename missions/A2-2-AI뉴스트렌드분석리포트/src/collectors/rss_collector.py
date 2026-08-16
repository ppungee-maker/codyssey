"""방법 1: 공개 RSS 피드로 뉴스 수집 (feedparser)."""

from __future__ import annotations

import logging

import feedparser
import httpx

logger = logging.getLogger("news_pipeline")


def collect(rss_url: str, *, timeout: float = 10.0, limit: int | None = None) -> list[dict]:
    """RSS 항목 리스트를 반환한다. 실패해도 예외를 올리지 않고 빈 리스트 + 로그."""
    try:
        resp = httpx.get(rss_url, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("RSS 수집 실패 (%s): %s", rss_url, exc)
        return []

    feed = feedparser.parse(resp.content)
    if feed.bozo and not feed.entries:
        logger.warning("RSS 파싱 경고 (%s): %s", rss_url, feed.bozo_exception)

    entries = feed.entries[:limit] if limit else feed.entries
    items = []
    for e in entries:
        items.append(
            {
                "title": getattr(e, "title", "").strip(),
                "url": getattr(e, "link", "").strip(),
                "published_at": getattr(e, "published", None),
                "summary_raw": getattr(e, "summary", ""),
            }
        )
    logger.info("RSS 수집 완료: %d건 (%s)", len(items), rss_url)
    return items
