"""CSV/Excel 파일에서 리뷰 데이터를 읽어 raw_reviews에 저장.

필수 필드: review_text (컬럼명 review_text/리뷰/content 등 흔한 별칭도 인식).
선택 필드: rating(1~5), date, product_name.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

logger = logging.getLogger("review_pipeline")

_TEXT_ALIASES = ["review_text", "review", "content", "text", "리뷰", "내용"]
_RATING_ALIASES = ["rating", "star", "score", "별점"]
_DATE_ALIASES = ["date", "review_date", "작성일", "날짜"]
_PRODUCT_ALIASES = ["product_name", "product", "제품명", "제품"]
_ID_ALIASES = ["review_id", "id"]


def _find_column(columns: list[str], aliases: list[str]) -> str | None:
    lowered = {c.lower(): c for c in columns}
    for alias in aliases:
        if alias.lower() in lowered:
            return lowered[alias.lower()]
    return None


def load_file(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(path)
    return pd.read_csv(path)


def import_reviews(conn, path: Path) -> tuple[int, int]:
    """(raw 저장 건수, 필수필드 누락으로 스킵된 건수) 반환."""
    from . import db  # 지연 import로 순환참조 방지

    if not path.exists():
        raise FileNotFoundError(f"리뷰 파일을 찾을 수 없습니다: {path}")

    df = load_file(path)
    columns = list(df.columns)
    text_col = _find_column(columns, _TEXT_ALIASES)
    if text_col is None:
        raise ValueError(f"필수 필드(리뷰 텍스트) 컬럼을 찾을 수 없습니다. 실제 컬럼: {columns}")

    rating_col = _find_column(columns, _RATING_ALIASES)
    date_col = _find_column(columns, _DATE_ALIASES)
    product_col = _find_column(columns, _PRODUCT_ALIASES)
    id_col = _find_column(columns, _ID_ALIASES)

    now = datetime.now(timezone.utc).isoformat()
    saved, skipped = 0, 0
    for _, row in df.iterrows():
        text = row.get(text_col)
        if pd.isna(text) or not str(text).strip():
            skipped += 1
            continue
        raw_obj = row.dropna().to_dict()
        db.insert_raw(
            conn,
            source_review_id=row.get(id_col) if id_col else None,
            review_text=str(text),
            rating=row.get(rating_col) if rating_col else None,
            review_date=str(row.get(date_col)) if date_col and not pd.isna(row.get(date_col)) else None,
            product_name=str(row.get(product_col)) if product_col and not pd.isna(row.get(product_col)) else None,
            imported_at=now,
            raw_obj={k: str(v) for k, v in raw_obj.items()},
        )
        saved += 1

    logger.info("import 완료: %d건 저장, %d건 스킵 (%s)", saved, skipped, path)
    return saved, skipped
