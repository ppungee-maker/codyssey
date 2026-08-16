"""API 키/프로바이더 설정 — 코드에 키를 직접 쓰지 않고 env/설정파일에서 읽는다."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


@dataclass
class AppConfig:
    provider: str = "mock"  # "mock" | "openai"
    openai_api_key: str | None = None

    @classmethod
    def load(cls, config_path: Path | None = None) -> "AppConfig":
        path = config_path or DEFAULT_CONFIG_PATH
        data: dict = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                print(f"[경고] 설정 파일 파싱 실패, 기본값 사용: {path}")

        provider = os.environ.get("BRAND_PROVIDER") or data.get("provider") or "mock"
        api_key = os.environ.get("OPENAI_API_KEY") or data.get("openai_api_key")
        return cls(provider=provider, openai_api_key=api_key)
