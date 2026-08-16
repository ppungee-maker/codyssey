"""AI 감정분석/키워드추출 프로바이더 인터페이스."""

from __future__ import annotations

from abc import ABC, abstractmethod


class SentimentAnalyzer(ABC):
    @abstractmethod
    def analyze(self, review_text: str) -> tuple[str, float]:
        """(sentiment, confidence) 반환. sentiment는 '긍정'|'부정'|'중립'."""
        ...


class Extractor(ABC):
    @abstractmethod
    def extract(self, reviews: list[dict], scope: str) -> dict:
        """{'positive_keywords', 'negative_keywords', 'summary', 'suggestions'} 반환."""
        ...
