"""명령줄 인터페이스: login / check / b1-3.

사용:
  codyssey-qa login     # 로그인 후 세션 저장 (필요할 때만)
  codyssey-qa check     # 저장된 세션이 유효한지 확인
  codyssey-qa b1-3      # 세션 재사용 → B1-3 학습맵까지 이동 + QA 리포트
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime

from playwright.sync_api import sync_playwright

from . import auth, config, flows
from .browser import launch_context
from .qa import QAMonitor


def cmd_login(settings: config.Settings, headed: bool) -> int:
    with sync_playwright() as p:
        browser, ctx = launch_context(p, use_saved_session=False, headed=headed)
        page = ctx.new_page()
        ok = auth.login(page, settings)
        page.wait_for_timeout(2500)
        browser.close()
        return 0 if ok else 1


def cmd_check(settings: config.Settings, headed: bool) -> int:
    with sync_playwright() as p:
        browser, ctx = launch_context(p, use_saved_session=True, headed=headed)
        page = ctx.new_page()
        logged_in = auth.is_logged_in(page)
        print("[✓] 저장된 세션 유효 — 로그인 상태" if logged_in
              else "[✗] 세션 없음/만료 — codyssey-qa login 필요")
        page.wait_for_timeout(2000)
        browser.close()
        return 0 if logged_in else 1


def cmd_b1_3(settings: config.Settings, headed: bool) -> int:
    with sync_playwright() as p:
        browser, ctx = launch_context(p, use_saved_session=True, headed=headed)
        page = ctx.new_page()
        monitor = QAMonitor().attach(page)

        if not auth.ensure_logged_in(page, settings):
            browser.close()
            return 1

        reached, url = flows.navigate_to_b1_3(page)
        print(monitor.report(
            title="B1-3 이동 경로",
            checks={
                "로그인 상태 도달": "OK",
                "B1-3 학습맵 도달": "OK (learningMap)" if reached else f"확인필요 — {url}",
            },
        ))
        page.wait_for_timeout(1500)
        browser.close()
        return 0 if reached else 1


def cmd_map(settings: config.Settings, headed: bool) -> int:
    with sync_playwright() as p:
        browser, ctx = launch_context(p, use_saved_session=True, headed=headed)
        page = ctx.new_page()
        monitor = QAMonitor().attach(page)

        if not auth.ensure_logged_in(page, settings):
            browser.close()
            return 1

        reached, url = flows.navigate_to_b1_3(page)
        if not reached:
            print(f"[✗] 학습맵 진입 실패 — {url}")
            browser.close()
            return 1

        print("\n[*] 학습맵 미션 노드 순회 시작")
        nodes = flows.traverse_map_nodes(page, monitor)

        # ── 노드별 QA 표 ──
        print("\n================ QA 리포트 (B1 학습맵 노드 순회) ================")
        print(f"  {'노드':6} {'모달':6} {'콘솔Δ':6} {'HTTPΔ':6} 미션")
        opened_cnt = 0
        for n in nodes:
            opened_cnt += int(n.modal_opened)
            modal = "OK" if n.modal_opened else "잠김"
            title = (n.mission_title or "").replace("미션 :", "").strip() or "-"
            print(f"  {n.label:6} {modal:6} {n.console_delta:<6} {n.http_delta:<6} {title[:44]}")
        print(f"\n  노드 {len(nodes)}개 중 미션 모달 정상 {opened_cnt}개")
        print(monitor.report(
            title="누적 신호",
            checks={"순회 노드 수": str(len(nodes)), "미션 모달 정상": f"{opened_cnt}/{len(nodes)}"},
        ))

        # ── 리포트 저장 (JSON + Markdown) ──
        json_path, md_path = _save_map_report(url, nodes, opened_cnt, monitor)
        print(f"\n[✓] JSON 리포트 저장: {json_path}")
        print(f"[✓] Markdown 리포트 저장: {md_path}")

        page.wait_for_timeout(1500)
        browser.close()
        return 0


def _build_map_report(map_url, nodes, opened_cnt, monitor, generated_at) -> dict:
    return {
        "kind": "b1-map-node-traversal",
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "map_url": map_url,
        "summary": {
            "nodes_total": len(nodes),
            "missions_ok": opened_cnt,
            "missions_locked": len(nodes) - opened_cnt,
            **monitor.summary(),
        },
        "nodes": [asdict(n) for n in nodes],
    }


def _render_markdown(report: dict) -> str:
    s = report["summary"]
    out = [
        "# B1 학습맵 노드 순회 QA 리포트",
        "",
        f"- 생성: `{report['generated_at']}`",
        f"- 맵: {report['map_url']}",
        f"- 노드: {s['nodes_total']}개 (미션 정상 **{s['missions_ok']}** / 잠김 {s['missions_locked']})",
        "",
        "## 요약",
        "",
        f"- 콘솔 에러/경고: **{s['console_total']}건** (고유 {len(s['console_unique'])}종)",
        f"- HTTP 실패(4xx/5xx/net): **{s['http_failures_total']}건** ← 실제 점검 대상",
        f"- 네비게이션 취소(정상): {s['navigation_aborted']}건",
        "",
        "## 노드별 결과",
        "",
        "| 노드 | 모달 | 미션 | 콘솔Δ | HTTPΔ | 캡처 |",
        "|---|---|---|---|---|---|",
    ]
    for n in report["nodes"]:
        modal = "✅" if n["modal_opened"] else "🔒 잠김"
        title = (n["mission_title"] or "").replace("미션 :", "").strip() or "-"
        shot = n["shot"] or "-"
        out.append(f"| {n['label']} | {modal} | {title} | {n['console_delta']} | {n['http_delta']} | {shot} |")

    out += ["", "## 콘솔 신호 (중복 집계)", ""]
    if s["console_unique"]:
        for item in s["console_unique"]:
            out.append(f"- `{item['message'].strip()}` ×{item['count']}")
    else:
        out.append("- (없음)")

    out += ["", "## HTTP 실패", ""]
    if s["http_failures"]:
        for item in s["http_failures"]:
            out.append(f"- [{item['status']}] {item['method']} {item['url']} ×{item['count']}")
    else:
        out.append("- (없음) ✅")

    out.append("")
    return "\n".join(out)


def _save_map_report(map_url, nodes, opened_cnt, monitor) -> tuple[str, str]:
    """노드별 결과 + 누적 QA 신호를 JSON + Markdown 두 포맷으로 저장하고 경로를 반환."""
    config.REPORTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now()
    report = _build_map_report(map_url, nodes, opened_cnt, monitor, ts)

    base = config.REPORTS_DIR / f"map-qa-{ts:%Y%m%d-%H%M%S}"
    json_path = base.with_suffix(".json")
    md_path = base.with_suffix(".md")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    rel = lambda p: str(p.relative_to(config.PROJECT_ROOT))
    return rel(json_path), rel(md_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codyssey-qa", description="코디세이 사이트 QA 자동화")
    parser.add_argument("--headless", action="store_true",
                        help="headless 로 실행 (기본은 headed — 항상 눈으로 보기)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("login", help="로그인 후 세션 저장")
    sub.add_parser("check", help="저장된 세션 유효성 확인")
    sub.add_parser("b1-3", help="B1-3 학습맵까지 이동 + QA 리포트")
    sub.add_parser("map", help="B1 학습맵 미션 노드 순회 QA")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = config.load_settings()
    headed = not args.headless
    handlers = {"login": cmd_login, "check": cmd_check, "b1-3": cmd_b1_3, "map": cmd_map}
    return handlers[args.command](settings, headed)


if __name__ == "__main__":
    raise SystemExit(main())
