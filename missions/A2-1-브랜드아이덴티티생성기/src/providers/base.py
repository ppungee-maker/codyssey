"""LLM/이미지 프로바이더 인터페이스 — mock/openai 등 구현체가 이 계약을 따른다."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import BrandBrief, ColorPalette, NamingCandidate


class LLMProvider(ABC):
    @abstractmethod
    def generate_naming(self, brief: BrandBrief) -> list[NamingCandidate]: ...

    @abstractmethod
    def generate_slogans(self, brief: BrandBrief) -> list[str]: ...

    @abstractmethod
    def generate_story(self, brief: BrandBrief) -> str: ...

    @abstractmethod
    def generate_palette(self, brief: BrandBrief) -> ColorPalette: ...


class ImageProvider(ABC):
    @abstractmethod
    def generate_logos(
        self, brief: BrandBrief, brand_name: str, palette: ColorPalette, count: int = 2
    ) -> list[bytes]:
        """PNG 바이트 리스트를 반환한다."""
        ...
