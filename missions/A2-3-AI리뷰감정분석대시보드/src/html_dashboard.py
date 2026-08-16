"""보너스: 차트 3종 + 통계를 하나의 단일 HTML 파일로 묶은 대시보드."""

from __future__ import annotations

import base64
import html
from pathlib import Path


def _embed_image(path: Path) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f'<img src="data:image/png;base64,{data}" alt="{path.name}" style="max-width:100%;height:auto;border:1px solid #ddd;border-radius:8px;">'


def build_html(*, stats: dict, report_text: str, chart_paths: dict[str, Path]) -> str:
    stat_rows = "".join(
        f"<tr><td>{html.escape(str(k))}</td><td>{html.escape(str(v))}</td></tr>"
        for k, v in stats.items()
    )
    charts_html = "".join(
        f'<div class="chart"><h3>{html.escape(title)}</h3>{_embed_image(path)}</div>'
        for title, path in chart_paths.items()
        if path.exists()
    )
    report_html = html.escape(report_text).replace("\n", "<br>")

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>A2-3 리뷰 감정 분석 대시보드</title>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 960px; margin: 32px auto; padding: 0 16px; color: #212529; }}
  h1 {{ font-size: 1.5rem; }}
  table {{ border-collapse: collapse; margin: 16px 0; }}
  td {{ border: 1px solid #ddd; padding: 6px 12px; }}
  .charts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 24px; margin: 24px 0; }}
  .chart h3 {{ font-size: 1rem; margin-bottom: 8px; }}
  .report {{ background: #f8f9fa; padding: 16px; border-radius: 8px; font-size: 0.9rem; line-height: 1.6; }}
</style>
</head>
<body>
<h1>AI 리뷰 감정 분석 대시보드</h1>
<table>{stat_rows}</table>
<div class="charts">{charts_html}</div>
<div class="report">{report_html}</div>
</body>
</html>
"""


def save_html(html_text: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_text, encoding="utf-8")
