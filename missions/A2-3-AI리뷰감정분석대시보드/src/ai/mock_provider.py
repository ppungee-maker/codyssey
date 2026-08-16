"""무료·오프라인 mock AI 프로바이더 — 키워드 사전 기반 결정적 감정분석/추출.

인터페이스(SentimentAnalyzer/Extractor)는 실제 LLM 구현체와 동일하므로, 나중에 진짜
API로 교체해도 `main.py`/`query.py`는 수정할 필요가 없다.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter

from .base import Extractor, SentimentAnalyzer

_POSITIVE_WORDS = [
    "좋", "만족", "훌륭", "최고", "편안", "빠르", "추천", "예쁘", "안정", "가성비",
]
_NEGATIVE_WORDS = [
    "고장", "실망", "불편", "별로", "아쉽", "힘들", "파손", "부실", "끊기", "느리",
]

# 보너스(다국어 감정분석): 영문 리뷰도 같은 로직으로 처리할 수 있도록 영문 키워드 사전 추가.
_POSITIVE_WORDS_EN = [
    "good", "great", "love", "excellent", "satisfied", "comfortable", "fast",
    "recommend", "reliable", "worth",
]
_NEGATIVE_WORDS_EN = [
    "broken", "disappointed", "uncomfortable", "bad", "poor", "difficult",
    "damaged", "cheap", "slow", "terrible",
]


def _score(text: str) -> tuple[int, int]:
    lowered = text.lower()
    pos = sum(text.count(w) for w in _POSITIVE_WORDS)
    pos += sum(lowered.count(w) for w in _POSITIVE_WORDS_EN)
    neg = sum(text.count(w) for w in _NEGATIVE_WORDS)
    neg += sum(lowered.count(w) for w in _NEGATIVE_WORDS_EN)
    return pos, neg


class MockSentimentAnalyzer(SentimentAnalyzer):
    def analyze(self, review_text: str) -> tuple[str, float]:
        pos, neg = _score(review_text)
        total = pos + neg
        if total == 0:
            return "중립", 0.5

        if pos > neg:
            sentiment = "긍정"
            confidence = 0.5 + 0.5 * (pos - neg) / total
        elif neg > pos:
            sentiment = "부정"
            confidence = 0.5 + 0.5 * (neg - pos) / total
        else:
            sentiment = "중립"
            confidence = 0.5

        # 리뷰 텍스트로 결정적 지터를 줘서 항상 정확히 0.5/1.0만 나오지 않게 함
        jitter = (int(hashlib.sha256(review_text.encode()).hexdigest()[:4], 16) % 10) / 100
        confidence = min(1.0, round(confidence - jitter, 2))
        return sentiment, max(0.0, confidence)


_TRAILING_PARTICLES = ("이", "가", "은", "는", "을", "를", "에", "로", "과", "와", "도", "만", "의")


def _strip_particle(word: str) -> str:
    if len(word) > 2 and word[-1] in _TRAILING_PARTICLES:
        return word[:-1]
    return word


def _extract_words(text: str) -> list[str]:
    korean = [_strip_particle(w) for w in re.findall(r"[가-힣]{2,}", text)]
    english = [w.lower() for w in re.findall(r"[A-Za-z]{3,}", text)]
    return korean + english


class MockExtractor(Extractor):
    def extract(self, reviews: list[dict], scope: str) -> dict:
        pos_words: Counter[str] = Counter()
        neg_words: Counter[str] = Counter()
        for r in reviews:
            words = _extract_words(r["review_text"])
            if r.get("sentiment") == "긍정":
                pos_words.update(words)
            elif r.get("sentiment") == "부정":
                neg_words.update(words)

        positive_keywords = [w for w, _ in pos_words.most_common(6)]
        negative_keywords = [w for w, _ in neg_words.most_common(6)]

        summary = (
            f"{scope} 범위에서 총 {len(reviews)}건의 리뷰를 분석했습니다. "
            f"긍정 리뷰에서는 '{', '.join(positive_keywords[:3]) or '뚜렷한 키워드 없음'}'이(가), "
            f"부정 리뷰에서는 '{', '.join(negative_keywords[:3]) or '뚜렷한 키워드 없음'}'이(가) 자주 언급됐습니다."
        )
        suggestions = (
            "부정 키워드가 반복되는 항목(배터리/연결안정성/AS 등)을 우선 개선 과제로 검토하고, "
            "긍정 키워드는 마케팅 메시지에 강조하는 것을 제안합니다."
            if negative_keywords
            else "특별한 개선 필요 사항이 발견되지 않았습니다."
        )
        return {
            "positive_keywords": positive_keywords,
            "negative_keywords": negative_keywords,
            "summary": summary,
            "suggestions": suggestions,
        }
