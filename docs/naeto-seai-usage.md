> **이 리포 적응 메모** (원문은 아래 그대로 보존, 이 박스만 추가):
> - 세션 저장 경로는 `artifacts/state/daejeon.json`이 아니라 **`auth_state.json`**
>   (`codyssey login`으로 생성, `src/codyssey/config.AUTH_STATE`).
> - 실행은 `uv run <cmd>`가 아니라 설치된 **`codyssey`** 콘솔 스크립트
>   (예: `codyssey naeto "..."`, `codyssey precheck --mission B1-3 ...`).
> - 구현은 `src/codyssey/naeto.py`, `src/codyssey/precheck.py`. 엔드포인트 표는
>   [`docs/api-endpoints.md`](api-endpoints.md)에도 정리되어 있다(이 문서는 사용법 위주,
>   그쪽은 엔드포인트 단일 출처).

---

# 네이토 · 세이AI 사용법 (사전지식 0 에이전트용)

Codyssey 대전 페이지가 쓰는 두 AI 기능을 **직접 리플레이**하는 도구 두 개의 자립 매뉴얼.
이 문서 하나만 읽으면 배경 지식 없이도 호출할 수 있게 썼다.

- **네이토(학습 네이토)** = 학습맵 챗봇 + 멀티모달 생성(이미지/음성/영상). CLI = `naeto`.
- **세이AI(사전평가)** = 미션 repo 를 AI Codyssey 로 채점받아 Pass/Fail·평가의견 회수. CLI = `precheck`.

둘 다 **codyssey.kr 자체 기능이 아니라 학교 프록시**다 — 서버는 LLM 프록시 + 토큰 미터링만
하고, 인증은 로그인 세션 쿠키를 쓴다. 자체 API 키 없다.

---

## 0. 공통 전제 (먼저 안 맞으면 둘 다 안 됨)

### 실행 방법
이 repo(`codyssey`) 패키지 안에서 돈다. 항상 `uv run <cmd>`:
```bash
uv run naeto "..."          # 네이토
uv run precheck --mission … # 세이AI
```

### 인증 = 로그인 세션 쿠키 (API 키 아님)
1. `.env` 에 자격증명:
   ```
   CODYSSEY_USER_ID=<코디세이 아이디>
   CODYSSEY_USER_PW=<비밀번호>
   ```
   (부계정은 `CODYSSEY_PROFILE=alt` + `CODYSSEY_ALT_USER_ID/PW`. 프로필명이 곧 키 프리픽스.)
2. 브라우저로 1회 로그인해 세션 쿠키를 `artifacts/state/daejeon.json`(storage_state)에 저장:
   ```bash
   uv run python -m codyssey.discovery.capture --auto
   ```
   이후 httpx 가 이 쿠키를 실어 endpoint 를 직접 때린다(브라우저 재기동 0).
3. **세션은 서버 idle TTL 로 자주 만료**된다(JSESSIONID). `naeto` 는 명령 시작 시 값싼 GET 으로
   선제 감지해 **자동 재로그인**한다(`ensure_session`). `precheck` 는 자동 재로그인이 없어 만료 시
   `세션 만료(로그인 리다이렉트)…` 로 실패 → 위 `capture --auto` 재실행.

### 호스트·엔드포인트 (Settings 기본값)
| 이름 | 값 | 용도 |
|---|---|---|
| `api_usr` | `https://api.usr.codyssey.kr` | 네이토·평가 리플레이 대상 |
| `api_ams` | `https://api.ams.codyssey.kr` | 로그인(`/authenticate`) |
`.env` 로 override 가능(`CODYSSEY_API_USR` 등). 세션 쿠키는 `.codyssey.kr` 서브도메인 공유.

### 비용 = virtualTokens(vt)
네이토 멀티모달·챗은 **월 virtualTokens 쿼터**를 차감한다. 쿼터 부족 = HTTP `402`.
응답·CLI 로그가 `vt`(과금)·`잔여`를 보여준다. 영상(video)이 특히 비싸다 — 아래 경고 참조.

---

## 1. 네이토 (학습 챗 + 멀티모달) — `naeto`

`claude -p` 스타일 한방 CLI. **claude 명령에서 단어만 `naeto` 로 바꿔도 동작**하게 정렬했다.
서버는 무상태 → 매 호출 전체 대화 이력을 body 로 보낸다(모델·시스템프롬프트·메시지 전부 클라가 실음).

### 1.1 챗 (기본 서브커맨드)
```bash
uv run naeto "파이썬 데코레이터 설명"                 # 기본 = chat
uv run naeto -p "..." --model claude-opus-4-8         # -p 는 boolean(항상 print, no-op). --model 미러
cat 코드.py | uv run naeto "이 코드 리뷰해"            # 파이프 = 프롬프트에 이어붙음(둘 다 전송)
echo "리뷰해" | uv run naeto -                          # '-' = stdin 전체가 프롬프트
uv run naeto "3*3?" --output-format json               # {"result": …} 파이프용(스트리밍 끔)
uv run naeto "안녕" --system-prompt "영어로" --append-system-prompt "느낌표"  # system 합성
uv run naeto "이 이미지 뭐야" --image photo.png        # 비전 입력(멀티모달, 반복 가능)
uv run naeto "이 문서 요약" --pdf spec.pdf              # PDF 입력
uv run naeto "sin 그래프 그려줘" --code-out plot        # 코드실행 산출 이미지 저장(plot_1.png…)
uv run naeto -p "이 코드 리뷰해" --preset codeReview   # 프리셋 페르소나(그 systemPrompt 재현)
```
- 기본 모델 = `gemini-3-flash`. `--model`/`-m` 으로 교체. 목록 = `uv run naeto models`.
- 시스템 프롬프트 우선순위: `--raw`(빈) > `--system-prompt` > `--preset` systemPrompt > 제네릭.
- 본문은 **stdout**(스트리밍), 미터링(`모델 · vt · session`)은 **stderr** → `2>/dev/null` 로 본문만.

### 1.2 프리셋(페르소나) — UI 챗 메뉴 4종
```bash
uv run naeto presets            # tutor / codeReview / debug / concept (systemPrompt 미리보기)
uv run naeto chat "..." --preset debug
```
`--preset` = 그 프리셋의 `systemPrompt`·`summaryPrompt` 를 body 에 실어 UI 를 충실 재현. `presetCd` 는
서버 필수 태그, 실거동은 systemPrompt 가 결정.

### 1.3 세션 이어가기 (대화 = 세션)
무상태 CLI 호출도 서버가 세션으로 저장한다(호출당 `sessionId` 발급).
```bash
uv run naeto sessions                    # 저장된 챗 세션 목록(최신순)
uv run naeto history <sessionId>         # 그 세션 대화 turn
uv run naeto chat "이어서…" -s <sessionId>  # 이전 대화 재전송 + 같은 세션에 append
```

### 1.4 멀티모달 생성 (이미지 동기 · 음성 동기 · 영상 비동기)
```bash
uv run naeto image "친환경 텀블러 제품샷" -o cup.png    # 기본 gpt-image-1-mini, low 품질(저렴)
uv run naeto tts "한 번의 선택" -o vo.mp3 --voice nova   # 기본 tts-1/alloy
uv run naeto video "카페 텀블러 슬로우 돌리인" -o ad.mp4 --duration 4  # 기본 veo-3.1-fast
uv run naeto logs                                       # 미디어 생성 로그(vt 과금 감사, 중복 확인)
```
- **영상은 비동기** = job 등록 후 `media-logs` 폴링으로 `s3Key` 확보(기본 300s 타임아웃).
- ⚠ **Veo 표준/8초 등 고비용 조합은 월쿼터(1M) 초과로 402**. Fast·단초(4s) 권장.
- ⚠ **저장 실패 = 이중 과금 위험**: 미디어는 서버 생성·과금 뒤 다운로드다. 없는 폴더로 저장하다
  크래시하면 재실행 시 또 과금된다(실측: tts 550 vt = 275×2). CLI 는 부모 폴더 자동 생성으로 방어.

### 1.5 ReAct 에이전트 (로컬 도구 툴콜)
```bash
uv run naeto agent "작업…" --max-steps 6            # 기본 claude-haiku-4(지시이행력)
uv run naeto agent "…" --allow-exec                 # shell/python 로컬실행 등록(위험)
```

### 네이토 실 엔드포인트 (라이브 캡처, 근거 = `api/naeto/client.py`)
| 기능 | 메서드·경로 | body 핵심 | 응답 |
|---|---|---|---|
| 챗 | POST `/learning/usr/ai/ask-stream` | `{sessionId,modelCd,mbrId,systemPrompt,presetCd,messages:[{role,content}]}` | `text/event-stream`: `event:delta`(청크)…`event:done`(`{answer,virtualTokens,sessionId,…}`) |
| 모델 목록 | GET `/learning/usr/ai/models` | — | 모델+배수 |
| 프리셋 | GET `/learning/usr/ai/presets` | — | 4종(systemPrompt 포함) |
| 세션 목록 | GET `/learning/usr/ai/sessions` | — | `{sessionId,title,msgCnt,…}` |
| 세션 이력 | GET `/learning/usr/ai/history?sessionId=` | — | turn 목록 |
| 이미지 | POST `/learning/usr/ai/image-gen` | `{provider,model,size,quality,prompt}` | 동기 `{images:[{url}],virtualTokens}` |
| 음성 | POST `/learning/usr/ai/tts-gen` | `{provider,model,voice,speed,input}` | 동기 `{url,virtualTokens}` |
| 영상 | POST `/learning/usr/ai/video-gen` | `{provider,model,resolution,durationSeconds,prompt}` | 비동기 job(`jobId`) |
| 미디어 로그 | GET `/learning/usr/ai/media-logs` | — | 성공 이력(video 폴링용 `s3Key`) |
| 다운로드 | GET `/learning/usr/ai/files/{s3Key}` | 쿠키 인증 | 바이트 |
| mbrId | GET `/rest/user/info/detail` | — | 세션 사용자 `mbrId` |

- SSE `data:` 는 JSON 인코딩 문자열. `event:done` payload 에 최종 `answer`·과금·`sessionId`.
- `mbrId` = `.env` `CODYSSEY_MBR_ID` 우선, 없으면 `user/info/detail` 에서 자동 추출.
- provider 는 modelCd 접두사로 추론(`gpt-image/tts-`=openai, `imagen/gemini/veo`=google). 애매하면 `--provider`.

---

## 2. 세이AI (미션 사전평가) — `precheck`

미션 모달 `[평가 요청] → [AI Codyssey로 사전 평가받기]` 버튼의 endpoint 를 리플레이.
GitHub repo+branch 를 세이AI(LLM)가 분석해 **미션 기능요구 기준으로 Pass/Fail 채점**하고
평가의견을 돌려준다.

### 성질 (중요)
- **self-serve · read-only**: 사람 알림 0, 서버 쓰기 0. 몇 번 돌려도 안전(동료평가 요청과 다름).
- **비결정적**: 세이AI 가 LLM 이라 같은 repo 도 회차마다 점수·문항 스키마가 미세하게 달라진다.
  1회 PASS 는 표본 오차일 수 있다(수렴 판정은 여러 회 필요).
- LLM 분석이라 **수십 초** 소요(timeout 기본 120s).

### 사용
```bash
uv run precheck --mission B1-3                        # B1-3 기본 repo 채점(편의 맵)
uv run precheck --mission B1-3 --repo <URL> --branch main
uv run precheck --uqstn 186010 --repo <URL>          # 미션번호 직접 교체(--repo 동반 필수)
uv run precheck --mission B1-3 --json                # criteria 전문 JSON(파이프용)
uv run precheck --mission B1-3 --verbose             # 문항 사유 전문
```
`--mission`(편의 맵) 또는 `--uqstn`(직접) 중 하나 필수(mutually exclusive). repo 미지정 시 중단.

### 출력
```
[PASS] 100%(15/15)  (15/15 통과)
요약: …
문항별:
  ✅ 평가기준 1: Pass — <사유 첫줄>
  ❌ 평가기준 2: Fail — …
```
`is_pass` = 전 문항 통과(=만점) 여부.

### ID 모델 (문제 1개 = 3키)
미션 하나를 가리키려면 **3키**가 필요하다:
| 키 | 뜻 | 대전 AI Native Basic 기본 |
|---|---|---|
| `projectNo` | 학습 프로젝트 | `143003` |
| `lcorsNo` | 과정(개인/팀) | `1128005`(개인) / `1128006`(팀) |
| `uqstnNo` | 단위문제 | 미션별(예 B1-3 = `186002`) |
`--mission B1-3` 은 이 3키를 편의 맵(`api/missions.py`)에서 채운다. 맵에 없는 미션은
`--uqstn <번호> --repo <URL>`(+필요시 `--lcors`)로 직접.

### 세이AI 실 엔드포인트 (근거 = `api/evaluation.py`)
```
POST /rest/ai/evaluation/   (JSON body)
  body: {projectNo, lcorsNo, uqstnNo, repoUrl, branchNm}
  resp: {code, message, result}
    result = ```json … ``` 코드펜스로 감싼 JSON 문자열:
      {"Summary": {"최종평가 결과": "100%(15/15)", "요약 내용": "…"},
       "세부 내용": [{"평가기준 1": "Pass", "사유": "…"}, …]}
```
- ⚠ **result 스키마가 회차마다 변한다**(LLM 출력): 키 공백(`세부내용`/`세부 내용`), verdict 위치,
  사유 str/list, list/dict 혼재. `_parse_result` 가 A~D 4스키마를 흡수해 `AiEvalResult` 로 정규화.
- repo 삭제·접근 불가면 세이AI 가 비JSON(에러문구) 반환 → `result 파싱 실패(비JSON)` RuntimeError.
- 채점 대상 repo 는 **공개 HTTPS URL** 이어야 한다(세이AI 가 원격을 clone). 답안 push 는 이 문서 밖.

### (참고) 제출물이 받은 평가 회수
같은 `api/evaluation.py` 에 요청자 시점 조회가 있다 — 동료/교수가 **내 제출물에 준** 평가:
```
POST /ev/request/evlTotList → result.mtlEvlDataTxnDtoList[]
  {evlMbrNm(평가자), mtlEvlResltNm(PASS/FAIL), mtlEvlScr, evlFdbkCn(의견 전문), …}
```
`received_evals()`. 취소건(상태 `00005`)은 점수·의견이 비어 기본 제외.

---

## 3. 자주 나는 에러

| 증상 | 원인 | 대응 |
|---|---|---|
| `세션 만료(로그인 리다이렉트)…` | JSESSIONID idle 만료 | `capture --auto` 재실행(naeto 는 자동) |
| HTTP `402` / `쿼터 부족` | 월 virtualTokens 소진 | 저비용 모델·조합, 다음 달 대기 |
| `세이AI result 파싱 실패(비JSON)` | repo 삭제·비공개·접근불가 | repo URL·공개여부·branch 확인 |
| `teamSn 미확인` (평가 저장 경로) | 평가요청 미생성 | 미션에서 평가요청 먼저 |
| video 렌더 타임아웃 | 고해상·장초 | `--duration 4`·fast 모델, `--poll-timeout` ↑ |

---

## 4. 스스로 구축할 영역 (이 문서가 안 다루는 것)
- **auth 구체 절차**: 코디세이 로그인·git push 인증은 각자 몫. 여기선 "세션 쿠키가 필요하다"까지만.
- **답안 생성·push**: 세이AI 는 원격 repo 를 clone 해 채점한다 — 답안 작성·commit·push 는 별도.
- **인자 설계·확장**: 위는 이 repo 구현. 다른 CLI 로 다시 짜도 실 endpoint 는 §1·§2 표가 정본.
