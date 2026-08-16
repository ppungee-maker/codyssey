"""logging 모듈 설정 — INFO/WARNING/ERROR 레벨을 콘솔 + 파일(logs/app.log)에 기록."""

from __future__ import annotations

import logging
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("news_pipeline")
    if logger.handlers:
        return logger  # 중복 설정 방지

    logger.setLevel(level)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    file_handler = logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger
