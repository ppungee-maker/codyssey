from .base import ImageProvider, LLMProvider
from .mock_provider import MockImageProvider, MockLLMProvider

__all__ = ["LLMProvider", "ImageProvider", "MockLLMProvider", "MockImageProvider"]


def build_providers(config) -> tuple[LLMProvider, ImageProvider]:
    """config.provider 에 따라 실제 사용할 (LLM, Image) 프로바이더 쌍을 만든다.

    openai 프로바이더가 요청됐는데 키가 없거나 openai 패키지가 없으면, 에러 메시지를
    출력하고 mock으로 안전하게 폴백한다(요구사항 9: API 키 문제 시 명확한 안내).
    """
    if config.provider == "openai":
        if not config.openai_api_key:
            print(
                "[안내] provider=openai 이지만 OPENAI_API_KEY가 없습니다. "
                ".env 또는 config.json에 키를 설정하세요. 이번 실행은 mock으로 대체합니다."
            )
        else:
            try:
                from .openai_provider import OpenAIImageProvider, OpenAILLMProvider

                return OpenAILLMProvider(config.openai_api_key), OpenAIImageProvider(
                    config.openai_api_key
                )
            except ImportError as exc:
                print(f"[안내] openai 패키지 로드 실패({exc}) — mock으로 대체합니다.")

    return MockLLMProvider(), MockImageProvider()
