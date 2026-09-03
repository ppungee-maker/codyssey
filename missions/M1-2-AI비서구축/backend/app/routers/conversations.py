"""대화 기록 API.

    POST   /api/conversations
    GET    /api/conversations
    GET    /api/conversations/{id}
    DELETE /api/conversations/{id}
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models import Conversation, ConversationCreate, ConversationSummary
from ..storage import store

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.post("", response_model=Conversation, status_code=201)
def create_conversation(payload: ConversationCreate) -> Conversation:
    title = payload.title or "새 대화"
    messages = [m.model_dump() for m in payload.messages]
    row = store.add_conversation(title, messages)
    return Conversation(**row)


@router.get("", response_model=list[ConversationSummary])
def list_conversations() -> list[ConversationSummary]:
    rows = store.list_conversations()
    return [
        ConversationSummary(
            id=r["id"], title=r["title"], message_count=len(r["messages"]),
            created_at=r["created_at"], updated_at=r["updated_at"],
        )
        for r in rows
    ]


@router.get("/{conv_id}", response_model=Conversation)
def get_conversation(conv_id: str) -> Conversation:
    """대화 불러오기 — 특정 대화의 전체 messages를 반환(요구사항 6의 옵션 A)."""
    row = store.get_conversation(conv_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"대화를 찾을 수 없습니다: {conv_id}")
    return Conversation(**row)


@router.delete("/{conv_id}", status_code=204)
def delete_conversation(conv_id: str) -> None:
    if not store.delete_conversation(conv_id):
        raise HTTPException(status_code=404, detail=f"대화를 찾을 수 없습니다: {conv_id}")
