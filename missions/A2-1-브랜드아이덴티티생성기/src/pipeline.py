"""브리프 → 네이밍/슬로건/스토리/팔레트/로고 → 저장 까지의 전체 파이프라인.

요구사항 9(에러 처리): 각 생성 단계는 개별 try/except로 감싸, 하나가 실패해도
`errors`에 기록만 하고 다음 단계로 계속 진행한다.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import BrandBrief, BrandResult
from .palette import render_palette
from .providers.base import ImageProvider, LLMProvider


def run(
    brief: BrandBrief, out_dir: Path, llm: LLMProvider, image: ImageProvider
) -> BrandResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    result = BrandResult(brief=brief)

    try:
        result.namings = llm.generate_naming(brief)
    except Exception as exc:
        result.errors.append(f"네이밍 생성 실패: {exc}")
        print(f"[에러] 네이밍 생성 실패: {exc}")

    try:
        result.slogans = llm.generate_slogans(brief)
    except Exception as exc:
        result.errors.append(f"슬로건 생성 실패: {exc}")
        print(f"[에러] 슬로건 생성 실패: {exc}")

    try:
        result.story = llm.generate_story(brief)
    except Exception as exc:
        result.errors.append(f"브랜드 스토리 생성 실패: {exc}")
        print(f"[에러] 브랜드 스토리 생성 실패: {exc}")

    try:
        result.palette = llm.generate_palette(brief)
        render_palette(result.palette, out_dir / "color_palette.png")
    except Exception as exc:
        result.errors.append(f"컬러 팔레트 생성/시각화 실패: {exc}")
        print(f"[에러] 컬러 팔레트 생성/시각화 실패: {exc}")

    try:
        brand_name = result.namings[0].name if result.namings else brief.industry
        palette = result.palette
        if palette is None:
            raise RuntimeError("팔레트가 없어 로고를 생성할 수 없습니다")
        logos = image.generate_logos(brief, brand_name, palette, count=3)
        for i, logo_bytes in enumerate(logos, start=1):
            filename = f"logo_{i}.png"
            (out_dir / filename).write_bytes(logo_bytes)
            result.logo_files.append(filename)
    except Exception as exc:
        result.errors.append(f"로고 시안 생성 실패: {exc}")
        print(f"[에러] 로고 시안 생성 실패: {exc}")

    (out_dir / "brand_result.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result
