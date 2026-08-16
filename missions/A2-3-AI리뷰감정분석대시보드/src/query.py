"""list/show/stats 서브커맨드가 쓰는 조회 로직."""

from __future__ import annotations

import sqlite3
from collections import Counter

from . import db


def list_reviews(conn: sqlite3.Connection, *, sentiment=None, rating=None, date_from=None,
                  date_to=None, sort: str = "date_desc", page: int = 1, page_size: int = 10):
    order_map = {
        "date_desc": "review_date DESC",
        "date_asc": "review_date ASC",
        "rating_desc": "rating DESC",
        "rating_asc": "rating ASC",
    }
    order_by = order_map.get(sort, "review_date DESC")
    offset = (page - 1) * page_size
    rows = db.fetch_clean(
        conn, sentiment=sentiment, rating=rating, date_from=date_from, date_to=date_to,
        order_by=order_by, limit=page_size, offset=offset,
    )
    total = len(db.fetch_clean(conn, sentiment=sentiment, rating=rating, date_from=date_from, date_to=date_to))
    return rows, total


def show_review(conn: sqlite3.Connection, review_id: int) -> sqlite3.Row | None:
    row = conn.execute(
        "SELECT c.*, s.sentiment, s.confidence FROM clean_reviews c "
        "LEFT JOIN sentiments s ON s.review_id = c.id AND s.id = ("
        "  SELECT MAX(id) FROM sentiments WHERE review_id = c.id) WHERE c.id = ?",
        (review_id,),
    ).fetchone()
    return row


def compute_stats(conn: sqlite3.Connection) -> dict:
    rows = db.fetch_clean(conn)
    total = len(rows)
    sentiments = Counter(r["sentiment"] for r in rows if r["sentiment"])
    ratings = [r["rating"] for r in rows if r["rating"] is not None]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0.0

    return {
        "total_reviews": total,
        "sentiment_ratio": {
            k: round(v / total * 100, 1) if total else 0.0 for k, v in sentiments.items()
        },
        "sentiment_count": dict(sentiments),
        "average_rating": round(avg_rating, 2),
        "rated_count": len(ratings),
    }


def compare_products(conn: sqlite3.Connection) -> list[dict]:
    """보너스: 제품별 리뷰 건수/평균 별점/감정 비율을 비교한다."""
    rows = db.fetch_clean(conn)
    by_product: dict[str, list] = {}
    for r in rows:
        name = r["product_name"] or "(제품 미지정)"
        by_product.setdefault(name, []).append(r)

    results = []
    for name, product_rows in by_product.items():
        ratings = [r["rating"] for r in product_rows if r["rating"] is not None]
        sentiments = Counter(r["sentiment"] for r in product_rows if r["sentiment"])
        total = len(product_rows)
        results.append({
            "product_name": name,
            "review_count": total,
            "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
            "sentiment_ratio": {
                k: round(v / total * 100, 1) if total else 0.0 for k, v in sentiments.items()
            },
        })
    return sorted(results, key=lambda x: x["average_rating"] or 0)
