"""네이토 — 학습맵 AI 챗봇 + 멀티모달 생성(이미지/TTS/영상) 프록시.

api.usr.codyssey.kr 를 브라우저 없이 직접 호출한다(api.py 의 세션 쿠키 재사용 패턴).
서버는 무상태 — 매 호출 전체 대화 이력을 body 로 보낸다. 과금 단위는 virtualTokens(vt),
쿼터 소진 시 HTTP 402. 엔드포인트 상세는 docs/api-endpoints.md·docs/naeto-seai-usage.md 참고.
"""

from __future__ import annotations

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
    on_delta: Callable[[str], None] | None = None,
) -> ChatResult:
    """POST /learning/usr/ai/ask-stream 을 SSE로 스트리밍 소비해 최종 답변을 반환.

    무상태 서버라 messages 에 전체 대화 이력을 실어 보내야 한다.

    ⚠ 실측(2026-07-24): 레퍼런스 문서와 달리 presetCd는 선택이 아니라 **필수**
    (없으면 `event:error`로 "유효한 프리셋이 필요합니다" 응답) — 기본값 "tutor"로 지정.
    """
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
