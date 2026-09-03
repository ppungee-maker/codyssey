"""무료·오프라인 mock LLM — 실제 API 키 없이도 "컨텍스트 주입이 실제로 동작하는지"를
검증할 수 있게, system_prompt에 주입된 데이터 요약 수치를 답변에 그대로 반영한다.

진짜 자연어 생성은 아니지만, 이 미션의 핵심 요구사항은 "데이터 요약이 시스템
프롬프트에 삽입되고 그걸 기반으로 답한다"는 흐름 자체이므로, mock도 그 흐름이
실제로 연결돼 있음을 보여줘야 한다(단순히 고정 문자열을 반환하면 컨텍스트 주입이
실제로 되는지 확인할 수 없다).
"""

from __future__ import annotations

import re

from .base import LLMProvider

_NUM = r"[-+]?\d+(?:\.\d+)?"


def _extract(pattern: str, text: str, default: str = "정보 없음") -> str:
    m = re.search(pattern, text)
    return m.group(1) if m else default


class MockLLMProvider(LLMProvider):
    def chat(self, system_prompt: str, history: list[dict], user_message: str) -> str:
        count = _extract(rf"건수[:：]\s*({_NUM})", system_prompt)
        mean = _extract(rf"평균[:：]\s*({_NUM})", system_prompt)
        trend = _extract(r"추세[:：]\s*(\S+)", system_prompt)
        period = _extract(r"기간[:：]\s*(\S+\s*~\s*\S+)", system_prompt)

        lowered = user_message.lower()
        if any(k in user_message for k in ("추세", "트렌드", "요즘", "최근")):
            focus = f"최근 추세는 '{trend}'입니다."
        elif any(k in user_message for k in ("평균", "얼마")):
            focus = f"현재 저장된 데이터의 평균값은 {mean}입니다."
        elif any(k in user_message for k in ("몇 개", "건수", "개수")):
            focus = f"현재 저장된 데이터는 총 {count}건입니다."
        else:
            focus = f"현재 데이터는 {period} 기간, 총 {count}건이 저장돼 있고 추세는 '{trend}'입니다."

        return (
            f"[mock 응답] '{user_message.strip()}'에 대해 답변드릴게요. {focus} "
            f"(이 응답은 OPENAI_API_KEY 미설정 시 사용되는 결정적 mock이며, 실제 배포 시엔 "
            f"GPT가 같은 컨텍스트로 자연어 답변을 생성합니다.)"
        )
