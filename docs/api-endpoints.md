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

### `GET /learning/learningProgress/status/list`

| | |
|---|---|
| 용도 | **이 계정이 속한 모든 과정(project)**의 미션을 한 번에 조회 — `lpNo` 파라미터 불필요, 계정 기준 전수 |
| 인증 | `JSESSIONID` 쿠키 |
| 응답 필드 | `result.uqstns[]` — 각 항목에 `projectNo`/`projectNm`(과정 번호/이름), `lcorsNo`, `uqstnNo`, `uqstnNm`, `useYn`, `uqstnForceEndYmd` 등 |
| 발견 경위 | 대전 캠퍼스 계정으로 로그인 중, 이 계정에 **두 번째 과정**이 걸려있는 걸 여기서 처음 확인함(2026-08-16): `projectNo=143002` = "AI 활용 학습 (AI Native Advanced)" (기존에 쓰던 `143003`="AI 도구 학습 Basic"과 별개). 이후 2026-09-03에 **세 번째 과정**도 확인: `projectNo=143001` = "AI 응용 학습 (AI Native Master)" |
| ⚠️ 주의 | `uqstnForceEndYmd`가 과정마다 오래된 날짜(예: 2026-03-11)로 찍혀 있어도 `useYn=Y`면 무시하고 넘어갈 것 — 서울 코디세이 공통 일정 값이 찍히는 것으로 보이며 실제 마감과 무관(제니형님 확인, 2026-08-16) |
| 발굴일 | 2026-08-16 (143002 확인), 2026-09-03 (143001 확인) |



베이스도 동일하게 `https://api.usr.codyssey.kr`, 인증도 동일 `JSESSIONID` 쿠키 — 별도 API 키 없음.
사용법 전체(파라미터 조합·CLI 플래그 설계 근거)는 [`docs/naeto-seai-usage.md`](naeto-seai-usage.md) §1 참고,
여기는 엔드포인트 표만.

과금 단위는 virtualTokens(vt). **HTTP 402 = 월 쿼터 소진.**

⚠️ **호스트 전체 함정**: 학습맵/미션 API(`/learning/learningProgress/...`)는 응답이
`{code,message,result}`로 감싸여 있지만, **네이토 GET 목록류(`models`/`presets`/`sessions`/
`history`/`media-logs`)는 감싸지 않은 bare 배열**을 바로 반환한다(`result` 키 없음). 같은 host인데
엔드포인트 그룹마다 응답 포맷이 다르다 — `["result"]`로 인덱싱하면 `TypeError`. (2026-07-24 실호출로 검증됨)

### `POST /learning/usr/ai/ask-stream` — 챗 ✅ 검증됨

| | |
|---|---|
| 용도 | AI 챗 (서버 무상태 — 매 호출 전체 대화 이력을 body로 재전송해야 함) |
| Body | `{sessionId, modelCd, mbrId, systemPrompt, presetCd, messages:[{role,content}]}` |
| 응답 | `text/event-stream` — `event:delta`(청크) 반복 후 `event:done`(`data:`에 `{answer,virtualTokens,sessionId,...}`) |
| ⚠️ 함정 1 | 각 SSE 프레임은 `event:`/`data:`/빈 줄(경계) 3줄 조합. 최종 답변·과금은 delta가 아니라 `done` 이벤트에만 있음 |
| ⚠️ 함정 2 (실측) | `presetCd`는 레퍼런스 문서엔 선택사항처럼 적혀있지만 **실제로는 필수** — 안 주면 200 응답에 `event:error`, `data:유효한 프리셋이 필요합니다: presetCd 필수`가 옴. 4개 프리셋(tutor/codeReview/debug/concept) 중 하나로 기본값 지정해야 함(`naeto.py`는 `"tutor"`로 기본값) |
| ⚠️ 함정 3 (실측) | `event:error`의 `data:`는 **JSON이 아니라 그냥 에러 문구 텍스트** — delta/done과 같은 파서로 `json.loads`하면 크래시. event 종류별로 분기해서 처리해야 함 |
| 실측 비용 | `gemini-3-flash` 기본 모델, 짧은 질문 1회 응답 = **1,680 vt** |
| 발굴일 | 2026-07-24 (실호출로 검증) |

### `GET /learning/usr/ai/models` / `presets` / `sessions` — 목록 조회 ✅ 검증됨

| | |
|---|---|
| 용도 | 모델 목록(배수 포함) / 프리셋 4종(tutor·codeReview·debug·concept, systemPrompt+summaryPrompt 포함) / 저장된 챗 세션 목록(`sessionId,mbrId,title,lastModelCd,msgCnt,...`) |
| 인증 | `JSESSIONID` 쿠키 |
| 응답 | bare 배열 (`["result"]` 아님, 위 함정 참고) |
| 비고 | 무료(과금 없음) — 2026-07-24 실호출로 정상 동작 확인 |

### `GET /learning/usr/ai/history?sessionId=<id>` — 세션 대화 이력 ✅ 검증됨

세션 이어가기(`-s`/`--session-id`)에 필요. 무료. 응답도 bare 배열, 각 turn은
`{role, content, virtualTokens, inputTokens/outputTokens, modelCd, ...}` — `role`/`content`가
`chat()`의 messages 형식과 그대로 호환되어 세션 이어가기에 바로 재사용 가능.

### `POST /learning/usr/ai/image-gen` — 이미지 생성 ✅ 검증됨 (`tts-gen`은 아직 미검증)

| | |
|---|---|
| 용도 | 이미지(`{provider,model,size,quality,prompt}`) / 음성(`{provider,model,voice,speed,input}`) 생성 |
| 응답 | 동기 — `{images:[{url}], virtualTokens}` / `{url, virtualTokens}` |
| ⚠️ 함정 1 | `provider`는 modelCd 접두사로 추론(`gpt-image*`/`tts-*`→openai, `imagen*`/`gemini*`/`veo*`→google) |
| ⚠️ 함정 2 (실측) | `url`은 절대 URL도 bare s3Key도 아니고 **이미 `/learning/usr/ai/files/...`로 시작하는 전체 API 경로**로 옴. `/files/{value}`로 한 번 더 감싸면 경로가 중복돼 404 — `value.startswith("/")`면 그대로 GET해야 함 |
| 실측 비용 | `gpt-image-1-mini` / `size=1024x1536` / `quality=low` = **2,000 vt** (회당, 일정) |
| 발굴일 | 2026-07-24 (실호출로 검증, B2-1 예시답안 이미지 6장 생성) |

### `POST /learning/usr/ai/video-gen` — 비동기 생성 (가장 비쌈)

| | |
|---|---|
| 용도 | `{provider,model,resolution,durationSeconds,prompt}` → `{jobId}` (즉시 미디어 없음) |
| 후속 | `GET /learning/usr/ai/media-logs`를 폴링해 해당 `jobId`의 `s3Key` 확보 → `GET /learning/usr/ai/files/{s3Key}`(쿠키 인증, 바이트) 다운로드 |
| ⚠️ 함정 1 | Veo 표준/8초 등 고비용 조합은 월쿼터 초과로 402 — fast+4초 권장(기본값) |
| ⚠️ 함정 2 (실제 사고) | 미디어는 **생성·과금이 다운로드보다 먼저** 일어난다. 저장 폴더가 없어서 로컬 저장이 크래시하면, 순진하게 재실행 시 또 과금됨(실측: TTS 550vt = 275×2). **모든 생성 함수는 네트워크 호출 전에 `out_dir.mkdir(parents=True, exist_ok=True)`부터 실행**해야 함 |
| 발굴일 | 2026-07-24 (레퍼런스 문서 기반, 미검증) |

### `GET /rest/user/info/detail` — mbrId 조회 ✅ 검증됨

챗 body의 `mbrId` 확보용. `.env`의 `CODYSSEY_MBR_ID`가 있으면 이 호출 생략.
응답은 `{code,message,result}`로 감싸져 있고 `result.mbrId`에 있음 — 2026-07-24 실호출로 확인.

구현: `src/codyssey/naeto.py`, CLI: `codyssey naeto {models|presets|sessions|history|logs|chat|image|tts|video}`

---

## 세이AI (미션 사전평가)

베이스 동일 `https://api.usr.codyssey.kr`. 사용법은 [`docs/naeto-seai-usage.md`](naeto-seai-usage.md) §2 참고.

### `POST /rest/ai/evaluation/` — 미션 repo AI 채점

| | |
|---|---|
| 용도 | GitHub repo를 세이AI(LLM)로 채점 — Pass/Fail + 문항별 평가의견 |
| 인증 | `JSESSIONID` 쿠키 |
| Body | `{projectNo, lcorsNo, uqstnNo, repoUrl, branchNm}` — 앞 3개는 `list_missions()`로 조회(하드코딩 맵 안 씀) |
| 응답 | `{code, message, result}` — `result`는 ` ```json ... ``` ` 코드펜스로 감싼 JSON **문자열** |
| ⚠️ 함정 1 | `result` 파싱된 JSON의 스키마가 **호출마다 변함**(LLM 출력): `세부 내용`/`세부내용`(공백 유무), `사유`가 string/list 혼재, verdict 필드 위치 이동. 4개 변형을 관용적으로 흡수하는 정규화 필요(고정 스키마 검증기 쓰면 안 됨) |
| ⚠️ 함정 2 | repo 삭제/비공개/접근불가면 `result`가 JSON이 아니라 에러 문구 텍스트로 옴 — 별도 예외로 구분 처리 |
| 성질 | self-serve, read-only, 반복 호출 안전. LLM 분석이라 수십초~2분 소요 |
| 발굴일 | 2026-07-24 (레퍼런스 문서 기반, 미검증) |

### `POST /ev/request/evlTotList` — 받은 평가 조회 ⚠️ 부분 검증됨

| | |
|---|---|
| 용도 | 내 제출물에 동료/교수가 **준** 평가 목록 (세이AI 자가채점과는 다른 데이터) |
| Body | `{"lpNo": <lpNo>}` — 200은 오지만(실호출 확인) 이것만으로는 목록이 안 나옴, 아래 참고 |
| 응답(레퍼런스 문서 기준) | `result.mtlEvlDataTxnDtoList[]` — `{evlMbrNm(평가자), mtlEvlResltNm(PASS/FAIL), mtlEvlScr, evlFdbkCn(의견), ...}` |
| ⚠️ 실측 결과(2026-07-24) | `{"lpNo": lp_no}`만 보내면 `result`가 `{"teamSn": 0, "evlPsblYn": "N"}` 스텁만 오고 `mtlEvlDataTxnDtoList` 자체가 없음. lpNo 단위가 아니라 **미션(projectNo/lcorsNo/uqstnNo) 단위로 스코프**해야 실제 목록이 나올 가능성이 높음 — 문서의 "teamSn 미확인 → 미션에서 평가요청 먼저" 경고와 부합. 정확한 스코프 파라미터는 실제 평가요청이 존재하는 미션이 생기면 재검증 필요 |
| 방어 처리 | `received_evals()`는 `mtlEvlDataTxnDtoList` 부재 시 크래시 대신 빈 리스트 반환 |
| 취소건 필터 | 상태값 `00005`인 항목 제외 — 필드명(`evlStusCd`)은 레퍼런스 문서에 명시 없어 추정치, 실제 목록이 나오면 재검증 필요 |
| 발굴일 | 2026-07-24 (레퍼런스 문서 + 부분 실호출) |

구현: `src/codyssey/precheck.py`, CLI: `codyssey precheck <label> <repo_url> [--branch]`, `codyssey received-evals`
