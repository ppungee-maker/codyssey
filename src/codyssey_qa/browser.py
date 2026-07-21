"""브라우저 컨텍스트 생성 (항상 headed, 저장된 세션 재사용)."""

from __future__ import annotations

from playwright.sync_api import Browser, BrowserContext, Playwright

from . import config


def launch_context(
    playwright: Playwright,
    *,
    use_saved_session: bool,
    headed: bool = True,
    slow_mo: int = 120,
) -> tuple[Browser, BrowserContext]:
    """Chromium 을 띄우고 컨텍스트를 만든다.

    headed 는 기본 True (코디세이 QA 정책: 항상 눈으로 볼 수 있게).
    use_saved_session 이 True 이고 auth_state.json 이 있으면 세션을 복원한다.
    """
    browser = playwright.chromium.launch(headless=not headed, slow_mo=slow_mo)
    kwargs = {"locale": "ko-KR", "viewport": {"width": 1440, "height": 900}}
    if use_saved_session and config.AUTH_STATE.exists():
        kwargs["storage_state"] = str(config.AUTH_STATE)
        print(f"[*] 저장된 세션 재사용: {config.AUTH_STATE.name}")
    else:
        print("[*] 새 세션 (로그인 필요)")
    return browser, browser.new_context(**kwargs)
