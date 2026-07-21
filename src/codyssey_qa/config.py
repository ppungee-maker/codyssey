"""설정·경로·URL 상수.

자격증명은 프로젝트 루트의 `.env`(또는 실제 환경변수)에서 읽는다.
런타임 산출물(auth_state.json, screenshots/)은 프로젝트 루트 기준으로 둔다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# ── 프로젝트 루트 탐색 (pyproject.toml 이 있는 상위 디렉토리) ──
def find_project_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for parent in [here, *here.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


PROJECT_ROOT = find_project_root()
ENV_FILE = PROJECT_ROOT / ".env"
AUTH_STATE = PROJECT_ROOT / "auth_state.json"
SHOTS_DIR = PROJECT_ROOT / "screenshots"
REPORTS_DIR = PROJECT_ROOT / "qa-reports"

# ── 코디세이 URL / 셀렉터 (memory: codyssey-login-endpoint, codyssey-usr-app) ──
LOGIN_URL = "https://codyssey.kr/loginForm"
AUTH_API = "https://api.ams.codyssey.kr/authenticate"
USR_MAIN = "https://usr.codyssey.kr/main/"   # → 캠퍼스별 /{campus}/main/ 리다이렉트

# B1-3 = 노코드자동화 코스. 메인 카드 텍스트 클릭 → learningMap 진입.
B1_3_CARD_TEXT = "노코드 자동화 기초"


@dataclass(frozen=True)
class Settings:
    user_id: str | None
    password: str | None
    login_url: str = LOGIN_URL

    @property
    def has_credentials(self) -> bool:
        return bool(
            self.user_id
            and self.password
            and self.password != "your_password_here"
        )


def _parse_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def load_settings() -> Settings:
    """`.env` 파일 → 실제 환경변수 순으로 병합해 Settings 를 만든다 (환경변수 우선)."""
    env = _parse_env_file(ENV_FILE)
    for key in ("CODYSSEY_ID", "CODYSSEY_PW", "CODYSSEY_LOGIN_URL"):
        if os.environ.get(key):
            env[key] = os.environ[key]
    return Settings(
        user_id=env.get("CODYSSEY_ID"),
        password=env.get("CODYSSEY_PW"),
        login_url=env.get("CODYSSEY_LOGIN_URL", LOGIN_URL),
    )
