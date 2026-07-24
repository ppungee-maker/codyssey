"""세이AI(precheck) — 미션 GitHub repo 자동 사전평가 프록시.

미션 모달의 "AI Codyssey로 사전 평가받기" 버튼 엔드포인트를 리플레이한다. LLM 채점이라
결과가 호출마다 조금씩 달라질 수 있고(비결정적) 최대 2분 정도 걸린다. self-serve·read-only라
반복 호출해도 부작용 없음. 엔드포인트 상세는 docs/api-endpoints.md·docs/naeto-seai-usage.md 참고.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from . import api, config


class PrecheckError(RuntimeError):
    """세이AI가 비JSON(에러 문구)을 반환했거나 result 파싱에 실패했을 때 (예: repo 접근불가)."""


@dataclass(frozen=True)
class CriterionResult:
    criterion: str
    verdict: str
    reason: str


@dataclass(frozen=True)
class PrecheckResult:
    passed: bool | None  # 판단 불가 시 None
    score_text: str | None  # 예: "100%(15/15)"
    summary: str | None
    criteria: list[CriterionResult]
    raw: dict  # 원본 파싱 결과(디버깅용)


_JSON_FENCE_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL)
_PCT_RE = re.compile(r"(\d+)\s*%")


def _extract_json(result_field: str) -> dict:
    m = _JSON_FENCE_RE.search(result_field)
    payload = m.group(1) if m else result_field
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise PrecheckError(
            f"세이AI result 파싱 실패(비JSON) — repo 접근 불가/삭제 여부 확인 필요: {result_field[:200]!r}"
        ) from exc


def _normalize(parsed: dict) -> PrecheckResult:
    summary_block = parsed.get("Summary") or parsed.get("summary") or {}
    score_text = summary_block.get("최종평가 결과") or summary_block.get("최종 평가 결과")
    summary_text = summary_block.get("요약 내용") or summary_block.get("요약")

    details = parsed.get("세부 내용") or parsed.get("세부내용") or parsed.get("details") or []
    criteria: list[CriterionResult] = []
    for item in details:
        if not isinstance(item, dict):
            continue
        crit_key = next((k for k in item if k.startswith("평가기준")), None)
        verdict = item.get(crit_key) if crit_key else None
        reason = item.get("사유")
        if isinstance(reason, list):
            reason = "; ".join(str(r) for r in reason)
        criteria.append(
            CriterionResult(
                criterion=crit_key or "?",
                verdict=str(verdict) if verdict is not None else "?",
                reason=str(reason) if reason is not None else "",
            )
        )

    passed: bool | None = None
    if score_text:
        m = _PCT_RE.search(score_text)
        passed = bool(m) and int(m.group(1)) == 100
    elif criteria:
        passed = all(c.verdict.strip().lower() in ("pass", "true", "합격") for c in criteria)

    return PrecheckResult(
        passed=passed, score_text=score_text, summary=summary_text, criteria=criteria, raw=parsed
    )


def run_precheck(
    label: str, repo_url: str, branch: str = "main", *, lp_no: int = config.DEFAULT_LP_NO
) -> PrecheckResult:
    """label(예: "B1-3")의 미션에 대해 repo_url을 세이AI로 채점받는다."""
    refs, _team_sn = api.list_missions(lp_no)
    ref = refs.get(label)
    if ref is None:
        raise ValueError(f"[{label}] 노드를 찾지 못함 (라벨 오타 가능성 — 예: B2-1)")

    body = {
        "projectNo": ref.project_no,
        "lcorsNo": ref.lcors_no,
        "uqstnNo": ref.uqstn_no,
        "repoUrl": repo_url,
        "branchNm": branch,
    }
    with api._client(timeout=120) as client:  # 세이AI는 느림(최대 2분) — 기본 15s 오버라이드
        resp = api._post_json(client, "/rest/ai/evaluation/", body)

    parsed = _extract_json(resp["result"])
    return _normalize(parsed)


@dataclass(frozen=True)
class ReceivedEval:
    evaluator: str
    result: str  # PASS/FAIL
    score: float | None
    feedback: str


def received_evals(lp_no: int = config.DEFAULT_LP_NO) -> list[ReceivedEval]:
    """내 제출물이 동료/교수에게 받은 평가 조회. 취소건(상태 00005)은 기본 제외.

    ⚠ 실호출로 확인됨(2026-07-24): body를 `{"lpNo": lp_no}`만 주면 200은 오지만
    `result`가 `{"teamSn": 0, "evlPsblYn": "N"}` 처럼 빈 스텁만 반환하고
    `mtlEvlDataTxnDtoList`가 아예 없다 — lpNo만으로는 "평가 조회 가능 여부"만 확인되고
    실제 목록은 미션(projectNo/lcorsNo/uqstnNo) 단위로 스코프해야 나올 가능성이 높음
    (레퍼런스 문서의 "teamSn 미확인 → 미션에서 평가요청 먼저" 경고와 부합).
    지금은 그 목록 필드가 없으면 크래시 대신 빈 리스트로 처리한다 — 정확한 스코프 파라미터는
    실제로 평가요청이 생성된 미션이 생기면 재확인 필요.
    """
    body = {"lpNo": lp_no}
    with api._client() as client:
        resp = api._post_json(client, "/ev/request/evlTotList", body)

    items = resp["result"].get("mtlEvlDataTxnDtoList", [])
    out: list[ReceivedEval] = []
    for item in items:
        if item.get("evlStusCd") == "00005":  # 취소건 (필드명 추정 — 검증 필요)
            continue
        out.append(
            ReceivedEval(
                evaluator=item.get("evlMbrNm", "?"),
                result=item.get("mtlEvlResltNm", "?"),
                score=item.get("mtlEvlScr"),
                feedback=item.get("evlFdbkCn") or "",
            )
        )
    return out
