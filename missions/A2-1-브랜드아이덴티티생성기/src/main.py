"""브랜드 아이덴티티 생성기 CLI.

대화형(input) 실행이 기본이지만, 자동 테스트/채점 편의를 위해
`--brief`/`--output` 인자를 주면 프롬프트 없이 바로 실행된다.

    python -m src.main                                # 대화형
    python -m src.main --brief sample_data/brief_example.json --output output
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import AppConfig
from .models import BriefValidationError, BrandBrief
from .pipeline import run
from .providers import build_providers


def _prompt_brief_path() -> Path:
    while True:
        raw = input("브랜드 브리프 JSON 파일 경로를 입력하세요: ").strip()
        path = Path(raw)
        if path.exists():
            return path
        print(f"  -> 파일을 찾을 수 없습니다: {path}. 다시 입력해주세요.")


def _prompt_output_dir() -> Path:
    raw = input("결과를 저장할 폴더 경로 (기본값: ./output): ").strip()
    return Path(raw) if raw else Path("./output")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI 브랜드 아이덴티티 생성기")
    parser.add_argument("--brief", type=Path, help="브랜드 브리프 JSON 경로")
    parser.add_argument("--output", type=Path, default=None, help="출력 폴더 (기본 ./output)")
    parser.add_argument("--config", type=Path, default=None, help="config.json 경로 override")
    args = parser.parse_args(argv)

    print("=== AI 브랜드 아이덴티티 생성기 ===")

    brief_path = args.brief if args.brief else _prompt_brief_path()
    output_dir = args.output if args.output else (_prompt_output_dir() if args.brief is None else Path("./output"))

    try:
        brief = BrandBrief.from_json(brief_path)
    except BriefValidationError as exc:
        print(f"[에러] 브리프 로드 실패: {exc}")
        return 1

    config = AppConfig.load(args.config)
    llm, image = build_providers(config)

    print(f"[*] provider={config.provider if config.provider == 'openai' and config.openai_api_key else 'mock'}")
    print(f"[*] 브리프: {brief.industry} / {brief.target} / {', '.join(brief.keywords)}")

    result = run(brief, output_dir, llm, image)

    print()
    print(f"[완료] 결과 저장 위치: {output_dir.resolve()}")
    print(f"  - brand_result.json (네이밍 {len(result.namings)}개, 슬로건 {len(result.slogans)}개)")
    print(f"  - color_palette.png ({'생성됨' if result.palette else '실패'})")
    print(f"  - 로고 시안 {len(result.logo_files)}개: {', '.join(result.logo_files) or '없음'}")
    if result.errors:
        print(f"  - [주의] 일부 단계 실패: {len(result.errors)}건 (brand_result.json의 errors 참고)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
