"""실제 OpenAI API를 쓰는 프로바이더 — OPENAI_API_KEY가 있을 때만 선택적으로 로드된다.

이 미션 제출 환경에는 유료 API 키가 없어 mock_provider가 기본값이지만, 인터페이스가
동일하므로 키만 넣으면 config.json의 "provider": "openai" 로 바로 교체된다.
"""

from __future__ import annotations

import json
import re

from ..models import BrandBrief, ColorPalette, NamingCandidate
from .base import ImageProvider, LLMProvider

try:
    from openai import OpenAI
except ImportError as exc:  # pragma: no cover - 키 없는 기본 실행 경로에선 도달 안 함
    raise ImportError("openai 패키지가 설치되어 있지 않습니다: pip install openai") from exc

_TEXT_MODEL = "gpt-4o-mini"
_IMAGE_MODEL = "dall-e-3"


def _ask_json(client: OpenAI, prompt: str) -> dict:
    resp = client.chat.completions.create(
        model=_TEXT_MODEL,
        messages=[
            {"role": "system", "content": "You are a branding assistant. Reply with JSON only."},
            {"role": "user", "content": prompt},
        ],
    )
    content = resp.choices[0].message.content or "{}"
    match = re.search(r"\{.*\}", content, re.DOTALL)
    return json.loads(match.group(0) if match else content)


class OpenAILLMProvider(LLMProvider):
    def __init__(self, api_key: str):
        self._client = OpenAI(api_key=api_key)

    def generate_naming(self, brief: BrandBrief) -> list[NamingCandidate]:
        prompt = (
            f"업종: {brief.industry}\n타겟: {brief.target}\n키워드: {', '.join(brief.keywords)}\n"
            "위 브리프로 브랜드명 후보 3~5개를 한글명(name)과 영문명(name_en) 둘 다 포함해 "
            '{"namings": [{"name": "...", "name_en": "...", "meaning": "..."}]} JSON으로.'
        )
        data = _ask_json(self._client, prompt)
        return [
            NamingCandidate(n["name"], n["meaning"], n.get("name_en"))
            for n in data.get("namings", [])
        ]

    def generate_slogans(self, brief: BrandBrief) -> list[str]:
        prompt = (
            f"업종: {brief.industry}\n타겟: {brief.target}\n키워드: {', '.join(brief.keywords)}\n"
            '슬로건 3개를 {"slogans": ["...", "...", "..."]} JSON으로.'
        )
        data = _ask_json(self._client, prompt)
        return list(data.get("slogans", []))

    def generate_story(self, brief: BrandBrief) -> str:
        prompt = (
            f"업종: {brief.industry}\n타겟: {brief.target}\n키워드: {', '.join(brief.keywords)}\n"
            '300자 내외 브랜드 스토리를 {"story": "..."} JSON으로.'
        )
        data = _ask_json(self._client, prompt)
        return str(data.get("story", ""))

    def generate_palette(self, brief: BrandBrief) -> ColorPalette:
        prompt = (
            f"업종: {brief.industry}\n타겟: {brief.target}\n톤앤매너: {brief.tone or '미지정'}\n"
            '메인 컬러 1개 + 서브 컬러 2~3개를 HEX로 '
            '{"main": "#RRGGBB", "subs": ["#RRGGBB", ...]} JSON으로.'
        )
        data = _ask_json(self._client, prompt)
        return ColorPalette(main=data["main"], subs=list(data.get("subs", [])))

    def analyze_competitors(self, brief: BrandBrief) -> list[dict]:
        if not brief.competitors:
            return []
        prompt = (
            f"업종: {brief.industry}\n타겟: {brief.target}\n키워드: {', '.join(brief.keywords)}\n"
            f"경쟁사: {', '.join(brief.competitors)}\n"
            "각 경쟁사에 대해 간단 분석과 우리 브랜드의 차별화 포인트를 "
            '{"competitors": [{"name": "...", "analysis": "...", "differentiation": "..."}]} JSON으로.'
        )
        data = _ask_json(self._client, prompt)
        return list(data.get("competitors", []))


class OpenAIImageProvider(ImageProvider):
    def __init__(self, api_key: str):
        self._client = OpenAI(api_key=api_key)

    def generate_logos(
        self, brief: BrandBrief, brand_name: str, palette: ColorPalette, count: int = 2
    ) -> list[bytes]:
        import base64

        results = []
        prompt = (
            f"Minimal flat-style logo mark for a brand named '{brand_name}' in the "
            f"{brief.industry} industry, main color {palette.main}, no text, vector-style."
        )
        for _ in range(count):
            resp = self._client.images.generate(
                model=_IMAGE_MODEL, prompt=prompt, size="1024x1024", n=1,
                response_format="b64_json",
            )
            results.append(base64.b64decode(resp.data[0].b64_json))
        return results
