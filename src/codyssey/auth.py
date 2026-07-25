"""로그인 및 세션 검증.

로그인은 화면 폼(form#login)에 값을 넣고 제출하지만, 실제 인증은 JS 가
api.ams.codyssey.kr/authenticate 로 보낸다. 그 응답의 success 필드로 성공을 판정한다.
성공 시 usr.codyssey.kr 로 리다이렉트되며 세션(JSESSIONID)이 잡힌다.
"""

from __future__ import annotations

from playwright.sync_api import Page

from . import api, config


def login(page: Page, settings: config.Settings) -> bool:
    """폼 로그인 수행 후 성공하면 세션을 auth_state.json 에 저장한다."""
    if not settings.has_credentials:
        print("[!] .env 에 CODYSSEY_ID / CODYSSEY_PW 를 채워주세요.")
        return False

    print(f"[*] 로그인 페이지 열기: {settings.login_url}")
    page.goto(settings.login_url, wait_until="domcontentloaded")
    page.fill("#userId", settings.user_id)
    page.fill("#password", settings.password)

    # 인증 API 응답을 잡아 성공 여부 판정
    with page.expect_response(lambda r: config.AUTH_API in r.url, timeout=15000) as resp_info:
        page.click("form#login button[type=submit]")
    resp = resp_info.value

    ok = False
    try:
        data = resp.json()
        ok = bool(data.get("success"))
        print(f"[*] /authenticate → HTTP {resp.status}, success={data.get('success')}, "
              f"message={data.get('message')}")
    except Exception as exc:  # noqa: BLE001 - 진단 목적
        print(f"[!] 응답 파싱 실패: {exc} (HTTP {resp.status})")

    if not ok:
        print("[✗] 로그인 실패 — 아이디/비번 확인 필요")
        return False

    # 로그인 성공 시 usr.codyssey.kr 로 자동 리다이렉트. 정착까지 조건 대기.
    # ⚠️ SSE 상시연결 때문에 networkidle 은 절대 쓰지 않는다 (무한 대기).
    # wait_for_url 이 리다이렉트 정착을 보장하므로 고정 슬립(wait_for_timeout)은 불필요 —
    # 느리고 불안정(flaky)해서 조건 대기로 대체했다.
    try:
        page.wait_for_url("**usr.codyssey.kr/**", timeout=10000)
    except Exception as exc:  # noqa: BLE001 - 대기 실패해도 success 판정은 통과, 진단만 남긴다
        print(f"[!] usr 리다이렉트 대기 실패({exc}) — 세션 저장은 계속 진행")
    page.context.storage_state(path=str(config.AUTH_STATE))
    print(f"[✓] 로그인 성공 — 착지: {page.url}")
    print(f"[✓] 세션 저장: {config.AUTH_STATE.name}")
    return True


def is_logged_in(_page: Page | None = None) -> bool:
    """세션(auth_state.json)이 유효한지 httpx 로 검증 — 브라우저 네비게이션 불필요.

    이전엔 usr 메인으로 이동해 URL 에 'login' 문자열이 없으면 로그인으로 봤지만, SPA 는
    어떤 경로든 200 셸을 반환해 미인증도 로그인으로 오판할 수 있었다. 실제 인증이 필요한
    XHR(user/info/detail)을 httpx 로 때려 302/401 여부로 판정한다(api.session_valid).
    _page 인자는 기존 호출부(page 전달) 하위호환용으로 남기며 쓰지 않는다.
    """
    return api.session_valid()


def ensure_logged_in(page: Page, settings: config.Settings) -> bool:
    """세션이 유효하면 재사용, 아니면 자동 재로그인."""
    if is_logged_in(page):
        print("[✓] 세션 재사용 — 로그인 상태")
        return True
    print("[*] 세션 만료/없음 — 자동 재로그인 시도")
    return login(page, settings)
