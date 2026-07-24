# codyssey-qa

코디세이(codyssey.kr) 사이트 QA 자동화 — Playwright(Python).
로그인 세션을 재사용하며 **항상 headed 모드**로 학습 콘텐츠를 순회하고,
콘솔 에러 / HTTP 실패를 수집해 QA 리포트를 만든다.

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
codyssey-qa mission B2-1   # 브라우저 없이 API 직접 호출로 미션 원문(문제기술)만 빠르게 읽기

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
| `mission <label>` | 브라우저 없이 API로 미션 원문만 빠르게 읽기 (예: `mission B2-1`) | `qa-reports/mission-<label>-*.md` |

## 구조

```
src/codyssey_qa/
  config.py    설정·경로·URL·자격증명 로딩
  browser.py   headed 컨텍스트 + 세션(storage_state) 재사용
  auth.py      로그인 / 세션 검증 / 자동 재로그인
  qa.py        QAMonitor — 콘솔·HTTP 신호 수집 + 리포트
  flows.py     학습 콘텐츠 이동 플로우 (navigate_to_b1_3, traverse_map_nodes)
  api.py       api.usr.codyssey.kr 직접 호출 (브라우저 없이 미션 원문 읽기, list_missions/fetch_mission)
  cli.py       login / check / b1-3 / map / mission 서브커맨드
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
- 콘텐츠를 "읽기"만 하면 되는 경우 DOM 순회보다 직접 API 호출이 빠르고 안정적이다
  (`mission` 명령이 그 예). 발굴한 엔드포인트는 [`docs/api-endpoints.md`](docs/api-endpoints.md) 참고.
