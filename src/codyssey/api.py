"""api.usr.codyssey.kr 직접 호출 — 브라우저 없이 미션 원문을 읽어온다.

Playwright로 노드를 클릭해 모달을 여는 대신, 실제 프론트가 호출하는 JSON API를
httpx로 직접 재현한다. 인증은 `auth_state.json`에 저장된 JSESSIONID 쿠키를 그대로
재사용한다(로그인 자체는 여전히 `codyssey login`으로 브라우저를 통해 수행).

엔드포인트 상세(파라미터, 응답 필드 경로, 함정)는 `docs/api-endpoints.md` 참고.
새 엔드포인트를 발굴하면 여기가 아니라 그 문서에 기록한다.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx

from . import config


class SessionExpired(RuntimeError):
    """저장된 세션(JSESSIONID)이 만료/무효일 때."""


@dataclass(frozen=True)
class MissionRef:
    label: str
    title: str
    project_no: int
    lcors_no: int
    uqstn_no: int


def _load_cookies() -> dict[str, str]:
    if not config.AUTH_STATE.exists():
        raise SessionExpired("auth_state.json 없음 — codyssey login 먼저 실행")
    data = json.loads(config.AUTH_STATE.read_text(encoding="utf-8"))
    return {c["name"]: c["value"] for c in data.get("cookies", [])}


def _client(timeout: float = 15) -> httpx.Client:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://usr.codyssey.kr/",
        "User-Agent": "Mozilla/5.0",
    }
    return httpx.Client(
        base_url=config.LEARNING_API_BASE, cookies=_load_cookies(), headers=headers, timeout=timeout
    )


def _get_json(client: httpx.Client, path: str, **params) -> dict:
    r = client.get(path, params=params)
    if r.status_code == 401:
        raise SessionExpired("세션 만료(401) — codyssey login 필요")
    r.raise_for_status()
    return r.json()


def _post_json(client: httpx.Client, path: str, json_body: dict) -> dict:
    r = client.post(path, json=json_body)
    if r.status_code == 401:
        raise SessionExpired("세션 만료(401) — codyssey login 필요")
    r.raise_for_status()
    return r.json()


_member_id_cache: str | None = None


def get_member_id() -> str:
    """mbrId — `.env`의 CODYSSEY_MBR_ID 우선, 없으면 /rest/user/info/detail 조회 (프로세스 내 캐시)."""
    global _member_id_cache
    if _member_id_cache is not None:
        return _member_id_cache
    settings = config.load_settings()
    if settings.mbr_id:
        _member_id_cache = settings.mbr_id
        return _member_id_cache
    with _client() as client:
        data = _get_json(client, "/rest/user/info/detail")
    _member_id_cache = data["result"]["mbrId"]
    return _member_id_cache


def list_missions(lp_no: int = config.DEFAULT_LP_NO) -> tuple[dict[str, MissionRef], str]:
    """학습맵의 미션 노드(label → 식별자) 전체 + 내 팀 번호(teamSn)를 가져온다."""
    with _client() as client:
        data = _get_json(client, "/learning/learningProgress/child/list", lpNo=lp_no)

    project_data = data["result"]["projectData"]
    team_sn = project_data["myTeamMemberInfo"]["teamSn"]

    # lcorsNo 오름차순 = B1 그룹, B2 그룹 순서 (API 응답 순서에 의존하지 않도록 명시 정렬)
    ordered_lcors = sorted(project_data["lcors"], key=lambda lcors: lcors["lcorsNo"])

    refs: dict[str, MissionRef] = {}
    for group_idx, lcors in enumerate(ordered_lcors, start=1):
        for uq in lcors["uqstns"]:
            label = f"B{group_idx}-{uq['uqstnSqnt']}"
            refs[label] = MissionRef(
                label=label,
                title=uq["uqstnNm"],
                project_no=lp_no,
                lcors_no=lcors["lcorsNo"],
                uqstn_no=uq["uqstnNo"],
            )
    return refs, team_sn


_LEADING_IMAGE_RE = re.compile(r"^!\[\]\(data:image/[^)]+\)\s*\n*")


def _clean_mission_markdown(raw: str | None) -> str | None:
    """skllDesc 맨 앞의 base64 헤더 이미지 마크다운을 제거."""
    if raw is None:
        return None
    return _LEADING_IMAGE_RE.sub("", raw, count=1).strip()


def fetch_mission(label: str, *, lp_no: int = config.DEFAULT_LP_NO) -> tuple[MissionRef | None, str | None]:
    """label(예: "B2-1")의 미션 원문(마크다운)을 브라우저 없이 직접 읽어온다.

    반환: (MissionRef 또는 None(라벨 없음/잠김), 원문 텍스트 또는 None).
    세션이 만료됐으면 SessionExpired 예외.
    """
    refs, team_sn = list_missions(lp_no)
    ref = refs.get(label)
    if ref is None:
        return None, None

    with _client() as client:
        data = _get_json(
            client,
            "/learning/learningProgress/uqstn/detail",
            projectNo=ref.project_no,
            lcorsNo=ref.lcors_no,
            uqstnNo=ref.uqstn_no,
            pjtTeamSn=team_sn,
        )
    raw = data["result"]["uqstn"]["sklls"]["skllDesc"]
    return ref, _clean_mission_markdown(raw)
