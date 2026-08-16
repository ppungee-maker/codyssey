"""SQLite 저장소 — raw/clean 리뷰 분리 저장 + 감정분석/키워드추출 결과.

요구사항 11: 메모리(list/dict)만으로 관리하지 않고 반드시 영구 저장소를 쓴다.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_review_id TEXT,
    review_text TEXT NOT NULL,
    rating TEXT,
    review_date TEXT,
    product_name TEXT,
    imported_at TEXT NOT NULL,
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clean_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_id INTEGER NOT NULL REFERENCES raw_reviews(id),
    dedup_key TEXT NOT NULL UNIQUE,
    review_text TEXT NOT NULL,
    rating INTEGER,
    review_date TEXT,
    product_name TEXT,
    imported_at TEXT NOT NULL,
    analyzed INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sentiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id INTEGER NOT NULL REFERENCES clean_reviews(id),
    sentiment TEXT NOT NULL,       -- 긍정 | 부정 | 중립
    confidence REAL NOT NULL,      -- 0.0 ~ 1.0
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS extracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


@contextmanager
def connect(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def insert_raw(conn: sqlite3.Connection, *, source_review_id, review_text: str, rating,
                review_date, product_name, imported_at: str, raw_obj: dict) -> int:
    cur = conn.execute(
        "INSERT INTO raw_reviews (source_review_id, review_text, rating, review_date, "
        "product_name, imported_at, raw_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(source_review_id) if source_review_id is not None else None, review_text,
         str(rating) if rating is not None else None, review_date, product_name, imported_at,
         json.dumps(raw_obj, ensure_ascii=False)),
    )
    return cur.lastrowid


def upsert_clean(conn: sqlite3.Connection, *, raw_id: int, dedup_key: str, review_text: str,
                  rating: int | None, review_date: str | None, product_name: str | None,
                  imported_at: str, policy: str) -> tuple[int, bool]:
    cur = conn.execute("SELECT id FROM clean_reviews WHERE dedup_key = ?", (dedup_key,))
    row = cur.fetchone()
    if row:
        if policy == "upsert":
            conn.execute(
                "UPDATE clean_reviews SET raw_id=?, review_text=?, rating=?, review_date=?, "
                "product_name=?, imported_at=? WHERE id=?",
                (raw_id, review_text, rating, review_date, product_name, imported_at, row["id"]),
            )
        return row["id"], False

    cur = conn.execute(
        "INSERT INTO clean_reviews (raw_id, dedup_key, review_text, rating, review_date, "
        "product_name, imported_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (raw_id, dedup_key, review_text, rating, review_date, product_name, imported_at),
    )
    return cur.lastrowid, True


def fetch_clean(conn: sqlite3.Connection, *, only_unanalyzed: bool = False,
                 sentiment: str | None = None, rating: int | None = None,
                 date_from: str | None = None, date_to: str | None = None,
                 order_by: str = "review_date DESC", limit: int | None = None,
                 offset: int = 0) -> list[sqlite3.Row]:
    query = (
        "SELECT c.*, s.sentiment, s.confidence FROM clean_reviews c "
        "LEFT JOIN sentiments s ON s.review_id = c.id AND s.id = ("
        "  SELECT MAX(id) FROM sentiments WHERE review_id = c.id) WHERE 1=1"
    )
    params: list = []
    if only_unanalyzed:
        query += " AND c.analyzed = 0"
    if sentiment:
        query += " AND s.sentiment = ?"
        params.append(sentiment)
    if rating:
        query += " AND c.rating = ?"
        params.append(rating)
    if date_from:
        query += " AND c.review_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND c.review_date <= ?"
        params.append(date_to)
    query += f" ORDER BY {order_by}"
    if limit:
        query += " LIMIT ? OFFSET ?"
        params += [limit, offset]
    return conn.execute(query, params).fetchall()


def save_sentiment(conn: sqlite3.Connection, *, review_id: int, sentiment: str,
                    confidence: float, created_at: str) -> None:
    conn.execute(
        "INSERT INTO sentiments (review_id, sentiment, confidence, created_at) VALUES (?, ?, ?, ?)",
        (review_id, sentiment, confidence, created_at),
    )
    conn.execute("UPDATE clean_reviews SET analyzed = 1 WHERE id = ?", (review_id,))


def save_extract(conn: sqlite3.Connection, *, scope: str, result: dict, created_at: str) -> None:
    conn.execute(
        "INSERT INTO extracts (scope, result_json, created_at) VALUES (?, ?, ?)",
        (scope, json.dumps(result, ensure_ascii=False), created_at),
    )
