import pytest

from app.llm.multimodal_provider import MockMultimodalProvider


@pytest.mark.asyncio
async def test_mock_image_provider_returns_png():
    provider = MockMultimodalProvider()
    result = await provider.generate_image(prompt="BFS graph traversal", size="1280x720")
    assert result.image_bytes.startswith(b"\x89PNG")
    assert result.provider == "mock_multimodal"
