"""무료·오프라인 mock 프로바이더 — 실제 LLM/이미지 생성 API 없이 결정적으로 결과를 만든다.

브리프 내용(업종/타겟/키워드/톤)을 그대로 템플릿에 꽂아 넣는 방식이라 진짜 생성형 AI
품질은 아니지만, 인터페이스(LLMProvider/ImageProvider)는 실제 API 구현체
(`openai_provider.py`)와 동일하므로 API 키만 있으면 그대로 교체 가능하다.
"""

from __future__ import annotations

import hashlib
import io
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..models import BrandBrief, ColorPalette, NamingCandidate
from .base import ImageProvider, LLMProvider

_NAME_SUFFIXES = ["랩", "웍스", "베이스", "허브", "루트", "스튜디오"]
_EN_SUFFIXES = ["Labs", "Works", "Hub", "Base", "Studio", "Co"]

# 보너스(다국어 네이밍)용 한->영 근사 사전. 사전에 없는 단어는 발음 그대로 로마자 폴백.
# mock 구현이라 실제 번역 품질은 아님 — 실 API 연동 시 openai_provider가 이 자리를 대체.
_EN_HINTS: dict[str, str] = {
    "집중": "Focus", "루틴": "Routine", "느긋함": "Ease", "여유": "Ease",
    "커피": "Coffee", "스페셜티": "Specialty", "빵": "Bread", "베이커리": "Bakery",
    "건강": "Health", "운동": "Fit", "여행": "Journey", "책": "Read",
    "디자인": "Design", "속도": "Speed", "신뢰": "Trust", "감성": "Mood",
    "프리미엄": "Premium", "친환경": "Eco", "미니멀": "Minimal", "스마트": "Smart",
}

_ROMAN_MAP = str.maketrans({
    "가": "ga", "나": "na", "다": "da", "라": "ra", "마": "ma", "바": "ba", "사": "sa",
    "아": "a", "자": "ja", "차": "cha", "카": "ka", "타": "ta", "파": "pa", "하": "ha",
})


def _romanize_fallback(word: str) -> str:
    """사전에 없는 한글 단어의 아주 단순한 음차 폴백 (완전한 로마자 변환기는 아님)."""
    roman = word.translate(_ROMAN_MAP)
    return roman.capitalize() if roman != word else "Brand"


def _to_english(word: str) -> str:
    return _EN_HINTS.get(word.strip(), _romanize_fallback(word.strip()))

_SLOGAN_TEMPLATES = [
    "{keyword}, 이제 {target}의 새로운 기준입니다.",
    "당신의 하루에 {keyword}를 더하다.",
    "{industry}의 다음 장을 여는 {keyword}.",
    "{target}를 위한, {keyword} 그 이상의 경험.",
]

_TONE_PALETTES: dict[str, ColorPalette] = {
    "모던": ColorPalette(main="#2B2D42", subs=["#8D99AE", "#EDF2F4"]),
    "따뜻한": ColorPalette(main="#E07A5F", subs=["#F2CC8F", "#81B29A"]),
    "신뢰": ColorPalette(main="#1B4965", subs=["#5FA8D3", "#CAE9FF"]),
    "활기찬": ColorPalette(main="#F94144", subs=["#F9C74F", "#90BE6D"]),
    "미니멀": ColorPalette(main="#22223B", subs=["#4A4E69", "#C9ADA7"]),
}
_FALLBACK_PALETTES = list(_TONE_PALETTES.values())


def _seed(brief: BrandBrief) -> int:
    raw = f"{brief.industry}|{brief.target}|{','.join(brief.keywords)}"
    return int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8], 16)


class MockLLMProvider(LLMProvider):
    def generate_naming(self, brief: BrandBrief) -> list[NamingCandidate]:
        rng = random.Random(_seed(brief))
        candidates = []
        for i in range(4):
            kw = rng.choice(brief.keywords).strip()
            suffix = _NAME_SUFFIXES[i % len(_NAME_SUFFIXES)]
            en_suffix = _EN_SUFFIXES[i % len(_EN_SUFFIXES)]
            name = f"{kw}{suffix}"
            name_en = f"{_to_english(kw)} {en_suffix}"
            meaning = (
                f"'{kw}'에서 착안한 이름으로, {brief.industry} 영역에서 "
                f"{brief.target}에게 어필하는 '{suffix}' 컨셉을 담았습니다."
            )
            candidates.append(NamingCandidate(name=name, meaning=meaning, name_en=name_en))
        return candidates

    def generate_slogans(self, brief: BrandBrief) -> list[str]:
        rng = random.Random(_seed(brief) + 1)
        keywords = list(brief.keywords)
        rng.shuffle(keywords)
        slogans = []
        for i, template in enumerate(_SLOGAN_TEMPLATES[:3]):
            kw = keywords[i % len(keywords)]
            slogans.append(
                template.format(keyword=kw, target=brief.target, industry=brief.industry)
            )
        return slogans

    def generate_story(self, brief: BrandBrief) -> str:
        tone = brief.tone or "진솔한"
        notes = f" {brief.notes}" if brief.notes else ""
        story = (
            f"{brief.industry} 시장에서 {brief.target}가 겪는 불편함을 지켜보며 브랜드가 시작됐습니다. "
            f"핵심 키워드인 '{', '.join(brief.keywords)}'를 중심으로, {tone} 태도로 문제를 풀어가고자 합니다. "
            f"경쟁이 치열한 이 영역에서도 {brief.target}가 가장 먼저 떠올리는 이름이 되는 것이 목표입니다."
            f"{notes}"
        )
        return story[:320]

    def generate_palette(self, brief: BrandBrief) -> ColorPalette:
        if brief.tone and brief.tone in _TONE_PALETTES:
            return _TONE_PALETTES[brief.tone]
        rng = random.Random(_seed(brief) + 2)
        return rng.choice(_FALLBACK_PALETTES)

    def analyze_competitors(self, brief: BrandBrief) -> list[dict]:
        """보너스: 입력된 경쟁사 각각에 대해 간단한 차별화 포인트를 제안한다."""
        results = []
        for competitor in brief.competitors:
            analysis = (
                f"'{competitor}'는 {brief.industry} 시장에서 이미 인지도를 확보한 브랜드로 보입니다. "
                f"우리 브랜드는 '{', '.join(brief.keywords)}' 키워드를 중심으로 {brief.target}에게 "
                f"더 구체적으로 어필할 여지가 있습니다."
            )
            differentiation = (
                f"{competitor}가 다루지 않는 '{brief.keywords[0]}' 경험을 전면에 내세우는 포지셔닝을 제안합니다."
            )
            results.append({
                "name": competitor,
                "analysis": analysis,
                "differentiation": differentiation,
            })
        return results


_KOREAN_FONT_CANDIDATES = [
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",  # macOS
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",  # macOS (구버전)
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",  # Linux (nanum 설치 시)
    "C:\\Windows\\Fonts\\malgun.ttf",  # Windows
]


def _load_font(size: int) -> ImageFont.ImageFont:
    for path in _KOREAN_FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        # 구버전 Pillow는 size 인자를 지원하지 않음
        return ImageFont.load_default()


class MockImageProvider(ImageProvider):
    """실제 이미지 생성 API 대신 PIL로 추상 도형 로고를 그려 PNG로 저장한다."""

    def generate_logos(
        self, brief: BrandBrief, brand_name: str, palette: ColorPalette, count: int = 2
    ) -> list[bytes]:
        words = brand_name.split()
        initials = "".join(w[0] for w in words) if len(words) > 1 else brand_name[:2]
        shapes = ["circle", "rounded_rect", "monogram"]
        colors = [palette.main, *palette.subs]
        results = []
        for i in range(count):
            shape = shapes[i % len(shapes)]
            color = colors[i % len(colors)]
            results.append(self._render(shape, initials, color))
        return results

    @staticmethod
    def _render(shape: str, initials: str, hex_color: str) -> bytes:
        size = 512
        img = Image.new("RGB", (size, size), "#FFFFFF")
        draw = ImageDraw.Draw(img)
        pad = 48

        if shape == "circle":
            draw.ellipse([pad, pad, size - pad, size - pad], fill=hex_color)
        elif shape == "rounded_rect":
            draw.rounded_rectangle([pad, pad, size - pad, size - pad], radius=64, fill=hex_color)
        else:  # monogram
            draw.rectangle([0, 0, size, size], fill=hex_color)

        font = _load_font(size // 3)
        text_color = "#FFFFFF" if shape != "monogram" else "#FFFFFF"
        bbox = draw.textbbox((0, 0), initials, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(
            ((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]),
            initials,
            fill=text_color,
            font=font,
        )

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
