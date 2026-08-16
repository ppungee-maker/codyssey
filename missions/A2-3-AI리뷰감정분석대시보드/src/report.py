"""dashboard 서브커맨드용 리포트: 품질 지표 + TOP N + AI 추출 결과 (콘솔 + TXT/MD)."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


def check_negative_spike(
    conn: sqlite3.Connection, *, recent_days: int = 7, baseline_days: int = 30,
    threshold_pp: float = 15.0,
) -> dict:
    """보너스: 최근 N일 부정 리뷰 비율이 그 이전 기간 대비 급증했는지 확인한다.

    threshold_pp(퍼센트포인트) 이상 높으면 경고. 데이터가 부족하면 정상으로 간주.
    """
    rows = conn.execute(
        "SELECT c.review_date, s.sentiment FROM clean_reviews c "
        "LEFT JOIN sentiments s ON s.review_id = c.id AND s.id = ("
        "  SELECT MAX(id) FROM sentiments WHERE review_id = c.id) "
        "WHERE c.review_date IS NOT NULL AND s.sentiment IS NOT NULL"
    ).fetchall()
    if not rows:
        return {"triggered": False, "reason": "분석된 리뷰 없음"}

    dates = [date.fromisoformat(r["review_date"]) for r in rows]
    latest = max(dates)
    recent_cutoff = latest - timedelta(days=recent_days)
    baseline_cutoff = latest - timedelta(days=recent_days + baseline_days)

    def ratio(rows_subset):
        total = len(rows_subset)
        if total == 0:
            return None
        neg = sum(1 for r in rows_subset if r["sentiment"] == "부정")
        return neg / total * 100

    recent_rows = [r for r, d in zip(rows, dates) if d > recent_cutoff]
    baseline_rows = [r for r, d in zip(rows, dates) if baseline_cutoff < d <= recent_cutoff]

    recent_ratio = ratio(recent_rows)
    baseline_ratio = ratio(baseline_rows)

    if recent_ratio is None or baseline_ratio is None:
        return {"triggered": False, "reason": "비교할 이전 기간 데이터 부족", "recent_ratio": recent_ratio}

    spike = recent_ratio - baseline_ratio
    return {
        "triggered": spike >= threshold_pp,
        "recent_ratio": round(recent_ratio, 1),
        "baseline_ratio": round(baseline_ratio, 1),
        "spike_pp": round(spike, 1),
        "recent_days": recent_days,
        "baseline_days": baseline_days,
    }


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

    spike = check_negative_spike(conn)
    lines.append("")
    lines.append("## 알림 (보너스: 감정 변화 급증 체크)")
    if spike.get("triggered"):
        lines.append(
            f"- ⚠️ 경고: 최근 {spike['recent_days']}일 부정비율 {spike['recent_ratio']}% "
            f"vs 이전 {spike['baseline_days']}일 {spike['baseline_ratio']}% "
            f"(+{spike['spike_pp']}pt 급증)"
        )
    elif "recent_ratio" in spike and spike.get("baseline_ratio") is not None:
        lines.append(
            f"- 정상 범위: 최근 {spike['recent_days']}일 부정비율 {spike['recent_ratio']}% "
            f"vs 이전 {spike['baseline_days']}일 {spike['baseline_ratio']}%"
        )
    else:
        lines.append(f"- 판단 불가: {spike.get('reason', '데이터 부족')}")

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
