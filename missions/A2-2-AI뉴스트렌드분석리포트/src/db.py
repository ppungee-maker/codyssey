"""SQLite 저장소 — raw/clean 뉴스 분리 저장 + 요약/분석 결과.

요구사항 10: 메모리(list/dict)만으로 관리하지 않고 반드시 영구 저장소를 쓴다.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    source_name TEXT NOT NULL,
    collect_method TEXT NOT NULL,   -- 'rss' | 'crawl'
    collected_at TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    UNIQUE(url, collect_method)
);

CREATE TABLE IF NOT EXISTS clean_news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_id INTEGER NOT NULL REFERENCES raw_news(id),
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    published_at TEXT,
    source_name TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    summarized INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_id INTEGER NOT NULL REFERENCES clean_news(id),
    summary TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sentiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_id INTEGER NOT NULL REFERENCES clean_news(id),
    sentiment TEXT NOT NULL,   -- 긍정 | 부정 | 중립
    confidence REAL NOT NULL,
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


def upsert_raw(conn: sqlite3.Connection, *, url: str, source_name: str, method: str,
                collected_at: str, raw_obj: dict, policy: str) -> tuple[int, bool]:
    """raw_news에 insert. (row_id, is_new) 반환. policy='skip'이면 기존 행 유지, 'upsert'면 갱신."""
    cur = conn.execute(
        "SELECT id FROM raw_news WHERE url = ? AND collect_method = ?", (url, method)
    )
    row = cur.fetchone()
    if row:
        if policy == "upsert":
            conn.execute(
                "UPDATE raw_news SET source_name=?, collected_at=?, raw_json=? WHERE id=?",
                (source_name, collected_at, json.dumps(raw_obj, ensure_ascii=False), row["id"]),
            )
        return row["id"], False

    cur = conn.execute(
        "INSERT INTO raw_news (url, source_name, collect_method, collected_at, raw_json) "
        "VALUES (?, ?, ?, ?, ?)",
        (url, source_name, method, collected_at, json.dumps(raw_obj, ensure_ascii=False)),
    )
    return cur.lastrowid, True


def upsert_clean(conn: sqlite3.Connection, *, raw_id: int, url: str, title: str, category: str,
                  published_at: str | None, source_name: str, collected_at: str,
                  policy: str) -> tuple[int, bool]:
    cur = conn.execute("SELECT id FROM clean_news WHERE url = ?", (url,))
    row = cur.fetchone()
    if row:
        if policy == "upsert":
            conn.execute(
                "UPDATE clean_news SET raw_id=?, title=?, category=?, published_at=?, "
                "source_name=?, collected_at=? WHERE id=?",
                (raw_id, title, category, published_at, source_name, collected_at, row["id"]),
            )
        return row["id"], False

    cur = conn.execute(
        "INSERT INTO clean_news (raw_id, url, title, category, published_at, source_name, "
        "collected_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (raw_id, url, title, category, published_at, source_name, collected_at),
    )
    return cur.lastrowid, True


def fetch_clean(conn: sqlite3.Connection, *, only_unsummarized: bool = False,
                 category: str | None = None, keyword: str | None = None,
                 date_from: str | None = None, date_to: str | None = None,
                 limit: int | None = None, offset: int = 0) -> list[sqlite3.Row]:
    query = "SELECT * FROM clean_news WHERE 1=1"
    params: list = []
    if only_unsummarized:
        query += " AND summarized = 0"
    if category:
        query += " AND category = ?"
        params.append(category)
    if keyword:
        query += " AND title LIKE ?"
        params.append(f"%{keyword}%")
    if date_from:
        query += " AND collected_at >= ?"
        params.append(date_from)
    if date_to:
        query += " AND collected_at <= ?"
        params.append(date_to)
    query += " ORDER BY collected_at DESC"
    if limit:
        query += " LIMIT ? OFFSET ?"
        params += [limit, offset]
    return conn.execute(query, params).fetchall()


def fetch_by_id(conn: sqlite3.Connection, news_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT c.*, s.sentiment, s.confidence FROM clean_news c "
        "LEFT JOIN sentiments s ON s.news_id = c.id AND s.id = ("
        "  SELECT MAX(id) FROM sentiments WHERE news_id = c.id) WHERE c.id = ?",
        (news_id,),
    ).fetchone()


def save_sentiment(conn: sqlite3.Connection, *, news_id: int, sentiment: str,
                    confidence: float, created_at: str) -> None:
    conn.execute(
        "INSERT INTO sentiments (news_id, sentiment, confidence, created_at) VALUES (?, ?, ?, ?)",
        (news_id, sentiment, confidence, created_at),
    )


def save_summary(conn: sqlite3.Connection, *, news_id: int, summary: str, created_at: str) -> None:
    conn.execute(
        "INSERT INTO summaries (news_id, summary, created_at) VALUES (?, ?, ?)",
        (news_id, summary, created_at),
    )
    conn.execute("UPDATE clean_news SET summarized = 1 WHERE id = ?", (news_id,))


def save_analysis(conn: sqlite3.Connection, *, scope: str, result: dict, created_at: str) -> None:
    conn.execute(
        "INSERT INTO analyses (scope, result_json, created_at) VALUES (?, ?, ?)",
        (scope, json.dumps(result, ensure_ascii=False), created_at),
    )
