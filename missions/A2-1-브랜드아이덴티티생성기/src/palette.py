"""컬러 팔레트를 PNG로 시각화."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .models import ColorPalette


def render_palette(palette: ColorPalette, out_path: Path) -> None:
    colors = [palette.main, *palette.subs]
    labels = ["Main", *[f"Sub {i + 1}" for i in range(len(palette.subs))]]

    fig, ax = plt.subplots(figsize=(2 * len(colors), 2.6))
    for i, (color, label) in enumerate(zip(colors, labels)):
        ax.add_patch(plt.Rectangle((i, 0), 1, 1, color=color))
        ax.text(i + 0.5, -0.15, f"{label}\n{color}", ha="center", va="top", fontsize=10)

    ax.set_xlim(0, len(colors))
    ax.set_ylim(-0.4, 1)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
