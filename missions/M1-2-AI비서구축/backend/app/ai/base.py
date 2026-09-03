"""LLM 프로바이더 인터페이스 — mock/openai 구현체가 이 계약을 따른다."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def chat(self, system_prompt: str, history: list[dict], user_message: str) -> str:
        """system_prompt + 과거 대화(history) + 새 사용자 메시지 -> 답변 텍스트."""
        ...
