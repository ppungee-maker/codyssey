"""무료·오프라인 mock AI 프로바이더 — 실제 LLM 호출 없이 결정적으로 요약/분석을 만든다.

인터페이스(Summarizer/Analyzer)는 실제 API 구현체와 동일하므로, 나중에 진짜 LLM으로
교체해도 `report.py`/`main.py`는 수정할 필요가 없다. (`docs/모범답안-A2-2.md` 참고)
"""

from __future__ import annotations

import re
from collections import Counter

from .base import Analyzer, Summarizer

_STOPWORDS = {
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "is", "are", "with",
    "how", "why", "what", "new", "show", "hn", "now", "says", "after", "into",
    "from", "that", "this", "will", "can", "not", "its", "it's",
}


class MockSummarizer(Summarizer):
    def summarize(self, title: str) -> str:
        return f"[요약] {title.strip()} — 핵심 내용을 한 문장으로 압축한 자동 요약입니다."


def _extract_words(title: str) -> list[str]:
    words = re.findall(r"[A-Za-z가-힣]{2,}", title.lower())
    return [w for w in words if w not in _STOPWORDS]


class MockAnalyzer(Analyzer):
    def analyze(self, titles: list[str], scope: str) -> dict:
        counter: Counter[str] = Counter()
        for t in titles:
            counter.update(_extract_words(t))
        top_keywords = [w for w, _ in counter.most_common(8)]

        trend = (
            f"{scope} 기간 수집된 {len(titles)}건의 기사에서 '{', '.join(top_keywords[:3]) or '뚜렷한 키워드 없음'}' "
            "관련 언급이 두드러졌습니다."
        )
        common_or_diff = (
            "여러 기사에서 공통적으로 다뤄지는 주제는 상위 키워드로 요약되며, "
            "개별 기사는 세부 적용 사례에서 차이를 보입니다."
        )
        implications = (
            "해당 키워드 관련 동향을 지속 모니터링하고, 팀 내 관련 학습/실험 아이템으로 "
            "우선순위를 검토할 필요가 있습니다."
        )
        return {
            "trend": trend,
            "keywords": top_keywords,
            "common_or_diff": common_or_diff,
            "implications": implications,
        }
