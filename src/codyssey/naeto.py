"""네이토 — 학습맵 AI 챗봇 + 멀티모달 생성(이미지/TTS/영상) 프록시.

api.usr.codyssey.kr 를 브라우저 없이 직접 호출한다(api.py 의 세션 쿠키 재사용 패턴).
서버는 무상태 — 매 호출 전체 대화 이력을 body 로 보낸다. 과금 단위는 virtualTokens(vt),
쿼터 소진 시 HTTP 402. 엔드포인트 상세는 docs/api-endpoints.md·docs/naeto-seai-usage.md 참고.
"""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import httpx

from . import api, config


class QuotaExceeded(RuntimeError):
    """virtualTokens 월 쿼터 소진 (HTTP 402)."""


DEFAULT_CHAT_MODEL = "gemini-3-flash"
DEFAULT_IMAGE_MODEL = "gpt-image-1-mini"
DEFAULT_TTS_MODEL = "tts-1"
DEFAULT_TTS_VOICE = "alloy"
DEFAULT_VIDEO_MODEL = "veo-3.1-fast"


# ── ask-stream 멀티모달 첨부 ─────────────────────────────────────────────────
_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".pdf": "application/pdf",
    # 텍스트류는 type="text" 로 나가고 내용이 프롬프트에 인라인된다(실측 전달됨).
    # mediaType 이 octet-stream 이어도 전달되지만, 프론트가 File.type 을 그대로 싣는 만큼
    # 정확한 값을 보내 서버 분기(image/pdf/그외)와 어긋나지 않게 한다.
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".json": "application/json",
    ".py": "text/x-python",
    ".html": "text/html",
    ".css": "text/css",
    ".js": "text/javascript",
    ".yml": "text/yaml",
    ".yaml": "text/yaml",
}
# 첨부 1건의 원본(디코딩 후) 바이트 상한 — 넘으면 서버가 **에러 없이 조용히 버린다**.
# 2026-07-25 이진탐색 실측: 1,048,000B 전달됨 / 1,049,200B 무시 → 경계 = 정확히 1 MiB.
# 초과 시 모델은 "첨부가 없다" 고 답하고 inputTokens 도 안 늘어 원인이 안 보인다 → 클라가 막는다.
ATTACH_MAX_BYTES = 1024 * 1024


def _attachment(path: str) -> dict:
    """파일 경로 → ask-stream 첨부 {type, mediaType, data(base64), fileName}.

    type 분기는 프론트(SPA 번들)와 동일: `image/*`→image, `application/pdf`→pdf, 그 외→text.

    2026-07-25 실측(모델 4종 교차 확인):
    - **image ✅** vision 으로 전달(1 MiB 이하). **text ✅** 내용이 프롬프트에 인라인.
    - **pdf ❌** `type:"pdf"` 는 프론트에도 있지만 실제로 모델에 도달하지 않는다
      (gemini-3-flash·gemini-3.1-pro·gpt-5.4-mini·claude-sonnet-4 전부 "첨부 없음" 응답).
      → 여기서 **거부**한다. 조용히 버려질 첨부를 만들어 보내면 "모델이 문서를 못 봤다" 는 사실이
      호출자에게 전달되지 않는다(오답을 정답처럼 받는다). 변환 경로는 `naeto_pdf.py`.
    - 크기 초과도 조용히 버려진다 → `ATTACH_MAX_BYTES` 주석 참고. 여기서 즉시 실패시킨다.
    """
    p = Path(path)
    if not p.is_file():
        raise RuntimeError(f"첨부 파일 없음: {path}")
    media_type = _MIME.get(p.suffix.lower(), "application/octet-stream")
    if media_type == "application/pdf":
        raise RuntimeError(
            f"{p.name}: PDF 는 서버가 모델에 전달하지 않는다(type:'pdf' 무시). "
            "`codyssey naeto chat --pdf <파일>` 또는 naeto_pdf.pdf_attachments() 로 "
            "텍스트·이미지로 변환해 첨부하라."
        )
    # stat 으로 재보고 따로 읽으면 그 사이 파일이 커질 수 있다(생성 중인 렌더 산출물 등) —
    # 실제로 보내는 바이트로 검증해야 상한 초과가 서버까지 새지 않는다.
    data = p.read_bytes()
    if len(data) > ATTACH_MAX_BYTES:
        raise RuntimeError(
            f"첨부 파일 {p.name} 이 {len(data):,}B — 상한 {ATTACH_MAX_BYTES:,}B(1 MiB) 초과. "
            "서버가 에러 없이 버려서 모델이 '첨부 없음' 이라 답한다 — 리사이즈·분할 후 재시도."
        )
    return {
        "type": "image" if media_type.startswith("image/") else "text",
        "mediaType": media_type,
        "data": base64.b64encode(data).decode(),
        "fileName": p.name,
    }


def _infer_provider(model: str) -> str:
    if model.startswith(("gpt-image", "tts-")):
        return "openai"
    if model.startswith(("imagen", "gemini", "veo")):
        return "google"
    raise ValueError(f"provider 추론 불가한 모델명: {model!r} — --provider 로 직접 지정 필요")


def _raise_for_billing(r: httpx.Response) -> None:
    if r.status_code == 401:
        raise api.SessionExpired("세션 만료(401) — codyssey login 필요")
    if r.status_code == 402:
        raise QuotaExceeded("virtualTokens 쿼터 소진(402) — 저비용 모델/조합을 쓰거나 다음 달 대기")
    r.raise_for_status()


def ensure_session_alive() -> None:
    """과금 호출 전 저가 생존 확인. 만료면 api.SessionExpired 그대로 전파(자동 재로그인 없음)."""
    with api._client() as client:
        api._get_json(client, "/learning/usr/ai/models")


def list_models() -> list[dict]:
    with api._client() as client:
        return api._get_json(client, "/learning/usr/ai/models")  # 응답이 이 host에서만 바로 배열(비-{result:} 래핑)


def list_presets() -> list[dict]:
    with api._client() as client:
        return api._get_json(client, "/learning/usr/ai/presets")


def list_sessions() -> list[dict]:
    with api._client() as client:
        return api._get_json(client, "/learning/usr/ai/sessions")


def get_history(session_id: str) -> list[dict]:
    with api._client() as client:
        return api._get_json(client, "/learning/usr/ai/history", sessionId=session_id)


def media_logs() -> list[dict]:
    """미디어 생성 로그(성공 이력, video 폴링 결과·과금 감사용)."""
    with api._client() as client:
        return api._get_json(client, "/learning/usr/ai/media-logs")


@dataclass(frozen=True)
class ChatResult:
    answer: str
    session_id: str | None
    virtual_tokens: float | None


def chat(
    messages: list[dict],
    *,
    session_id: str | None = None,
    model_cd: str = DEFAULT_CHAT_MODEL,
    system_prompt: str | None = None,
    preset_cd: str = "tutor",
    attachments: list[str] | None = None,
    on_delta: Callable[[str], None] | None = None,
) -> ChatResult:
    """POST /learning/usr/ai/ask-stream 을 SSE로 스트리밍 소비해 최종 답변을 반환.

    무상태 서버라 messages 에 전체 대화 이력을 실어 보내야 한다.

    ⚠ 실측(2026-07-24): 레퍼런스 문서와 달리 presetCd는 선택이 아니라 **필수**
    (없으면 `event:error`로 "유효한 프리셋이 필요합니다" 응답) — 기본값 "tutor"로 지정.

    attachments: 파일 경로 목록 → 마지막 user 메시지에 base64 인라인(이미지 vision·텍스트 인라인).
    호출자가 직접 붙이지 않고 여기서 받는 이유는 `_attachment` 의 크기·PDF 게이트를 우회할 자리를
    남기지 않기 위해서다 — 게이트를 건너뛴 첨부는 **에러 없이 버려져** 오답을 정답처럼 만든다.
    """
    if attachments:
        last_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
        if last_user is None:
            raise RuntimeError("첨부를 실을 user 메시지가 없다 — messages 에 user turn 이 필요하다.")
        last_user["attachments"] = [_attachment(p) for p in attachments]
    body = {
        "sessionId": session_id,
        "modelCd": model_cd,
        "mbrId": api.get_member_id(),
        "systemPrompt": system_prompt,
        "presetCd": preset_cd,
        "messages": messages,
    }

    final: dict | None = None
    with api._client(timeout=120) as client:
        with client.stream("POST", "/learning/usr/ai/ask-stream", json=body) as r:
            _raise_for_billing(r)
            event: str | None = None
            data_lines: list[str] = []

            def _flush() -> None:
                nonlocal final
                if not data_lines:
                    return
                raw = "\n".join(data_lines)
                if event == "error":
                    raise RuntimeError(f"네이토 챗 오류: {raw}")
                payload = json.loads(raw)
                if event == "delta" and on_delta:
                    on_delta(payload if isinstance(payload, str) else payload.get("text", ""))
                elif event == "done":
                    final = payload

            for line in r.iter_lines():
                if line == "":
                    _flush()
                    event, data_lines = None, []
                elif line.startswith("event:"):
                    event = line[len("event:"):].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[len("data:"):].strip())
            _flush()

    if final is None:
        raise RuntimeError("SSE 스트림이 'done' 이벤트 없이 종료됨")
    return ChatResult(
        answer=final["answer"],
        session_id=final.get("sessionId", session_id),
        virtual_tokens=final.get("virtualTokens"),
    )


def _resolve_media_url(client: httpx.Client, value: str) -> bytes:
    """image-gen/tts-gen 응답의 url 필드 다운로드.

    실측(2026-07-24): 절대 URL도 bare s3Key도 아니고, 이미 `/learning/usr/ai/files/...`로
    시작하는 전체 API 경로로 옴 — `/files/{value}`로 한 번 더 감싸면 경로가 중복돼 404.
    """
    if value.startswith("http") or value.startswith("/"):
        r = client.get(value)
    else:
        r = client.get(f"/learning/usr/ai/files/{value}")
    r.raise_for_status()
    return r.content


@dataclass(frozen=True)
class ImageResult:
    urls: list[str]
    local_paths: list[Path]
    virtual_tokens: float | None


def image_gen(
    prompt: str,
    *,
    provider: str | None = None,
    model: str = DEFAULT_IMAGE_MODEL,
    size: str = "1024x1024",
    quality: str = "low",
    out_dir: Path = config.MEDIA_DIR,
) -> ImageResult:
    out_dir.mkdir(parents=True, exist_ok=True)  # 이중과금 방지: 과금 호출보다 먼저
    ensure_session_alive()
    body = {
        "provider": provider or _infer_provider(model),
        "model": model,
        "size": size,
        "quality": quality,
        "prompt": prompt,
    }
    with api._client(timeout=60) as client:
        r = client.post("/learning/usr/ai/image-gen", json=body)
        _raise_for_billing(r)
        data = r.json()
        urls = [img["url"] for img in data["images"]]
        local_paths = []
        for i, url in enumerate(urls):
            content = _resolve_media_url(client, url)
            path = out_dir / f"image-{int(time.time())}-{i}.png"
            path.write_bytes(content)
            local_paths.append(path)
    return ImageResult(urls=urls, local_paths=local_paths, virtual_tokens=data.get("virtualTokens"))


@dataclass(frozen=True)
class TtsResult:
    url: str
    local_path: Path
    virtual_tokens: float | None


def tts_gen(
    text: str,
    *,
    provider: str | None = None,
    model: str = DEFAULT_TTS_MODEL,
    voice: str = DEFAULT_TTS_VOICE,
    speed: float = 1.0,
    out_dir: Path = config.MEDIA_DIR,
) -> TtsResult:
    out_dir.mkdir(parents=True, exist_ok=True)  # 이중과금 방지: 과금 호출보다 먼저
    ensure_session_alive()
    body = {
        "provider": provider or _infer_provider(model),
        "model": model,
        "voice": voice,
        "speed": speed,
        "input": text,
    }
    with api._client(timeout=60) as client:
        r = client.post("/learning/usr/ai/tts-gen", json=body)
        _raise_for_billing(r)
        data = r.json()
        content = _resolve_media_url(client, data["url"])
        path = out_dir / f"tts-{int(time.time())}.mp3"
        path.write_bytes(content)
    return TtsResult(url=data["url"], local_path=path, virtual_tokens=data.get("virtualTokens"))


@dataclass(frozen=True)
class VideoResult:
    job_id: str
    s3_key: str
    local_path: Path
    virtual_tokens: float | None


def video_gen(
    prompt: str,
    *,
    provider: str | None = None,
    model: str = DEFAULT_VIDEO_MODEL,
    resolution: str = "720p",
    duration_seconds: int = 4,
    out_dir: Path = config.MEDIA_DIR,
    poll_interval: float = 5.0,
    timeout: float = 300.0,
) -> VideoResult:
    out_dir.mkdir(parents=True, exist_ok=True)  # 이중과금 방지: 과금 호출보다 먼저 (실측 사고 사례 있음)
    ensure_session_alive()
    body = {
        "provider": provider or _infer_provider(model),
        "model": model,
        "resolution": resolution,
        "durationSeconds": duration_seconds,
        "prompt": prompt,
    }
    with api._client() as client:
        r = client.post("/learning/usr/ai/video-gen", json=body)
        _raise_for_billing(r)
        job_id = r.json()["jobId"]

    deadline = time.monotonic() + timeout
    match: dict | None = None
    while time.monotonic() < deadline:
        match = next((m for m in media_logs() if m.get("jobId") == job_id and m.get("s3Key")), None)
        if match:
            break
        time.sleep(poll_interval)

    if match is None:
        raise TimeoutError(
            f"video-gen job {job_id} 이 {timeout:.0f}s 내 완료되지 않음 — 과금은 이미 발생했을 수 있음. "
            f"잠시 후 'codyssey naeto logs' 로 재확인하세요 (jobId: {job_id})"
        )

    s3_key = match["s3Key"]
    with api._client() as client:
        r = client.get(f"/learning/usr/ai/files/{s3_key}")
        r.raise_for_status()
        local_path = out_dir / f"video-{job_id}.mp4"
        local_path.write_bytes(r.content)

    return VideoResult(
        job_id=job_id, s3_key=s3_key, local_path=local_path, virtual_tokens=match.get("virtualTokens")
    )
