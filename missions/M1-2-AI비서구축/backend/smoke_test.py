"""9개 엔드포인트를 실제로 호출해보는 스모크 테스트 — 별도 서버 실행 없이
`TestClient`로 앱을 직접 구동해 검증한다.

실행:
    cd backend && python smoke_test.py
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def check(label: str, condition: bool) -> None:
    status = "OK" if condition else "FAIL"
    print(f"[{status}] {label}")
    if not condition:
        raise SystemExit(1)


def main() -> None:
    # `with` 블록 안에서만 FastAPI startup 이벤트(자동 시딩)가 실행된다.
    with TestClient(app) as client:
        _run_checks(client)


def _run_checks(client: TestClient) -> None:
    # 1. health + 시딩 확인
    r = client.get("/")
    check("GET / (health)", r.status_code == 200)

    r = client.get("/api/data")
    check("GET /api/data (시드 데이터 존재)", r.status_code == 200 and len(r.json()) >= 100)

    # 2. summary
    r = client.get("/api/data/summary")
    check("GET /api/data/summary", r.status_code == 200 and r.json()["count"] > 0)

    # 3. CRUD
    r = client.post("/api/data", json={"date": "2026-01-01", "value": 123.0, "memo": "smoke test"})
    check("POST /api/data", r.status_code == 201)
    data_id = r.json()["id"]

    r = client.put(f"/api/data/{data_id}", json={"value": 456.0})
    check("PUT /api/data/{id}", r.status_code == 200 and r.json()["value"] == 456.0)

    r = client.delete(f"/api/data/{data_id}")
    check("DELETE /api/data/{id}", r.status_code == 204)

    r = client.put(f"/api/data/{data_id}", json={"value": 1})
    check("PUT /api/data/{존재하지않는id} -> 404", r.status_code == 404)

    # 4. chat (컨텍스트 주입 + 자동 대화 저장)
    r = client.post("/api/chat", json={"message": "요즘 추세가 어때?"})
    check("POST /api/chat (신규 대화)", r.status_code == 200 and "증가" in r.json()["answer"] + "감소" + "유지")
    conv_id = r.json()["conversation_id"]

    r = client.post("/api/chat", json={"message": "평균은?", "conversation_id": conv_id})
    check("POST /api/chat (대화 이어가기)", r.status_code == 200 and r.json()["conversation_id"] == conv_id)

    r = client.post("/api/chat", json={"message": ""})
    check("POST /api/chat (빈 메시지 -> 422 검증 오류)", r.status_code == 422)

    # 5. conversations
    r = client.get("/api/conversations")
    check("GET /api/conversations", r.status_code == 200 and len(r.json()) >= 1)

    r = client.get(f"/api/conversations/{conv_id}")
    check("GET /api/conversations/{id} (불러오기)", r.status_code == 200 and len(r.json()["messages"]) == 4)

    r = client.delete(f"/api/conversations/{conv_id}")
    check("DELETE /api/conversations/{id}", r.status_code == 204)

    r = client.get(f"/api/conversations/{conv_id}")
    check("GET /api/conversations/{삭제된id} -> 404", r.status_code == 404)

    print("\n전부 통과 — 9개 엔드포인트 + 검증/404 에러 케이스까지 정상 동작 확인.")


if __name__ == "__main__":
    main()
