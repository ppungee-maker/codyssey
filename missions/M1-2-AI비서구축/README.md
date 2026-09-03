# AI 비서 — 내 데이터를 아는 챗봇

> 요구사항 10이 요구하는 필수 README 항목을 그대로 이 문서에 담았다.

## 서비스 소개

일반 ChatGPT는 사용자의 데이터를 모른다. 이 서비스는 사용자가 저장한 시계열
데이터(날짜/값/메모)를 실시간으로 요약해 AI의 시스템 프롬프트에 주입함으로써,
"내 데이터를 아는" 챗봇을 만든다. 기본 시드 데이터로 NVDA 2년치 종가(M1-1에서
분석한 것과 동일한 데이터)를 담아뒀지만, 실제로는 어떤 시계열 데이터든(운동 기록,
학습 시간, 매출 등) CRUD로 직접 관리할 수 있다.

## 기술 스택

| 영역 | 기술 |
|---|---|
| 백엔드 | FastAPI, Pydantic(요청 검증), uvicorn |
| 저장소 | Firestore(배포) / in-memory(로컬 개발 기본값) — provider 인터페이스로 전환 가능 |
| AI | OpenAI GPT(배포) / 결정적 mock(로컬 개발 기본값) — 컨텍스트 주입 흐름은 동일 |
| 프론트엔드 | Vanilla HTML/CSS/JavaScript (프레임워크 미사용, 요구사항) |
| 배포(예정) | Render(백엔드), Vercel(프론트엔드) — [`docs/01-배포가이드.md`](docs/01-배포가이드.md) |

## 배포 URL

⏳ **아직 미배포** — Firebase/OpenAI/Render/Vercel 실 계정이 필요해 코드 완성 후
배포는 보류했다(제니형님 지시). 대신 로컬에서 백엔드+프론트엔드를 동시에 띄우고
전체 플로우(데이터 CRUD, 요약, 챗봇 컨텍스트 주입, 대화 저장/불러오기)를 Playwright로
직접 조작해 검증했다 — [`captures/local-run/`](captures/local-run/) 참고.

배포를 진행하면 이 표를 채운다:

| 항목 | URL |
|---|---|
| 프론트엔드 (Vercel) | (배포 후 채울 자리) |
| 백엔드 API (Render) | (배포 후 채울 자리) |
| Swagger UI | `<백엔드 URL>/docs` |

## 로컬 실행 방법

[`docs/00-실행가이드.md`](docs/00-실행가이드.md) 참고. 요약하면:

```bash
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload
cd frontend && python3 -m http.server 5500   # 새 터미널
```

## 환경 변수 목록 (최소 세트)

| 변수 | 없을 때 동작 |
|---|---|
| `OPENAI_API_KEY` | mock LLM 사용(로컬 개발 기본값) |
| `OPENAI_MODEL` | 기본값 `gpt-4o-mini` |
| `FIREBASE_CREDENTIALS_JSON` | in-memory store 사용(로컬 개발 기본값) |
| `FIREBASE_PROJECT_ID` | - |
| `CORS_ORIGINS` | 기본값 `*`(전체 허용, 배포 시 프론트 URL로 제한 권장) |

자세한 값 형식은 [`backend/.env.example`](backend/.env.example) 참고.

## 제출 스크린샷

배포 URL이 없어 로컬 실행 화면으로 대체 — [`captures/local-run/`](captures/local-run/):

- 데이터 요약이 보이는 채팅 화면(질문+답변 포함): [`03-채팅응답.png`](captures/local-run/03-채팅응답.png)
- 데이터 관리 화면(CRUD 중 추가 동작): [`04-데이터추가.png`](captures/local-run/04-데이터추가.png)
- 대화 기록 화면(불러오기 동작): [`05-대화불러오기.png`](captures/local-run/05-대화불러오기.png)
- Swagger UI: [`01-swagger-ui.png`](captures/local-run/01-swagger-ui.png)

## 문서 구조

- [`docs/00-실행가이드.md`](docs/00-실행가이드.md) — 로컬 실행 절차
- [`docs/01-배포가이드.md`](docs/01-배포가이드.md) — Render+Vercel 배포 단계별 가이드
- [`docs/모범답안-M1-2.md`](docs/모범답안-M1-2.md) — 요구사항 충족 매핑
