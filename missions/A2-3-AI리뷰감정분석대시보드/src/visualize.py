"""matplotlib 대시보드 시각화: 감정 분포, 시간별 추이, 별점별 감정 분포. 한글 폰트 적용."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt

_KOREAN_FONT_CANDIDATES = [
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "C:\\Windows\\Fonts\\malgun.ttf",
]


def _apply_korean_font() -> None:
    for path in _KOREAN_FONT_CANDIDATES:
        if Path(path).exists():
            fm.fontManager.addfont(path)
            family = fm.FontProperties(fname=path).get_name()
            plt.rcParams["font.family"] = family
            plt.rcParams["axes.unicode_minus"] = False
            return


_apply_korean_font()

_SENTIMENT_COLORS = {"긍정": "#2F9E44", "부정": "#E03131", "중립": "#868E96"}


def sentiment_distribution(rows: list[dict], out_path: Path) -> None:
    counter = Counter(r["sentiment"] for r in rows if r["sentiment"])
    labels = list(counter.keys())
    values = [counter[k] for k in labels]
    colors = [_SENTIMENT_COLORS.get(k, "#4C6EF5") for k in labels]

    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    ax.pie(values, labels=labels, autopct="%1.0f%%", colors=colors, startangle=90)
    ax.set_title("감정 분포")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def sentiment_trend(rows: list[dict], out_path: Path) -> None:
    by_day: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        day = (r["review_date"] or "")[:10]
        if day and r["sentiment"]:
            by_day[day][r["sentiment"]] += 1
    days = sorted(by_day)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for sentiment, color in _SENTIMENT_COLORS.items():
        values = [by_day[d].get(sentiment, 0) for d in days]
        ax.plot(days, values, marker="o", label=sentiment, color=color)
    ax.set_title("시간별 감정 추이")
    ax.set_ylabel("건수")
    ax.tick_params(axis="x", rotation=45)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def rating_sentiment_correlation(rows: list[dict], out_path: Path) -> None:
    ratings = sorted({r["rating"] for r in rows if r["rating"] is not None})
    matrix = {s: [0] * len(ratings) for s in _SENTIMENT_COLORS}
    for r in rows:
        if r["rating"] is None or not r["sentiment"]:
            continue
        idx = ratings.index(r["rating"])
        matrix[r["sentiment"]][idx] += 1

    fig, ax = plt.subplots(figsize=(7, 4.5))
    bottom = [0] * len(ratings)
    for sentiment, color in _SENTIMENT_COLORS.items():
        ax.bar([str(r) for r in ratings], matrix[sentiment], bottom=bottom, label=sentiment, color=color)
        bottom = [b + v for b, v in zip(bottom, matrix[sentiment])]
    ax.set_title("별점별 감정 분포")
    ax.set_xlabel("별점")
    ax.set_ylabel("건수")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
