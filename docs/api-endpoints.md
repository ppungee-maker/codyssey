# 코디세이 API 엔드포인트 레퍼런스 (리버스엔지니어링)

공식 문서가 없는 내부 API를 자동화 과정에서 발굴한 기록. 새 엔드포인트를 찾으면
아래 포맷으로 이 파일에 추가한다 (README/코드 docstring엔 요약 링크만).

**발굴 방법**: Playwright `page.on("request")` / `page.on("response")`로 원하는
동작(노드 클릭 등) 시 오가는 XHR을 한 번 스니핑 → 재현 가능하면 `httpx`로 직접
호출하는 헬퍼를 만든다. DOM 클릭 자동화보다 훨씬 빠르고 안정적이다.

---

## 인증

### `POST https://api.ams.codyssey.kr/authenticate`

| | |
|---|---|
| 용도 | 로그인 |
| 인증 | 불필요 (로그인 자체) |
| Content-Type | `application/x-www-form-urlencoded` |
| 필수 헤더 | `X-Requested-With: XMLHttpRequest`, `Accept: application/json`, `Origin: https://codyssey.kr` |
| Body | `userId=<email>&password=<pw>` |
| 성공 응답 | `{"success": true, "memberType": "REGULAR", ...}` + `location` 헤더 → `usr.codyssey.kr` |
| 실패 응답 | HTTP 401, `{"message_code":"E0000","success":false,"message":"..."}` |
| 세션 | 성공 시 `JSESSIONID` 쿠키(domain=`.codyssey.kr`) 발급 — 이후 모든 서브도메인 API에 공유됨 |
| 발굴일 | 2026-07-21 |

구현: `src/codyssey/auth.py`

---

## 학습맵 / 미션 콘텐츠

베이스: `https://api.usr.codyssey.kr` — **`usr.codyssey.kr`가 아님**. 경로에 캠퍼스
세그먼트(`/daejeon` 등)를 붙이면 401. 캠퍼스 prefix는 프론트 SPA 라우팅 전용이고
API 경로에는 없다.

공통 필수 헤더: `X-Requested-With: XMLHttpRequest`, `Accept: application/json`
(없으면 API가 아니라 SPA index.html HTML 셸이 응답으로 옴).

### `GET /learning/learningProgress/child/list?lpNo=<lpNo>`

| | |
|---|---|
| 용도 | 학습맵 전체 구조 + 미션 노드 목록 조회 |
| 인증 | `JSESSIONID` 쿠키 |
| 파라미터 | `lpNo` — 프로젝트(과정) 번호. 이 계정 기준 `143003` = "AI 도구 학습 (AI Native Basic)" |
| 응답 필드 | `result.projectData.lcors[]` — 노드 그룹(그룹0=B1계열, 그룹1=B2계열). 각 `lcors.uqstns[]`의 `uqstnSqnt`가 노드 번호 → `label = f"B{그룹순번(1부터)}-{uqstnSqnt}"` |
| 응답 필드 | `result.projectData.myTeamMemberInfo.teamSn` — 내 팀 번호, detail 호출의 `pjtTeamSn`에 필요 |
| 발굴일 | 2026-07-24 |

### `GET /learning/learningProgress/uqstn/detail?projectNo=<lpNo>&lcorsNo=<lcorsNo>&uqstnNo=<uqstnNo>&pjtTeamSn=<teamSn>`

| | |
|---|---|
| 용도 | 미션 상세(문제기술 원문) 조회 |
| 인증 | `JSESSIONID` 쿠키 |
| 파라미터 | 위 list 응답에서 얻은 `lcorsNo`/`uqstnNo`/`teamSn` |
| 응답 필드 | `result.uqstn.sklls.skllDesc` — 미션 원문 마크다운. 맨 앞에 `![](data:image/jpeg;base64,...)` 헤더 이미지가 붙어있어 제거 필요 |
| ⚠️ 함정 | `result.uqstn.uqstnCn`은 이름이 그럴듯하지만 **항상 `null`** — 본문 아님, 헷갈리지 말 것 |
| 발굴일 | 2026-07-24 |

구현: `src/codyssey/api.py` (`list_missions`, `fetch_mission`), CLI: `codyssey mission <label>`
