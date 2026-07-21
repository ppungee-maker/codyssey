"""학습 콘텐츠 이동 플로우."""

from __future__ import annotations

from dataclasses import dataclass

from playwright.sync_api import Page

from . import config

# 미션 모달 닫기 버튼 (aria-label "Close modal", ✕)
MISSION_MODAL_CLOSE = "button.modal-close-btn"


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


# ── 학습맵 미션 노드 순회 QA ──────────────────────────────────
@dataclass
class NodeResult:
    label: str
    modal_opened: bool
    mission_title: str | None
    console_delta: int
    http_delta: int
    shot: str | None


def _node_labels(page: Page) -> list[str]:
    """맵에서 B?-? 형태 노드 라벨 전수 (정렬)."""
    labels = page.evaluate(r"""() => {
      const out = new Set();
      for (const e of document.querySelectorAll('*')) {
        const t = (e.textContent || '').trim();
        if (/^B\d-\d$/.test(t)) out.add(t);
      }
      return [...out];
    }""")
    return sorted(labels)


def _mission_title(page: Page) -> str | None:
    """열린 미션 모달의 '미션 : ...' 헤더 텍스트."""
    return page.evaluate(r"""() => {
      for (const e of document.querySelectorAll('*')) {
        const t = (e.textContent || '').trim();
        if (/^미션\s*[:：]/.test(t) && t.length < 80 && e.children.length <= 3) return t;
      }
      return null;
    }""")


def _close_mission_modal(page: Page) -> None:
    close = page.locator(MISSION_MODAL_CLOSE)
    if close.count() and close.first.is_visible():
        close.first.click()
        page.wait_for_timeout(800)


def traverse_map_nodes(page: Page, monitor) -> list[NodeResult]:
    """학습맵의 모든 미션 노드를 순회하며 클릭→모달 확인→캡처→닫기.

    노드별로 발생한 콘솔에러/HTTP실패 증가분을 QAMonitor 카운터 델타로 기록한다.
    잠김 노드는 모달이 열리지 않는 것으로 관찰된다(그 자체가 QA 결과).
    """
    config.SHOTS_DIR.mkdir(exist_ok=True)
    labels = _node_labels(page)
    print(f"[*] 발견된 미션 노드: {labels}")

    results: list[NodeResult] = []
    for label in labels:
        _close_mission_modal(page)  # 이전 모달 잔존 방지

        c0, h0 = len(monitor.console_messages), len(monitor.http_failures)
        loc = page.get_by_text(label, exact=True).first
        box = loc.bounding_box() if loc.count() else None
        if not box:
            print(f"  [{label}] 노드 좌표 없음 — 스킵")
            results.append(NodeResult(label, False, None, 0, 0, None))
            continue

        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.wait_for_timeout(2200)

        close = page.locator(MISSION_MODAL_CLOSE)
        opened = bool(close.count()) and close.first.is_visible()
        title = _mission_title(page) if opened else None

        shot = None
        if opened:
            shot_path = config.SHOTS_DIR / f"node-{label}.png"
            page.screenshot(path=str(shot_path), full_page=True)
            shot = shot_path.name

        c_delta = len(monitor.console_messages) - c0
        h_delta = len(monitor.http_failures) - h0
        state = f"모달 OK — {title}" if opened else "모달 안뜸(잠김 추정)"
        print(f"  [{label}] {state}  (console+{c_delta}, http+{h_delta})")

        results.append(NodeResult(label, opened, title, c_delta, h_delta, shot))
        _close_mission_modal(page)

    return results
