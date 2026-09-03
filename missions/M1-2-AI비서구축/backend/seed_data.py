"""seed_nvda_daily.csv(M1-1에서 쓴 NVDA 2년 일봉 502건)를 (date, value, memo) 형태로
불러와 저장소(store)에 채운다. 앱이 처음부터 "관심 있는 시계열 데이터 100건 이상"을
갖고 있어야 한다는 요구사항을 충족하기 위한 초기 적재 스크립트.

실행:
    python seed_data.py
"""

from __future__ import annotations

import csv
from datetime import date as date_type
from pathlib import Path

from app.storage.base import Store

CSV_PATH = Path(__file__).resolve().parent / "seed_nvda_daily.csv"


def seed_if_empty(store: Store) -> int:
    """store가 비어있을 때만 CSV로 시딩한다. 채운 건수를 반환(0이면 스킵됨)."""
    if store.list_data():
        return 0

    count = 0
    with CSV_PATH.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            store.add_data(
                date=date_type.fromisoformat(row["date"]),
                value=float(row["close"]),
                memo="NVDA 종가 (Yahoo Finance, M1-1 데이터 재사용)",
            )
            count += 1
    return count


def main() -> None:
    from app.storage import store  # 지연 import — 앱 시작 시점의 store를 그대로 씀

    count = seed_if_empty(store)
    if count:
        print(f"[완료] {count}건 시딩 완료")
    else:
        print("[안내] 이미 데이터가 있어 시딩을 건너뜁니다(중복 적재 방지).")


if __name__ == "__main__":
    main()
