"""AI 리뷰 감정 분석 대시보드 CLI.

서브커맨드: import, clean, analyze, extract, list, show, stats, dashboard, export

    python -m src.main import --file sample_data/reviews_sample.csv
    python -m src.main clean
    python -m src.main analyze --all
    python -m src.main extract
    python -m src.main list --sentiment 부정 --rating 1
    python -m src.main show --id 3
    python -m src.main stats
    python -m src.main dashboard
    python -m src.main export --format csv --sentiment 부정
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import db, query
from . import report as report_mod
from .ai.mock_provider import MockExtractor, MockSentimentAnalyzer
from .cleaner import clean_review
from .config import AppConfig
from .exporter import export as export_data
from .importer import import_reviews
from .logging_setup import setup_logging
from .visualize import rating_sentiment_correlation, sentiment_distribution, sentiment_trend

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def cmd_import(config: AppConfig, args, logger) -> None:
    with db.connect(config.db_path) as conn:
        saved, skipped = import_reviews(conn, args.file)
    print(f"[완료] import: raw {saved}건 저장, 필수필드 누락 {skipped}건 스킵")


def cmd_clean(config: AppConfig, args, logger) -> None:
    cleaned, skipped = 0, 0
    with db.connect(config.db_path) as conn:
        raw_rows = conn.execute("SELECT * FROM raw_reviews").fetchall()
        for raw in raw_rows:
            record = clean_review(raw, min_length=config.min_review_length)
            if record is None:
                skipped += 1
                continue
            _, is_new = db.upsert_clean(
                conn, raw_id=raw["id"], dedup_key=record["dedup_key"],
                review_text=record["review_text"], rating=record["rating"],
                review_date=record["review_date"], product_name=record["product_name"],
                imported_at=raw["imported_at"], policy=config.dedup_policy,
            )
            cleaned += is_new
    print(f"[완료] clean: 신규 정제 {cleaned}건, 필수필드/짧은리뷰 스킵 {skipped}건")


def cmd_analyze(config: AppConfig, args, logger) -> None:
    analyzer = MockSentimentAnalyzer()
    now = _now_iso()
    with db.connect(config.db_path) as conn:
        if args.id:
            rows = [r for r in db.fetch_clean(conn) if r["id"] == args.id]
        elif args.all:
            rows = db.fetch_clean(conn)
        else:  # 기본값: unanalyzed
            rows = db.fetch_clean(conn, only_unanalyzed=True)

        for row in rows:
            try:
                sentiment, confidence = analyzer.analyze(row["review_text"])
                db.save_sentiment(conn, review_id=row["id"], sentiment=sentiment,
                                   confidence=confidence, created_at=now)
            except Exception as exc:
                logger.error("감정분석 실패 (id=%s): %s", row["id"], exc)
    print(f"[완료] analyze: {len(rows)}건 처리")


def cmd_extract(config: AppConfig, args, logger) -> None:
    extractor = MockExtractor()
    now = _now_iso()
    with db.connect(config.db_path) as conn:
        rows = db.fetch_clean(
            conn, sentiment=args.sentiment, date_from=args.date_from, date_to=args.date_to,
        )
        if args.product:
            rows = [r for r in rows if r["product_name"] == args.product]
        reviews = [dict(r) for r in rows]
        scope = args.product or args.sentiment or "전체"
        result = extractor.extract(reviews, scope)
        db.save_extract(conn, scope=scope, result=result, created_at=now)
    print(f"[완료] extract(scope={scope}): {len(reviews)}건 -> {result['summary']}")


def cmd_list(config: AppConfig, args, logger) -> None:
    with db.connect(config.db_path) as conn:
        rows, total = query.list_reviews(
            conn, sentiment=args.sentiment, rating=args.rating, date_from=args.date_from,
            date_to=args.date_to, sort=args.sort, page=args.page, page_size=config.page_size,
        )
    print(f"총 {total}건 중 {len(rows)}건 (page {args.page}, page_size {config.page_size})")
    for r in rows:
        print(f"  #{r['id']:<4} [{r['sentiment'] or '-'}] ({r['rating'] or '-'}점) {r['review_text'][:40]}")


def cmd_show(config: AppConfig, args, logger) -> None:
    with db.connect(config.db_path) as conn:
        row = query.show_review(conn, args.id)
    if row is None:
        print(f"[에러] id={args.id} 리뷰를 찾을 수 없습니다")
        return
    print(json.dumps(dict(row), ensure_ascii=False, indent=2))


def cmd_stats(config: AppConfig, args, logger) -> None:
    with db.connect(config.db_path) as conn:
        stats = query.compute_stats(conn)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


def cmd_dashboard(config: AppConfig, args, logger) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with db.connect(config.db_path) as conn:
        rows = [dict(r) for r in db.fetch_clean(conn)]
        sentiment_distribution(rows, OUTPUT_DIR / "chart_sentiment.png")
        sentiment_trend(rows, OUTPUT_DIR / "chart_trend.png")
        rating_sentiment_correlation(rows, OUTPUT_DIR / "chart_rating_sentiment.png")
        text = report_mod.build_report(conn)

    out_path = OUTPUT_DIR / "dashboard_report.md"
    report_mod.save_report(text, out_path)
    print(text)
    print(f"\n[완료] 대시보드: chart_sentiment.png, chart_trend.png, chart_rating_sentiment.png, {out_path.name}")


def cmd_export(config: AppConfig, args, logger) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ext = {"csv": "csv", "jsonl": "jsonl", "excel": "xlsx"}[args.format]
    out_path = OUTPUT_DIR / f"export.{ext}"
    with db.connect(config.db_path) as conn:
        n = export_data(conn, args.format, out_path, sentiment=args.sentiment, rating_min=args.rating_min)
    print(f"[완료] export({args.format}): {n}건 -> {out_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI 리뷰 감정 분석 대시보드 CLI")
    parser.add_argument("--config", type=Path, default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    p_import = sub.add_parser("import", help="CSV/Excel 리뷰 파일 가져오기")
    p_import.add_argument("--file", type=Path, required=True)
    p_import.set_defaults(func=cmd_import)

    p_clean = sub.add_parser("clean", help="raw -> clean 정제")
    p_clean.set_defaults(func=cmd_clean)

    p_analyze = sub.add_parser("analyze", help="AI 감정 분석")
    group = p_analyze.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true")
    group.add_argument("--id", type=int)
    group.add_argument("--unanalyzed", action="store_true", default=True)
    p_analyze.set_defaults(func=cmd_analyze)

    p_extract = sub.add_parser("extract", help="키워드/요약/개선제안 추출")
    p_extract.add_argument("--sentiment", choices=["긍정", "부정", "중립"], default=None)
    p_extract.add_argument("--product", type=str, default=None)
    p_extract.add_argument("--date-from", type=str, default=None)
    p_extract.add_argument("--date-to", type=str, default=None)
    p_extract.set_defaults(func=cmd_extract)

    p_list = sub.add_parser("list", help="리뷰 목록 조회")
    p_list.add_argument("--sentiment", choices=["긍정", "부정", "중립"], default=None)
    p_list.add_argument("--rating", type=int, default=None)
    p_list.add_argument("--date-from", type=str, default=None)
    p_list.add_argument("--date-to", type=str, default=None)
    p_list.add_argument("--sort", choices=["date_desc", "date_asc", "rating_desc", "rating_asc"], default="date_desc")
    p_list.add_argument("--page", type=int, default=1)
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="리뷰 상세 조회")
    p_show.add_argument("--id", type=int, required=True)
    p_show.set_defaults(func=cmd_show)

    p_stats = sub.add_parser("stats", help="전체 통계 요약")
    p_stats.set_defaults(func=cmd_stats)

    p_dashboard = sub.add_parser("dashboard", help="차트 3종 + 리포트 생성")
    p_dashboard.set_defaults(func=cmd_dashboard)

    p_export = sub.add_parser("export", help="데이터 내보내기")
    p_export.add_argument("--format", choices=["csv", "jsonl", "excel"], default="csv")
    p_export.add_argument("--sentiment", choices=["긍정", "부정", "중립"], default=None)
    p_export.add_argument("--rating-min", type=int, default=None)
    p_export.set_defaults(func=cmd_export)

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
