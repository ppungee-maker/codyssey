"""데이터 API — CRUD 4개 + summary 1개.

    POST   /api/data
    GET    /api/data
    PUT    /api/data/{id}
    DELETE /api/data/{id}
    GET    /api/data/summary
"""

from __future__ import annotations

from statistics import mean as _mean

from fastapi import APIRouter, HTTPException

from ..models import DataPoint, DataPointCreate, DataPointUpdate, DataSummary
from ..storage import store

router = APIRouter(prefix="/api/data", tags=["data"])


@router.post("", response_model=DataPoint, status_code=201)
def create_data(payload: DataPointCreate) -> DataPoint:
    row = store.add_data(payload.date, payload.value, payload.memo)
    return DataPoint(**row)


@router.get("", response_model=list[DataPoint])
def list_data() -> list[DataPoint]:
    return [DataPoint(**row) for row in store.list_data()]


@router.put("/{data_id}", response_model=DataPoint)
def update_data(data_id: str, payload: DataPointUpdate) -> DataPoint:
    row = store.update_data(
        data_id, date=payload.date, value=payload.value, memo=payload.memo,
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"데이터를 찾을 수 없습니다: {data_id}")
    return DataPoint(**row)


@router.delete("/{data_id}", status_code=204)
def delete_data(data_id: str) -> None:
    if not store.delete_data(data_id):
        raise HTTPException(status_code=404, detail=f"데이터를 찾을 수 없습니다: {data_id}")


@router.get("/summary", response_model=DataSummary)
def get_summary() -> DataSummary:
    """요약 정보 — 챗봇 컨텍스트 주입(POST /api/chat)이 그대로 이 응답을 사용한다."""
    rows = store.list_data()
    if not rows:
        return DataSummary(count=0, trend="데이터 부족", trend_detail="저장된 데이터가 없습니다")

    values = [r["value"] for r in rows]
    dates = sorted(r["date"] for r in rows)

    # 추세: 최근 20%(최소 3건) 구간 평균 vs 그 이전 구간 평균 비교 — 아주 단순한 방식이지만
    # "추세 판단 기준"을 명시적으로 코드에 남기는 것이 목적(M1-1 REPORT.md와 같은 태도).
    window = max(3, len(rows) // 5)
    recent = values[-window:]
    before = values[:-window] if len(values) > window else values
    recent_avg, before_avg = _mean(recent), _mean(before)
    diff_ratio = (recent_avg - before_avg) / before_avg if before_avg else 0

    if diff_ratio > 0.02:
        trend, trend_detail = "증가", f"최근 구간 평균({recent_avg:.2f})이 이전 대비 {diff_ratio*100:+.1f}%"
    elif diff_ratio < -0.02:
        trend, trend_detail = "감소", f"최근 구간 평균({recent_avg:.2f})이 이전 대비 {diff_ratio*100:+.1f}%"
    else:
        trend, trend_detail = "유지", f"최근 구간 평균({recent_avg:.2f})이 이전과 큰 차이 없음({diff_ratio*100:+.1f}%)"

    return DataSummary(
        count=len(rows), date_from=dates[0], date_to=dates[-1],
        mean=round(_mean(values), 4), max=round(max(values), 4), min=round(min(values), 4),
        trend=trend, trend_detail=trend_detail,
    )
