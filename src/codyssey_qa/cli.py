"""명령줄 인터페이스: login / check / b1-3.

사용:
  codyssey-qa login     # 로그인 후 세션 저장 (필요할 때만)
  codyssey-qa check     # 저장된 세션이 유효한지 확인
  codyssey-qa b1-3      # 세션 재사용 → B1-3 학습맵까지 이동 + QA 리포트
"""

from __future__ import annotations

import argparse

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codyssey-qa", description="코디세이 사이트 QA 자동화")
    parser.add_argument("--headless", action="store_true",
                        help="headless 로 실행 (기본은 headed — 항상 눈으로 보기)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("login", help="로그인 후 세션 저장")
    sub.add_parser("check", help="저장된 세션 유효성 확인")
    sub.add_parser("b1-3", help="B1-3 학습맵까지 이동 + QA 리포트")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = config.load_settings()
    headed = not args.headless
    handlers = {"login": cmd_login, "check": cmd_check, "b1-3": cmd_b1_3}
    return handlers[args.command](settings, headed)


if __name__ == "__main__":
    raise SystemExit(main())
