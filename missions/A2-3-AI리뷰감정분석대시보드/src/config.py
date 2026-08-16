"""설정 파일(config.json) 로드 — API 키, 중복 정책, 시각화 옵션 등."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT / "config.json"


@dataclass
class AppConfig:
    dedup_policy: str = "skip"  # "skip" | "upsert"
    min_review_length: int = 5
    ai_provider: str = "mock"
    ai_api_key: str | None = None
    db_path: Path = ROOT / "data" / "reviews.db"
    page_size: int = 10

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
        for key in ("dedup_policy", "min_review_length", "ai_provider", "page_size"):
            if key in data:
                setattr(cfg, key, data[key])
        if "db_path" in data:
            cfg.db_path = ROOT / data["db_path"]
        cfg.ai_api_key = os.environ.get("AI_API_KEY") or data.get("ai_api_key")
        return cfg
