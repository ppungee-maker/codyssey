"""AI 요약/분석 프로바이더 인터페이스."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Summarizer(ABC):
    @abstractmethod
    def summarize(self, title: str) -> str: ...


class Analyzer(ABC):
    @abstractmethod
    def analyze(self, titles: list[str], scope: str) -> dict:
        """{'trend': str, 'keywords': [...], 'common_or_diff': str, 'implications': str} 반환."""
        ...
