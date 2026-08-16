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


class SentimentAnalyzer(ABC):
    """보너스: 뉴스 제목의 감성(긍정/부정/중립)을 분석한다."""

    @abstractmethod
    def analyze_sentiment(self, title: str) -> tuple[str, float]:
        """(sentiment, confidence) 반환. sentiment는 '긍정'|'부정'|'중립'."""
        ...
