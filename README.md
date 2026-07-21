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

# 콘솔 스크립트 대신 모듈로도 실행 가능
python -m codyssey_qa b1-3
# headless 로 돌리려면
codyssey-qa --headless check
```

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
- `qa-reports/`   — `map` 실행 시 노드별 결과 + 누적 QA 신호를 담은 타임스탬프 JSON
  (`map-qa-YYYYMMDD-HHMMSS.json`)

둘 다 `.gitignore` 처리되어 커밋되지 않는다 (로컬 QA 산출물).

## 알아둘 것 (자동화 함정)

- `usr.codyssey.kr` 는 상시 SSE 연결이 있어 `wait_for_load_state("networkidle")` 이 끝나지 않는다
  → `domcontentloaded` + 고정 대기 사용.
- 인증의 핵심은 `JSESSIONID` 쿠키(`.codyssey.kr`, 서브도메인 공유). `storage_state` 로 통째로 재사용.
- 네트워크 실패 중 `net::ERR_ABORTED` 는 페이지 전환 시 취소된 정상 요청 → 실제 실패와 분리.
