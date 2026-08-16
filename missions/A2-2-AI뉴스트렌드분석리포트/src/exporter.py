"""데이터 내보내기: CSV / JSONL / Excel, --status summarized 필터 지원."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

import pandas as pd


def _query(conn: sqlite3.Connection, status: str | None) -> list[sqlite3.Row]:
    query = "SELECT * FROM clean_news"
    if status == "summarized":
        query += " WHERE summarized = 1"
    query += " ORDER BY collected_at DESC"
    return conn.execute(query).fetchall()


def export(conn: sqlite3.Connection, fmt: str, out_path: Path, *, status: str | None = None) -> int:
    rows = [dict(r) for r in _query(conn, status)]
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
