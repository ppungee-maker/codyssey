"""실제 Firestore 저장소 — `FIREBASE_CREDENTIALS_JSON`(서비스 계정 키 JSON 문자열)이
환경변수로 설정됐을 때만 선택된다. `firebase-admin`이 없거나 자격증명이 없으면
`config.py`가 자동으로 `MemoryStore`를 대신 선택하므로, 이 파일은 로컬 개발 환경에선
import조차 되지 않을 수 있다(요구사항: 컬렉션 구조 data/conversations).

컬렉션 구조:
  data           문서 1개 = DataPoint 1건 (date, value, memo, created_at)
  conversations  문서 1개 = 대화 1건 (title, messages: list[{role, content}], created_at, updated_at)
"""

from __future__ import annotations

import json
from datetime import date as date_type
from datetime import datetime, timezone

from .base import Store

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError as exc:  # pragma: no cover - 로컬 개발 기본 경로에선 도달 안 함
    raise ImportError(
        "firebase-admin이 설치되어 있지 않습니다: pip install firebase-admin"
    ) from exc


def _init_client(credentials_json: str, project_id: str | None):
    if not firebase_admin._apps:
        cred = credentials.Certificate(json.loads(credentials_json))
        firebase_admin.initialize_app(cred, {"projectId": project_id} if project_id else None)
    return firestore.client()


class FirestoreStore(Store):
    def __init__(self, credentials_json: str, project_id: str | None = None) -> None:
        self._db = _init_client(credentials_json, project_id)
        self._data_col = self._db.collection("data")
        self._conv_col = self._db.collection("conversations")

    # --- data ---
    def add_data(self, date: date_type, value: float, memo: str | None) -> dict:
        doc_ref = self._data_col.document()
        row = {
            "date": date.isoformat(), "value": value, "memo": memo,
            "created_at": datetime.now(timezone.utc),
        }
        doc_ref.set(row)
        return {"id": doc_ref.id, **row}

    def list_data(self) -> list[dict]:
        docs = self._data_col.order_by("date").stream()
        return [{"id": d.id, **d.to_dict()} for d in docs]

    def get_data(self, data_id: str) -> dict | None:
        doc = self._data_col.document(data_id).get()
        return {"id": doc.id, **doc.to_dict()} if doc.exists else None

    def update_data(self, data_id: str, **fields) -> dict | None:
        doc_ref = self._data_col.document(data_id)
        if not doc_ref.get().exists:
            return None
        updates = {k: (v.isoformat() if isinstance(v, date_type) else v)
                   for k, v in fields.items() if v is not None}
        doc_ref.update(updates)
        doc = doc_ref.get()
        return {"id": doc.id, **doc.to_dict()}

    def delete_data(self, data_id: str) -> bool:
        doc_ref = self._data_col.document(data_id)
        if not doc_ref.get().exists:
            return False
        doc_ref.delete()
        return True

    # --- conversations ---
    def add_conversation(self, title: str, messages: list[dict]) -> dict:
        doc_ref = self._conv_col.document()
        now = datetime.now(timezone.utc)
        row = {"title": title, "messages": messages, "created_at": now, "updated_at": now}
        doc_ref.set(row)
        return {"id": doc_ref.id, **row}

    def list_conversations(self) -> list[dict]:
        docs = self._conv_col.order_by("updated_at", direction="DESCENDING").stream()
        return [{"id": d.id, **d.to_dict()} for d in docs]

    def get_conversation(self, conv_id: str) -> dict | None:
        doc = self._conv_col.document(conv_id).get()
        return {"id": doc.id, **doc.to_dict()} if doc.exists else None

    def append_messages(self, conv_id: str, messages: list[dict]) -> dict | None:
        doc_ref = self._conv_col.document(conv_id)
        doc = doc_ref.get()
        if not doc.exists:
            return None
        existing = doc.to_dict()
        updated_messages = [*existing.get("messages", []), *messages]
        now = datetime.now(timezone.utc)
        doc_ref.update({"messages": updated_messages, "updated_at": now})
        doc = doc_ref.get()
        return {"id": doc.id, **doc.to_dict()}

    def delete_conversation(self, conv_id: str) -> bool:
        doc_ref = self._conv_col.document(conv_id)
        if not doc_ref.get().exists:
            return False
        doc_ref.delete()
        return True
