"""보너스: 데이터를 embed 한 단일 HTML 대시보드 생성.

외부 라이브러리(CDN) 없이 순수 JS + SVG로 인터랙티브 라인차트를 그린다 — 기간
버튼(3개월/6개월/1년/전체)을 눌러 탐색 가능하다("기간을 바꿔보며 탐색"이라는
보너스 요구사항을 실제 인터랙션으로 충족).

실행:
    python notebooks/build_dashboard.py
산출물:
    dashboard/index.html
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "nvda_2y_daily.csv"
OUT_PATH = ROOT / "dashboard" / "index.html"


def load_rows() -> list[dict]:
    rows = []
    with DATA_PATH.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({
                "date": r["date"],
                "close": float(r["close"]),
                "volume": int(float(r["volume"])) if r["volume"] else 0,
            })
    return rows


HTML_TEMPLATE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>NVDA 시계열 대시보드</title>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 1000px; margin: 32px auto; padding: 0 16px; color: #212529; }}
  h1 {{ font-size: 1.4rem; }}
  .controls {{ margin: 16px 0; display: flex; gap: 8px; flex-wrap: wrap; }}
  button {{ padding: 6px 14px; border: 1px solid #ced4da; border-radius: 6px; background: #fff; cursor: pointer; font-size: 0.9rem; }}
  button.active {{ background: #1B4965; color: #fff; border-color: #1B4965; }}
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin: 16px 0; }}
  .stat {{ background: #f8f9fa; border-radius: 8px; padding: 10px 14px; }}
  .stat .label {{ font-size: 0.75rem; color: #868e96; }}
  .stat .value {{ font-size: 1.1rem; font-weight: 600; }}
  svg {{ width: 100%; height: 360px; border: 1px solid #eee; border-radius: 8px; }}
  .hint {{ color: #868e96; font-size: 0.85rem; margin-top: 8px; }}
</style>
</head>
<body>
<h1>NVDA 종가 시계열 대시보드 (보너스)</h1>
<div class="controls" id="range-controls"></div>
<div class="stats" id="stats"></div>
<svg id="chart" viewBox="0 0 900 360" preserveAspectRatio="none"></svg>
<p class="hint">버튼을 눌러 기간을 바꾸면 차트와 통계(변화율/최고/최저)가 즉시 다시 계산됩니다.</p>

<script>
const DATA = {data_json};
const RANGES = [
  {{ label: "3개월", days: 63 }},
  {{ label: "6개월", days: 126 }},
  {{ label: "1년", days: 252 }},
  {{ label: "전체", days: null }},
];

function filterData(days) {{
  if (days === null) return DATA;
  return DATA.slice(-days);
}}

function renderStats(rows) {{
  const first = rows[0], last = rows[rows.length - 1];
  const change = ((last.close / first.close) - 1) * 100;
  const closes = rows.map(r => r.close);
  const max = Math.max(...closes), min = Math.min(...closes);
  const stats = [
    {{ label: "기간", value: `${{first.date}} ~ ${{last.date}}` }},
    {{ label: "데이터 건수", value: `${{rows.length}}건` }},
    {{ label: "구간 수익률", value: `${{change >= 0 ? "+" : ""}}${{change.toFixed(1)}}%` }},
    {{ label: "최고가", value: max.toFixed(2) }},
    {{ label: "최저가", value: min.toFixed(2) }},
  ];
  document.getElementById("stats").innerHTML = stats.map(s =>
    `<div class="stat"><div class="label">${{s.label}}</div><div class="value">${{s.value}}</div></div>`
  ).join("");
}}

function renderChart(rows) {{
  const W = 900, H = 360, PAD = 30;
  const closes = rows.map(r => r.close);
  const max = Math.max(...closes), min = Math.min(...closes);
  const range = max - min || 1;
  const stepX = (W - PAD * 2) / (rows.length - 1);

  const points = rows.map((r, i) => {{
    const x = PAD + i * stepX;
    const y = H - PAD - ((r.close - min) / range) * (H - PAD * 2);
    return `${{x.toFixed(1)}},${{y.toFixed(1)}}`;
  }}).join(" ");

  const svg = document.getElementById("chart");
  svg.innerHTML = `
    <polyline points="${{points}}" fill="none" stroke="#1B4965" stroke-width="1.5" />
    <text x="${{PAD}}" y="15" font-size="11" fill="#868e96">${{max.toFixed(1)}}</text>
    <text x="${{PAD}}" y="${{H - PAD + 15}}" font-size="11" fill="#868e96">${{min.toFixed(1)}}</text>
  `;
}}

function setRange(days, btn) {{
  document.querySelectorAll("#range-controls button").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  const rows = filterData(days);
  renderStats(rows);
  renderChart(rows);
}}

const controls = document.getElementById("range-controls");
RANGES.forEach((r, i) => {{
  const btn = document.createElement("button");
  btn.textContent = r.label;
  btn.onclick = () => setRange(r.days, btn);
  controls.appendChild(btn);
  if (i === RANGES.length - 1) btn.click();  // 기본값: 전체 기간
}});
</script>
</body>
</html>
"""


def main() -> None:
    rows = load_rows()
    html = HTML_TEMPLATE.format(data_json=json.dumps(rows, ensure_ascii=False))
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(html, encoding="utf-8")
    print(f"[완료] 대시보드 생성: {OUT_PATH} ({len(rows)}건 embed)")


if __name__ == "__main__":
    main()
