"""데이터 수집 스크립트 — Yahoo Finance 공개 차트 API에서 NVDA 2년 일봉을 받아
data/nvda_2y_daily.csv 로 저장한다. 인증·API 키 불필요.

재수집하면 최신 거래일까지 데이터가 갱신되며(범위가 "최근 2년"이므로 실행 시점에
따라 리포트의 수치와 살짝 달라질 수 있다), 리포트에 실린 수치는 이 리포지토리에
커밋된 data/nvda_2y_daily.csv 기준이다.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

import httpx

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "nvda_2y_daily.csv"
URL = "https://query1.finance.yahoo.com/v8/finance/chart/NVDA"


def fetch() -> list[dict]:
    r = httpx.get(
        URL, params={"range": "2y", "interval": "1d"}, timeout=15,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    r.raise_for_status()
    result = r.json()["chart"]["result"][0]
    timestamps = result["timestamp"]
    quote = result["indicators"]["quote"][0]

    rows = []
    for i, ts in enumerate(timestamps):
        close = quote["close"][i]
        if close is None:
            continue
        date = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
        rows.append({
            "date": date,
            "open": round(quote["open"][i], 4) if quote["open"][i] is not None else "",
            "high": round(quote["high"][i], 4) if quote["high"][i] is not None else "",
            "low": round(quote["low"][i], 4) if quote["low"][i] is not None else "",
            "close": round(close, 4),
            "volume": quote["volume"][i] if quote["volume"][i] is not None else "",
        })
    return rows


def main() -> None:
    rows = fetch()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)}건 저장 -> {OUT_PATH} ({rows[0]['date']} ~ {rows[-1]['date']})")


if __name__ == "__main__":
    main()
