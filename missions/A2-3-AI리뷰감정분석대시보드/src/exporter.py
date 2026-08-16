"""데이터 내보내기: CSV / JSONL / Excel, --sentiment / --rating-min 필터 지원."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

import pandas as pd


def _query(conn: sqlite3.Connection, sentiment: str | None, rating_min: int | None) -> list[dict]:
    query = (
        "SELECT c.*, s.sentiment, s.confidence FROM clean_reviews c "
        "LEFT JOIN sentiments s ON s.review_id = c.id AND s.id = ("
        "  SELECT MAX(id) FROM sentiments WHERE review_id = c.id) WHERE 1=1"
    )
    params: list = []
    if sentiment:
        query += " AND s.sentiment = ?"
        params.append(sentiment)
    if rating_min:
        query += " AND c.rating >= ?"
        params.append(rating_min)
    query += " ORDER BY c.review_date DESC"
    return [dict(r) for r in conn.execute(query, params).fetchall()]


def export(conn: sqlite3.Connection, fmt: str, out_path: Path, *, sentiment: str | None = None,
           rating_min: int | None = None) -> int:
    rows = _query(conn, sentiment, rating_min)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "csv":
        with out_path.open("w", newline="", encoding="utf-8-sig") as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
    elif fmt == "jsonl":
        with out_path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    elif fmt == "excel":
        pd.DataFrame(rows).to_excel(out_path, index=False)
    else:
        raise ValueError(f"지원하지 않는 포맷: {fmt}")

    return len(rows)
