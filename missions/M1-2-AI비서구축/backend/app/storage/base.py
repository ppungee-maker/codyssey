"""저장소 인터페이스 — data 컬렉션 + conversations 컬렉션.

실제 구현체 둘: `memory_store.py`(로컬 개발용, 기본값) / `firestore_store.py`(배포용).
두 구현체가 이 인터페이스만 지키면 라우터 코드는 어느 쪽을 쓰는지 몰라도 된다
(A2 시리즈의 LLMProvider/ImageProvider와 동일한 설계 패턴).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date as date_type


class Store(ABC):
    # --- data ---
    @abstractmethod
    def add_data(self, date: date_type, value: float, memo: str | None) -> dict: ...

    @abstractmethod
    def list_data(self) -> list[dict]: ...

    @abstractmethod
    def get_data(self, data_id: str) -> dict | None: ...

    @abstractmethod
    def update_data(self, data_id: str, **fields) -> dict | None: ...

    @abstractmethod
    def delete_data(self, data_id: str) -> bool: ...

    # --- conversations ---
    @abstractmethod
    def add_conversation(self, title: str, messages: list[dict]) -> dict: ...

    @abstractmethod
    def list_conversations(self) -> list[dict]: ...

    @abstractmethod
    def get_conversation(self, conv_id: str) -> dict | None: ...

    @abstractmethod
    def append_messages(self, conv_id: str, messages: list[dict]) -> dict | None: ...

    @abstractmethod
    def delete_conversation(self, conv_id: str) -> bool: ...
