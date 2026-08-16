"""품질 지표 + TOP N 집계 + AI 인사이트를 묶은 리포트 생성 (콘솔 + TXT/MD)."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def build_report(conn: sqlite3.Connection) -> str:
    raw_count = conn.execute("SELECT COUNT(*) FROM raw_news").fetchone()[0]
    clean_count = conn.execute("SELECT COUNT(*) FROM clean_news").fetchone()[0]
    summarized_count = conn.execute(
        "SELECT COUNT(*) FROM clean_news WHERE summarized = 1"
    ).fetchone()[0]

    clean_rate = (clean_count / raw_count * 100) if raw_count else 0.0
    summary_rate = (summarized_count / clean_count * 100) if clean_count else 0.0

    cats = conn.execute("SELECT category FROM clean_news").fetchall()
    top_categories = Counter(r["category"] for r in cats).most_common(5)

    latest_analysis_row = conn.execute(
        "SELECT * FROM analyses ORDER BY id DESC LIMIT 1"
    ).fetchone()
    analysis = json.loads(latest_analysis_row["result_json"]) if latest_analysis_row else None

    lines = [
        "# 뉴스 트렌드 분석 리포트",
        f"생성 시각: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## 품질 지표",
        f"- 총 수집(raw) 건수: {raw_count}",
        f"- 정제 성공률(clean/raw): {clean_rate:.1f}%",
        f"- 요약 완료율(summarized/clean): {summary_rate:.1f}%",
        "",
        "## TOP 5 카테고리",
    ]
    for cat, cnt in top_categories:
        lines.append(f"- {cat}: {cnt}건")

    lines.append("")
    lines.append("## AI 인사이트")
    if analysis:
        lines.append(f"- 트렌드: {analysis['trend']}")
        lines.append(f"- 핵심 키워드: {', '.join(analysis['keywords'])}")
        lines.append(f"- 공통점/차이점: {analysis['common_or_diff']}")
        lines.append(f"- 시사점: {analysis['implications']}")
    else:
        lines.append("- (아직 `analyze` 서브커맨드를 실행하지 않았습니다)")

    return "\n".join(lines)


def save_report(text: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
