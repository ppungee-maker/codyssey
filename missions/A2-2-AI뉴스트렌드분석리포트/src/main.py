"""AI 뉴스 트렌드 분석 리포트 CLI.

필수 서브커맨드: fetch, clean, summarize, analyze, report, export
보너스 서브커맨드: list, show, sentiment

    python -m src.main fetch --limit 20
    python -m src.main clean
    python -m src.main summarize --unsummarized
    python -m src.main analyze --category AI
    python -m src.main report
    python -m src.main export --format csv --status summarized
    python -m src.main list --category AI --page 1
    python -m src.main show --id 3
    python -m src.main sentiment --all
"""

from __future__ import annotations

import argparse
import json as json_mod
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import db, report as report_mod
from .ai.mock_provider import MockAnalyzer, MockSentimentAnalyzer, MockSummarizer
from .cleaner import clean_record
from .collectors import crawler, rss_collector
from .config import AppConfig
from .exporter import export as export_data
from .logging_setup import setup_logging
from .visualize import category_distribution, daily_trend, sentiment_distribution

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def cmd_fetch(config: AppConfig, args, logger) -> None:
    now = _now_iso()
    with db.connect(config.db_path) as conn:
        total_new = 0
        if args.method in ("rss", "both"):
            for item in rss_collector.collect(config.rss_url, timeout=config.request_timeout, limit=args.limit):
                _, is_new = db.upsert_raw(
                    conn, url=item["url"], source_name=config.rss_source_name, method="rss",
                    collected_at=now, raw_obj=item, policy=config.dedup_policy,
                )
                total_new += is_new
        if args.method in ("crawl", "both"):
            for item in crawler.collect(config.crawl_url, timeout=config.request_timeout, limit=args.limit):
                _, is_new = db.upsert_raw(
                    conn, url=item["url"], source_name=config.crawl_source_name, method="crawl",
                    collected_at=now, raw_obj=item, policy=config.dedup_policy,
                )
                total_new += is_new
    print(f"[완료] fetch: 신규 {total_new}건 저장 (정책={config.dedup_policy})")


def cmd_clean(config: AppConfig, args, logger) -> None:
    import json as _json

    now = _now_iso()
    cleaned, skipped = 0, 0
    with db.connect(config.db_path) as conn:
        raw_rows = conn.execute("SELECT * FROM raw_news").fetchall()
        for raw in raw_rows:
            raw_obj = _json.loads(raw["raw_json"])
            record = clean_record(raw_obj, collected_at=raw["collected_at"], categories=config.categories)
            if record is None:
                skipped += 1
                continue
            _, is_new = db.upsert_clean(
                conn, raw_id=raw["id"], url=record["url"], title=record["title"],
                category=record["category"], published_at=record["published_at"],
                source_name=raw["source_name"], collected_at=raw["collected_at"],
                policy=config.dedup_policy,
            )
            cleaned += is_new
    print(f"[완료] clean: 신규 정제 {cleaned}건, 필수필드 누락 스킵 {skipped}건")


def cmd_summarize(config: AppConfig, args, logger) -> None:
    summarizer = MockSummarizer()
    now = _now_iso()
    with db.connect(config.db_path) as conn:
        if args.id:
            rows = [r for r in db.fetch_clean(conn) if r["id"] == args.id]
        elif args.all:
            rows = db.fetch_clean(conn)
        else:  # 기본값: unsummarized
            rows = db.fetch_clean(conn, only_unsummarized=True)

        for row in rows:
            try:
                summary = summarizer.summarize(row["title"])
                db.save_summary(conn, news_id=row["id"], summary=summary, created_at=now)
            except Exception as exc:
                logger.error("요약 실패 (id=%s): %s", row["id"], exc)
    print(f"[완료] summarize: {len(rows)}건 처리")


def cmd_analyze(config: AppConfig, args, logger) -> None:
    analyzer = MockAnalyzer()
    now = _now_iso()
    with db.connect(config.db_path) as conn:
        rows = db.fetch_clean(conn, category=args.category)
        titles = [r["title"] for r in rows]
        scope = args.category or "전체"
        result = analyzer.analyze(titles, scope)
        db.save_analysis(conn, scope=scope, result=result, created_at=now)
    print(f"[완료] analyze(scope={scope}): {len(titles)}건 분석 -> {result['trend']}")


def cmd_report(config: AppConfig, args, logger) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with db.connect(config.db_path) as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM clean_news").fetchall()]
        category_distribution(rows, OUTPUT_DIR / "chart_category.png")
        daily_trend(rows, OUTPUT_DIR / "chart_daily_trend.png")
        text = report_mod.build_report(conn)

    ext = "md" if args.format == "md" else "txt"
    out_path = OUTPUT_DIR / f"report.{ext}"
    report_mod.save_report(text, out_path)
    print(text)
    print(f"\n[완료] 리포트 저장: {out_path}, 차트: chart_category.png, chart_daily_trend.png")


def cmd_list(config: AppConfig, args, logger) -> None:
    """보너스: 뉴스 목록 조회 (필터 + 페이지네이션)."""
    page_size = 10
    with db.connect(config.db_path) as conn:
        rows = db.fetch_clean(
            conn, category=args.category, keyword=args.keyword,
            date_from=args.date_from, date_to=args.date_to,
            limit=page_size, offset=(args.page - 1) * page_size,
        )
        total = len(db.fetch_clean(
            conn, category=args.category, keyword=args.keyword,
            date_from=args.date_from, date_to=args.date_to,
        ))
    print(f"총 {total}건 중 {len(rows)}건 (page {args.page})")
    for r in rows:
        print(f"  #{r['id']:<4} [{r['category']}] {r['title'][:50]}")


def cmd_show(config: AppConfig, args, logger) -> None:
    """보너스: 뉴스 상세 조회."""
    with db.connect(config.db_path) as conn:
        row = db.fetch_by_id(conn, args.id)
        if row is None:
            print(f"[에러] id={args.id} 뉴스를 찾을 수 없습니다")
            return
        summary_row = conn.execute(
            "SELECT summary FROM summaries WHERE news_id = ? ORDER BY id DESC LIMIT 1", (args.id,)
        ).fetchone()
    data = dict(row)
    data["summary"] = summary_row["summary"] if summary_row else None
    print(json_mod.dumps(data, ensure_ascii=False, indent=2))


def cmd_sentiment(config: AppConfig, args, logger) -> None:
    """보너스: 뉴스 제목 감성 분석."""
    analyzer = MockSentimentAnalyzer()
    now = _now_iso()
    with db.connect(config.db_path) as conn:
        rows = db.fetch_clean(conn, category=args.category) if args.category else db.fetch_clean(conn)
        for row in rows:
            try:
                sentiment, confidence = analyzer.analyze_sentiment(row["title"])
                db.save_sentiment(conn, news_id=row["id"], sentiment=sentiment,
                                   confidence=confidence, created_at=now)
            except Exception as exc:
                logger.error("감성분석 실패 (id=%s): %s", row["id"], exc)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        all_rows = [dict(r) for r in conn.execute(
            "SELECT c.*, s.sentiment FROM clean_news c LEFT JOIN sentiments s "
            "ON s.news_id = c.id AND s.id = (SELECT MAX(id) FROM sentiments WHERE news_id = c.id)"
        ).fetchall()]
    sentiment_distribution(all_rows, OUTPUT_DIR / "chart_sentiment.png")
    print(f"[완료] sentiment: {len(rows)}건 분석 -> chart_sentiment.png")


def cmd_export(config: AppConfig, args, logger) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ext = {"csv": "csv", "jsonl": "jsonl", "excel": "xlsx"}[args.format]
    out_path = OUTPUT_DIR / f"export.{ext}"
    with db.connect(config.db_path) as conn:
        n = export_data(conn, args.format, out_path, status=args.status)
    print(f"[완료] export({args.format}, status={args.status}): {n}건 -> {out_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI 뉴스 트렌드 분석 리포트 CLI")
    parser.add_argument("--config", type=Path, default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch", help="RSS/크롤링으로 뉴스 수집")
    p_fetch.add_argument("--limit", type=int, default=20)
    p_fetch.add_argument("--method", choices=["rss", "crawl", "both"], default="both")
    p_fetch.set_defaults(func=cmd_fetch)

    p_clean = sub.add_parser("clean", help="raw_news -> clean_news 정제")
    p_clean.set_defaults(func=cmd_clean)

    p_sum = sub.add_parser("summarize", help="AI 요약")
    group = p_sum.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true")
    group.add_argument("--id", type=int)
    group.add_argument("--unsummarized", action="store_true", default=True)
    p_sum.set_defaults(func=cmd_summarize)

    p_analyze = sub.add_parser("analyze", help="AI 종합 인사이트 분석")
    p_analyze.add_argument("--category", type=str, default=None)
    p_analyze.add_argument("--date", type=str, default=None, help="(예약 옵션 — 현재는 category만 스코프)")
    p_analyze.set_defaults(func=cmd_analyze)

    p_report = sub.add_parser("report", help="리포트 + 차트 생성")
    p_report.add_argument("--format", choices=["md", "txt"], default="md")
    p_report.set_defaults(func=cmd_report)

    p_export = sub.add_parser("export", help="데이터 내보내기")
    p_export.add_argument("--format", choices=["csv", "jsonl", "excel"], default="csv")
    p_export.add_argument("--status", choices=["summarized"], default=None)
    p_export.set_defaults(func=cmd_export)

    p_list = sub.add_parser("list", help="[보너스] 뉴스 목록 조회")
    p_list.add_argument("--category", type=str, default=None)
    p_list.add_argument("--keyword", type=str, default=None)
    p_list.add_argument("--date-from", type=str, default=None)
    p_list.add_argument("--date-to", type=str, default=None)
    p_list.add_argument("--page", type=int, default=1)
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="[보너스] 뉴스 상세 조회")
    p_show.add_argument("--id", type=int, required=True)
    p_show.set_defaults(func=cmd_show)

    p_sentiment = sub.add_parser("sentiment", help="[보너스] 뉴스 감성 분석 + 시각화")
    p_sentiment.add_argument("--category", type=str, default=None, help="지정 시 해당 카테고리만, 미지정 시 전체")
    p_sentiment.set_defaults(func=cmd_sentiment)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logger = setup_logging()
    config = AppConfig.load(args.config)
    args.func(config, args, logger)
    return 0


if __name__ == "__main__":
    sys.exit(main())
