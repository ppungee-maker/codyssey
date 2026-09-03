"""NVDA(엔비디아) 2년 일봉 시계열 분석.

데이터: Yahoo Finance 공개 차트 API(`query1.finance.yahoo.com/v8/finance/chart/NVDA`,
인증 불필요) — 2024-09-03 ~ 2026-09-02, 502 거래일.

실행:
    python notebooks/analyze.py

산출물(images/final/):
    01_price_trend.png            종가 + 이동평균(20/60일)
    02_volatility.png             일일 변화율 + 20일 변동성(표준편차)
    03_monthly_stats.png          월별 평균 종가 + 거래량
    04_decomposition.png          [보너스] 추세/계절성 분해
    05_aggregation_comparison.png [반례] 집계 단위(일/주/월)별 비교 — 같은 데이터도
                                   집계 단위를 바꾸면 그림·변동성 수치가 달라짐을 시연
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "nvda_2y_daily.csv"
IMG_DIR = ROOT / "images" / "final"

_KOREAN_FONT_CANDIDATES = [
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
]


def _apply_korean_font() -> None:
    for path in _KOREAN_FONT_CANDIDATES:
        if Path(path).exists():
            fm.fontManager.addfont(path)
            plt.rcParams["font.family"] = fm.FontProperties(fname=path).get_name()
            plt.rcParams["axes.unicode_minus"] = False
            return


_apply_korean_font()


def load_data() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


def basic_info(df: pd.DataFrame) -> dict:
    return {
        "기간": f"{df['date'].min().date()} ~ {df['date'].max().date()}",
        "행 수": len(df),
        "컬럼": list(df.columns),
        "결측치": df.isna().sum().to_dict(),
    }


def clean_data(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """결측치/이상치 처리. 기준을 명시적으로 정하고 처리 결과를 함께 반환한다."""
    log = {}

    # 결측치: 종가(close)가 없는 행은 분석에 쓸 수 없으므로 제거. 그 외 컬럼의 결측은
    # 앞값으로 보간(거래정지 등으로 값이 비었다고 가정, 시계열 연속성 유지가 목적).
    before = len(df)
    df = df.dropna(subset=["close"]).copy()
    log["종가 결측 제거"] = before - len(df)

    for col in ["open", "high", "low", "volume"]:
        na_count = df[col].isna().sum()
        if na_count:
            df[col] = df[col].ffill()
        log[f"{col} 결측 보간"] = int(na_count)

    # 이상치: 전일 대비 종가 변화율이 ±50%를 넘는 행은 데이터 오류로 간주(개별 종목이
    # 하루 만에 반토막나거나 2배가 되는 일은 액면분할·데이터 결손이 아니면 드물다).
    # 실제로는 없을 가능성이 높지만, 있다면 근거를 남기고 제거한다.
    df["pct_change"] = df["close"].pct_change()
    outliers = df[df["pct_change"].abs() > 0.5]
    log["이상치(일변동 ±50% 초과) 건수"] = len(outliers)
    if len(outliers):
        log["이상치 날짜"] = outliers["date"].dt.date.astype(str).tolist()
        df = df[df["pct_change"].abs() <= 0.5].copy()

    return df.reset_index(drop=True), log


def apply_techniques(df: pd.DataFrame) -> pd.DataFrame:
    """시계열 분석 기법 최소 2가지: (1) 이동평균 (2) 변화율/변동성. 여기선 3가지 적용."""
    df = df.copy()
    df["ma20"] = df["close"].rolling(window=20).mean()
    df["ma60"] = df["close"].rolling(window=60).mean()
    df["daily_return"] = df["close"].pct_change() * 100  # %
    df["volatility_20d"] = df["daily_return"].rolling(window=20).std()
    df["month"] = df["date"].dt.to_period("M")
    df["weekday"] = df["date"].dt.day_name()
    return df


def chart_price_trend(df: pd.DataFrame, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(df["date"], df["close"], label="종가", color="#1B4965", linewidth=1)
    ax.plot(df["date"], df["ma20"], label="20일 이동평균", color="#5FA8D3", linewidth=1.2)
    ax.plot(df["date"], df["ma60"], label="60일 이동평균", color="#F76707", linewidth=1.2)
    ax.set_title("NVDA 종가 추이 + 이동평균 (2024-09 ~ 2026-09)")
    ax.set_ylabel("종가 (USD)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def chart_volatility(df: pd.DataFrame, out_path: Path) -> None:
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
    ax1.bar(df["date"], df["daily_return"], color="#4C6EF5", width=1.5)
    ax1.set_title("일일 변화율 (%)")
    ax1.axhline(0, color="black", linewidth=0.5)

    ax2.plot(df["date"], df["volatility_20d"], color="#C1585A")
    ax2.set_title("20일 변동성 (일일 변화율의 표준편차)")
    ax2.set_ylabel("표준편차 (%)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def chart_monthly_stats(df: pd.DataFrame, out_path: Path) -> None:
    monthly = df.groupby("month").agg(avg_close=("close", "mean"), avg_volume=("volume", "mean"))
    monthly.index = monthly.index.astype(str)

    fig, ax1 = plt.subplots(figsize=(11, 5))
    ax1.bar(monthly.index, monthly["avg_volume"], color="#CED4DA", label="평균 거래량")
    ax1.set_ylabel("평균 거래량")
    ax1.tick_params(axis="x", rotation=60)

    ax2 = ax1.twinx()
    ax2.plot(monthly.index, monthly["avg_close"], color="#E8590C", marker="o", label="평균 종가")
    ax2.set_ylabel("평균 종가 (USD)")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
    ax1.set_title("월별 평균 종가 · 평균 거래량")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def chart_aggregation_comparison(df: pd.DataFrame, out_path: Path) -> dict:
    """[반례] 집계 단위(일/주/월)를 바꾸면 같은 데이터에서도 그림과 수치가 달라짐을
    직접 보여준다 — 3절에서 "월 단위를 왜 썼는지" 설명한 것의 반례 검증판.
    """
    s = df.set_index("date")["close"]
    weekly = s.resample("W").mean()
    monthly = s.resample("ME").mean()

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8))
    ax1.plot(s.index, s.values, color="#CED4DA", linewidth=0.8, label="일별 원본")
    ax1.plot(weekly.index, weekly.values, color="#4C6EF5", linewidth=1.3, label="주별 평균")
    ax1.plot(monthly.index, monthly.values, color="#E8590C", linewidth=1.8, label="월별 평균")
    ax1.set_title("집계 단위별 비교: 일/주/월 평균 종가 (같은 데이터, 다른 그림)")
    ax1.set_ylabel("종가 (USD)")
    ax1.legend()

    daily_ret_std = df["daily_return"].std()
    weekly_ret_std = (weekly.pct_change().dropna() * 100).std()
    bars = ax2.bar(
        ["일별 변화율\n표준편차", "주별 변화율\n표준편차"],
        [daily_ret_std, weekly_ret_std],
        color=["#4C6EF5", "#E8590C"],
    )
    ax2.set_ylabel("표준편차 (%)")
    ax2.set_title("같은 데이터, 다른 집계 단위 → 다른 변동성 수치")
    for bar, v in zip(bars, [daily_ret_std, weekly_ret_std]):
        ax2.text(bar.get_x() + bar.get_width() / 2, v, f"{v:.2f}%", ha="center", va="bottom")

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return {"daily_return_std": round(daily_ret_std, 2), "weekly_return_std": round(weekly_ret_std, 2)}


def decompose_trend_seasonality(df: pd.DataFrame, out_path: Path) -> dict:
    """보너스(A): 시계열 분해 — 이동평균 기반 고전적 분해(추세=중심이동평균,
    계절성=요일별 잔차 평균, 잔차=원본-추세-계절성). statsmodels 없이 직접 구현해
    외부 대형 의존성을 늘리지 않는다.
    """
    s = df.set_index("date")["close"]
    trend = s.rolling(window=21, center=True, min_periods=1).mean()
    detrended = s - trend
    weekday_seasonal = detrended.groupby(df.set_index("date").index.day_name()).mean()
    seasonal = detrended.index.day_name().map(weekday_seasonal)
    seasonal = pd.Series(seasonal.values, index=detrended.index)
    residual = detrended - seasonal

    fig = plt.figure(figsize=(11, 9))
    gs = fig.add_gridspec(4, 1)
    ax0 = fig.add_subplot(gs[0])
    ax1 = fig.add_subplot(gs[1], sharex=ax0)
    ax2 = fig.add_subplot(gs[2])  # 계절성은 요일 5개뿐이라 시계열이 아니라 막대로 표현
    ax3 = fig.add_subplot(gs[3], sharex=ax0)

    ax0.plot(s.index, s.values, color="#1B4965")
    ax0.set_title("원본 (종가)")
    ax1.plot(trend.index, trend.values, color="#F76707")
    ax1.set_title("추세 (21일 중심 이동평균)")

    weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    weekday_kr = {"Monday": "월", "Tuesday": "화", "Wednesday": "수", "Thursday": "목", "Friday": "금"}
    values = [weekday_seasonal.get(d, 0) for d in weekday_order]
    colors = ["#2F9E44" if v >= 0 else "#C1585A" for v in values]
    ax2.bar([weekday_kr[d] for d in weekday_order], values, color=colors)
    ax2.axhline(0, color="black", linewidth=0.5)
    ax2.set_title("요일 계절성 (요일별 평균 잔차, 5개 값 — 반복 패턴 아님)")

    ax3.plot(residual.index, residual.values, color="#868E96")
    ax3.set_title("잔차")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)

    return {"weekday_seasonal": weekday_seasonal.round(2).to_dict()}


def baseline_forecast(df: pd.DataFrame, horizon: int = 5) -> dict:
    """보너스(B): 베이스라인 예측 — 최근 20일 이동평균을 다음 horizon 거래일에 그대로 연장.

    정확도가 목적이 아니라 "가정과 한계"를 명시하는 것이 목적이므로, 복잡한 모델
    대신 가장 단순한 베이스라인(최근 평균 유지)을 쓴다.
    """
    last_ma = df["close"].tail(20).mean()
    last_date = df["date"].max()
    forecast_dates = pd.bdate_range(last_date + pd.Timedelta(days=1), periods=horizon)
    forecast = pd.Series([last_ma] * horizon, index=forecast_dates)
    return {
        "가정": "최근 20일 평균 종가가 향후에도 유지된다고 가정(추세·모멘텀 미반영)",
        "한계": "실제로는 추세가 이어지면 저평가, 꺾이면 고평가 예측이 됨 — 방향성 예측 불가",
        "기준값(최근 20일 평균)": round(last_ma, 2),
        "예측 구간": f"{forecast_dates[0].date()} ~ {forecast_dates[-1].date()}",
    }


def derive_insights(df: pd.DataFrame, clean_log: dict) -> list[str]:
    total_return = (df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100
    max_row = df.loc[df["close"].idxmax()]
    min_row = df.loc[df["close"].idxmin()]
    avg_vol_first_half = df["volatility_20d"].iloc[: len(df) // 2].mean()
    avg_vol_second_half = df["volatility_20d"].iloc[len(df) // 2 :].mean()
    weekday_returns = df.groupby("weekday")["daily_return"].mean().sort_values(ascending=False)
    best_day, best_day_val = weekday_returns.index[0], weekday_returns.iloc[0]
    worst_day, worst_day_val = weekday_returns.index[-1], weekday_returns.iloc[-1]

    insights = [
        f"1. 관찰: 분석 기간 전체 수익률은 {total_return:+.1f}%다 "
        f"({df['date'].iloc[0].date()} 종가 {df['close'].iloc[0]:.2f} -> "
        f"{df['date'].iloc[-1].date()} 종가 {df['close'].iloc[-1]:.2f}). "
        f"해석: 기간 내 뚜렷한 상승 또는 하락 추세가 있었음을 시사한다.",
        f"2. 관찰: 최고가는 {max_row['date'].date()}의 {max_row['close']:.2f}, "
        f"최저가는 {min_row['date'].date()}의 {min_row['close']:.2f}로 "
        f"고점 대비 저점 하락폭은 {(1 - min_row['close']/max_row['close'])*100:.1f}%다. "
        f"해석: 해당 구간에 큰 변동성 이벤트(실적 발표·업황 뉴스 등)가 있었을 가능성이 있다.",
        f"3. 관찰: 20일 변동성 평균이 전반부 {avg_vol_first_half:.2f}%, "
        f"후반부 {avg_vol_second_half:.2f}%로 "
        f"{'후반부가 더 불안정했다' if avg_vol_second_half > avg_vol_first_half else '후반부가 더 안정적이었다'}. "
        f"해석: 시장의 불확실성 수준이 기간 중 변화했다는 뜻이다.",
        f"4. 관찰: 요일별 평균 변화율이 가장 높은 요일은 {best_day}({best_day_val:+.2f}%), "
        f"가장 낮은 요일은 {worst_day}({worst_day_val:+.2f}%)다. "
        f"해석: 다만 표본이 요일당 약 100건 내외로 통계적 유의성은 약하고, 우연일 가능성을 배제할 수 없다.",
    ]
    if clean_log.get("이상치(일변동 ±50% 초과) 건수", 0) == 0:
        insights.append(
            "5. 관찰: 정제 과정에서 ±50% 이상의 일일 급변동(데이터 오류 의심)은 없었다. "
            "해석: 원본 데이터의 품질이 양호해 별도 보정 없이 분석에 활용할 수 있었다."
        )
    return insights


def main() -> None:
    IMG_DIR.mkdir(parents=True, exist_ok=True)

    df_raw = load_data()
    info = basic_info(df_raw)
    print("=== 데이터 기본 정보 ===")
    for k, v in info.items():
        print(f"  {k}: {v}")

    df_clean, clean_log = clean_data(df_raw)
    print("\n=== 정제 로그 ===")
    for k, v in clean_log.items():
        print(f"  {k}: {v}")

    df = apply_techniques(df_clean)

    chart_price_trend(df, IMG_DIR / "01_price_trend.png")
    chart_volatility(df, IMG_DIR / "02_volatility.png")
    chart_monthly_stats(df, IMG_DIR / "03_monthly_stats.png")
    decomp_info = decompose_trend_seasonality(df, IMG_DIR / "04_decomposition.png")
    agg_info = chart_aggregation_comparison(df, IMG_DIR / "05_aggregation_comparison.png")
    forecast_info = baseline_forecast(df)

    print("\n=== [반례] 집계 단위별 변동성 비교 ===")
    print(f"  {agg_info}")

    insights = derive_insights(df, clean_log)
    print("\n=== 인사이트 ===")
    for line in insights:
        print(f"  {line}")

    print("\n=== 보너스: 요일 계절성 (평균 잔차) ===")
    print(f"  {decomp_info['weekday_seasonal']}")
    print("\n=== 보너스: 베이스라인 예측 ===")
    for k, v in forecast_info.items():
        print(f"  {k}: {v}")

    print(f"\n[완료] 차트 5개 저장: {IMG_DIR}")


if __name__ == "__main__":
    main()
