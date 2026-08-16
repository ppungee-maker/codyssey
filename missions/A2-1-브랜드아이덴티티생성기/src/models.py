"""브랜드 브리프/결과 데이터 모델."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


class BriefValidationError(ValueError):
    """브리프 JSON이 필수 필드를 충족하지 못했을 때."""


@dataclass
class BrandBrief:
    industry: str
    target: str
    keywords: list[str]
    tone: str | None = None
    competitors: list[str] = field(default_factory=list)
    notes: str | None = None

    @classmethod
    def from_json(cls, path: Path) -> "BrandBrief":
        if not path.exists():
            raise BriefValidationError(f"브리프 파일을 찾을 수 없습니다: {path}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise BriefValidationError(f"브리프 JSON 파싱 실패: {exc}") from exc

        missing = [f for f in ("industry", "target", "keywords") if not data.get(f)]
        if missing:
            raise BriefValidationError(
                f"필수 필드 누락: {', '.join(missing)} (industry/target/keywords는 필수)"
            )
        keywords = data["keywords"]
        if not isinstance(keywords, list) or not keywords:
            raise BriefValidationError("keywords는 비어있지 않은 배열이어야 합니다")

        return cls(
            industry=data["industry"],
            target=data["target"],
            keywords=list(keywords),
            tone=data.get("tone"),
            competitors=list(data.get("competitors") or []),
            notes=data.get("notes"),
        )


@dataclass
class NamingCandidate:
    name: str
    meaning: str

    def to_dict(self) -> dict:
        return {"name": self.name, "meaning": self.meaning}


@dataclass
class ColorPalette:
    main: str
    subs: list[str]

    def to_dict(self) -> dict:
        return {"main": self.main, "subs": self.subs}


@dataclass
class BrandResult:
    brief: BrandBrief
    namings: list[NamingCandidate] = field(default_factory=list)
    slogans: list[str] = field(default_factory=list)
    story: str = ""
    palette: ColorPalette | None = None
    logo_files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "brief": {
                "industry": self.brief.industry,
                "target": self.brief.target,
                "keywords": self.brief.keywords,
                "tone": self.brief.tone,
                "competitors": self.brief.competitors,
                "notes": self.brief.notes,
            },
            "namings": [n.to_dict() for n in self.namings],
            "slogans": self.slogans,
            "story": self.story,
            "palette": self.palette.to_dict() if self.palette else None,
            "logo_files": self.logo_files,
            "errors": self.errors,
        }
