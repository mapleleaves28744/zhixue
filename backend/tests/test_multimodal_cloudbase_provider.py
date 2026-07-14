from __future__ import annotations

from app.llm.multimodal_provider import CloudBaseImageProvider, build_multimodal_provider


def test_cloudbase_image_provider_is_selected_when_configured(monkeypatch) -> None:
    monkeypatch.setattr("app.llm.multimodal_provider.settings.multimodal_provider", "cloudbase_image")
    monkeypatch.setattr("app.llm.multimodal_provider.settings.cloudbase_image_api_key", "local-test-key")
    monkeypatch.setattr("app.llm.multimodal_provider.settings.cloudbase_image_base_url", "https://api.example/v1")

    provider = build_multimodal_provider()

    assert isinstance(provider, CloudBaseImageProvider)
    assert provider.provider_name == "cloudbase_image"


def test_cloudbase_image_provider_uses_supported_landscape_size() -> None:
    provider = CloudBaseImageProvider()

    assert provider._normalize_size("1280x720") == "1280x720"
    assert provider._normalize_size("1024x768") == "1280x720"
