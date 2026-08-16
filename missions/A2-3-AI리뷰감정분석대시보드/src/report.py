"""dashboard 서브커맨드용 리포트: 품질 지표 + TOP N + AI 추출 결과 (콘솔 + TXT/MD)."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def build_report(conn: sqlite3.Connection) -> str:
    raw_count = conn.execute("SELECT COUNT(*) FROM raw_reviews").fetchone()[0]
    clean_count = conn.execute("SELECT COUNT(*) FROM clean_reviews").fetchone()[0]
    analyzed_count = conn.execute(
        "SELECT COUNT(*) FROM clean_reviews WHERE analyzed = 1"
    ).fetchone()[0]

    clean_rate = (clean_count / raw_count * 100) if raw_count else 0.0
    analyzed_rate = (analyzed_count / clean_count * 100) if clean_count else 0.0

    rows = conn.execute(
        "SELECT product_name, rating FROM clean_reviews WHERE product_name IS NOT NULL AND rating IS NOT NULL"
    ).fetchall()
    by_product = defaultdict(list)
    for r in rows:
        by_product[r["product_name"]].append(r["rating"])
    top_products = sorted(
        ((name, sum(rs) / len(rs), len(rs)) for name, rs in by_product.items()),
        key=lambda x: x[1],
    )[:3]

    latest_extract_row = conn.execute(
        "SELECT * FROM extracts ORDER BY id DESC LIMIT 1"
    ).fetchone()
    extract = json.loads(latest_extract_row["result_json"]) if latest_extract_row else None

    lines = [
        "# 리뷰 감정 분석 대시보드 리포트",
        f"생성 시각: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## 품질 지표",
        f"- 총 수집(raw) 건수: {raw_count}",
        f"- 정제 성공률(clean/raw): {clean_rate:.1f}%",
        f"- 감정분석 완료율(analyzed/clean): {analyzed_rate:.1f}%",
        "",
        "## TOP 3 개선 필요 제품 (평균 별점 낮은 순)",
    ]
    for name, avg, cnt in top_products:
        lines.append(f"- {name}: 평균 {avg:.2f}점 ({cnt}건)")

    lines.append("")
    lines.append("## AI 추출 결과")
    if extract:
        lines.append(f"- 긍정 키워드: {', '.join(extract['positive_keywords']) or '없음'}")
        lines.append(f"- 부정 키워드: {', '.join(extract['negative_keywords']) or '없음'}")
        lines.append(f"- 요약: {extract['summary']}")
        lines.append(f"- 개선 제안: {extract['suggestions']}")
    else:
        lines.append("- (아직 `extract` 서브커맨드를 실행하지 않았습니다)")

    return "\n".join(lines)


def save_report(text: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
