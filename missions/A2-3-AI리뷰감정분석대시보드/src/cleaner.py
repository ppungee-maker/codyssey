"""정제 규칙: 필수필드 검증, 텍스트 정규화, 별점 범위 검증, 날짜 형식 통일, 짧은 리뷰 필터링."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime

logger = logging.getLogger("review_pipeline")


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def validate_rating(raw_rating) -> int | None:
    if raw_rating is None or str(raw_rating).strip() in ("", "nan", "None"):
        return None
    try:
        rating = int(float(raw_rating))
    except (TypeError, ValueError):
        logger.warning("별점 파싱 실패: %r", raw_rating)
        return None
    if not (1 <= rating <= 5):
        logger.warning("별점 범위 초과(1~5 아님), 제외: %r", raw_rating)
        return None
    return rating


def normalize_date(raw_date: str | None) -> str | None:
    if not raw_date or str(raw_date).strip() in ("", "nan", "None"):
        return None
    raw_date = str(raw_date).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw_date[: len(fmt) + 2], fmt).date().isoformat()
        except ValueError:
            continue
    logger.warning("날짜 형식 인식 실패, 원본 보존: %r", raw_date)
    return raw_date


def dedup_key(review_text: str, product_name: str | None) -> str:
    raw = f"{review_text.strip()}|{(product_name or '').strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def clean_review(raw_row, *, min_length: int) -> dict | None:
    """raw_reviews 한 행을 정제. 필수필드 누락/너무 짧은 리뷰는 None(스킵)."""
    text = normalize_text(raw_row["review_text"])
    if not text:
        logger.warning("리뷰 텍스트 없음, 스킵 (raw_id=%s)", raw_row["id"])
        return None
    if len(text) < min_length:
        logger.info("짧은 리뷰 필터링(len=%d < %d), 스킵 (raw_id=%s)", len(text), min_length, raw_row["id"])
        return None

    return {
        "review_text": text,
        "rating": validate_rating(raw_row["rating"]),
        "review_date": normalize_date(raw_row["review_date"]),
        "product_name": (raw_row["product_name"] or "").strip() or None,
        "dedup_key": dedup_key(text, raw_row["product_name"]),
    }
