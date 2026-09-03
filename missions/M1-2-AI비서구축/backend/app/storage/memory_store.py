"""로컬 개발/테스트용 저장소 — 프로세스 메모리 dict. Firebase 프로젝트 없이도
API 전체를 실행·검증할 수 있게 하기 위한 기본값(Firestore 자격증명이 없을 때 자동 선택).

프로세스가 끝나면 데이터가 사라지므로 배포 환경에서는 반드시 FIREBASE_CREDENTIALS_JSON을
설정해 `firestore_store.py`가 선택되게 해야 한다.
"""

from __future__ import annotations

import itertools
import threading
from datetime import date as date_type
from datetime import datetime, timezone

from .base import Store


class MemoryStore(Store):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, dict] = {}
        self._conversations: dict[str, dict] = {}
        self._data_counter = itertools.count(1)
        self._conv_counter = itertools.count(1)

    # --- data ---
    def add_data(self, date: date_type, value: float, memo: str | None) -> dict:
        with self._lock:
            data_id = f"d{next(self._data_counter)}"
            row = {
                "id": data_id, "date": date, "value": value, "memo": memo,
                "created_at": datetime.now(timezone.utc),
            }
            self._data[data_id] = row
            return dict(row)

    def list_data(self) -> list[dict]:
        with self._lock:
            return sorted((dict(r) for r in self._data.values()), key=lambda r: r["date"])

    def get_data(self, data_id: str) -> dict | None:
        with self._lock:
            row = self._data.get(data_id)
            return dict(row) if row else None

    def update_data(self, data_id: str, **fields) -> dict | None:
        with self._lock:
            row = self._data.get(data_id)
            if row is None:
                return None
            for k, v in fields.items():
                if v is not None:
                    row[k] = v
            return dict(row)

    def delete_data(self, data_id: str) -> bool:
        with self._lock:
            return self._data.pop(data_id, None) is not None

    # --- conversations ---
    def add_conversation(self, title: str, messages: list[dict]) -> dict:
        with self._lock:
            conv_id = f"c{next(self._conv_counter)}"
            now = datetime.now(timezone.utc)
            row = {
                "id": conv_id, "title": title, "messages": list(messages),
                "created_at": now, "updated_at": now,
            }
            self._conversations[conv_id] = row
            return dict(row)

    def list_conversations(self) -> list[dict]:
        with self._lock:
            return sorted(
                (dict(r) for r in self._conversations.values()),
                key=lambda r: r["updated_at"], reverse=True,
            )

    def get_conversation(self, conv_id: str) -> dict | None:
        with self._lock:
            row = self._conversations.get(conv_id)
            return dict(row) if row else None

    def append_messages(self, conv_id: str, messages: list[dict]) -> dict | None:
        with self._lock:
            row = self._conversations.get(conv_id)
            if row is None:
                return None
            row["messages"] = [*row["messages"], *messages]
            row["updated_at"] = datetime.now(timezone.utc)
            return dict(row)

    def delete_conversation(self, conv_id: str) -> bool:
        with self._lock:
            return self._conversations.pop(conv_id, None) is not None
