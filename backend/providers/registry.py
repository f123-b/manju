from __future__ import annotations

import os
from typing import Any

from .base import BaseProvider
from .http import HttpProvider
from .mock import MockProvider
from .voice import VoiceHttpProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self.external_url = os.environ.get("SHORT_DRAMA_PROVIDER_URL")
        self.external_name = os.environ.get("SHORT_DRAMA_PROVIDER_NAME", "External Video API")
        self.external_model = os.environ.get("SHORT_DRAMA_PROVIDER_MODEL", "video-default")
        self.api_key = os.environ.get("SHORT_DRAMA_PROVIDER_API_KEY")
        self.voice_endpoints = {
            "cosyvoice": os.environ.get("SHORT_DRAMA_COSYVOICE_URL") or os.environ.get("SHORT_DRAMA_VOICE_PROVIDER_URL"),
            "chatterbox": os.environ.get("SHORT_DRAMA_CHATTERBOX_URL"),
            "gpt-sovits": os.environ.get("SHORT_DRAMA_GPTSOVITS_URL"),
        }
        self.voice_model = os.environ.get("SHORT_DRAMA_VOICE_PROVIDER_MODEL", "voice-default")

    def resolve(self, kind: str, provider: str | None = None, model: str | None = None) -> BaseProvider:
        if kind in {"image", "video"} and self.external_url and (not provider or provider == self.external_name):
            return HttpProvider(kind, self.external_url, self.external_name, model or self.external_model, self.api_key)
        if kind == "audio":
            provider_key = (provider or os.environ.get("SHORT_DRAMA_VOICE_PROVIDER") or "mock").lower()
            endpoint = self.voice_endpoints.get(provider_key)
            if endpoint:
                return VoiceHttpProvider(provider_key, endpoint, model or self.voice_model, self.api_key)
        return MockProvider(kind, model)

    def summary(self) -> dict[str, Any]:
        return {
            "mode": "remote" if self.external_url or any(self.voice_endpoints.values()) else "demo",
            "provider": self.external_name if self.external_url else "Local Demo",
            "configured": bool(self.external_url or any(self.voice_endpoints.values())),
            "types": ["text", "image", "video", "audio"],
            "voiceProviders": {key: bool(value) for key, value in self.voice_endpoints.items()},
        }
