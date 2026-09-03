"""AI 챗봇 API — 컨텍스트 주입.

    POST /api/chat

동작 흐름(요구사항 7 그대로):
  1. 데이터 요약 조회(/api/data/summary 와 같은 로직)
  2. 요약을 시스템 프롬프트에 삽입
  3. LLM 호출(provider — mock 또는 OpenAI)
  4. 대화 내용을 conversations 에 자동 저장
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..ai import provider
from ..config import settings
from ..models import ChatRequest, ChatResponse
from ..storage import store
from .data import get_summary

router = APIRouter(prefix="/api/chat", tags=["chat"])

SYSTEM_PROMPT_TEMPLATE = """당신은 사용자의 개인 데이터를 이해하고 답하는 AI 비서입니다.
아래는 사용자가 저장한 시계열 데이터의 요약입니다 — 이 정보를 참고해 답변하세요.

[데이터 요약]
건수: {count}
기간: {date_from} ~ {date_to}
평균: {mean}
최고: {max}
최저: {min}
추세: {trend} ({trend_detail})

사용자가 데이터와 무관한 질문을 하면 일반적인 비서로서 답하되, 데이터 관련 질문에는
반드시 위 요약 수치를 근거로 답하세요.
"""


def build_system_prompt() -> str:
    summary = get_summary()
    return SYSTEM_PROMPT_TEMPLATE.format(
        count=summary.count,
        date_from=summary.date_from or "-",
        date_to=summary.date_to or "-",
        mean=summary.mean if summary.mean is not None else "-",
        max=summary.max if summary.max is not None else "-",
        min=summary.min if summary.min is not None else "-",
        trend=summary.trend,
        trend_detail=summary.trend_detail,
    )


@router.post("", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    if payload.conversation_id:
        conv = store.get_conversation(payload.conversation_id)
        if conv is None:
            raise HTTPException(status_code=404, detail=f"대화를 찾을 수 없습니다: {payload.conversation_id}")
        history = conv["messages"]
        conv_id = conv["id"]
    else:
        title = payload.message[:30]
        conv = store.add_conversation(title, [])
        history = []
        conv_id = conv["id"]

    system_prompt = build_system_prompt()
    answer = provider.chat(system_prompt, history, payload.message)

    store.append_messages(conv_id, [
        {"role": "user", "content": payload.message},
        {"role": "assistant", "content": answer},
    ])

    return ChatResponse(
        conversation_id=conv_id, answer=answer,
        provider="openai" if settings.use_real_ai else "mock",
    )
