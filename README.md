# codyssey-qa

코디세이(codyssey.kr) 사이트 QA 자동화 — Playwright(Python).
로그인 세션을 재사용하며 **항상 headed 모드**로 학습 콘텐츠를 순회하고,
콘솔 에러 / HTTP 실패를 수집해 QA 리포트를 만든다.

> 이 저장소는 두 부분으로 구성된다.
> ① **`src/codyssey_qa/`** — 코디세이 사이트 QA 자동화 도구 (이 문서의 주제)
> ② **`B1-3-노코드자동화/`** — 코디세이 학습 미션 B1-3 산출물 ([아래 설명](#b1-3-노코드자동화--노코드-자동화-미션-산출물-별도))

## 설치

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
playwright install chromium
```

## 설정

`.env.example` 을 복사해 `.env` 를 만들고 값을 채운다 (`.env` 는 git 에 올라가지 않음).

```
CODYSSEY_LOGIN_URL=https://codyssey.kr/loginForm
CODYSSEY_ID=<이메일>
CODYSSEY_PW=<비밀번호>
```

## 사용

```bash
codyssey-qa login     # 로그인 후 세션 저장 (auth_state.json)
codyssey-qa check     # 저장된 세션이 유효한지 확인
codyssey-qa b1-3      # 세션 재사용 → B1-3(노코드자동화) 학습맵까지 이동 + QA 리포트
codyssey-qa map       # B1 학습맵 미션 노드(B1-1~B2-3) 순회 QA + JSON 리포트 저장

# 콘솔 스크립트 대신 모듈로도 실행 가능
python -m codyssey_qa b1-3
# headless 로 돌리려면
codyssey-qa --headless check
```

### 전형적 QA 흐름

```bash
# 1) 최초 1회만 로그인 → 세션(auth_state.json) 저장
codyssey-qa login

# 2) 이후에는 세션을 재사용하므로 로그인 없이 바로 QA 실행
codyssey-qa map        # B1 학습맵 노드 순회 → qa-reports/ 에 JSON+MD 리포트

# 3) 세션이 만료되면 map/b1-3 실행 시 자동으로 재로그인한다.
#    수동 확인이 필요하면:
codyssey-qa check
```

각 명령이 하는 일:

| 명령 | 하는 일 | 산출물 |
|---|---|---|
| `login` | 폼 로그인 후 세션 저장 | `auth_state.json` |
| `check` | 저장된 세션 유효성 확인 | (콘솔 출력) |
| `b1-3` | 메인 → B1-3 학습맵까지 이동 + QA 리포트 | `screenshots/b1-3-노코드자동화.png` |
| `map` | B1 학습맵 미션 노드(B1-1~B2-3) 순회 QA | `screenshots/node-*.png`, `qa-reports/map-qa-*.json`·`.md` |

## 구조

```
src/codyssey_qa/
  config.py    설정·경로·URL·자격증명 로딩
  browser.py   headed 컨텍스트 + 세션(storage_state) 재사용
  auth.py      로그인 / 세션 검증 / 자동 재로그인
  qa.py        QAMonitor — 콘솔·HTTP 신호 수집 + 리포트
  flows.py     학습 콘텐츠 이동 플로우 (navigate_to_b1_3, traverse_map_nodes)
  cli.py       login / check / b1-3 / map 서브커맨드
```

## 산출물

- `screenshots/`  — 이동/노드별 화면 캡처 (`node-B1-1.png` 등)
- `qa-reports/`   — `map` 실행 시 노드별 결과 + 누적 QA 신호를 담은 타임스탬프 리포트.
  같은 이름으로 **JSON**(`map-qa-*.json`, 기계용)과 **Markdown**(`map-qa-*.md`, 사람용) 동시 생성

둘 다 `.gitignore` 처리되어 커밋되지 않는다 (로컬 QA 산출물).

## 알아둘 것 (자동화 함정)

- `usr.codyssey.kr` 는 상시 SSE 연결이 있어 `wait_for_load_state("networkidle")` 이 끝나지 않는다
  → `domcontentloaded` + 고정 대기 사용.
- 인증의 핵심은 `JSESSIONID` 쿠키(`.codyssey.kr`, 서브도메인 공유). `storage_state` 로 통째로 재사용.
- 네트워크 실패 중 `net::ERR_ABORTED` 는 페이지 전환 시 취소된 정상 요청 → 실제 실패와 분리.

---

## `B1-3-노코드자동화/` — 노코드 자동화 미션 산출물 (별도)

QA 자동화 도구(`src/codyssey_qa/`)와는 **무관한 별개 폴더**로, 코디세이 학습
미션 **B1-3 「노코드 자동화 기초: 워크플로우 설계」**의 실습 산출물과 참고 자료를 모아둔 곳이다.
(코디세이 학습맵의 B1-3 노드가 바로 이 미션이며, `codyssey-qa b1-3` 이 도달하는 그 콘텐츠다.)

```
B1-3-노코드자동화/
├── docs/
│   ├── 00-실행가이드.md              Make/Zapier 구축·캡처 체크리스트
│   ├── 01-프로젝트1-비교분석보고서.md   Make vs Zapier 비교 (프로젝트 1)
│   ├── 02-프로젝트2-설계문서.md         메일 AI 요약 파이프라인 설계 (프로젝트 2)
│   ├── 작업메모.md                    진행 메모 및 에러 로그
│   └── 모범답안-B1-3.md               미션 요구사항을 모두 충족하는 참고 모범답안
└── captures/make/                    Make 워크플로우 실행 화면 캡처
```

미션 요구사항 요약:
- **프로젝트 1**: 동일 워크플로우를 서로 다른 2개 이상 도구(Make·Zapier)로 구현하고 비교 분석
- **프로젝트 2**: 자유 주제 자동화를 1개 도구로 설계·구현 (Trigger 발생 시 자동 실행)
- 공통: Trigger 1+ / Action 2+ / 조건 분기(Filter·Router) 1+ / 각 분기 1회 이상 실행
- 보너스: 생성형 AI 연동 Action, 실패 알림·재시도 전략

> 제출물 캡처·문서에는 API Key·토큰·수신자 이메일 등 민감정보를 남기지 않는다(마스킹 원칙).
