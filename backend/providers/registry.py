from __future__ import annotations

import os
from typing import Any

from .base import BaseProvider
from .http import HttpProvider
from .mock import MockProvider
from .voice import VoiceHttpProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self.apply_settings({
            "providerUrl": os.environ.get("SHORT_DRAMA_PROVIDER_URL", ""),
            "providerName": os.environ.get("SHORT_DRAMA_PROVIDER_NAME", "External Video API"),
            "providerModel": os.environ.get("SHORT_DRAMA_PROVIDER_MODEL", "video-default"),
            "providerApiKey": os.environ.get("SHORT_DRAMA_PROVIDER_API_KEY", ""),
            "voiceProvider": os.environ.get("SHORT_DRAMA_VOICE_PROVIDER", "mock"),
            "voiceModel": os.environ.get("SHORT_DRAMA_VOICE_PROVIDER_MODEL", "voice-default"),
            "cosyvoiceUrl": os.environ.get("SHORT_DRAMA_COSYVOICE_URL") or os.environ.get("SHORT_DRAMA_VOICE_PROVIDER_URL", ""),
            "chatterboxUrl": os.environ.get("SHORT_DRAMA_CHATTERBOX_URL", ""),
            "gptSovitsUrl": os.environ.get("SHORT_DRAMA_GPTSOVITS_URL", ""),
            "llmProviderUrl": os.environ.get("SHORT_DRAMA_LLM_PROVIDER_URL", ""),
            "llmProviderName": os.environ.get("SHORT_DRAMA_LLM_PROVIDER_NAME", "OpenAI Compatible"),
            "llmModel": os.environ.get("SHORT_DRAMA_LLM_MODEL", "gpt-4o-mini"),
        })

    def apply_settings(self, settings: dict[str, Any]) -> None:
        self.external_url = settings.get("providerUrl") or None
        self.external_name = settings.get("providerName") or "External Video API"
        self.external_model = settings.get("providerModel") or "video-default"
        self.api_key = settings.get("providerApiKey") or None
        self.voice_provider = (settings.get("voiceProvider") or "mock").lower()
        self.voice_endpoints = {
            "cosyvoice": settings.get("cosyvoiceUrl") or None,
            "chatterbox": settings.get("chatterboxUrl") or None,
            "gpt-sovits": settings.get("gptSovitsUrl") or None,
        }
        self.voice_model = settings.get("voiceModel") or "voice-default"
        self.llm_url = settings.get("llmProviderUrl") or None
        self.llm_name = settings.get("llmProviderName") or "OpenAI Compatible"
        self.llm_model = settings.get("llmModel") or "gpt-4o-mini"

    def reload(self) -> None:
        from ..services.runtime_settings import _raw_settings

        self.apply_settings(_raw_settings())

    def resolve(self, kind: str, provider: str | None = None, model: str | None = None) -> BaseProvider:
        if kind in {"image", "video"} and self.external_url and (not provider or provider == self.external_name):
            return HttpProvider(kind, self.external_url, self.external_name, model or self.external_model, self.api_key)
        if kind == "audio":
            provider_key = (provider or self.voice_provider or "mock").lower()
            endpoint = self.voice_endpoints.get(provider_key)
            if endpoint:
                return VoiceHttpProvider(provider_key, endpoint, model or self.voice_model, self.api_key)
        return MockProvider(kind, model)

    def summary(self) -> dict[str, Any]:
        image_video_provider = self.external_name if self.external_url else "Local Demo"
        image_video_model = self.external_model if self.external_url else "mock-image/video"
        audio_provider = self.voice_provider if any(self.voice_endpoints.values()) else "Local Demo"
        return {
            "mode": "remote" if self.external_url or any(self.voice_endpoints.values()) else "demo",
            "provider": self.external_name if self.external_url else (self.voice_provider if any(self.voice_endpoints.values()) else "Local Demo"),
            "configured": bool(self.external_url or any(self.voice_endpoints.values())),
            "types": ["text", "image", "video", "audio"],
            "voiceProviders": {key: bool(value) for key, value in self.voice_endpoints.items()},
            "providers": {
                "image": {"provider": image_video_provider, "model": image_video_model, "configured": bool(self.external_url)},
                "video": {"provider": image_video_provider, "model": self.external_model if self.external_url else "mock-video", "configured": bool(self.external_url)},
                "audio": {"provider": audio_provider, "model": self.voice_model, "configured": bool(any(self.voice_endpoints.values()))},
                "llm": {"provider": self.llm_name if self.llm_url else "Local Agent", "model": self.llm_model, "configured": bool(self.llm_url)},
            },
        }
