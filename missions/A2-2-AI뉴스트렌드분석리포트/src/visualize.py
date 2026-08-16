"""matplotlib 시각화: 카테고리별 뉴스 수, 일자별 수집 추이. 한글 폰트 적용."""

from __future__ import annotations

from collections import Counter
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


def category_distribution(rows: list[dict], out_path: Path) -> None:
    counter = Counter(r["category"] for r in rows)
    labels, values = zip(*counter.most_common()) if counter else ([], [])

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar(labels, values, color="#4C6EF5")
    ax.set_title("카테고리별 뉴스 수")
    ax.set_ylabel("건수")
    for i, v in enumerate(values):
        ax.text(i, v + 0.05, str(v), ha="center")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def daily_trend(rows: list[dict], out_path: Path) -> None:
    counter: Counter[str] = Counter()
    for r in rows:
        day = (r.get("collected_at") or "")[:10]
        if day:
            counter[day] += 1
    days = sorted(counter)
    values = [counter[d] for d in days]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(days, values, marker="o", color="#F76707")
    ax.set_title("일자별 수집 추이")
    ax.set_ylabel("건수")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
