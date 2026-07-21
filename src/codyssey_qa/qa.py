"""QA 감시기: 페이지의 콘솔 에러/경고와 HTTP 실패를 수집하고 리포트로 정리한다."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from playwright.sync_api import Page


@dataclass
class QAMonitor:
    """page 에 훅을 걸어 QA 신호를 수집한다.

    - console_messages : 콘솔 error/warning 텍스트
    - http_failures    : HTTP 4xx/5xx 또는 (네비게이션 취소가 아닌) 네트워크 실패
    - aborted          : 페이지 전환 중 취소된 요청 (정상 — 실패와 분리)
    """

    console_messages: list[str] = field(default_factory=list)
    http_failures: list[tuple] = field(default_factory=list)
    aborted: list[tuple] = field(default_factory=list)

    def attach(self, page: Page) -> "QAMonitor":
        page.on("console", self._on_console)
        page.on("response", self._on_response)
        page.on("requestfailed", self._on_request_failed)
        return self

    # ── 핸들러 ──────────────────────────────────────────────
    def _on_console(self, msg) -> None:
        if msg.type in ("error", "warning"):
            self.console_messages.append(msg.text)

    def _on_response(self, resp) -> None:
        if resp.status >= 400 and "google" not in resp.url:
            self.http_failures.append((resp.status, resp.request.method, resp.url))

    def _on_request_failed(self, req) -> None:
        failure = str(req.failure or "")
        if "ERR_ABORTED" in failure:        # 페이지 전환 시 취소 → 정상
            self.aborted.append((req.method, req.url))
        else:
            self.http_failures.append(("FAILED", req.method, f"{req.url} :: {failure}"))

    # ── 리포트 ──────────────────────────────────────────────
    def report(self, *, title: str, checks: dict[str, str]) -> str:
        lines = [f"\n================ QA 리포트 ({title}) ================"]
        for label, value in checks.items():
            lines.append(f"  {label:22}: {value}")
        # 콘솔 메시지는 첫 줄 기준으로 중복 집계 (같은 경고 도배 방지)
        console_counts = Counter(m.splitlines()[0][:120] for m in self.console_messages)
        lines.append(f"  {'콘솔 에러/경고':22}: {len(self.console_messages)} 건 "
                     f"(고유 {len(console_counts)}종)")
        for text, cnt in console_counts.most_common(10):
            suffix = f"  ×{cnt}" if cnt > 1 else ""
            lines.append(f"     - {text}{suffix}")
        # HTTP 실패도 (상태·메서드·경로) 기준 중복 집계
        http_counts = Counter((s, m, u.split("?")[0]) for s, m, u in self.http_failures)
        lines.append(f"  {'HTTP 실패(4xx/5xx/net)':22}: {len(self.http_failures)} 건  ← 실제 점검 대상")
        for (status, method, url), cnt in http_counts.most_common(15):
            suffix = f"  ×{cnt}" if cnt > 1 else ""
            lines.append(f"     - [{status}] {method} {url[:110]}{suffix}")
        lines.append(f"  {'(참고) 네비게이션 취소':22}: {len(self.aborted)} 건  ← 페이지 전환 중 취소, 정상")
        lines.append("=" * 58)
        return "\n".join(lines)
