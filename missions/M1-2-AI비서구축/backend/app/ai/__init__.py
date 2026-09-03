from ..config import settings
from .base import LLMProvider
from .mock_provider import MockLLMProvider


def build_provider() -> LLMProvider:
    if settings.use_real_ai:
        try:
            from .openai_provider import OpenAILLMProvider

            return OpenAILLMProvider(settings.openai_api_key, settings.openai_model)
        except ImportError as exc:
            print(f"[안내] OpenAI 프로바이더 로드 실패({exc}) — mock으로 대체합니다.")
    return MockLLMProvider()


provider: LLMProvider = build_provider()
