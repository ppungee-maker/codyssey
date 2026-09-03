"""실제 OpenAI API를 쓰는 프로바이더 — OPENAI_API_KEY가 있을 때만 선택적으로 로드된다."""

from __future__ import annotations

from .base import LLMProvider

try:
    from openai import OpenAI
except ImportError as exc:  # pragma: no cover - 키 없는 기본 실행 경로에선 도달 안 함
    raise ImportError("openai 패키지가 설치되어 있지 않습니다: pip install openai") from exc


class OpenAILLMProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def chat(self, system_prompt: str, history: list[dict], user_message: str) -> str:
        messages = [{"role": "system", "content": system_prompt}]
        messages += [{"role": h["role"], "content": h["content"]} for h in history]
        messages.append({"role": "user", "content": user_message})

        resp = self._client.chat.completions.create(
            model=self._model, messages=messages, temperature=0.4,
        )
        return resp.choices[0].message.content or ""
