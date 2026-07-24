"""명령줄 인터페이스: login / check / b1-3 / map / mission / naeto / precheck.

사용:
  codyssey login              # 로그인 후 세션 저장 (필요할 때만)
  codyssey check              # 저장된 세션이 유효한지 확인
  codyssey b1-3                # 세션 재사용 → B1-3 학습맵까지 이동 + QA 리포트
  codyssey map                 # B1 학습맵 미션 노드 순회 QA
  codyssey mission B2-1        # 브라우저 없이 API 직접 호출로 미션 원문 읽기
  codyssey naeto chat "..."    # 네이토 챗 (AI 프록시, virtualTokens 과금)
  codyssey precheck B1-3 <repo_url>   # 세이AI 미션 사전평가
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime

from playwright.sync_api import sync_playwright

from . import api, auth, config, flows, naeto, precheck
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
              else "[✗] 세션 없음/만료 — codyssey login 필요")
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


def cmd_mission(settings: config.Settings, headed: bool, label: str) -> int:
    """브라우저 없이 API 직접 호출로 미션 원문을 읽어온다 (api.py 참고, 빠름)."""
    try:
        ref, text = api.fetch_mission(label)
    except api.SessionExpired:
        print("[✗] 세션 만료 — codyssey login 먼저 실행하세요")
        return 1

    if ref is None:
        print(f"[✗] [{label}] 노드를 찾지 못함 (라벨 오타 가능성 — 예: B2-1)")
        return 1

    print(f"[✓] [{label}] {ref.title}")
    print("\n----- 미션 원문 -----")
    print(text)
    print("---------------------\n")

    md_path = _save_mission_text(ref, text)
    print(f"[✓] 저장: {md_path}")
    return 0


def _save_mission_text(ref: "api.MissionRef", text: str | None) -> str:
    """읽어온 미션 원문을 qa-reports/mission-<label>-<timestamp>.md 로 저장하고 상대경로를 반환."""
    config.REPORTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now()
    path = config.REPORTS_DIR / f"mission-{ref.label}-{ts:%Y%m%d-%H%M%S}.md"
    body = [
        f"# 미션 {ref.label} 원문",
        "",
        f"- 생성: `{ts.isoformat(timespec='seconds')}`",
        f"- 미션명: {ref.title}",
        f"- 식별자: projectNo={ref.project_no} lcorsNo={ref.lcors_no} uqstnNo={ref.uqstn_no}",
        "",
        "## 본문",
        "",
        text or "(내용 없음)",
        "",
    ]
    path.write_text("\n".join(body), encoding="utf-8")
    return str(path.relative_to(config.PROJECT_ROOT))


# ── naeto / precheck (브라우저 없이 API 직접 호출, api.py mission 과 동일 패턴) ──

def _handle_ai_errors(fn):
    """naeto/precheck 커맨드 공통 에러 처리: 세션만료·쿼터소진을 표준 메시지로."""
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except api.SessionExpired:
            print("[✗] 세션 만료 — codyssey login 먼저 실행하세요")
            return 1
        except naeto.QuotaExceeded as exc:
            print(f"[✗] {exc}")
            return 1
    return wrapper


@_handle_ai_errors
def cmd_precheck(settings: config.Settings, headed: bool, label: str, repo_url: str, branch: str) -> int:
    try:
        result = precheck.run_precheck(label, repo_url, branch)
    except (ValueError, precheck.PrecheckError) as exc:
        print(f"[✗] {exc}")
        return 1

    icon = "✓" if result.passed else ("✗" if result.passed is False else "?")
    print(f"[{icon}] {label} — {result.score_text or '(점수 불명)'}")
    if result.summary:
        print(result.summary)
    for c in result.criteria:
        mark = "✅" if c.verdict.strip().lower() in ("pass", "true", "합격") else "❌"
        print(f"  {mark} {c.criterion}: {c.verdict} — {c.reason}")
    return 0 if result.passed else 1


@_handle_ai_errors
def cmd_received_evals(settings: config.Settings, headed: bool) -> int:
    evals = precheck.received_evals()
    if not evals:
        print("[*] 받은 평가 없음")
        return 0
    for e in evals:
        print(f"[{e.result}] {e.evaluator} — 점수 {e.score if e.score is not None else '?'}")
        if e.feedback:
            print(f"    {e.feedback}")
    return 0


@_handle_ai_errors
def cmd_naeto_models(settings: config.Settings, headed: bool) -> int:
    for m in naeto.list_models():
        print(m)
    return 0


@_handle_ai_errors
def cmd_naeto_presets(settings: config.Settings, headed: bool) -> int:
    for p in naeto.list_presets():
        print(p)
    return 0


@_handle_ai_errors
def cmd_naeto_sessions(settings: config.Settings, headed: bool) -> int:
    for s in naeto.list_sessions():
        print(s)
    return 0


@_handle_ai_errors
def cmd_naeto_history(settings: config.Settings, headed: bool, session_id: str) -> int:
    for turn in naeto.get_history(session_id):
        print(turn)
    return 0


@_handle_ai_errors
def cmd_naeto_logs(settings: config.Settings, headed: bool) -> int:
    for log in naeto.media_logs():
        print(log)
    return 0


def _history_to_messages(session_id: str) -> list[dict]:
    """이전 세션 대화를 chat() 이 요구하는 messages 형식으로 최선 변환.
    ⚠ history 응답의 정확한 필드명이 문서에 없어 role/content 가정 — 안 맞으면 빈 이력으로 대체."""
    try:
        turns = naeto.get_history(session_id)
        return [{"role": t["role"], "content": t["content"]} for t in turns]
    except (KeyError, TypeError):
        print("[!] 세션 이력 형식을 해석하지 못해 새 대화로 진행합니다 (필드명 확인 필요)")
        return []


@_handle_ai_errors
def cmd_naeto_chat(
    settings: config.Settings, headed: bool, message: str,
    session_id: str | None, model: str, preset: str | None, system_prompt: str | None,
) -> int:
    messages = _history_to_messages(session_id) if session_id else []
    messages.append({"role": "user", "content": message})

    result = naeto.chat(
        messages, session_id=session_id, model_cd=model,
        system_prompt=system_prompt, preset_cd=preset,
    )
    print(result.answer)
    print(f"\n[* session={result.session_id} vt={result.virtual_tokens}]")
    return 0


@_handle_ai_errors
def cmd_naeto_image(settings: config.Settings, headed: bool, prompt: str, model: str, size: str, quality: str) -> int:
    result = naeto.image_gen(prompt, model=model, size=size, quality=quality)
    for p in result.local_paths:
        print(f"[✓] 저장: {p}")
    print(f"[* vt={result.virtual_tokens}]")
    return 0


@_handle_ai_errors
def cmd_naeto_tts(settings: config.Settings, headed: bool, text: str, model: str, voice: str) -> int:
    result = naeto.tts_gen(text, model=model, voice=voice)
    print(f"[✓] 저장: {result.local_path}")
    print(f"[* vt={result.virtual_tokens}]")
    return 0


@_handle_ai_errors
def cmd_naeto_video(
    settings: config.Settings, headed: bool, prompt: str, model: str,
    resolution: str, duration: int, yes: bool,
) -> int:
    if not yes:
        print("[!] 비디오 생성은 유료(veo) 호출 중 가장 비쌉니다 — 비용을 확인했다면 --yes 를 추가하세요")
        return 1
    result = naeto.video_gen(prompt, model=model, resolution=resolution, duration_seconds=duration)
    print(f"[✓] 저장: {result.local_path}")
    print(f"[* vt={result.virtual_tokens}]")
    return 0


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
    parser = argparse.ArgumentParser(prog="codyssey", description="코디세이 사이트 QA 자동화")
    parser.add_argument("--headless", action="store_true",
                        help="headless 로 실행 (기본은 headed — 항상 눈으로 보기)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("login", help="로그인 후 세션 저장")
    sub.add_parser("check", help="저장된 세션 유효성 확인")
    sub.add_parser("b1-3", help="B1-3 학습맵까지 이동 + QA 리포트")
    sub.add_parser("map", help="B1 학습맵 미션 노드 순회 QA")
    mission_p = sub.add_parser("mission", help="학습맵의 특정 노드(예: B2-1) 미션 원문을 읽어옴")
    mission_p.add_argument("label", help="노드 라벨 (예: B2-1)")

    precheck_p = sub.add_parser("precheck", help="세이AI로 미션 repo 사전평가")
    precheck_p.add_argument("label", help="미션 노드 라벨 (예: B1-3)")
    precheck_p.add_argument("repo_url", help="채점 대상 공개 HTTPS repo URL")
    precheck_p.add_argument("--branch", default="main")

    sub.add_parser("received-evals", help="내 제출물이 받은 동료/교수 평가 조회")

    naeto_p = sub.add_parser("naeto", help="네이토 AI 챗/생성 (virtualTokens 과금)")
    naeto_sub = naeto_p.add_subparsers(dest="naeto_command", required=True)
    naeto_sub.add_parser("models", help="사용 가능한 모델 목록")
    naeto_sub.add_parser("presets", help="프리셋(페르소나) 목록")
    naeto_sub.add_parser("sessions", help="저장된 챗 세션 목록")
    naeto_sub.add_parser("logs", help="미디어 생성 로그(과금 감사, video 폴링 결과)")
    history_p = naeto_sub.add_parser("history", help="세션 대화 이력 조회")
    history_p.add_argument("session_id")
    chat_p = naeto_sub.add_parser("chat", help="챗 (기본, virtualTokens 과금)")
    chat_p.add_argument("message")
    chat_p.add_argument("-s", "--session-id", default=None, help="이어갈 세션 id")
    chat_p.add_argument("-m", "--model", default=naeto.DEFAULT_CHAT_MODEL)
    chat_p.add_argument("--preset", default="tutor", help="presetCd — 서버가 필수로 요구함 (기본 tutor)")
    chat_p.add_argument("--system-prompt", default=None)
    image_p = naeto_sub.add_parser("image", help="이미지 생성 (virtualTokens 과금)")
    image_p.add_argument("prompt")
    image_p.add_argument("--model", default=naeto.DEFAULT_IMAGE_MODEL)
    image_p.add_argument("--size", default="1024x1024")
    image_p.add_argument("--quality", default="low")
    tts_p = naeto_sub.add_parser("tts", help="음성 합성 (virtualTokens 과금)")
    tts_p.add_argument("text")
    tts_p.add_argument("--model", default=naeto.DEFAULT_TTS_MODEL)
    tts_p.add_argument("--voice", default=naeto.DEFAULT_TTS_VOICE)
    video_p = naeto_sub.add_parser("video", help="영상 생성 (virtualTokens 과금, 가장 비쌈)")
    video_p.add_argument("prompt")
    video_p.add_argument("--model", default=naeto.DEFAULT_VIDEO_MODEL)
    video_p.add_argument("--resolution", default="720p")
    video_p.add_argument("--duration", type=int, default=4)
    video_p.add_argument("--yes", action="store_true", help="비용을 확인했고 진행에 동의함")

    return parser


NAETO_HANDLERS = {
    "models": lambda s, h, a: cmd_naeto_models(s, h),
    "presets": lambda s, h, a: cmd_naeto_presets(s, h),
    "sessions": lambda s, h, a: cmd_naeto_sessions(s, h),
    "logs": lambda s, h, a: cmd_naeto_logs(s, h),
    "history": lambda s, h, a: cmd_naeto_history(s, h, a.session_id),
    "chat": lambda s, h, a: cmd_naeto_chat(s, h, a.message, a.session_id, a.model, a.preset, a.system_prompt),
    "image": lambda s, h, a: cmd_naeto_image(s, h, a.prompt, a.model, a.size, a.quality),
    "tts": lambda s, h, a: cmd_naeto_tts(s, h, a.text, a.model, a.voice),
    "video": lambda s, h, a: cmd_naeto_video(s, h, a.prompt, a.model, a.resolution, a.duration, a.yes),
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = config.load_settings()
    headed = not args.headless
    if args.command == "mission":
        return cmd_mission(settings, headed, args.label)
    if args.command == "precheck":
        return cmd_precheck(settings, headed, args.label, args.repo_url, args.branch)
    if args.command == "received-evals":
        return cmd_received_evals(settings, headed)
    if args.command == "naeto":
        return NAETO_HANDLERS[args.naeto_command](settings, headed, args)
    handlers = {"login": cmd_login, "check": cmd_check, "b1-3": cmd_b1_3, "map": cmd_map}
    return handlers[args.command](settings, headed)


if __name__ == "__main__":
    raise SystemExit(main())
