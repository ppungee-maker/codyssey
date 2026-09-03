"""Pydantic 요청/응답 스키마 — 요구사항: Pydantic으로 요청 데이터 검증."""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class DataPointCreate(BaseModel):
    date: date_type
    value: float
    memo: str | None = None


class DataPointUpdate(BaseModel):
    date: date_type | None = None
    value: float | None = None
    memo: str | None = None


class DataPoint(BaseModel):
    id: str
    date: date_type
    value: float
    memo: str | None = None
    created_at: datetime


class DataSummary(BaseModel):
    count: int
    date_from: date_type | None = None
    date_to: date_type | None = None
    mean: float | None = None
    max: float | None = None
    min: float | None = None
    trend: str  # "증가" | "감소" | "유지" | "데이터 부족"
    trend_detail: str


class MessageIn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None

    @field_validator("message")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message는 빈 문자열일 수 없습니다")
        return v


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    provider: str  # "mock" | "openai" — 응답이 어느 경로로 생성됐는지 투명하게 노출


class ConversationCreate(BaseModel):
    title: str | None = None
    messages: list[MessageIn] = Field(default_factory=list)


class Conversation(BaseModel):
    id: str
    title: str
    messages: list[MessageIn]
    created_at: datetime
    updated_at: datetime


class ConversationSummary(BaseModel):
    id: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime
