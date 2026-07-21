"""학습 콘텐츠 이동 플로우."""

from __future__ import annotations

from playwright.sync_api import Page

from . import config


def navigate_to_b1_3(page: Page) -> tuple[bool, str]:
    """메인에서 '노코드 자동화 기초' 카드를 눌러 B1-3 학습맵까지 스스로 이동.

    반환: (learningMap 도달 여부, 최종 URL)
    """
    config.SHOTS_DIR.mkdir(exist_ok=True)

    page.goto(config.USR_MAIN, wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    print(f"[*] 메인 도착: {page.url}")

    card = page.locator(f"text={config.B1_3_CARD_TEXT}").first
    if card.count() == 0:
        print(f"[✗] '{config.B1_3_CARD_TEXT}' 카드를 찾지 못함 (커리큘럼 편성 변경 가능성)")
        page.screenshot(path=str(config.SHOTS_DIR / "b1-3-실패-카드없음.png"), full_page=True)
        return False, page.url

    print(f"[*] '{config.B1_3_CARD_TEXT}' 카드 클릭 → 학습맵 이동")
    card.scroll_into_view_if_needed()
    card.click()
    page.wait_for_timeout(5000)

    reached = "learningMap" in page.url
    print(f"[{'✓' if reached else '?'}] 도착 URL: {page.url}")

    shot = config.SHOTS_DIR / "b1-3-노코드자동화.png"
    page.screenshot(path=str(shot), full_page=True)
    print(f"[*] 캡처: {shot.name}")
    return reached, page.url
