"""설정 파일(config.json) 로드 — API 키, 뉴스 소스, 중복 정책 등."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "config.json"


@dataclass
class AppConfig:
    rss_url: str = "https://feeds.bbci.co.uk/news/technology/rss.xml"
    rss_source_name: str = "BBC Technology"
    crawl_url: str = "https://news.ycombinator.com/"
    crawl_source_name: str = "Hacker News"
    dedup_policy: str = "skip"  # "skip" | "upsert"
    ai_api_key: str | None = None
    ai_provider: str = "mock"
    db_path: Path = ROOT / "data" / "news.db"
    request_timeout: float = 10.0
    categories: dict[str, list[str]] = field(
        default_factory=lambda: {
            "AI": ["ai", "artificial intelligence", "openai", "chatgpt", "llm"],
            "보안": ["security", "hack", "breach", "cyber", "malware"],
            "스타트업": ["startup", "funding", "raise", "series a", "series b"],
            "빅테크": ["apple", "google", "microsoft", "amazon", "meta"],
        }
    )

    @classmethod
    def load(cls, config_path: Path | None = None) -> "AppConfig":
        path = config_path or DEFAULT_CONFIG_PATH
        data: dict = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                print(f"[경고] 설정 파일 파싱 실패, 기본값 사용: {path}")

        cfg = cls()
        for key in (
            "rss_url", "rss_source_name", "crawl_url", "crawl_source_name",
            "dedup_policy", "ai_provider",
        ):
            if key in data:
                setattr(cfg, key, data[key])
        if "db_path" in data:
            cfg.db_path = ROOT / data["db_path"]
        cfg.ai_api_key = os.environ.get("AI_API_KEY") or data.get("ai_api_key")
        return cfg
