"""방법 2: 뉴스 사이트 크롤링 (BeautifulSoup, httpx). RSS가 없는 소스를 흉내낸 예시로
Hacker News 프론트페이지(정적 HTML, 크롤링 친화적)를 사용한다.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("news_pipeline")

_HEADERS = {"User-Agent": "codyssey-mission-a2-2/1.0 (educational crawler)"}


def collect(crawl_url: str, *, timeout: float = 10.0, limit: int | None = 30) -> list[dict]:
    try:
        resp = httpx.get(crawl_url, timeout=timeout, headers=_HEADERS, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("크롤링 실패 (%s): %s", crawl_url, exc)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    rows = soup.select("tr.athing")[:limit]
    now_iso = datetime.now(timezone.utc).isoformat()

    items = []
    for row in rows:
        link = row.select_one("span.titleline > a")
        if not link:
            continue
        items.append(
            {
                "title": link.get_text(strip=True),
                "url": link.get("href", "").strip(),
                "published_at": None,  # HN 목록엔 절대시각이 없어 수집시각으로 대체(정제 단계에서 처리)
                "scraped_at": now_iso,
            }
        )
    logger.info("크롤링 완료: %d건 (%s)", len(items), crawl_url)
    return items
