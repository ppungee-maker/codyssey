"""FastAPI 앱 진입점 — CORS 설정 + 라우터 등록.

로컬 실행:
    uvicorn app.main:app --reload
Swagger UI: http://127.0.0.1:8000/docs
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import chat, conversations, data
from .storage import store

app = FastAPI(
    title="AI 비서 API",
    description="내 데이터를 이해하는 AI 비서 — 데이터 CRUD, 요약, 대화 기록, GPT 컨텍스트 주입 챗봇",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(data.router)
app.include_router(conversations.router)
app.include_router(chat.router)


@app.on_event("startup")
def seed_on_startup() -> None:
    """MemoryStore(로컬 개발 기본값)는 프로세스 메모리라 시작할 때마다 비어있다 —
    앱을 켜자마자 CRUD/요약/챗봇을 바로 시연할 수 있게 자동으로 시딩한다.
    Firestore(배포 환경)는 데이터가 영속되므로 이미 있으면 건너뛴다.
    """
    from seed_data import seed_if_empty

    count = seed_if_empty(store)
    if count:
        print(f"[시딩] {count}건 자동 적재")


@app.get("/", tags=["health"])
def health() -> dict:
    return {
        "status": "ok",
        "storage": "firestore" if settings.use_real_storage else "memory (로컬 개발 기본값)",
        "ai_provider": "openai" if settings.use_real_ai else "mock (로컬 개발 기본값)",
    }
