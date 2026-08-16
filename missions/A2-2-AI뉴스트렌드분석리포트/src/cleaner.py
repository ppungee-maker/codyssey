"""정제 규칙: 필수 필드 검증, 텍스트 정규화, 날짜 형식 통일, 결측값 처리, 카테고리 분류."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

logger = logging.getLogger("news_pipeline")


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_date(published_at: str | None, fallback_iso: str) -> str:
    """RFC822(RSS)/ISO 등 다양한 포맷을 ISO 8601로 통일. 파싱 실패/결측이면 수집시각으로 대체."""
    if not published_at:
        return fallback_iso
    try:
        dt = parsedate_to_datetime(published_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(published_at).astimezone(timezone.utc).isoformat()
    except ValueError:
        logger.warning("날짜 파싱 실패, 수집시각으로 대체: %r", published_at)
        return fallback_iso


def classify_category(title: str, categories: dict[str, list[str]]) -> str:
    lowered = title.lower()
    for category, keywords in categories.items():
        if any(kw in lowered for kw in keywords):
            return category
    return "일반"


def clean_record(raw: dict, *, collected_at: str, categories: dict[str, list[str]]) -> dict | None:
    """필수 필드(title, url) 검증 실패 시 None 반환 — 호출부가 skip 처리."""
    title = normalize_text(raw.get("title", ""))
    url = (raw.get("url") or "").strip()
    if not title or not url:
        logger.warning("필수 필드 누락으로 스킵: %r", raw)
        return None

    return {
        "title": title,
        "url": url,
        "published_at": normalize_date(raw.get("published_at"), collected_at),
        "category": classify_category(title, categories),
    }
